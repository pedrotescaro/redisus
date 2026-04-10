from __future__ import annotations

import json
import random
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from .segmentation_dataset import (
    build_segmentation_manifest,
    crop_to_mask,
    resize_image_and_mask,
    write_segmentation_manifest,
)
from .segmentation_metrics import binary_dice_score, binary_ece, binary_iou_score

SEED = 42
random.seed(SEED)
np.random.seed(SEED)


def _import_torch_modules():
    try:
        import torch
        import torch.nn as nn
        from torch.utils.data import DataLoader, Dataset
        from torchvision import models
    except ImportError as exc:
        raise RuntimeError(
            "Treino de wound-mask requer PyTorch/torchvision instalados."
        ) from exc
    return torch, nn, DataLoader, Dataset, models


@dataclass(slots=True)
class WoundMaskTrainingConfig:
    data_dir: str = "data/datasets/fuseg"
    metadata_path: str | None = None
    manifest_path: str = "data/manifests/wound_mask_split.json"
    output_dir: str = "models/wound_mask_deeplabv3"
    image_size: int = 384
    batch_size: int = 6
    epochs: int = 35
    learning_rate: float = 3e-4
    weight_decay: float = 1e-4
    train_ratio: float = 0.7
    val_ratio: float = 0.15
    crop_to_wound: bool = True
    crop_margin_ratio: float = 0.12
    patience: int = 8
    threshold: float = 0.5
    seed: int = SEED
    num_workers: int = 0
    notes: list[str] = field(
        default_factory=lambda: [
            "Segmentacao binaria pele vs ferida com DeepLabV3-ResNet50",
            "Split agrupado por lesion_id e fallback em patient_id",
            "Entrada 384x384 com crop guiado pela mascara da ferida",
        ]
    )


def prepare_wound_mask_manifest(config: WoundMaskTrainingConfig) -> Path:
    manifest = build_segmentation_manifest(
        config.data_dir,
        metadata_path=config.metadata_path,
        train_ratio=config.train_ratio,
        val_ratio=config.val_ratio,
        seed=config.seed,
    )
    return write_segmentation_manifest(manifest, config.manifest_path)


def _build_model(models, *, num_classes: int = 1):
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


def _augment_binary_sample(image_rgb: np.ndarray, mask: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    if np.random.random() > 0.5:
        image_rgb = np.fliplr(image_rgb).copy()
        mask = np.fliplr(mask).copy()
    if np.random.random() > 0.5:
        image_rgb = np.flipud(image_rgb).copy()
        mask = np.flipud(mask).copy()
    if np.random.random() > 0.5:
        angle = float(np.random.uniform(-18, 18))
        h, w = image_rgb.shape[:2]
        matrix = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
        image_rgb = cv2.warpAffine(image_rgb, matrix, (w, h), borderMode=cv2.BORDER_REFLECT)
        mask = cv2.warpAffine(mask, matrix, (w, h), flags=cv2.INTER_NEAREST, borderMode=cv2.BORDER_CONSTANT)
    if np.random.random() > 0.5:
        alpha = float(np.random.uniform(0.92, 1.08))
        beta = float(np.random.uniform(-8, 8))
        image_rgb = np.clip(image_rgb.astype(np.float32) * alpha + beta, 0, 255).astype(np.uint8)
    return image_rgb, mask


def train_wound_mask_model(config: WoundMaskTrainingConfig) -> dict[str, Any]:
    torch, nn, DataLoader, Dataset, models = _import_torch_modules()

    class BinaryMaskDataset(Dataset):
        def __init__(self, samples: list[dict[str, Any]], *, training: bool):
            self.samples = samples
            self.training = training

        def __len__(self) -> int:
            return len(self.samples)

        def __getitem__(self, index: int):
            sample = self.samples[index]
            image = cv2.imread(sample["image_path"], cv2.IMREAD_COLOR)
            mask = cv2.imread(sample["mask_path"], cv2.IMREAD_GRAYSCALE)
            if image is None or mask is None:
                raise FileNotFoundError(f"Falha ao carregar sample: {sample}")

            image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            mask = (mask > 127).astype(np.uint8)

            if config.crop_to_wound:
                image, mask, _ = crop_to_mask(
                    image,
                    mask,
                    margin_ratio=config.crop_margin_ratio,
                )

            if self.training:
                image, mask = _augment_binary_sample(image, mask)

            image, mask = resize_image_and_mask(image, mask, size=config.image_size)
            image = image.astype(np.float32) / 255.0
            image = np.transpose(image, (2, 0, 1))
            mask = mask.astype(np.float32)[None, ...]

            return torch.from_numpy(image), torch.from_numpy(mask)

    def dice_bce_loss(logits, targets):
        probs = logits.sigmoid()
        bce = nn.functional.binary_cross_entropy_with_logits(logits, targets)
        intersection = (probs * targets).sum(dim=(1, 2, 3))
        union = probs.sum(dim=(1, 2, 3)) + targets.sum(dim=(1, 2, 3))
        dice_loss = 1.0 - ((2.0 * intersection + 1.0) / (union + 1.0))
        return bce + dice_loss.mean()

    manifest_path = Path(config.manifest_path)
    if not manifest_path.exists():
        manifest_path = prepare_wound_mask_manifest(config)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    train_samples = list(manifest["splits"]["train"])
    val_samples = list(manifest["splits"]["val"])
    test_samples = list(manifest["splits"]["test"])

    if not train_samples or not val_samples:
        raise RuntimeError("Manifesto de wound-mask sem amostras suficientes para treino/validacao.")

    train_dataset = BinaryMaskDataset(train_samples, training=True)
    val_dataset = BinaryMaskDataset(val_samples, training=False)
    test_dataset = BinaryMaskDataset(test_samples, training=False)

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
    model = _build_model(models, num_classes=1).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=config.learning_rate, weight_decay=config.weight_decay)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=max(config.epochs, 1))

    output_dir = Path(config.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    history: dict[str, list[float]] = {
        "train_loss": [],
        "val_loss": [],
        "val_dice": [],
        "val_iou": [],
        "val_ece": [],
    }
    best_val_dice = -1.0
    patience_counter = 0

    def run_epoch(loader, *, training: bool) -> dict[str, float]:
        model.train(training)
        running_loss = 0.0
        dice_scores: list[float] = []
        iou_scores: list[float] = []
        ece_labels: list[np.ndarray] = []
        ece_scores: list[np.ndarray] = []

        for images, masks in loader:
            images = images.to(device)
            masks = masks.to(device)
            outputs = model(images)["out"]
            loss = dice_bce_loss(outputs, masks)

            if training:
                optimizer.zero_grad()
                loss.backward()
                torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
                optimizer.step()

            running_loss += float(loss.item())
            probs = outputs.sigmoid().detach().cpu().numpy()
            targets = masks.detach().cpu().numpy()
            predictions = probs >= config.threshold
            for pred_mask, prob_mask, true_mask in zip(predictions, probs, targets):
                pred_2d = pred_mask[0]
                prob_2d = prob_mask[0]
                true_2d = true_mask[0] > 0.5
                dice_scores.append(binary_dice_score(pred_2d, true_2d))
                iou_scores.append(binary_iou_score(pred_2d, true_2d))
                ece_labels.append(true_2d.astype(np.uint8))
                ece_scores.append(prob_2d.astype(np.float32))

        ece = binary_ece(
            np.concatenate([item.reshape(-1) for item in ece_labels]) if ece_labels else np.array([], dtype=np.uint8),
            np.concatenate([item.reshape(-1) for item in ece_scores]) if ece_scores else np.array([], dtype=np.float32),
            threshold=config.threshold,
        )
        return {
            "loss": running_loss / max(len(loader), 1),
            "dice": float(np.mean(dice_scores)) if dice_scores else 0.0,
            "iou": float(np.mean(iou_scores)) if iou_scores else 0.0,
            "ece": ece,
        }

    for _epoch in range(config.epochs):
        train_metrics = run_epoch(train_loader, training=True)
        val_metrics = run_epoch(val_loader, training=False)
        scheduler.step()

        history["train_loss"].append(train_metrics["loss"])
        history["val_loss"].append(val_metrics["loss"])
        history["val_dice"].append(val_metrics["dice"])
        history["val_iou"].append(val_metrics["iou"])
        history["val_ece"].append(val_metrics["ece"])

        if val_metrics["dice"] > best_val_dice + 1e-4:
            best_val_dice = val_metrics["dice"]
            patience_counter = 0
            torch.save(
                {
                    "model_state_dict": model.state_dict(),
                    "epoch": len(history["train_loss"]),
                    "val_metrics": val_metrics,
                    "config": asdict(config),
                },
                output_dir / "wound_mask_deeplabv3_384.pth",
            )
        else:
            patience_counter += 1
            if patience_counter >= config.patience:
                break

    checkpoint = torch.load(output_dir / "wound_mask_deeplabv3_384.pth", map_location=device)
    model.load_state_dict(checkpoint["model_state_dict"])
    test_metrics = run_epoch(test_loader, training=False) if test_samples else {}

    metadata = {
        "model_name": "deeplabv3-resnet50-wound-mask",
        "task": "wound_mask_segmentation",
        "input_size": config.image_size,
        "best_val_dice": best_val_dice,
        "history": history,
        "test_metrics": test_metrics,
        "manifest_summary": manifest["summary"],
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

    parser = argparse.ArgumentParser(description="Treino DeepLabV3 para mascara binaria de ferida.")
    parser.add_argument("--data_dir", type=str, required=True)
    parser.add_argument("--metadata_path", type=str, default=None)
    parser.add_argument("--manifest_path", type=str, default="data/manifests/wound_mask_split.json")
    parser.add_argument("--output_dir", type=str, default="models/wound_mask_deeplabv3")
    parser.add_argument("--image_size", type=int, default=384)
    parser.add_argument("--batch_size", type=int, default=6)
    parser.add_argument("--epochs", type=int, default=35)
    parser.add_argument("--lr", type=float, default=3e-4)
    parser.add_argument("--weight_decay", type=float, default=1e-4)
    parser.add_argument("--patience", type=int, default=8)
    args = parser.parse_args()

    config = WoundMaskTrainingConfig(
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
    )
    train_wound_mask_model(config)


if __name__ == "__main__":
    main()
