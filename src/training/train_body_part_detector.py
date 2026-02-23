#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple

import torch
from torch import nn
from torch.optim import AdamW
from torch.utils.data import DataLoader
from torchvision import datasets, models, transforms


IMAGENET_MEAN = [0.485, 0.456, 0.406]
IMAGENET_STD = [0.229, 0.224, 0.225]


@dataclass
class Config:
    dataset_dir: str = "dataset/body_parts"
    output_dir: str = "models/body_part_detector"
    image_size: int = 224
    batch_size: int = 24
    epochs: int = 25
    lr: float = 3e-4
    weight_decay: float = 1e-4
    val_split: float = 0.2
    num_workers: int = 0
    freeze_backbone_epochs: int = 5
    adv_epsilon: float = 0.0
    adv_alpha: float = 0.5


def build_transforms(size: int) -> Tuple[transforms.Compose, transforms.Compose]:
    train_tf = transforms.Compose([
        transforms.Resize((size, size)),
        transforms.RandomHorizontalFlip(p=0.5),
        transforms.RandomRotation(degrees=10),
        transforms.ColorJitter(brightness=0.08, contrast=0.08, saturation=0.05, hue=0.01),
        transforms.ToTensor(),
        transforms.Normalize(mean=IMAGENET_MEAN, std=IMAGENET_STD),
    ])
    val_tf = transforms.Compose([
        transforms.Resize((size, size)),
        transforms.ToTensor(),
        transforms.Normalize(mean=IMAGENET_MEAN, std=IMAGENET_STD),
    ])
    return train_tf, val_tf


def split_indices(size: int, val_split: float, seed: int = 42) -> Tuple[List[int], List[int]]:
    generator = torch.Generator().manual_seed(seed)
    indices = torch.randperm(size, generator=generator).tolist()
    val_size = int(size * val_split)
    val_idx = indices[:val_size]
    train_idx = indices[val_size:]
    return train_idx, val_idx


def make_loaders(cfg: Config):
    train_tf, val_tf = build_transforms(cfg.image_size)

    base_ds = datasets.ImageFolder(cfg.dataset_dir)
    train_idx, val_idx = split_indices(len(base_ds), cfg.val_split)

    train_ds = datasets.ImageFolder(cfg.dataset_dir, transform=train_tf)
    val_ds = datasets.ImageFolder(cfg.dataset_dir, transform=val_tf)

    train_subset = torch.utils.data.Subset(train_ds, train_idx)
    val_subset = torch.utils.data.Subset(val_ds, val_idx)

    train_loader = DataLoader(
        train_subset,
        batch_size=cfg.batch_size,
        shuffle=True,
        num_workers=cfg.num_workers,
        pin_memory=torch.cuda.is_available(),
    )
    val_loader = DataLoader(
        val_subset,
        batch_size=cfg.batch_size,
        shuffle=False,
        num_workers=cfg.num_workers,
        pin_memory=torch.cuda.is_available(),
    )
    return base_ds.classes, train_loader, val_loader


def build_model(num_classes: int) -> nn.Module:
    model = models.mobilenet_v3_small(weights=models.MobileNet_V3_Small_Weights.DEFAULT)
    in_features = model.classifier[-1].in_features
    model.classifier[-1] = nn.Linear(in_features, num_classes)
    return model


def set_backbone_trainable(model: nn.Module, trainable: bool) -> None:
    for name, param in model.named_parameters():
        if not name.startswith("classifier"):
            param.requires_grad = trainable


def accuracy(outputs: torch.Tensor, targets: torch.Tensor) -> float:
    preds = outputs.argmax(dim=1)
    return float((preds == targets).float().mean().item())


def _clamp_normalized_images(images: torch.Tensor) -> torch.Tensor:
    mean = torch.tensor(IMAGENET_MEAN, device=images.device, dtype=images.dtype).view(1, 3, 1, 1)
    std = torch.tensor(IMAGENET_STD, device=images.device, dtype=images.dtype).view(1, 3, 1, 1)
    min_v = (0.0 - mean) / std
    max_v = (1.0 - mean) / std
    return torch.max(torch.min(images, max_v), min_v)


def _fgsm_attack(
    model: nn.Module,
    images: torch.Tensor,
    labels: torch.Tensor,
    criterion: nn.Module,
    epsilon: float,
) -> torch.Tensor:
    adv_images = images.detach().clone().requires_grad_(True)
    outputs = model(adv_images)
    loss = criterion(outputs, labels)
    grads = torch.autograd.grad(loss, adv_images, only_inputs=True)[0]
    perturbed = adv_images + epsilon * grads.sign()
    perturbed = _clamp_normalized_images(perturbed)
    return perturbed.detach()


def run_epoch(
    model,
    loader,
    criterion,
    optimizer,
    device,
    train: bool,
    adv_epsilon: float = 0.0,
    adv_alpha: float = 0.5,
):
    model.train(train)
    total_loss = 0.0
    total_acc = 0.0
    total_samples = 0

    for images, labels in loader:
        images = images.to(device)
        labels = labels.to(device)

        with torch.set_grad_enabled(train):
            outputs = model(images)
            clean_loss = criterion(outputs, labels)

            if train and adv_epsilon > 0:
                adv_images = _fgsm_attack(
                    model=model,
                    images=images,
                    labels=labels,
                    criterion=criterion,
                    epsilon=adv_epsilon,
                )
                adv_outputs = model(adv_images)
                adv_loss = criterion(adv_outputs, labels)
                loss = (1.0 - adv_alpha) * clean_loss + adv_alpha * adv_loss
            else:
                loss = clean_loss

            if train:
                optimizer.zero_grad()
                loss.backward()
                optimizer.step()

        batch = labels.size(0)
        total_samples += batch
        total_loss += loss.item() * batch
        total_acc += accuracy(outputs, labels) * batch

    return total_loss / max(total_samples, 1), total_acc / max(total_samples, 1)


def export_onnx(model: nn.Module, output_path: Path, num_classes: int, image_size: int, device: torch.device):
    model.eval()
    dummy = torch.randn(1, 3, image_size, image_size, device=device)
    torch.onnx.export(
        model,
        dummy,
        str(output_path),
        input_names=["input"],
        output_names=["logits"],
        dynamic_axes={"input": {0: "batch"}, "logits": {0: "batch"}},
        opset_version=17,
    )


def train(cfg: Config):
    dataset_path = Path(cfg.dataset_dir)
    if not dataset_path.exists():
        raise FileNotFoundError(
            f"Dataset não encontrado em {dataset_path}. "
            "Crie pastas por classe (ex.: foot, lower_leg, hand, abdomen...)."
        )

    classes, train_loader, val_loader = make_loaders(cfg)
    num_classes = len(classes)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = build_model(num_classes).to(device)

    output_dir = Path(cfg.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    criterion = nn.CrossEntropyLoss()
    optimizer = AdamW(model.parameters(), lr=cfg.lr, weight_decay=cfg.weight_decay)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=cfg.epochs)

    best_val_acc = 0.0
    history: List[Dict] = []

    for epoch in range(1, cfg.epochs + 1):
        set_backbone_trainable(model, trainable=(epoch > cfg.freeze_backbone_epochs))

        train_loss, train_acc = run_epoch(
            model,
            train_loader,
            criterion,
            optimizer,
            device,
            train=True,
            adv_epsilon=cfg.adv_epsilon,
            adv_alpha=cfg.adv_alpha,
        )
        val_loss, val_acc = run_epoch(model, val_loader, criterion, optimizer, device, train=False)
        scheduler.step()

        entry = {
            "epoch": epoch,
            "train_loss": round(train_loss, 5),
            "train_acc": round(train_acc, 5),
            "val_loss": round(val_loss, 5),
            "val_acc": round(val_acc, 5),
        }
        history.append(entry)
        print(entry)

        if val_acc > best_val_acc:
            best_val_acc = val_acc
            torch.save(model.state_dict(), output_dir / "body_part_detector_best.pth")

    model.load_state_dict(torch.load(output_dir / "body_part_detector_best.pth", map_location=device))
    torch.save(model, output_dir / "body_part_detector_full.pt")

    metadata = {
        "classes": classes,
        "num_classes": num_classes,
        "image_size": cfg.image_size,
        "best_val_acc": round(best_val_acc, 5),
        "architecture": "mobilenet_v3_small",
        "adversarial_training": {
            "enabled": cfg.adv_epsilon > 0,
            "method": "fgsm",
            "epsilon": cfg.adv_epsilon,
            "alpha": cfg.adv_alpha,
        },
    }
    (output_dir / "history.json").write_text(json.dumps(history, indent=2, ensure_ascii=False), encoding="utf-8")
    (output_dir / "metadata.json").write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")

    onnx_path = output_dir / "body_part_detector.onnx"
    try:
        export_onnx(model, onnx_path, num_classes, cfg.image_size, device)
        print(f"ONNX exportado: {onnx_path}")
    except Exception as exc:
        print(f"Falha ao exportar ONNX: {exc}")

    print(f"Treino concluído. Melhor val_acc={best_val_acc:.2%}")
    print(f"Artefatos em: {output_dir}")


def parse_args() -> Config:
    parser = argparse.ArgumentParser(description="Treina detector de parte do corpo para feridas")
    parser.add_argument("--dataset", type=str, default="dataset/body_parts")
    parser.add_argument("--output", type=str, default="models/body_part_detector")
    parser.add_argument("--img-size", type=int, default=224)
    parser.add_argument("--batch-size", type=int, default=24)
    parser.add_argument("--epochs", type=int, default=25)
    parser.add_argument("--lr", type=float, default=3e-4)
    parser.add_argument("--val-split", type=float, default=0.2)
    parser.add_argument("--num-workers", type=int, default=0)
    parser.add_argument("--adv-epsilon", type=float, default=0.0,
                        help="Epsilon do FGSM (0 desativa treino adversarial). Ex.: 0.01")
    parser.add_argument("--adv-alpha", type=float, default=0.5,
                        help="Peso da loss adversarial na loss total (0-1).")
    args = parser.parse_args()

    adv_alpha = max(0.0, min(1.0, args.adv_alpha))

    return Config(
        dataset_dir=args.dataset,
        output_dir=args.output,
        image_size=args.img_size,
        batch_size=args.batch_size,
        epochs=args.epochs,
        lr=args.lr,
        val_split=args.val_split,
        num_workers=args.num_workers,
        adv_epsilon=max(0.0, args.adv_epsilon),
        adv_alpha=adv_alpha,
    )


if __name__ == "__main__":
    config = parse_args()
    train(config)
