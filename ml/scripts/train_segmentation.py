"""Train an experimental wound-vs-background segmentation baseline.

The default target is CO2Wounds-V2 after local dataset preparation. The model is
a small PyTorch U-Net so the baseline can run without the official repo's extra
dependencies (`segmentation_models_pytorch`, `albumentations`). It is not a
clinically validated model.
"""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path
from typing import Any

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from PIL import Image
from torch.utils.data import DataLoader, Dataset


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--train-manifest", default="ml/datasets/co2wounds_v2_train.jsonl")
    parser.add_argument("--val-manifest", default="ml/datasets/co2wounds_v2_val.jsonl")
    parser.add_argument("--output-dir", default="ml/outputs/co2wounds_v2_unet")
    parser.add_argument("--image-size", type=int, default=384)
    parser.add_argument("--epochs", type=int, default=30)
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument("--learning-rate", type=float, default=3e-4)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--device", choices=["auto", "cpu", "cuda"], default="auto")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--accept-experimental-non-commercial-use", action="store_true")
    return parser.parse_args()


def require_research_acceptance(accepted: bool) -> None:
    if accepted:
        return
    raise SystemExit(
        "Treino bloqueado: CO2Wounds-V2 deve ser usado aqui apenas para pesquisa/prototipo nao comercial. "
        "Rode com --accept-experimental-non-commercial-use apos revisar a licenca."
    )


def load_records(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise SystemExit(f"Manifesto nao encontrado: {path}. Rode ml/scripts/prepare_co2wounds_v2.py primeiro.")
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


class ManifestSegmentationDataset(Dataset):
    def __init__(self, records: list[dict[str, Any]], image_size: int, augment: bool = False):
        self.records = [record for record in records if record.get("image") and record.get("mask")]
        self.image_size = image_size
        self.augment = augment

    def __len__(self) -> int:
        return len(self.records)

    def __getitem__(self, index: int) -> tuple[torch.Tensor, torch.Tensor]:
        record = self.records[index]
        with Image.open(record["image"]) as image:
            image = image.convert("RGB").resize((self.image_size, self.image_size), Image.BILINEAR)
        with Image.open(record["mask"]) as mask:
            mask = mask.convert("L").resize((self.image_size, self.image_size), Image.NEAREST)

        image_array = np.asarray(image, dtype=np.float32) / 255.0
        mask_array = (np.asarray(mask, dtype=np.float32) > 0).astype(np.float32)

        if self.augment and random.random() < 0.5:
            image_array = np.ascontiguousarray(np.flip(image_array, axis=1))
            mask_array = np.ascontiguousarray(np.flip(mask_array, axis=1))

        image_tensor = torch.from_numpy(image_array.transpose(2, 0, 1))
        mask_tensor = torch.from_numpy(mask_array[None, :, :])
        return image_tensor, mask_tensor


class ConvBlock(nn.Module):
    def __init__(self, in_channels: int, out_channels: int):
        super().__init__()
        self.block = nn.Sequential(
            nn.Conv2d(in_channels, out_channels, kernel_size=3, padding=1),
            nn.BatchNorm2d(out_channels),
            nn.ReLU(inplace=True),
            nn.Conv2d(out_channels, out_channels, kernel_size=3, padding=1),
            nn.BatchNorm2d(out_channels),
            nn.ReLU(inplace=True),
        )

    def forward(self, value: torch.Tensor) -> torch.Tensor:
        return self.block(value)


class SmallUNet(nn.Module):
    def __init__(self):
        super().__init__()
        self.enc1 = ConvBlock(3, 32)
        self.enc2 = ConvBlock(32, 64)
        self.enc3 = ConvBlock(64, 128)
        self.pool = nn.MaxPool2d(2)
        self.bottleneck = ConvBlock(128, 256)
        self.up3 = nn.ConvTranspose2d(256, 128, kernel_size=2, stride=2)
        self.dec3 = ConvBlock(256, 128)
        self.up2 = nn.ConvTranspose2d(128, 64, kernel_size=2, stride=2)
        self.dec2 = ConvBlock(128, 64)
        self.up1 = nn.ConvTranspose2d(64, 32, kernel_size=2, stride=2)
        self.dec1 = ConvBlock(64, 32)
        self.head = nn.Conv2d(32, 1, kernel_size=1)

    def forward(self, image: torch.Tensor) -> torch.Tensor:
        enc1 = self.enc1(image)
        enc2 = self.enc2(self.pool(enc1))
        enc3 = self.enc3(self.pool(enc2))
        bottleneck = self.bottleneck(self.pool(enc3))
        dec3 = self.dec3(torch.cat([self.up3(bottleneck), enc3], dim=1))
        dec2 = self.dec2(torch.cat([self.up2(dec3), enc2], dim=1))
        dec1 = self.dec1(torch.cat([self.up1(dec2), enc1], dim=1))
        return self.head(dec1)


def dice_loss(logits: torch.Tensor, targets: torch.Tensor, eps: float = 1e-6) -> torch.Tensor:
    probs = torch.sigmoid(logits)
    intersection = (probs * targets).sum(dim=(1, 2, 3))
    union = probs.sum(dim=(1, 2, 3)) + targets.sum(dim=(1, 2, 3))
    dice = (2 * intersection + eps) / (union + eps)
    return 1 - dice.mean()


def combined_loss(logits: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
    return 0.5 * F.binary_cross_entropy_with_logits(logits, targets) + 0.5 * dice_loss(logits, targets)


def metric_counts(logits: torch.Tensor, targets: torch.Tensor) -> dict[str, int]:
    preds = torch.sigmoid(logits) >= 0.5
    truth = targets >= 0.5
    return {
        "tp": int((preds & truth).sum().item()),
        "fp": int((preds & ~truth).sum().item()),
        "tn": int((~preds & ~truth).sum().item()),
        "fn": int((~preds & truth).sum().item()),
    }


def safe_div(num: float, den: float) -> float:
    return float(num / den) if den else 0.0


def metrics_from_counts(counts: dict[str, int]) -> dict[str, float]:
    tp = counts["tp"]
    fp = counts["fp"]
    tn = counts["tn"]
    fn = counts["fn"]
    precision = safe_div(tp, tp + fp)
    recall = safe_div(tp, tp + fn)
    return {
        "dice": safe_div(2 * tp, 2 * tp + fp + fn),
        "iou": safe_div(tp, tp + fp + fn),
        "precision": precision,
        "recall": recall,
        "f1": safe_div(2 * precision * recall, precision + recall),
        "false_positive_rate": safe_div(fp, fp + tn),
        "false_negative_rate": safe_div(fn, fn + tp),
    }


def resolve_device(requested: str) -> torch.device:
    if requested == "cuda" and not torch.cuda.is_available():
        raise SystemExit("CUDA solicitada, mas indisponivel.")
    if requested == "auto":
        return torch.device("cuda" if torch.cuda.is_available() else "cpu")
    return torch.device(requested)


def run_epoch(
    *,
    model: nn.Module,
    loader: DataLoader,
    device: torch.device,
    optimizer: torch.optim.Optimizer | None = None,
) -> tuple[float, dict[str, float]]:
    training = optimizer is not None
    model.train(training)
    total_loss = 0.0
    total_counts = {"tp": 0, "fp": 0, "tn": 0, "fn": 0}

    for images, masks in loader:
        images = images.to(device)
        masks = masks.to(device)
        with torch.set_grad_enabled(training):
            logits = model(images)
            loss = combined_loss(logits, masks)
            if training:
                optimizer.zero_grad(set_to_none=True)
                loss.backward()
                optimizer.step()

        total_loss += float(loss.item()) * images.shape[0]
        counts = metric_counts(logits.detach().cpu(), masks.detach().cpu())
        for key, value in counts.items():
            total_counts[key] += value

    return total_loss / max(len(loader.dataset), 1), metrics_from_counts(total_counts)


def main() -> None:
    args = parse_args()
    require_research_acceptance(args.accept_experimental_non_commercial_use)
    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)

    train_records = load_records(Path(args.train_manifest))
    val_records = load_records(Path(args.val_manifest))
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    train_dataset = ManifestSegmentationDataset(train_records, args.image_size, augment=True)
    val_dataset = ManifestSegmentationDataset(val_records, args.image_size, augment=False)
    if not train_dataset or not val_dataset:
        raise SystemExit("Manifestos sem pares imagem+mascara suficientes para treino e validacao.")

    plan = {
        "dataset": "CO2Wounds-V2",
        "license_scope": "academic_research_prototype_only",
        "model": "SmallUNet",
        "train_records": len(train_dataset),
        "val_records": len(val_dataset),
        "image_size": args.image_size,
        "epochs": args.epochs,
        "batch_size": args.batch_size,
        "status": "dry_run" if args.dry_run else "training",
        "clinical_status": "experimental_not_clinically_validated",
    }
    (output_dir / "training_plan.json").write_text(json.dumps(plan, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(plan, indent=2, ensure_ascii=False))
    if args.dry_run:
        return

    device = resolve_device(args.device)
    model = SmallUNet().to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.learning_rate)
    train_loader = DataLoader(train_dataset, batch_size=args.batch_size, shuffle=True, num_workers=0)
    val_loader = DataLoader(val_dataset, batch_size=args.batch_size, shuffle=False, num_workers=0)

    best_dice = -1.0
    history: list[dict[str, Any]] = []
    for epoch in range(1, args.epochs + 1):
        train_loss, train_metrics = run_epoch(model=model, loader=train_loader, device=device, optimizer=optimizer)
        val_loss, val_metrics = run_epoch(model=model, loader=val_loader, device=device)
        record = {
            "epoch": epoch,
            "train_loss": train_loss,
            "val_loss": val_loss,
            "train_metrics": train_metrics,
            "val_metrics": val_metrics,
        }
        history.append(record)
        print(json.dumps(record, indent=2))

        if val_metrics["dice"] > best_dice:
            best_dice = val_metrics["dice"]
            torch.save(
                {
                    "model_state_dict": model.state_dict(),
                    "model": "SmallUNet",
                    "dataset": "CO2Wounds-V2",
                    "clinical_status": "experimental_not_clinically_validated",
                    "val_metrics": val_metrics,
                },
                output_dir / "best_small_unet.pt",
            )

    (output_dir / "history.json").write_text(json.dumps(history, indent=2), encoding="utf-8")
    (output_dir / "final_metrics.json").write_text(json.dumps(history[-1], indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
