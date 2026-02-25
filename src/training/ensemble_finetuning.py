#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
===============================================================================
REDISUS - ENSEMBLE FINE-TUNING PIPELINE
===============================================================================

Script para fine-tuning dos modelos da camada adicional de IA em datasets
clínicos locais. Permite adaptar os modelos pré-treinados (DermaIntel,
BiomedCLIP) para o contexto específico da instituição/população.

Modelos que podem ser fine-tuned:
  1. DermaIntel ViT: Fine-tuning do classificador de feridas (7 classes)
  2. BiomedCLIP: Fine-tuning do encoder visual para prompts clínicos customizados

O MedSAM não é fine-tuned aqui (requer pipeline específico de segmentação
com máscaras anotadas; use o treinamento de U-Net para isso).

Requisitos:
    pip install torch torchvision transformers open_clip_torch
    pip install albumentations scikit-learn matplotlib

Datasets suportados:
    - Pasta com subpastas por classe (ImageFolder)
    - CSV com colunas [image_path, label]

Uso:
    python ensemble_finetuning.py --model dermaintel --data_dir ./data/wounds
    python ensemble_finetuning.py --model biomedclip --data_dir ./data/wounds
===============================================================================
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np

# ---------------------------------------------------------------------------
# Configuração
# ---------------------------------------------------------------------------

SEED = 42
NUM_WORKERS = 2

# Classes REDISUS (5 classes de etiologia)
REDISUS_CLASSES = [
    "Ulcera Venosa",
    "Ulcera Arterial",
    "Pe Diabetico",
    "Lesao por Pressao",
    "Ferida Cirurgica",
]

# Classes DermaIntel (7 classes)
DERMAINTEL_CLASSES = [
    "Background",
    "Diabetic Wound",
    "Normal Skin",
    "Pressure Wound",
    "Surgical Wound",
    "Traumatic Wound",
    "Venous Wound",
]


class FinetuneConfig:
    """Configuracao centralizada do fine-tuning."""

    # Paths
    data_dir: str = "data/wounds"
    output_dir: str = "models/finetuned"
    checkpoint_dir: str = "models/checkpoints"

    # Training
    epochs: int = 30
    batch_size: int = 16
    learning_rate: float = 2e-5
    weight_decay: float = 0.01
    warmup_steps: int = 100

    # Fine-tuning strategy
    freeze_backbone_epochs: int = 5  # Feature extraction antes do fine-tuning
    unfreeze_layers: int = 4  # Quantas camadas do ViT descongelar
    label_smoothing: float = 0.1

    # Data augmentation
    augment: bool = True
    img_size: int = 224

    # Early stopping
    patience: int = 7
    min_delta: float = 0.001

    # Validation
    val_split: float = 0.2

    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            if hasattr(self, k):
                setattr(self, k, v)


# ---------------------------------------------------------------------------
# Dataset
# ---------------------------------------------------------------------------

def build_transforms(img_size: int, augment: bool = True, is_train: bool = True):
    """Constroi transformacoes para treino/validacao."""
    import torch
    from torchvision import transforms

    if is_train and augment:
        return transforms.Compose([
            transforms.Resize((img_size + 32, img_size + 32)),
            transforms.RandomCrop(img_size),
            transforms.RandomHorizontalFlip(p=0.5),
            transforms.RandomVerticalFlip(p=0.3),
            transforms.RandomRotation(15),
            transforms.ColorJitter(brightness=0.2, contrast=0.2, saturation=0.15),
            transforms.ToTensor(),
            transforms.Normalize(
                mean=[0.485, 0.456, 0.406],
                std=[0.229, 0.224, 0.225],
            ),
        ])
    else:
        return transforms.Compose([
            transforms.Resize((img_size, img_size)),
            transforms.ToTensor(),
            transforms.Normalize(
                mean=[0.485, 0.456, 0.406],
                std=[0.229, 0.224, 0.225],
            ),
        ])


class WoundImageFolder:
    """Dataset de imagens de feridas organizado em pastas por classe."""

    def __init__(self, root_dir: str, transform=None, class_names: Optional[List[str]] = None):
        from PIL import Image

        self.root = Path(root_dir)
        self.transform = transform
        self.samples: List[Tuple[str, int]] = []
        self.class_names: List[str] = []

        if class_names:
            self.class_names = class_names
        else:
            self.class_names = sorted([
                d.name for d in self.root.iterdir()
                if d.is_dir() and not d.name.startswith(".")
            ])

        self.class_to_idx = {name: i for i, name in enumerate(self.class_names)}
        self._Image = Image

        # Coleta amostras
        valid_exts = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".webp"}
        for cls_name in self.class_names:
            cls_dir = self.root / cls_name
            if not cls_dir.exists():
                continue
            cls_idx = self.class_to_idx[cls_name]
            for img_path in cls_dir.iterdir():
                if img_path.suffix.lower() in valid_exts:
                    self.samples.append((str(img_path), cls_idx))

        print(f"[Dataset] {len(self.samples)} imagens, {len(self.class_names)} classes")
        for name in self.class_names:
            count = sum(1 for _, c in self.samples if c == self.class_to_idx[name])
            print(f"  {name}: {count} imagens")

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx):
        path, label = self.samples[idx]
        img = self._Image.open(path).convert("RGB")
        if self.transform:
            img = self.transform(img)
        return img, label


# ---------------------------------------------------------------------------
# DermaIntel Fine-Tuning
# ---------------------------------------------------------------------------

def finetune_dermaintel(cfg: FinetuneConfig):
    """Fine-tuning do DermaIntel ViT para dataset local."""
    import torch
    import torch.nn as nn
    from torch.utils.data import DataLoader, random_split
    from transformers import ViTForImageClassification, ViTImageProcessor

    print("=" * 60)
    print("  REDISUS - Fine-Tuning DermaIntel ViT")
    print("=" * 60)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Device: {device}")

    # Carrega modelo pre-treinado
    model_id = "PayamFard123/dermaintel-wound-classifier"
    print(f"Carregando modelo base: {model_id}")
    model = ViTForImageClassification.from_pretrained(model_id)

    # Numero de classes do dataset
    train_transform = build_transforms(cfg.img_size, cfg.augment, is_train=True)
    val_transform = build_transforms(cfg.img_size, cfg.augment, is_train=False)

    full_dataset = WoundImageFolder(cfg.data_dir, transform=None)
    num_classes = len(full_dataset.class_names)

    # Ajusta head do classificador se numero de classes diferir
    if num_classes != model.config.num_labels:
        print(f"Ajustando classifier head: {model.config.num_labels} -> {num_classes} classes")
        model.classifier = nn.Linear(model.config.hidden_size, num_classes)
        model.config.num_labels = num_classes

    model.to(device)

    # Split treino/validacao
    val_size = int(len(full_dataset) * cfg.val_split)
    train_size = len(full_dataset) - val_size
    train_ds, val_ds = random_split(full_dataset, [train_size, val_size])

    # Aplica transforms corretos
    train_ds.dataset = WoundImageFolder(cfg.data_dir, transform=train_transform,
                                         class_names=full_dataset.class_names)
    val_ds_full = WoundImageFolder(cfg.data_dir, transform=val_transform,
                                    class_names=full_dataset.class_names)

    train_loader = DataLoader(train_ds, batch_size=cfg.batch_size,
                               shuffle=True, num_workers=NUM_WORKERS)
    val_loader = DataLoader(val_ds_full, batch_size=cfg.batch_size,
                             shuffle=False, num_workers=NUM_WORKERS)

    # Class weights para balanceamento
    labels = [label for _, label in full_dataset.samples]
    from sklearn.utils.class_weight import compute_class_weight
    class_weights = compute_class_weight("balanced", classes=np.unique(labels), y=labels)
    class_weights_tensor = torch.tensor(class_weights, dtype=torch.float32).to(device)

    # Loss e optimizer
    criterion = nn.CrossEntropyLoss(
        weight=class_weights_tensor,
        label_smoothing=cfg.label_smoothing,
    )
    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=cfg.learning_rate,
        weight_decay=cfg.weight_decay,
    )
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
        optimizer, T_max=cfg.epochs,
    )

    # --- Fase 1: Feature Extraction (backbone congelado) ---
    print(f"\nFase 1: Feature Extraction ({cfg.freeze_backbone_epochs} epochs)")
    for param in model.vit.parameters():
        param.requires_grad = False

    best_val_acc = 0.0
    patience_counter = 0
    history = {"train_loss": [], "val_loss": [], "val_acc": []}

    output_dir = Path(cfg.output_dir) / "dermaintel_finetuned"
    output_dir.mkdir(parents=True, exist_ok=True)

    for epoch in range(cfg.epochs):
        # Descongela backbone apos fase 1
        if epoch == cfg.freeze_backbone_epochs:
            print(f"\nFase 2: Fine-Tuning (descongelando ultimas {cfg.unfreeze_layers} camadas)")
            layers = list(model.vit.encoder.layer)
            for layer in layers[-cfg.unfreeze_layers:]:
                for param in layer.parameters():
                    param.requires_grad = True

        # Train
        model.train()
        running_loss = 0.0
        correct = 0
        total = 0

        for batch_idx, (images, labels_batch) in enumerate(train_loader):
            images, labels_batch = images.to(device), labels_batch.to(device)

            optimizer.zero_grad()
            outputs = model(images).logits
            loss = criterion(outputs, labels_batch)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
            optimizer.step()

            running_loss += loss.item()
            _, predicted = outputs.max(1)
            total += labels_batch.size(0)
            correct += predicted.eq(labels_batch).sum().item()

        train_loss = running_loss / max(len(train_loader), 1)
        train_acc = correct / max(total, 1)

        # Validation
        model.eval()
        val_loss = 0.0
        val_correct = 0
        val_total = 0

        with torch.no_grad():
            for images, labels_batch in val_loader:
                images, labels_batch = images.to(device), labels_batch.to(device)
                outputs = model(images).logits
                loss = criterion(outputs, labels_batch)

                val_loss += loss.item()
                _, predicted = outputs.max(1)
                val_total += labels_batch.size(0)
                val_correct += predicted.eq(labels_batch).sum().item()

        val_loss = val_loss / max(len(val_loader), 1)
        val_acc = val_correct / max(val_total, 1)

        scheduler.step()

        history["train_loss"].append(train_loss)
        history["val_loss"].append(val_loss)
        history["val_acc"].append(val_acc)

        phase = "FE" if epoch < cfg.freeze_backbone_epochs else "FT"
        print(
            f"[{phase}] Epoch {epoch+1}/{cfg.epochs} "
            f"| Train Loss: {train_loss:.4f} Acc: {train_acc:.1%} "
            f"| Val Loss: {val_loss:.4f} Acc: {val_acc:.1%} "
            f"| LR: {scheduler.get_last_lr()[0]:.2e}"
        )

        # Early stopping + checkpoint
        if val_acc > best_val_acc + cfg.min_delta:
            best_val_acc = val_acc
            patience_counter = 0
            # Salva melhor modelo
            model.save_pretrained(str(output_dir))
            print(f"  -> Melhor modelo salvo (val_acc={val_acc:.1%})")
        else:
            patience_counter += 1
            if patience_counter >= cfg.patience:
                print(f"  -> Early stopping (patience={cfg.patience})")
                break

    # Salva metadata
    metadata = {
        "model_base": "PayamFard123/dermaintel-wound-classifier",
        "finetuned_on": str(cfg.data_dir),
        "num_classes": num_classes,
        "class_names": full_dataset.class_names,
        "best_val_acc": best_val_acc,
        "epochs_trained": len(history["train_loss"]),
        "config": {
            "learning_rate": cfg.learning_rate,
            "batch_size": cfg.batch_size,
            "img_size": cfg.img_size,
            "freeze_backbone_epochs": cfg.freeze_backbone_epochs,
            "unfreeze_layers": cfg.unfreeze_layers,
            "label_smoothing": cfg.label_smoothing,
        },
        "timestamp": datetime.now().isoformat(),
    }

    with open(output_dir / "training_metadata.json", "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)

    print(f"\nFine-tuning concluido! Melhor val_acc: {best_val_acc:.1%}")
    print(f"Modelo salvo em: {output_dir}")

    return history


# ---------------------------------------------------------------------------
# BiomedCLIP Fine-Tuning (Adapter/Linear Probe)
# ---------------------------------------------------------------------------

def finetune_biomedclip(cfg: FinetuneConfig):
    """
    Fine-tuning do BiomedCLIP para classificacao de feridas.

    Abordagem: Linear Probe + Adapter (nao altera o encoder visual/textual).
    Treina apenas uma camada de classificacao sobre os embeddings CLIP.
    """
    import torch
    import torch.nn as nn
    from torch.utils.data import DataLoader, random_split

    print("=" * 60)
    print("  REDISUS - Fine-Tuning BiomedCLIP (Linear Probe)")
    print("=" * 60)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Device: {device}")

    # Carrega BiomedCLIP
    import open_clip

    model_clip, _, preprocess = open_clip.create_model_and_transforms(
        "hf-hub:microsoft/BiomedCLIP-PubMedBERT_256-vit_base_patch16_224",
        device=device,
    )
    model_clip.eval()
    for param in model_clip.parameters():
        param.requires_grad = False

    print("BiomedCLIP carregado (encoder congelado)")

    # Dataset
    full_dataset = WoundImageFolder(cfg.data_dir, transform=preprocess)
    num_classes = len(full_dataset.class_names)

    val_size = int(len(full_dataset) * cfg.val_split)
    train_size = len(full_dataset) - val_size
    train_ds, val_ds = random_split(
        full_dataset, [train_size, val_size],
        generator=torch.Generator().manual_seed(SEED),
    )

    train_loader = DataLoader(train_ds, batch_size=cfg.batch_size,
                               shuffle=True, num_workers=NUM_WORKERS)
    val_loader = DataLoader(val_ds, batch_size=cfg.batch_size,
                             shuffle=False, num_workers=NUM_WORKERS)

    # Classifier head sobre embeddings CLIP
    embed_dim = model_clip.visual.output_dim
    classifier = nn.Sequential(
        nn.LayerNorm(embed_dim),
        nn.Dropout(0.3),
        nn.Linear(embed_dim, 256),
        nn.GELU(),
        nn.Dropout(0.2),
        nn.Linear(256, num_classes),
    ).to(device)

    # Class weights
    labels = [label for _, label in full_dataset.samples]
    from sklearn.utils.class_weight import compute_class_weight
    class_weights = compute_class_weight("balanced", classes=np.unique(labels), y=labels)
    class_weights_tensor = torch.tensor(class_weights, dtype=torch.float32).to(device)

    criterion = nn.CrossEntropyLoss(weight=class_weights_tensor, label_smoothing=0.1)
    optimizer = torch.optim.AdamW(classifier.parameters(), lr=1e-3, weight_decay=0.01)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=cfg.epochs)

    output_dir = Path(cfg.output_dir) / "biomedclip_probe"
    output_dir.mkdir(parents=True, exist_ok=True)

    best_val_acc = 0.0
    patience_counter = 0

    for epoch in range(cfg.epochs):
        # Extract features -> train classifier
        classifier.train()
        running_loss = 0.0
        correct = 0
        total = 0

        for images, labels_batch in train_loader:
            images, labels_batch = images.to(device), labels_batch.to(device)

            with torch.no_grad():
                features = model_clip.encode_image(images)
                features = features / features.norm(dim=-1, keepdim=True)

            outputs = classifier(features)
            loss = criterion(outputs, labels_batch)

            optimizer.zero_grad()
            loss.backward()
            optimizer.step()

            running_loss += loss.item()
            _, predicted = outputs.max(1)
            total += labels_batch.size(0)
            correct += predicted.eq(labels_batch).sum().item()

        train_loss = running_loss / max(len(train_loader), 1)
        train_acc = correct / max(total, 1)

        # Validation
        classifier.eval()
        val_loss = 0.0
        val_correct = 0
        val_total = 0

        with torch.no_grad():
            for images, labels_batch in val_loader:
                images, labels_batch = images.to(device), labels_batch.to(device)
                features = model_clip.encode_image(images)
                features = features / features.norm(dim=-1, keepdim=True)
                outputs = classifier(features)
                loss = criterion(outputs, labels_batch)

                val_loss += loss.item()
                _, predicted = outputs.max(1)
                val_total += labels_batch.size(0)
                val_correct += predicted.eq(labels_batch).sum().item()

        val_loss = val_loss / max(len(val_loader), 1)
        val_acc = val_correct / max(val_total, 1)

        scheduler.step()

        print(
            f"Epoch {epoch+1}/{cfg.epochs} "
            f"| Train Loss: {train_loss:.4f} Acc: {train_acc:.1%} "
            f"| Val Loss: {val_loss:.4f} Acc: {val_acc:.1%}"
        )

        if val_acc > best_val_acc + cfg.min_delta:
            best_val_acc = val_acc
            patience_counter = 0
            torch.save(classifier.state_dict(), output_dir / "biomedclip_classifier.pt")
            print(f"  -> Melhor modelo salvo (val_acc={val_acc:.1%})")
        else:
            patience_counter += 1
            if patience_counter >= cfg.patience:
                print(f"  -> Early stopping (patience={cfg.patience})")
                break

    # Metadata
    metadata = {
        "model_base": "microsoft/BiomedCLIP-PubMedBERT_256-vit_base_patch16_224",
        "approach": "linear_probe",
        "embed_dim": embed_dim,
        "num_classes": num_classes,
        "class_names": full_dataset.class_names,
        "best_val_acc": best_val_acc,
        "timestamp": datetime.now().isoformat(),
    }

    with open(output_dir / "training_metadata.json", "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)

    print(f"\nLinear probe concluido! Melhor val_acc: {best_val_acc:.1%}")
    print(f"Modelo salvo em: {output_dir}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="REDISUS - Fine-tuning dos modelos ensemble"
    )
    parser.add_argument(
        "--model",
        type=str,
        required=True,
        choices=["dermaintel", "biomedclip"],
        help="Modelo para fine-tuning",
    )
    parser.add_argument("--data_dir", type=str, required=True, help="Diretorio com imagens")
    parser.add_argument("--output_dir", type=str, default="models/finetuned")
    parser.add_argument("--epochs", type=int, default=30)
    parser.add_argument("--batch_size", type=int, default=16)
    parser.add_argument("--lr", type=float, default=2e-5)
    parser.add_argument("--img_size", type=int, default=224)
    parser.add_argument("--freeze_epochs", type=int, default=5)
    parser.add_argument("--patience", type=int, default=7)

    args = parser.parse_args()

    cfg = FinetuneConfig(
        data_dir=args.data_dir,
        output_dir=args.output_dir,
        epochs=args.epochs,
        batch_size=args.batch_size,
        learning_rate=args.lr,
        img_size=args.img_size,
        freeze_backbone_epochs=args.freeze_epochs,
        patience=args.patience,
    )

    if args.model == "dermaintel":
        finetune_dermaintel(cfg)
    elif args.model == "biomedclip":
        finetune_biomedclip(cfg)


if __name__ == "__main__":
    main()
