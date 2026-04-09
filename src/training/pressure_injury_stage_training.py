from __future__ import annotations

import json
import random
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np

from .pressure_injury_dataset import (
    PRESSURE_INJURY_STAGE_LABELS,
    PRESSURE_INJURY_STAGE_ORDER,
    build_pressure_injury_manifest,
    write_pressure_injury_manifest,
)

SEED = 42
random.seed(SEED)
np.random.seed(SEED)


def _import_torch_modules():
    try:
        import torch
        import torch.nn as nn
        from torch.utils.data import DataLoader, Dataset, WeightedRandomSampler
        from torchvision import models, transforms
        from PIL import Image
    except ImportError as exc:
        raise RuntimeError(
            "Treinamento LP-only requer PyTorch/torchvision/Pillow. "
            "Instale as dependencias antes de rodar este pipeline."
        ) from exc
    return torch, nn, DataLoader, Dataset, WeightedRandomSampler, models, transforms, Image


@dataclass(slots=True)
class PressureInjuryTrainingConfig:
    raw_dataset_dir: str = "dataset/piid/raw"
    manifest_path: str = "dataset/piid/manifests/piid_lp_split.json"
    output_dir: str = "models/pressure_injury_stage_classifier"
    image_size: int = 224
    batch_size: int = 16
    epochs: int = 35
    learning_rate: float = 1e-3
    weight_decay: float = 1e-4
    focal_gamma: float = 1.5
    label_smoothing: float = 0.03
    stage3_loss_multiplier: float = 1.35
    stage4_loss_multiplier: float = 1.10
    stage34_sampler_multiplier: float = 1.20
    train_ratio: float = 0.7
    val_ratio: float = 0.15
    seed: int = SEED
    num_workers: int = 0
    notes: list[str] = field(
        default_factory=lambda: [
            "Transfer learning com ResNet50",
            "Data augmentation conservador para manter sinais clinicos de cor",
            "Validação estratificada por estágio",
        ]
    )


def ensure_pressure_injury_layout(config: PressureInjuryTrainingConfig) -> dict[str, Path]:
    raw_root = Path(config.raw_dataset_dir)
    manifest_path = Path(config.manifest_path)
    output_dir = Path(config.output_dir)
    dirs = {
        "raw_root": raw_root,
        "manifest_dir": manifest_path.parent,
        "output_dir": output_dir,
    }
    for path in dirs.values():
        path.mkdir(parents=True, exist_ok=True)
    for stage_code in PRESSURE_INJURY_STAGE_ORDER:
        (raw_root / stage_code).mkdir(parents=True, exist_ok=True)
    return dirs


def prepare_pressure_injury_manifest(config: PressureInjuryTrainingConfig) -> Path:
    ensure_pressure_injury_layout(config)
    manifest = build_pressure_injury_manifest(
        config.raw_dataset_dir,
        train_ratio=config.train_ratio,
        val_ratio=config.val_ratio,
        seed=config.seed,
    )
    return write_pressure_injury_manifest(manifest, config.manifest_path)


def _build_train_transform(transforms, image_size: int):
    return transforms.Compose(
        [
            transforms.Resize((image_size, image_size)),
            transforms.RandomHorizontalFlip(p=0.5),
            transforms.RandomVerticalFlip(p=0.2),
            transforms.RandomRotation(degrees=15),
            transforms.ColorJitter(brightness=0.08, contrast=0.06, saturation=0.03, hue=0.01),
            transforms.ToTensor(),
            transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
        ]
    )


def _build_eval_transform(transforms, image_size: int):
    return transforms.Compose(
        [
            transforms.Resize((image_size, image_size)),
            transforms.ToTensor(),
            transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
        ]
    )


def _compute_class_weights(samples: list[dict[str, Any]]) -> dict[int, float]:
    counts = {index: 0 for index in range(len(PRESSURE_INJURY_STAGE_ORDER))}
    for sample in samples:
        counts[int(sample["stage_index"])] += 1
    total = sum(counts.values()) or 1
    weights: dict[int, float] = {}
    for class_index, count in counts.items():
        weights[class_index] = round(total / max(1, len(counts) * count), 6)
    return weights


def _evaluate_predictions(predictions: list[int], targets: list[int]) -> dict[str, Any]:
    confusion = [
        [0 for _ in PRESSURE_INJURY_STAGE_ORDER]
        for _ in PRESSURE_INJURY_STAGE_ORDER
    ]
    correct = 0
    for predicted, target in zip(predictions, targets):
        confusion[target][predicted] += 1
        if predicted == target:
            correct += 1
    per_stage_accuracy: dict[str, float] = {}
    for stage_index, stage_code in enumerate(PRESSURE_INJURY_STAGE_ORDER):
        row_total = sum(confusion[stage_index])
        per_stage_accuracy[stage_code] = round(
            (confusion[stage_index][stage_index] / row_total) if row_total else 0.0,
            4,
        )
    return {
        "accuracy": round(correct / max(1, len(targets)), 4),
        "confusion_matrix": confusion,
        "per_stage_accuracy": per_stage_accuracy,
    }


def train_pressure_injury_stage_classifier(config: PressureInjuryTrainingConfig) -> dict[str, Any]:
    torch, nn, DataLoader, Dataset, WeightedRandomSampler, models, transforms, Image = _import_torch_modules()

    class PressureInjuryTorchDataset(Dataset):
        def __init__(self, samples: list[dict[str, Any]], transform):
            self.samples = samples
            self.transform = transform

        def __len__(self) -> int:
            return len(self.samples)

        def __getitem__(self, index: int):
            sample = self.samples[index]
            image = Image.open(sample["path"]).convert("RGB")
            return self.transform(image), int(sample["stage_index"])

    def build_model() -> Any:
        model = models.resnet50(weights=models.ResNet50_Weights.IMAGENET1K_V2)
        for parameter in model.parameters():
            parameter.requires_grad = False
        for parameter in model.layer4.parameters():
            parameter.requires_grad = True
        model.fc = nn.Sequential(
            nn.Linear(model.fc.in_features, 256),
            nn.ReLU(inplace=True),
            nn.Dropout(0.3),
            nn.Linear(256, len(PRESSURE_INJURY_STAGE_ORDER)),
        )
        return model

    ensure_pressure_injury_layout(config)
    manifest_path = Path(config.manifest_path)
    if not manifest_path.exists():
        manifest_path = prepare_pressure_injury_manifest(config)
    manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))

    train_samples = list(manifest["splits"]["train"])
    val_samples = list(manifest["splits"]["val"])
    test_samples = list(manifest["splits"]["test"])
    if not train_samples or not val_samples:
        raise RuntimeError("Manifesto do PIID sem amostras suficientes para treino/validação.")

    train_transform = _build_train_transform(transforms, config.image_size)
    eval_transform = _build_eval_transform(transforms, config.image_size)
    train_dataset = PressureInjuryTorchDataset(train_samples, train_transform)
    val_dataset = PressureInjuryTorchDataset(val_samples, eval_transform)
    test_dataset = PressureInjuryTorchDataset(test_samples, eval_transform)

    class_weights = _compute_class_weights(train_samples)
    stage3_index = PRESSURE_INJURY_STAGE_ORDER.index("stage_3")
    stage4_index = PRESSURE_INJURY_STAGE_ORDER.index("stage_4")
    class_weights[stage3_index] = round(class_weights[stage3_index] * config.stage3_loss_multiplier, 6)
    class_weights[stage4_index] = round(class_weights[stage4_index] * config.stage4_loss_multiplier, 6)
    sample_weights = []
    for sample in train_samples:
        sample_weight = class_weights[int(sample["stage_index"])]
        if sample["stage_code"] in {"stage_3", "stage_4"}:
            sample_weight *= config.stage34_sampler_multiplier
        sample_weights.append(sample_weight)
    sampler = WeightedRandomSampler(sample_weights, num_samples=len(sample_weights), replacement=True)

    train_loader = DataLoader(train_dataset, batch_size=config.batch_size, sampler=sampler, num_workers=config.num_workers)
    val_loader = DataLoader(val_dataset, batch_size=config.batch_size, shuffle=False, num_workers=config.num_workers)
    test_loader = DataLoader(test_dataset, batch_size=config.batch_size, shuffle=False, num_workers=config.num_workers)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = build_model().to(device)
    class_weight_tensor = torch.tensor([class_weights[i] for i in range(len(class_weights))], device=device)

    class WeightedFocalLoss(nn.Module):
        def __init__(self, weight, gamma: float, label_smoothing: float):
            super().__init__()
            self.register_buffer("weight", weight)
            self.gamma = gamma
            self.label_smoothing = label_smoothing

        def forward(self, logits, labels):
            ce_loss = nn.functional.cross_entropy(
                logits,
                labels,
                weight=self.weight,
                reduction="none",
                label_smoothing=self.label_smoothing,
            )
            pt = torch.exp(-ce_loss.detach())
            focal_weight = (1.0 - pt).pow(self.gamma)
            return (focal_weight * ce_loss).mean()

    criterion = WeightedFocalLoss(
        class_weight_tensor,
        gamma=config.focal_gamma,
        label_smoothing=config.label_smoothing,
    )
    optimizer = torch.optim.AdamW(
        [parameter for parameter in model.parameters() if parameter.requires_grad],
        lr=config.learning_rate,
        weight_decay=config.weight_decay,
    )

    def run_epoch(loader, *, training: bool):
        predictions: list[int] = []
        targets: list[int] = []
        total_loss = 0.0
        model.train(training)
        for inputs, labels in loader:
            inputs = inputs.to(device)
            labels = labels.to(device)
            if training:
                optimizer.zero_grad()
            logits = model(inputs)
            loss = criterion(logits, labels)
            if training:
                loss.backward()
                optimizer.step()
            total_loss += float(loss.item()) * int(labels.size(0))
            predicted = torch.argmax(logits, dim=1)
            predictions.extend(predicted.detach().cpu().tolist())
            targets.extend(labels.detach().cpu().tolist())
        metrics = _evaluate_predictions(predictions, targets)
        metrics["loss"] = round(total_loss / max(1, len(targets)), 4)
        return metrics

    history: list[dict[str, Any]] = []
    best_val_accuracy = -1.0
    best_state = None
    best_epoch = 0

    for epoch in range(config.epochs):
        train_metrics = run_epoch(train_loader, training=True)
        val_metrics = run_epoch(val_loader, training=False)
        history.append({"epoch": epoch + 1, "train": train_metrics, "val": val_metrics})
        if val_metrics["accuracy"] > best_val_accuracy:
            best_val_accuracy = float(val_metrics["accuracy"])
            best_epoch = epoch + 1
            best_state = {key: value.detach().cpu() for key, value in model.state_dict().items()}

    if best_state is None:
        raise RuntimeError("Treinamento nao gerou nenhum checkpoint valido.")

    model.load_state_dict(best_state)
    test_metrics = run_epoch(test_loader, training=False) if test_samples else {}

    output_dir = Path(config.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    weights_path = output_dir / "pressure_injury_stage_resnet50.pth"
    torch.save(best_state, weights_path)

    metadata = {
        "model_name": "PressureInjuryStageClassifier",
        "version": f"piid-stage-resnet50-{datetime.now().strftime('%Y%m%d')}",
        "framework": "PyTorch/torchvision",
        "dataset_name": manifest["dataset_name"],
        "source_root": manifest["source_root"],
        "class_names": list(PRESSURE_INJURY_STAGE_ORDER),
        "class_labels": dict(PRESSURE_INJURY_STAGE_LABELS),
        "image_size": config.image_size,
        "batch_size": config.batch_size,
        "epochs": config.epochs,
        "focal_gamma": config.focal_gamma,
        "label_smoothing": config.label_smoothing,
        "stage3_loss_multiplier": config.stage3_loss_multiplier,
        "stage4_loss_multiplier": config.stage4_loss_multiplier,
        "stage34_sampler_multiplier": config.stage34_sampler_multiplier,
        "best_epoch": best_epoch,
        "device": str(device),
        "notes": list(config.notes),
        "split_sizes": dict(manifest["summary"]["split_sizes"]),
        "train_class_weights": class_weights,
        "validation_metrics": history[-1]["val"] if history else {},
        "test_metrics": test_metrics,
        "created_at": datetime.now().isoformat(),
    }
    (output_dir / "training_history.json").write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "model_metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "weights_path": str(weights_path),
        "metadata_path": str(output_dir / "model_metadata.json"),
        "history_path": str(output_dir / "training_history.json"),
        "best_epoch": best_epoch,
        "validation_accuracy": best_val_accuracy,
        "test_metrics": test_metrics,
    }
