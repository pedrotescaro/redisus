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
import time
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
    parser.add_argument("--scheduler", choices=["none", "cosine"], default="none")
    parser.add_argument("--early-stopping-patience", type=int, default=0)
    parser.add_argument("--min-positive-ratio", type=float, default=0.0005)
    parser.add_argument("--max-positive-ratio", type=float, default=0.80)
    parser.add_argument("--num-workers", type=int, default=0)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--device", choices=["auto", "cpu", "cuda"], default="auto")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--overwrite-output", action="store_true")
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


def audit_records(
    records: list[dict[str, Any]],
    *,
    min_positive_ratio: float,
    max_positive_ratio: float,
) -> dict[str, Any]:
    failures: list[dict[str, Any]] = []
    positive_ratios: list[float] = []
    missing_files = 0
    size_mismatches = 0

    for record in records:
        image_path = Path(record.get("image", ""))
        mask_path = Path(record.get("mask", ""))
        if not image_path.exists() or not mask_path.exists():
            missing_files += 1
            failures.append({"id": record.get("id"), "error": "missing_file"})
            continue

        with Image.open(image_path) as image, Image.open(mask_path) as mask:
            if image.size != mask.size:
                size_mismatches += 1
                failures.append({"id": record.get("id"), "error": "size_mismatch", "image": image.size, "mask": mask.size})
                continue
            mask_array = np.asarray(mask.convert("L"))
            positive_ratio = float((mask_array > 0).mean())
            positive_ratios.append(positive_ratio)
            if positive_ratio < min_positive_ratio:
                failures.append({"id": record.get("id"), "error": "mask_too_small", "positive_ratio": positive_ratio})
            if positive_ratio > max_positive_ratio:
                failures.append({"id": record.get("id"), "error": "mask_too_large", "positive_ratio": positive_ratio})

    ratios = sorted(positive_ratios)
    return {
        "records": len(records),
        "missing_files": missing_files,
        "size_mismatches": size_mismatches,
        "failures": len(failures),
        "failure_examples": failures[:20],
        "positive_ratio_min": ratios[0] if ratios else None,
        "positive_ratio_median": ratios[len(ratios) // 2] if ratios else None,
        "positive_ratio_max": ratios[-1] if ratios else None,
    }


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


def guard_existing_outputs(output_dir: Path, *, overwrite: bool, dry_run: bool, resume: bool) -> None:
    if dry_run or overwrite or resume:
        return
    protected_outputs = [
        output_dir / "best_small_unet.pt",
        output_dir / "last_small_unet.pt",
        output_dir / "history.json",
        output_dir / "final_metrics.json",
    ]
    existing = [path for path in protected_outputs if path.exists()]
    if existing:
        files = ", ".join(str(path) for path in existing)
        raise SystemExit(
            "Saida existente detectada; para nao sobrescrever checkpoints/metricas, use outro --output-dir "
            f"ou rode conscientemente com --overwrite-output/--resume. Arquivos: {files}"
        )


def load_history(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


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
    guard_existing_outputs(output_dir, overwrite=args.overwrite_output, dry_run=args.dry_run, resume=args.resume)

    train_dataset = ManifestSegmentationDataset(train_records, args.image_size, augment=True)
    val_dataset = ManifestSegmentationDataset(val_records, args.image_size, augment=False)
    if not train_dataset or not val_dataset:
        raise SystemExit("Manifestos sem pares imagem+mascara suficientes para treino e validacao.")

    train_audit = audit_records(
        train_dataset.records,
        min_positive_ratio=args.min_positive_ratio,
        max_positive_ratio=args.max_positive_ratio,
    )
    val_audit = audit_records(
        val_dataset.records,
        min_positive_ratio=args.min_positive_ratio,
        max_positive_ratio=args.max_positive_ratio,
    )

    plan = {
        "dataset": "CO2Wounds-V2",
        "license_scope": "academic_research_prototype_only",
        "model": "SmallUNet",
        "train_records": len(train_dataset),
        "val_records": len(val_dataset),
        "train_audit": train_audit,
        "val_audit": val_audit,
        "image_size": args.image_size,
        "epochs": args.epochs,
        "batch_size": args.batch_size,
        "learning_rate": args.learning_rate,
        "scheduler": args.scheduler,
        "early_stopping_patience": args.early_stopping_patience,
        "device_requested": args.device,
        "resume": args.resume,
        "status": "dry_run" if args.dry_run else "training",
        "clinical_status": "experimental_not_clinically_validated",
    }
    (output_dir / "training_plan.json").write_text(json.dumps(plan, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(plan, indent=2, ensure_ascii=False))
    if args.dry_run:
        return

    device = resolve_device(args.device)
    plan["device_resolved"] = str(device)
    (output_dir / "training_plan.json").write_text(json.dumps(plan, indent=2, ensure_ascii=False), encoding="utf-8")
    model = SmallUNet().to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.learning_rate)
    scheduler = (
        torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=max(args.epochs, 1))
        if args.scheduler == "cosine"
        else None
    )
    train_loader = DataLoader(train_dataset, batch_size=args.batch_size, shuffle=True, num_workers=args.num_workers)
    val_loader = DataLoader(val_dataset, batch_size=args.batch_size, shuffle=False, num_workers=args.num_workers)

    best_dice = -1.0
    best_epoch = 0
    epochs_without_improvement = 0
    history: list[dict[str, Any]] = []
    start_epoch = 1
    if args.resume:
        checkpoint_path = output_dir / "last_small_unet.pt"
        if not checkpoint_path.exists():
            raise SystemExit(f"--resume solicitado, mas checkpoint nao encontrado: {checkpoint_path}")
        checkpoint = torch.load(checkpoint_path, map_location=device)
        model.load_state_dict(checkpoint["model_state_dict"])
        if checkpoint.get("optimizer_state_dict"):
            optimizer.load_state_dict(checkpoint["optimizer_state_dict"])
        if scheduler is not None and checkpoint.get("scheduler_state_dict"):
            scheduler.load_state_dict(checkpoint["scheduler_state_dict"])
        history = load_history(output_dir / "history.json")
        last_epoch = int(checkpoint.get("epoch", history[-1]["epoch"] if history else 0))
        best_epoch = int(checkpoint.get("best_epoch", 0))
        best_dice = float(checkpoint.get("best_dice", -1.0))
        start_epoch = last_epoch + 1
        print(
            json.dumps(
                {
                    "status": "resuming",
                    "checkpoint": str(checkpoint_path),
                    "start_epoch": start_epoch,
                    "target_epochs": args.epochs,
                    "best_epoch": best_epoch,
                    "best_dice": best_dice,
                },
                indent=2,
            ),
            flush=True,
        )

    if start_epoch > args.epochs:
        raise SystemExit(f"Nada para treinar: checkpoint ja esta na epoca {start_epoch - 1} de {args.epochs}.")

    for epoch in range(start_epoch, args.epochs + 1):
        started_at = time.perf_counter()
        train_loss, train_metrics = run_epoch(model=model, loader=train_loader, device=device, optimizer=optimizer)
        val_loss, val_metrics = run_epoch(model=model, loader=val_loader, device=device)
        current_lr = float(optimizer.param_groups[0]["lr"])
        if scheduler is not None:
            scheduler.step()
        record = {
            "epoch": epoch,
            "duration_seconds": round(time.perf_counter() - started_at, 3),
            "learning_rate": current_lr,
            "train_loss": train_loss,
            "val_loss": val_loss,
            "train_metrics": train_metrics,
            "val_metrics": val_metrics,
        }
        history.append(record)
        print(json.dumps(record, indent=2), flush=True)

        if val_metrics["dice"] > best_dice:
            best_dice = val_metrics["dice"]
            best_epoch = epoch
            epochs_without_improvement = 0
            torch.save(
                {
                    "model_state_dict": model.state_dict(),
                    "model": "SmallUNet",
                    "dataset": "CO2Wounds-V2",
                    "clinical_status": "experimental_not_clinically_validated",
                    "epoch": epoch,
                    "best_epoch": best_epoch,
                    "best_dice": best_dice,
                    "training_args": vars(args),
                    "val_metrics": val_metrics,
                },
                output_dir / "best_small_unet.pt",
            )
        else:
            epochs_without_improvement += 1

        (output_dir / "history.json").write_text(json.dumps(history, indent=2), encoding="utf-8")
        final_metrics = {
            **record,
            "status": "running_partial",
            "best_epoch": best_epoch,
            "best_dice": best_dice,
            "completed_epochs": epoch,
            "target_epochs": args.epochs,
        }
        (output_dir / "final_metrics.json").write_text(json.dumps(final_metrics, indent=2), encoding="utf-8")
        torch.save(
            {
                "model_state_dict": model.state_dict(),
                "optimizer_state_dict": optimizer.state_dict(),
                "scheduler_state_dict": scheduler.state_dict() if scheduler is not None else None,
                "model": "SmallUNet",
                "dataset": "CO2Wounds-V2",
                "clinical_status": "experimental_not_clinically_validated",
                "epoch": epoch,
                "best_epoch": best_epoch,
                "best_dice": best_dice,
                "training_args": vars(args),
                "val_metrics": val_metrics,
            },
            output_dir / "last_small_unet.pt",
        )

        if args.early_stopping_patience > 0 and epochs_without_improvement >= args.early_stopping_patience:
            print(
                json.dumps(
                    {
                        "status": "early_stopped",
                        "epoch": epoch,
                        "best_epoch": best_epoch,
                        "best_dice": best_dice,
                    },
                    indent=2,
                ),
                flush=True,
            )
            break

    final_metrics = {
        **history[-1],
        "status": "completed" if history[-1]["epoch"] >= args.epochs else "stopped_before_target",
        "best_epoch": best_epoch,
        "best_dice": best_dice,
        "completed_epochs": history[-1]["epoch"],
        "target_epochs": args.epochs,
    }
    (output_dir / "final_metrics.json").write_text(json.dumps(final_metrics, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
