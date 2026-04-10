from __future__ import annotations

import json
import random
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from ..core.config import TISSUE_NAMES, TissueType, get_tissue_color_map
from .segmentation_dataset import (
    build_segmentation_manifest,
    crop_to_mask,
    resize_image_and_mask,
    write_segmentation_manifest,
)
from .segmentation_metrics import (
    binary_average_precision,
    binary_ece,
    multiclass_confusion_matrix,
    per_class_dice,
    per_class_iou,
    per_class_recall,
)

SEED = 42
random.seed(SEED)
np.random.seed(SEED)


def _import_torch_modules():
    try:
        import torch
        import torch.nn as nn
        import torch.nn.functional as F
        from torch.utils.data import DataLoader, Dataset
        from torchvision import models
    except ImportError as exc:
        raise RuntimeError(
            "Treino de segmentacao de tecidos requer PyTorch/torchvision."
        ) from exc
    return torch, nn, F, DataLoader, Dataset, models


@dataclass(slots=True)
class TissueSegmentationTrainingConfig:
    data_dir: str = "data/datasets/wound_tissues"
    metadata_path: str | None = None
    manifest_path: str = "data/manifests/tissue_segmentation_split.json"
    output_dir: str = "models/tissue_segmentation_deeplabv3"
    image_size: int = 384
    batch_size: int = 4
    epochs: int = 45
    learning_rate: float = 2e-4
    weight_decay: float = 1e-4
    train_ratio: float = 0.7
    val_ratio: float = 0.15
    crop_to_wound: bool = True
    crop_margin_ratio: float = 0.10
    loss_name: str = "dice_ce"
    threshold: float = 0.5
    patience: int = 10
    seed: int = SEED
    num_workers: int = 0
    class_weights: dict[int, float] = field(
        default_factory=lambda: {
            int(TissueType.BACKGROUND.value): 0.35,
            int(TissueType.GRANULATION.value): 1.00,
            int(TissueType.SLOUGH.value): 1.15,
            int(TissueType.NECROSIS.value): 2.80,
            int(TissueType.PERIWOUND.value): 0.60,
        }
    )
    notes: list[str] = field(
        default_factory=lambda: [
            "Segmentacao de tecidos separada da deteccao da ferida",
            "Entrada 384x384 com crop na ROI da ferida",
            "Loss ponderada para necrose com metricas clinicas dedicadas",
        ]
    )


def prepare_tissue_segmentation_manifest(config: TissueSegmentationTrainingConfig) -> Path:
    manifest = build_segmentation_manifest(
        config.data_dir,
        metadata_path=config.metadata_path,
        train_ratio=config.train_ratio,
        val_ratio=config.val_ratio,
        seed=config.seed,
    )
    return write_segmentation_manifest(manifest, config.manifest_path)


def _build_model(models, *, num_classes: int):
    kwargs = {"num_classes": num_classes}
    try:
        kwargs["weights"] = None
        kwargs["weights_backbone"] = models.ResNet50_Weights.IMAGENET1K_V2
    except AttributeError:
        pass
    try:
        return models.segmentation.deeplabv3_resnet50(**kwargs)
    except TypeError:
        kwargs.pop("weights_backbone", None)
        return models.segmentation.deeplabv3_resnet50(**kwargs)


def decode_tissue_mask(mask: np.ndarray) -> np.ndarray:
    if mask.ndim == 2:
        if mask.max() <= int(TissueType.PERIWOUND.value):
            return mask.astype(np.uint8)
        unique_values = set(np.unique(mask).tolist())
        if unique_values <= {0, 1, 2, 3, 4, 255}:
            converted = mask.copy()
            converted[converted == 255] = 0
            return converted.astype(np.uint8)
        raise ValueError(f"Mascara monocanal em formato nao suportado: valores {sorted(unique_values)[:10]}")

    if mask.ndim != 3 or mask.shape[2] != 3:
        raise ValueError("Mascara de tecidos deve ser grayscale indexada ou RGB.")

    color_map = get_tissue_color_map().astype(np.int32)
    rgb_mask = cv2.cvtColor(mask, cv2.COLOR_BGR2RGB).astype(np.int32)
    flat = rgb_mask.reshape(-1, 3)
    distances = np.sum((flat[:, None, :] - color_map[None, :, :]) ** 2, axis=2)
    indices = np.argmin(distances, axis=1)
    return indices.reshape(mask.shape[:2]).astype(np.uint8)


def _augment_tissue_sample(image_rgb: np.ndarray, mask: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    if np.random.random() > 0.5:
        image_rgb = np.fliplr(image_rgb).copy()
        mask = np.fliplr(mask).copy()
    if np.random.random() > 0.5:
        image_rgb = np.flipud(image_rgb).copy()
        mask = np.flipud(mask).copy()
    if np.random.random() > 0.5:
        angle = float(np.random.uniform(-15, 15))
        h, w = image_rgb.shape[:2]
        matrix = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
        image_rgb = cv2.warpAffine(image_rgb, matrix, (w, h), borderMode=cv2.BORDER_REFLECT)
        mask = cv2.warpAffine(mask, matrix, (w, h), flags=cv2.INTER_NEAREST, borderMode=cv2.BORDER_CONSTANT)
    if np.random.random() > 0.5:
        alpha = float(np.random.uniform(0.96, 1.05))
        beta = float(np.random.uniform(-5, 5))
        image_rgb = np.clip(image_rgb.astype(np.float32) * alpha + beta, 0, 255).astype(np.uint8)
    return image_rgb, mask


def _sample_for_binary_metrics(labels: np.ndarray, scores: np.ndarray, max_samples: int = 200_000) -> tuple[np.ndarray, np.ndarray]:
    labels = labels.reshape(-1).astype(np.uint8)
    scores = scores.reshape(-1).astype(np.float32)
    if labels.size <= max_samples:
        return labels, scores
    rng = np.random.default_rng(42)
    indices = rng.choice(labels.size, size=max_samples, replace=False)
    return labels[indices], scores[indices]


def train_tissue_segmentation_model(config: TissueSegmentationTrainingConfig) -> dict[str, Any]:
    torch, nn, F, DataLoader, Dataset, models = _import_torch_modules()
    num_classes = len(TISSUE_NAMES)

    class TissueDataset(Dataset):
        def __init__(self, samples: list[dict[str, Any]], *, training: bool):
            self.samples = samples
            self.training = training

        def __len__(self) -> int:
            return len(self.samples)

        def __getitem__(self, index: int):
            sample = self.samples[index]
            image = cv2.imread(sample["image_path"], cv2.IMREAD_COLOR)
            raw_mask = cv2.imread(sample["mask_path"], cv2.IMREAD_UNCHANGED)
            if image is None or raw_mask is None:
                raise FileNotFoundError(f"Falha ao carregar sample de tecido: {sample}")

            image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            mask = decode_tissue_mask(raw_mask)

            crop_mask = (mask != int(TissueType.BACKGROUND.value)).astype(np.uint8)
            if config.crop_to_wound and np.any(crop_mask > 0):
                image, mask, _ = crop_to_mask(
                    image,
                    mask,
                    margin_ratio=config.crop_margin_ratio,
                )

            if self.training:
                image, mask = _augment_tissue_sample(image, mask)

            image, mask = resize_image_and_mask(image, mask, size=config.image_size)
            image = image.astype(np.float32) / 255.0
            image = np.transpose(image, (2, 0, 1))
            return torch.from_numpy(image), torch.from_numpy(mask.astype(np.int64))

    def multiclass_dice_ce_loss(logits, targets, class_weight_tensor):
        ce = F.cross_entropy(logits, targets, weight=class_weight_tensor)
        probs = torch.softmax(logits, dim=1)
        target_one_hot = F.one_hot(targets, num_classes=num_classes).permute(0, 3, 1, 2).float()
        intersection = (probs * target_one_hot).sum(dim=(2, 3))
        union = probs.sum(dim=(2, 3)) + target_one_hot.sum(dim=(2, 3))
        dice = (2.0 * intersection + 1.0) / (union + 1.0)
        weight = class_weight_tensor / class_weight_tensor.sum()
        dice_score = (dice * weight[None, :]).sum(dim=1).mean()
        return ce + (1.0 - dice_score)

    def focal_tversky_loss(logits, targets, class_weight_tensor, gamma: float = 1.33):
        probs = torch.softmax(logits, dim=1)
        target_one_hot = F.one_hot(targets, num_classes=num_classes).permute(0, 3, 1, 2).float()
        tp = (probs * target_one_hot).sum(dim=(2, 3))
        fp = (probs * (1.0 - target_one_hot)).sum(dim=(2, 3))
        fn = ((1.0 - probs) * target_one_hot).sum(dim=(2, 3))
        alpha = torch.tensor([0.35, 0.45, 0.50, 0.75, 0.40], device=logits.device)
        beta = 1.0 - alpha
        tversky = (tp + 1.0) / (tp + alpha[None, :] * fp + beta[None, :] * fn + 1.0)
        focal = torch.pow(1.0 - tversky, gamma)
        weight = class_weight_tensor / class_weight_tensor.sum()
        return (focal * weight[None, :]).sum(dim=1).mean()

    manifest_path = Path(config.manifest_path)
    if not manifest_path.exists():
        manifest_path = prepare_tissue_segmentation_manifest(config)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    train_samples = list(manifest["splits"]["train"])
    val_samples = list(manifest["splits"]["val"])
    test_samples = list(manifest["splits"]["test"])

    if not train_samples or not val_samples:
        raise RuntimeError("Manifesto de tecidos sem amostras suficientes para treino/validacao.")

    train_dataset = TissueDataset(train_samples, training=True)
    val_dataset = TissueDataset(val_samples, training=False)
    test_dataset = TissueDataset(test_samples, training=False)

    train_loader = DataLoader(
        train_dataset,
        batch_size=config.batch_size,
        shuffle=True,
        num_workers=config.num_workers,
    )
    val_loader = DataLoader(
        val_dataset,
        batch_size=config.batch_size,
        shuffle=False,
        num_workers=config.num_workers,
    )
    test_loader = DataLoader(
        test_dataset,
        batch_size=config.batch_size,
        shuffle=False,
        num_workers=config.num_workers,
    )

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = _build_model(models, num_classes=num_classes).to(device)
    class_weight_tensor = torch.tensor(
        [config.class_weights.get(class_index, 1.0) for class_index in range(num_classes)],
        dtype=torch.float32,
        device=device,
    )
    optimizer = torch.optim.AdamW(model.parameters(), lr=config.learning_rate, weight_decay=config.weight_decay)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=max(config.epochs, 1))

    output_dir = Path(config.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    history: dict[str, list[float]] = {
        "train_loss": [],
        "val_loss": [],
        "val_miou": [],
        "val_necrosis_recall": [],
        "val_necrosis_pr_auc": [],
        "val_necrosis_ece": [],
    }

    necrosis_index = int(TissueType.NECROSIS.value)
    best_score = (-1.0, -1.0)
    patience_counter = 0

    def compute_loss(logits, targets):
        if config.loss_name == "focal_tversky":
            return focal_tversky_loss(logits, targets, class_weight_tensor)
        return multiclass_dice_ce_loss(logits, targets, class_weight_tensor)

    def run_epoch(loader, *, training: bool) -> dict[str, Any]:
        model.train(training)
        running_loss = 0.0
        confusion = np.zeros((num_classes, num_classes), dtype=np.int64)
        necrosis_labels: list[np.ndarray] = []
        necrosis_scores: list[np.ndarray] = []

        for images, masks in loader:
            images = images.to(device)
            masks = masks.to(device)
            logits = model(images)["out"]
            loss = compute_loss(logits, masks)

            if training:
                optimizer.zero_grad()
                loss.backward()
                torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
                optimizer.step()

            running_loss += float(loss.item())
            probs = torch.softmax(logits.detach(), dim=1).cpu().numpy()
            predictions = np.argmax(probs, axis=1)
            targets_np = masks.detach().cpu().numpy()
            confusion += multiclass_confusion_matrix(predictions, targets_np, num_classes=num_classes)

            necrosis_labels.append((targets_np == necrosis_index).astype(np.uint8))
            necrosis_scores.append(probs[:, necrosis_index, :, :].astype(np.float32))

        recalls = per_class_recall(confusion)
        ious = per_class_iou(confusion)
        dice_scores = per_class_dice(confusion)

        necrosis_y, necrosis_p = _sample_for_binary_metrics(
            np.concatenate([item.reshape(-1) for item in necrosis_labels]) if necrosis_labels else np.array([], dtype=np.uint8),
            np.concatenate([item.reshape(-1) for item in necrosis_scores]) if necrosis_scores else np.array([], dtype=np.float32),
        )
        necrosis_pr_auc = binary_average_precision(necrosis_y, necrosis_p)
        necrosis_ece = binary_ece(necrosis_y, necrosis_p, threshold=config.threshold)

        return {
            "loss": running_loss / max(len(loader), 1),
            "confusion_matrix": confusion.tolist(),
            "recall_per_class": recalls,
            "iou_per_class": ious,
            "dice_per_class": dice_scores,
            "mean_iou": float(np.mean(ious[1:])) if len(ious) > 1 else float(np.mean(ious)),
            "necrosis_recall": recalls[necrosis_index],
            "necrosis_pr_auc": necrosis_pr_auc,
            "necrosis_ece": necrosis_ece,
        }

    for _epoch in range(config.epochs):
        train_metrics = run_epoch(train_loader, training=True)
        val_metrics = run_epoch(val_loader, training=False)
        scheduler.step()

        history["train_loss"].append(train_metrics["loss"])
        history["val_loss"].append(val_metrics["loss"])
        history["val_miou"].append(val_metrics["mean_iou"])
        history["val_necrosis_recall"].append(val_metrics["necrosis_recall"])
        history["val_necrosis_pr_auc"].append(val_metrics["necrosis_pr_auc"])
        history["val_necrosis_ece"].append(val_metrics["necrosis_ece"])

        ranking_score = (val_metrics["necrosis_recall"], val_metrics["mean_iou"])
        if ranking_score > best_score:
            best_score = ranking_score
            patience_counter = 0
            torch.save(
                {
                    "model_state_dict": model.state_dict(),
                    "epoch": len(history["train_loss"]),
                    "val_metrics": val_metrics,
                    "config": asdict(config),
                },
                output_dir / "tissue_segmentation_deeplabv3_384.pth",
            )
        else:
            patience_counter += 1
            if patience_counter >= config.patience:
                break

    checkpoint = torch.load(output_dir / "tissue_segmentation_deeplabv3_384.pth", map_location=device)
    model.load_state_dict(checkpoint["model_state_dict"])
    test_metrics = run_epoch(test_loader, training=False) if test_samples else {}

    metadata = {
        "model_name": "deeplabv3-resnet50-tissue-segmentation",
        "task": "tissue_segmentation",
        "input_size": config.image_size,
        "loss_name": config.loss_name,
        "class_weights": {str(key): value for key, value in config.class_weights.items()},
        "best_val_necrosis_recall": best_score[0],
        "best_val_mean_iou": best_score[1],
        "history": history,
        "test_metrics": test_metrics,
        "manifest_summary": manifest["summary"],
        "class_names": {str(key): value for key, value in TISSUE_NAMES.items()},
        "notes": list(config.notes),
        "timestamp": datetime.now().isoformat(),
    }
    (output_dir / "training_metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return metadata


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Treino de segmentacao de tecidos com DeepLabV3.")
    parser.add_argument("--data_dir", type=str, required=True)
    parser.add_argument("--metadata_path", type=str, default=None)
    parser.add_argument("--manifest_path", type=str, default="data/manifests/tissue_segmentation_split.json")
    parser.add_argument("--output_dir", type=str, default="models/tissue_segmentation_deeplabv3")
    parser.add_argument("--image_size", type=int, default=384)
    parser.add_argument("--batch_size", type=int, default=4)
    parser.add_argument("--epochs", type=int, default=45)
    parser.add_argument("--lr", type=float, default=2e-4)
    parser.add_argument("--weight_decay", type=float, default=1e-4)
    parser.add_argument("--patience", type=int, default=10)
    parser.add_argument("--loss_name", type=str, default="dice_ce", choices=["dice_ce", "focal_tversky"])
    args = parser.parse_args()

    config = TissueSegmentationTrainingConfig(
        data_dir=args.data_dir,
        metadata_path=args.metadata_path,
        manifest_path=args.manifest_path,
        output_dir=args.output_dir,
        image_size=args.image_size,
        batch_size=args.batch_size,
        epochs=args.epochs,
        learning_rate=args.lr,
        weight_decay=args.weight_decay,
        patience=args.patience,
        loss_name=args.loss_name,
    )
    train_tissue_segmentation_model(config)


if __name__ == "__main__":
    main()
