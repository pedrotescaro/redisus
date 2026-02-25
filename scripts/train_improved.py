#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
===============================================================================
REDISUS — TREINAMENTO MELHORADO DO CLASSIFICADOR DE FERIDAS v2.0 (PyTorch)
===============================================================================

Melhorias em relação ao treinamento v1.0 (accuracy ~44%):

1. CONSOLIDAÇÃO DE CLASSES: 24 → ~10 categorias clínicas significativas
2. MODELO: EfficientNet-B3 via timm (PyTorch Image Models)
3. TREINAMENTO EM 3 FASES: Feature Extraction → Fine-tune parcial → Fine-tune profundo
4. Label Smoothing + Class Weights + Cosine Annealing LR
5. Augmentação geométrica agressiva, cor conservativa (médica)
6. Test Time Augmentation (TTA) na avaliação

Uso:
    python scripts/train_improved.py
    python scripts/train_improved.py --epochs 40 --batch-size 16
    python scripts/train_improved.py --no-fine-tune

Requisitos (já instalados no venv):
    torch, torchvision, timm, numpy, opencv-python
===============================================================================
"""

import os
import sys
import json
import shutil
import argparse
import time
from pathlib import Path
from datetime import datetime
from typing import Tuple, Dict, List, Optional
from collections import Counter

import cv2
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader, WeightedRandomSampler
from torchvision import transforms
import timm

# Reprodutibilidade
SEED = 42
torch.manual_seed(SEED)
np.random.seed(SEED)
if torch.cuda.is_available():
    torch.cuda.manual_seed_all(SEED)

# Forçar flush + logging direto a arquivo (Tee-Object do PowerShell buffera)
import functools
import io

_LOG_FILE_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "train_v3_log.txt")
_log_file_handle = open(_LOG_FILE_PATH, "w", encoding="utf-8", buffering=1)  # line-buffered

_builtin_print = print
def print(*args, **kwargs):
    """Print to both stdout and log file with immediate flush."""
    kwargs['flush'] = True
    _builtin_print(*args, **kwargs)
    # Also write to log file
    try:
        msg = " ".join(str(a) for a in args)
        _log_file_handle.write(msg + "\n")
        _log_file_handle.flush()
    except Exception:
        pass

# ============================================================================
# MAPEAMENTO DE CONSOLIDAÇÃO DE CLASSES
# ============================================================================

CLASS_CONSOLIDATION = {
    "abdominal_wounds": "abdominal_wounds",
    "abdominal_wounds_examples_of_wound_dehiscence": "abdominal_wounds",
    "burn_and_scalds": "burns",
    "burns": "burns",
    "diabetic_foot_ulcers": "diabetic_ulcers",
    "epidermolysis_bullosa": "epidermolysis_bullosa",
    "extravasation_injuries": "miscellaneous",
    "haemangiomas": "miscellaneous",
    "malignant_wounds": "malignant_wounds",
    "meningitis_wounds": "miscellaneous",
    "miscellaneous_wounds": "miscellaneous",
    "necrotic_toes": "necrotic_wounds",
    "toes_infected_and_necrotic": "necrotic_wounds",
    "orthopaedic_wounds": "surgical_wounds",
    "pilonidal_sinus": "pilonidal_sinus",
    "pilonidal_sinus_wounds": "pilonidal_sinus",
    "pressure_ulcers_1": "pressure_ulcers",
    "pressure_ulcers_2": "pressure_ulcers",
    "pressure_ulcers_set_1_of_2": "pressure_ulcers",
    "pressure_ulcers_set_2_of_2": "pressure_ulcers",
    "venous_and_arterial_ulcers_set_2": "venous_arterial_ulcers",
    "venous_arterial_ulcers_1": "venous_arterial_ulcers",
    "venous_arterial_ulcers_2": "venous_arterial_ulcers",
    "venous_ulcers_and_arterial_ulcers_set_1": "venous_arterial_ulcers",
}

CLASS_DISPLAY_NAMES = {
    "abdominal_wounds": "Feridas Abdominais / Deiscência",
    "burns": "Queimaduras e Escaldaduras",
    "diabetic_ulcers": "Úlceras Diabéticas (Pé Diabético)",
    "epidermolysis_bullosa": "Epidermólise Bolhosa",
    "malignant_wounds": "Feridas Malignas",
    "miscellaneous": "Feridas Diversas",
    "necrotic_wounds": "Feridas Necróticas e Infecções",
    "pilonidal_sinus": "Cisto/Fístula Pilonidal",
    "pressure_ulcers": "Lesões por Pressão",
    "surgical_wounds": "Feridas Cirúrgicas / Ortopédicas",
    "venous_arterial_ulcers": "Úlceras Venosas e Arteriais",
}


# ============================================================================
# CONFIGURAÇÕES
# ============================================================================

class Config:
    DATASET_DIR = "dataset/medetec"
    CONSOLIDATED_DIR = "dataset/medetec_consolidated"
    OUTPUT_DIR = "models/wound_classifier_v2"

    IMG_SIZE = 224                            # 224 → standard ImageNet (mais rápido, menos overfitting)
    BATCH_SIZE = 16
    NUM_WORKERS = 0  # Windows compat
    MODEL_NAME = "efficientnet_b0"            # Melhor accuracy/params para dataset pequeno

    PHASE1_EPOCHS = 40                       # Mais épocas fase 1 (head precisa convergir bem)
    PHASE2_EPOCHS = 20
    PHASE3_EPOCHS = 15

    PHASE1_LR = 1e-3                         # LR mais alto para head convergir rápido
    PHASE2_LR = 1e-4
    PHASE3_LR = 2e-5

    DROPOUT = 0.30                           # Regularização moderada
    LABEL_SMOOTHING = 0.08
    WEIGHT_DECAY = 1e-4                       # Weight decay padrão
    MIXUP_ALPHA = 0.0                         # Desabilitado (muito agressivo para dataset pequeno)
    CUTMIX_ALPHA = 0.0                        # Desabilitado
    MIXUP_PROB = 0.0                          # Desabilitado
    MAX_CLASS_WEIGHT = 3.0                    # Cap nos pesos de classe (evita viés para minoria)

    PATIENCE = 15                             # Mais paciência (notebooks mostram ganhos até epoch 29+)
    PIN_MEMORY = False                        # False para CPU (evita warning)
    CONFIDENCE_THRESHOLD = 0.95               # Threshold de confiança alta (do notebook embeddings)


# ============================================================================
# DATASET
# ============================================================================

def consolidate_dataset(cfg: Config) -> str:
    """Consolida 24 classes → ~10 categorias clínicas."""
    src = Path(cfg.DATASET_DIR)
    dst = Path(cfg.CONSOLIDATED_DIR)

    if dst.exists():
        existing = [d for d in dst.iterdir() if d.is_dir()]
        if len(existing) >= 8:
            total_imgs = sum(1 for d in existing for f in d.iterdir() if f.suffix.lower() in {'.jpg', '.jpeg', '.png'})
            if total_imgs > 50:
                print(f"[OK] Dataset consolidado existente: {len(existing)} classes, {total_imgs} imgs")
                return str(dst)
        # Remove com retry para Windows
        import gc
        gc.collect()
        try:
            shutil.rmtree(dst, ignore_errors=True)
        except Exception:
            pass
        # Se ainda existe, trabalhar incrementalmente
        if not dst.exists():
            dst.mkdir(parents=True, exist_ok=True)

    print("\n" + "=" * 60)
    print("CONSOLIDANDO DATASET: 24 -> ~10 CLASSES")
    print("=" * 60)

    dst.mkdir(parents=True, exist_ok=True)
    stats = Counter()

    for orig_class, new_class in CLASS_CONSOLIDATION.items():
        orig_dir = src / orig_class
        if not orig_dir.exists():
            continue
        new_dir = dst / new_class
        new_dir.mkdir(exist_ok=True)

        images = list(orig_dir.glob("*.jpg")) + list(orig_dir.glob("*.jpeg")) + list(orig_dir.glob("*.png"))
        for img_path in images:
            new_name = f"{orig_class}_{img_path.name}"
            target = new_dir / new_name
            if not target.exists():
                shutil.copy2(img_path, target)
                stats[new_class] += 1

    total = sum(stats.values())
    print(f"\n[OK] {total} imagens em {len(stats)} classes:")
    for cls, count in sorted(stats.items(), key=lambda x: -x[1]):
        print(f"  {cls:30s} -> {count:4d} imgs")

    return str(dst)


class WoundDataset(Dataset):
    """Dataset PyTorch para classificacao de feridas."""

    VALID_EXT = {".jpg", ".jpeg", ".png", ".bmp", ".tif"}

    def __init__(self, root_dir: str, transform=None, split="train", val_ratio=0.2):
        self.root = Path(root_dir)
        self.transform = transform

        # Descobre classes
        self.classes = sorted([d.name for d in self.root.iterdir() if d.is_dir()])
        self.class_to_idx = {c: i for i, c in enumerate(self.classes)}

        # Coleta imagens
        all_samples = []
        for cls_name in self.classes:
            cls_dir = self.root / cls_name
            cls_idx = self.class_to_idx[cls_name]
            for img in cls_dir.iterdir():
                if img.suffix.lower() in self.VALID_EXT:
                    all_samples.append((str(img), cls_idx))

        # Split deterministico
        rng = np.random.RandomState(SEED)
        indices = rng.permutation(len(all_samples))
        split_idx = int(len(all_samples) * (1 - val_ratio))

        if split == "train":
            selected = indices[:split_idx]
        else:
            selected = indices[split_idx:]

        self.samples = [all_samples[i] for i in selected]
        self.targets = [s[1] for s in self.samples]

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx):
        path, label = self.samples[idx]
        img = cv2.imread(path)
        if img is None:
            img = np.zeros((300, 300, 3), dtype=np.uint8)
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

        if self.transform:
            img = self.transform(img)
        else:
            img = transforms.ToTensor()(img)

        return img, label


def get_transforms(img_size: int, is_train: bool):
    """Augmentacoes: geometricas agressivas, cor conservativa (otimizadas v3)."""
    if is_train:
        return transforms.Compose([
            transforms.ToPILImage(),
            transforms.Resize((img_size + 40, img_size + 40)),
            transforms.RandomCrop(img_size),
            transforms.RandomHorizontalFlip(p=0.5),
            transforms.RandomVerticalFlip(p=0.3),
            transforms.RandomRotation(25),
            transforms.RandomAffine(
                degrees=0, translate=(0.10, 0.10),
                scale=(0.85, 1.15), shear=8
            ),
            transforms.RandomPerspective(distortion_scale=0.15, p=0.3),
            # Cor conservativa mas mais variada (simula condições de iluminação)
            transforms.ColorJitter(
                brightness=0.15, contrast=0.15,
                saturation=0.10, hue=0.0  # NUNCA alterar hue em feridas!
            ),
            transforms.RandomGrayscale(p=0.03),
            transforms.GaussianBlur(kernel_size=3, sigma=(0.1, 1.5)),
            transforms.RandomAutocontrast(p=0.1),
            transforms.RandomEqualize(p=0.05),
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485, 0.456, 0.406],
                                 std=[0.229, 0.224, 0.225]),
            transforms.RandomErasing(p=0.15, scale=(0.02, 0.12)),
        ])
    else:
        return transforms.Compose([
            transforms.ToPILImage(),
            transforms.Resize((img_size, img_size)),
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485, 0.456, 0.406],
                                 std=[0.229, 0.224, 0.225]),
        ])


def create_dataloaders(cfg: Config, dataset_path: str):
    """Cria DataLoaders com class-balanced sampling."""
    train_tf = get_transforms(cfg.IMG_SIZE, is_train=True)
    val_tf = get_transforms(cfg.IMG_SIZE, is_train=False)

    train_ds = WoundDataset(dataset_path, transform=train_tf, split="train")
    val_ds = WoundDataset(dataset_path, transform=val_tf, split="val")

    # Class-balanced sampling (oversampling de classes raras)
    class_counts = Counter(train_ds.targets)
    num_classes = len(train_ds.classes)
    total = len(train_ds.targets)

    class_weights = {c: total / (num_classes * count) for c, count in class_counts.items()}
    sample_weights = [class_weights[t] for t in train_ds.targets]
    sampler = WeightedRandomSampler(sample_weights, num_samples=len(sample_weights), replacement=True)

    train_loader = DataLoader(
        train_ds, batch_size=cfg.BATCH_SIZE,
        sampler=sampler, num_workers=cfg.NUM_WORKERS,
        pin_memory=cfg.PIN_MEMORY, drop_last=True
    )
    val_loader = DataLoader(
        val_ds, batch_size=cfg.BATCH_SIZE,
        shuffle=False, num_workers=cfg.NUM_WORKERS,
        pin_memory=cfg.PIN_MEMORY
    )

    print(f"\n[OK] Dataset: {len(train_ds)} treino, {len(val_ds)} validacao")
    print(f"  Classes ({num_classes}):")
    for i, name in enumerate(train_ds.classes):
        count = class_counts.get(i, 0)
        display = CLASS_DISPLAY_NAMES.get(name, name)
        weight = class_weights.get(i, 1.0)
        print(f"  [{i}] {name:30s} {count:4d} imgs (w={weight:.2f}) -- {display}")

    return train_loader, val_loader, train_ds.classes, class_weights


# ============================================================================
# MODELO
# ============================================================================

class WoundClassifierV2(nn.Module):
    """timm backbone + cabeca de classificacao customizada."""

    def __init__(self, num_classes: int, dropout: float = 0.30, model_name: str = "efficientnet_b0"):
        super().__init__()
        self.model_name = model_name

        # Backbone pre-treinado via timm
        self.backbone = timm.create_model(
            model_name,
            pretrained=True,
            num_classes=0,  # Remove cabeca original
        )
        # Determine actual feature dim dynamically (timm num_features can be wrong)
        with torch.no_grad():
            dummy = torch.randn(1, 3, 224, 224)
            feat_dim = self.backbone(dummy).shape[-1]
        print(f"  Backbone feature dim: {feat_dim}")

        # Cabeca de classificacao MLP robusta (inspirada no SimpleMLPClassifier
        # do notebook wounds_classifier_embeddings.ipynb)
        # 3 camadas com BatchNorm + Dropout progressivo para melhor regularização
        hidden_size = 256
        self.head = nn.Sequential(
            nn.BatchNorm1d(feat_dim),
            nn.Dropout(dropout),
            nn.Linear(feat_dim, hidden_size),
            nn.BatchNorm1d(hidden_size),
            nn.ReLU(inplace=True),
            nn.Dropout(dropout * 0.6),
            nn.Linear(hidden_size, hidden_size),
            nn.BatchNorm1d(hidden_size),
            nn.ReLU(inplace=True),
            nn.Dropout(dropout * 0.3),  # Menos dropout nas camadas finais
            nn.Linear(hidden_size, num_classes),
        )

    def forward(self, x):
        features = self.backbone(x)
        return self.head(features)

    def freeze_backbone(self):
        for param in self.backbone.parameters():
            param.requires_grad = False

    def unfreeze_backbone(self, from_layer: int = 0):
        """Descongela backbone a partir de uma camada."""
        all_params = list(self.backbone.named_parameters())
        total = len(all_params)
        for i, (name, param) in enumerate(all_params):
            param.requires_grad = i >= from_layer
        trainable = sum(1 for _, p in all_params if p.requires_grad)
        print(f"  Backbone: {trainable}/{total} parametros treinaveis")


# ============================================================================
# MIXUP / CUTMIX (regularização forte para dataset pequeno)
# ============================================================================

def mixup_data(x, y, alpha=0.3):
    """Mixup: combina pares de imagens linearmente."""
    if alpha <= 0:
        return x, y, y, 1.0
    lam = np.random.beta(alpha, alpha)
    lam = max(lam, 1.0 - lam)  # garante lam >= 0.5
    batch_size = x.size(0)
    index = torch.randperm(batch_size, device=x.device)
    mixed_x = lam * x + (1.0 - lam) * x[index]
    return mixed_x, y, y[index], lam


def cutmix_data(x, y, alpha=0.3):
    """CutMix: recorta um patch de outra imagem."""
    if alpha <= 0:
        return x, y, y, 1.0
    lam = np.random.beta(alpha, alpha)
    batch_size = x.size(0)
    index = torch.randperm(batch_size, device=x.device)

    _, _, H, W = x.shape
    cut_ratio = np.sqrt(1.0 - lam)
    cut_w = int(W * cut_ratio)
    cut_h = int(H * cut_ratio)

    cx = np.random.randint(W)
    cy = np.random.randint(H)
    x1 = np.clip(cx - cut_w // 2, 0, W)
    y1 = np.clip(cy - cut_h // 2, 0, H)
    x2 = np.clip(cx + cut_w // 2, 0, W)
    y2 = np.clip(cy + cut_h // 2, 0, H)

    mixed_x = x.clone()
    mixed_x[:, :, y1:y2, x1:x2] = x[index, :, y1:y2, x1:x2]

    # adjust lambda to actual area
    lam = 1.0 - (x2 - x1) * (y2 - y1) / (W * H)
    return mixed_x, y, y[index], lam


def mixup_criterion(criterion, pred, y_a, y_b, lam):
    """Loss para dados mixados."""
    return lam * criterion(pred, y_a) + (1.0 - lam) * criterion(pred, y_b)


# ============================================================================
# TREINAMENTO
# ============================================================================

def train_epoch(model, loader, criterion, optimizer, device, scaler=None,
                mixup_alpha=0.0, cutmix_alpha=0.0, mix_prob=0.5):
    model.train()
    running_loss = 0.0
    correct = 0
    total = 0

    for images, labels in loader:
        images, labels = images.to(device), labels.to(device)
        optimizer.zero_grad()

        # Aplicar Mixup ou CutMix com probabilidade mix_prob
        use_mix = np.random.random() < mix_prob and (mixup_alpha > 0 or cutmix_alpha > 0)
        if use_mix:
            if np.random.random() < 0.5 and mixup_alpha > 0:
                images, targets_a, targets_b, lam = mixup_data(images, labels, mixup_alpha)
            else:
                images, targets_a, targets_b, lam = cutmix_data(images, labels, cutmix_alpha)
        else:
            targets_a, targets_b, lam = labels, labels, 1.0

        if scaler:
            with torch.amp.autocast('cuda'):
                outputs = model(images)
                loss = mixup_criterion(criterion, outputs, targets_a, targets_b, lam)
            scaler.scale(loss).backward()
            scaler.unscale_(optimizer)
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
            scaler.step(optimizer)
            scaler.update()
        else:
            outputs = model(images)
            loss = mixup_criterion(criterion, outputs, targets_a, targets_b, lam)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
            optimizer.step()

        running_loss += loss.item() * images.size(0)
        _, predicted = outputs.max(1)
        total += labels.size(0)
        correct += predicted.eq(labels).sum().item()

    return running_loss / total, correct / total


@torch.no_grad()
def validate(model, loader, criterion, device):
    model.eval()
    running_loss = 0.0
    correct = 0
    total = 0
    all_preds = []
    all_labels = []
    all_probs = []

    for images, labels in loader:
        images, labels = images.to(device), labels.to(device)
        outputs = model(images)
        loss = criterion(outputs, labels)

        running_loss += loss.item() * images.size(0)
        probs = torch.softmax(outputs, dim=1)
        _, predicted = outputs.max(1)
        total += labels.size(0)
        correct += predicted.eq(labels).sum().item()

        all_preds.extend(predicted.cpu().numpy())
        all_labels.extend(labels.cpu().numpy())
        all_probs.extend(probs.cpu().numpy())

    return (
        running_loss / total,
        correct / total,
        np.array(all_preds),
        np.array(all_labels),
        np.array(all_probs),
    )


def train_phase(
    model, train_loader, val_loader, criterion, optimizer, scheduler,
    device, scaler, epochs, phase_name, output_dir, patience=10,
    mixup_alpha=0.0, cutmix_alpha=0.0, mix_prob=0.0
):
    """Treina uma fase com early stopping e Mixup/CutMix."""
    print(f"\n{'='*60}")
    print(f"  {phase_name}")
    print(f"  Epocas: {epochs}, Patience: {patience}")
    if mix_prob > 0:
        print(f"  Mixup: alpha={mixup_alpha}, CutMix: alpha={cutmix_alpha}, prob={mix_prob}")
    print(f"{'='*60}")

    best_val_acc = 0.0
    best_val_loss = float("inf")
    patience_counter = 0
    best_state = None

    for epoch in range(1, epochs + 1):
        t0 = time.time()
        train_loss, train_acc = train_epoch(
            model, train_loader, criterion, optimizer, device, scaler,
            mixup_alpha=mixup_alpha, cutmix_alpha=cutmix_alpha, mix_prob=mix_prob,
        )
        val_loss, val_acc, _, _, _ = validate(model, val_loader, criterion, device)

        if scheduler:
            if isinstance(scheduler, optim.lr_scheduler.ReduceLROnPlateau):
                scheduler.step(val_loss)
            else:
                scheduler.step()

        elapsed = time.time() - t0
        lr = optimizer.param_groups[0]["lr"]

        print(
            f"  Epoch {epoch:3d}/{epochs}  "
            f"train_loss={train_loss:.4f}  train_acc={train_acc:.3f}  "
            f"val_loss={val_loss:.4f}  val_acc={val_acc:.3f}  "
            f"lr={lr:.2e}  {elapsed:.1f}s"
        )

        # Checkpoint do melhor modelo
        if val_acc > best_val_acc or (val_acc == best_val_acc and val_loss < best_val_loss):
            best_val_acc = val_acc
            best_val_loss = val_loss
            patience_counter = 0
            best_state = {k: v.cpu().clone() for k, v in model.state_dict().items()}
            safe_name = phase_name.lower().replace(' ', '_').replace('(', '').replace(')', '').replace('%', 'pct').replace(':', '')
            ckpt_path = os.path.join(output_dir, f"best_{safe_name}.pt")
            torch.save(best_state, ckpt_path)
        else:
            patience_counter += 1

        if patience_counter >= patience:
            print(f"  -> Early stopping apos {epoch} epocas")
            break

    # Restaura melhor modelo
    if best_state:
        model.load_state_dict(best_state)

    print(f"  [OK] {phase_name} -- Best val_acc: {best_val_acc:.4f}, val_loss: {best_val_loss:.4f}")
    return best_val_acc, best_val_loss


# ============================================================================
# AVALIACAO + TTA
# ============================================================================

@torch.no_grad()
def evaluate_with_tta(model, val_loader, device, class_names, confidence_threshold=0.95):
    """Avalia com Test Time Augmentation aprimorada (6 augmentações).
    
    Inclui análise de confiança baseada no notebook wounds_classifier_embeddings.ipynb:
    compara métricas gerais vs. métricas filtradas por threshold de confiança.
    """
    model.eval()
    all_probs = []
    all_labels = []

    for images, labels in val_loader:
        images = images.to(device)
        batch_preds = []

        # Original
        out = torch.softmax(model(images), dim=1)
        batch_preds.append(out)

        # Horizontal flip
        out = torch.softmax(model(torch.flip(images, [3])), dim=1)
        batch_preds.append(out)

        # Vertical flip
        out = torch.softmax(model(torch.flip(images, [2])), dim=1)
        batch_preds.append(out)

        # Both flips
        out = torch.softmax(model(torch.flip(images, [2, 3])), dim=1)
        batch_preds.append(out)

        # Brilho +5% (variação de iluminação)
        bright = torch.clamp(images * 1.05, 0, 1)
        out = torch.softmax(model(bright), dim=1)
        batch_preds.append(out)

        # Brilho -5%
        dark = torch.clamp(images * 0.95, 0, 1)
        out = torch.softmax(model(dark), dim=1)
        batch_preds.append(out)

        # Media TTA (6 augmentações)
        avg_pred = torch.stack(batch_preds).mean(dim=0)
        all_probs.extend(avg_pred.cpu().numpy())
        all_labels.extend(labels.numpy())

    all_probs = np.array(all_probs)
    all_labels = np.array(all_labels)
    all_preds = np.argmax(all_probs, axis=1)
    all_confs = np.max(all_probs, axis=1)

    # Accuracy
    acc = np.mean(all_preds == all_labels)

    # Top-3
    top3_correct = 0
    for i in range(len(all_labels)):
        top3 = np.argsort(all_probs[i])[-3:]
        if all_labels[i] in top3:
            top3_correct += 1
    top3_acc = top3_correct / len(all_labels)

    print(f"\n{'='*60}")
    print(f"  AVALIACAO FINAL (com TTA 6x)")
    print(f"{'='*60}")
    print(f"  Accuracy:     {acc:.2%}")
    print(f"  Top-3 Acc:    {top3_acc:.2%}")

    # Per-class
    print(f"\n  Por classe:")
    per_class = {}
    for i, name in enumerate(class_names):
        mask = all_labels == i
        if mask.sum() > 0:
            cls_acc = (all_preds[mask] == all_labels[mask]).mean()
            display = CLASS_DISPLAY_NAMES.get(name, name)
            print(f"    {name:30s} {cls_acc:6.2%} ({mask.sum()} amostras)")
            per_class[name] = {"accuracy": float(cls_acc), "samples": int(mask.sum())}

    # Top confusoes
    print(f"\n  Confusoes mais frequentes:")
    confusions = Counter()
    for t, p in zip(all_labels, all_preds):
        if t != p:
            confusions[(class_names[t], class_names[p])] += 1
    for (tc, pc), count in confusions.most_common(8):
        print(f"    {tc:25s} -> {pc:25s} ({count}x)")

    # ── Análise de confiança filtrada (do notebook embeddings) ──
    high_conf_mask = all_confs >= confidence_threshold
    n_high = high_conf_mask.sum()
    if n_high > 0:
        high_acc = np.mean(all_preds[high_conf_mask] == all_labels[high_conf_mask])
        coverage = n_high / len(all_labels)
        print(f"\n  {'─'*50}")
        print(f"  FILTRAGEM POR CONFIANÇA (threshold={confidence_threshold:.0%})")
        print(f"  {'─'*50}")
        print(f"  Amostras com alta confiança: {n_high}/{len(all_labels)} ({coverage:.1%})")
        print(f"  Accuracy (filtrado):         {high_acc:.2%} (vs. {acc:.2%} geral)")
        per_class["_high_confidence"] = {
            "threshold": confidence_threshold,
            "coverage": float(coverage),
            "accuracy_filtered": float(high_acc),
            "accuracy_all": float(acc),
        }
    else:
        print(f"\n  [WARN] Nenhuma predição com confiança >= {confidence_threshold:.0%}")

    # Entropia média (incerteza do modelo)
    eps = 1e-10
    entropies = -np.sum(all_probs * np.log(np.clip(all_probs, eps, 1.0)), axis=1)
    max_entropy = np.log(len(class_names))
    norm_entropies = entropies / max_entropy if max_entropy > 0 else entropies
    print(f"\n  Entropia média normalizada: {norm_entropies.mean():.4f} (0=confiante, 1=incerto)")
    print(f"  Confiança média:            {all_confs.mean():.4f}")

    return acc, top3_acc, per_class, all_probs, all_labels, all_preds


# ============================================================================
# SALVAR PARA PRODUCAO
# ============================================================================

def save_for_production(model, class_names, cfg, output_dir, metrics):
    """Salva modelo e metadados."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    # Modelo state_dict
    model_path = out / "wound_classifier_v2.pt"
    torch.save(model.state_dict(), str(model_path))
    print(f"[OK] Modelo state_dict: {model_path}")

    # Modelo completo (para facilitar carregamento)
    full_path = out / "wound_classifier_v2_full.pt"
    torch.save(model, str(full_path))
    print(f"[OK] Modelo completo: {full_path}")

    # TorchScript export
    try:
        model.eval()
        dummy = torch.randn(1, 3, cfg.IMG_SIZE, cfg.IMG_SIZE)
        if next(model.parameters()).is_cuda:
            dummy = dummy.cuda()
        scripted = torch.jit.trace(model, dummy)
        ts_path = out / "wound_classifier_v2_traced.pt"
        scripted.save(str(ts_path))
        print(f"[OK] TorchScript: {ts_path}")
    except Exception as e:
        print(f"[WARN] TorchScript export: {e}")

    # Metadados
    metadata = {
        "model_name": "WoundClassifier_v3_PyTorch",
        "version": "3.0.0",
        "framework": "PyTorch/timm",
        "base_model": cfg.MODEL_NAME,
        "input_shape": [cfg.IMG_SIZE, cfg.IMG_SIZE, 3],
        "class_names": class_names,
        "class_display_names": {n: CLASS_DISPLAY_NAMES.get(n, n) for n in class_names},
        "num_classes": len(class_names),
        "preprocessing": {
            "resize": [cfg.IMG_SIZE, cfg.IMG_SIZE],
            "normalize_mean": [0.485, 0.456, 0.406],
            "normalize_std": [0.229, 0.224, 0.225],
        },
        "consolidation_map": CLASS_CONSOLIDATION,
        "metrics": metrics,
        "created_at": datetime.now().isoformat(),
    }
    meta_path = out / "model_metadata_v2.json"
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)
    print(f"[OK] Metadados: {meta_path}")

    return str(model_path)


# ============================================================================
# MAIN
# ============================================================================

def main():
    parser = argparse.ArgumentParser(description="REDISUS -- Treino v2 PyTorch")
    parser.add_argument("--epochs", type=int, default=None)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--no-fine-tune", action="store_true")
    parser.add_argument("--skip-consolidation", action="store_true")
    args = parser.parse_args()

    print("""
    ================================================================
    |                                                              |
    |   REDISUS -- WOUND CLASSIFIER v3.1 (PyTorch)                |
    |   EfficientNet-B0 . 3 Fases . TTA . Regularizacao Leve      |
    |   24 classes -> ~10 categorias clinicas                      |
    |                                                              |
    ================================================================
    """)

    cfg = Config()
    if args.epochs:
        cfg.PHASE1_EPOCHS = args.epochs
    cfg.BATCH_SIZE = args.batch_size

    # Device
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Device: {device}")
    if device.type == "cuda":
        print(f"  GPU: {torch.cuda.get_device_name(0)}")
        print(f"  VRAM: {torch.cuda.get_device_properties(0).total_mem / 1e9:.1f} GB")

    # 1. Consolidar dataset
    if not args.skip_consolidation:
        dataset_path = consolidate_dataset(cfg)
    else:
        dataset_path = cfg.CONSOLIDATED_DIR

    # 2. DataLoaders
    train_loader, val_loader, class_names, class_weights_dict = create_dataloaders(cfg, dataset_path)
    num_classes = len(class_names)

    # 3. Loss com label smoothing + class weights
    weight_tensor = torch.ones(num_classes)
    for idx, w in class_weights_dict.items():
        weight_tensor[idx] = min(w, cfg.MAX_CLASS_WEIGHT)
    weight_tensor = weight_tensor.to(device)
    criterion = nn.CrossEntropyLoss(
        weight=weight_tensor,
        label_smoothing=cfg.LABEL_SMOOTHING,
    )

    # 4. Modelo
    print(f"\nConstruindo {cfg.MODEL_NAME} ({num_classes} classes)...")
    model = WoundClassifierV2(num_classes, dropout=cfg.DROPOUT, model_name=cfg.MODEL_NAME).to(device)
    total_params = sum(p.numel() for p in model.parameters())
    print(f"  Parametros totais: {total_params:,}")

    # AMP scaler (mixed precision)
    scaler = torch.amp.GradScaler('cuda') if device.type == "cuda" else None

    output_dir = cfg.OUTPUT_DIR
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    # ======================================================
    # FASE 1: Feature Extraction
    # ======================================================
    model.freeze_backbone()
    trainable = sum(1 for p in model.parameters() if p.requires_grad)
    print(f"\nFASE 1: Backbone CONGELADO ({trainable} params treinaveis)")

    opt1 = optim.AdamW(
        filter(lambda p: p.requires_grad, model.parameters()),
        lr=cfg.PHASE1_LR, weight_decay=cfg.WEIGHT_DECAY,
    )
    sched1 = optim.lr_scheduler.ReduceLROnPlateau(opt1, patience=5, factor=0.5)

    best_acc1, _ = train_phase(
        model, train_loader, val_loader, criterion, opt1, sched1,
        device, scaler, cfg.PHASE1_EPOCHS,
        "FASE 1: Feature Extraction", output_dir, cfg.PATIENCE,
        mixup_alpha=0.0, cutmix_alpha=0.0, mix_prob=0.0,
    )

    if args.no_fine_tune:
        print("\n[WARN] Fine-tuning desabilitado (--no-fine-tune)")
    else:
        # ======================================================
        # FASE 2: Fine-Tune Parcial
        # ======================================================
        all_params = list(model.backbone.named_parameters())
        total_backbone = len(all_params)
        unfreeze_from = int(total_backbone * 0.75)  # ultimos 25%
        model.unfreeze_backbone(from_layer=unfreeze_from)

        opt2 = optim.AdamW(
            filter(lambda p: p.requires_grad, model.parameters()),
            lr=cfg.PHASE2_LR, weight_decay=cfg.WEIGHT_DECAY,
        )
        sched2 = optim.lr_scheduler.CosineAnnealingLR(opt2, T_max=cfg.PHASE2_EPOCHS, eta_min=1e-6)

        best_acc2, _ = train_phase(
            model, train_loader, val_loader, criterion, opt2, sched2,
            device, scaler, cfg.PHASE2_EPOCHS,
            "FASE 2: Fine-Tune Parcial 25pct", output_dir, cfg.PATIENCE,
            mixup_alpha=0.0, cutmix_alpha=0.0, mix_prob=0.0,
        )

        # ======================================================
        # FASE 3: Fine-Tune Profundo
        # ======================================================
        unfreeze_from3 = int(total_backbone * 0.40)  # ultimos 60%
        model.unfreeze_backbone(from_layer=unfreeze_from3)

        opt3 = optim.AdamW(
            filter(lambda p: p.requires_grad, model.parameters()),
            lr=cfg.PHASE3_LR, weight_decay=cfg.WEIGHT_DECAY,
        )
        sched3 = optim.lr_scheduler.CosineAnnealingLR(opt3, T_max=cfg.PHASE3_EPOCHS, eta_min=1e-7)

        best_acc3, _ = train_phase(
            model, train_loader, val_loader, criterion, opt3, sched3,
            device, scaler, cfg.PHASE3_EPOCHS,
            "FASE 3: Fine-Tune Profundo 60pct", output_dir, cfg.PATIENCE,
            mixup_alpha=0.0, cutmix_alpha=0.0, mix_prob=0.0,  # sem mix na ultima fase
        )

    # ======================================================
    # AVALIACAO FINAL COM TTA
    # ======================================================
    acc, top3, per_class, all_probs, all_labels, all_preds = evaluate_with_tta(
        model, val_loader, device, class_names
    )

    metrics = {
        "accuracy": float(acc),
        "top3_accuracy": float(top3),
        "per_class": per_class,
        "total_val_samples": len(all_labels),
    }

    # SALVAR
    save_for_production(model, class_names, cfg, output_dir, metrics)

    print(f"\n{'='*60}")
    print(f"  TREINAMENTO v3.0 CONCLUIDO!")
    print(f"{'='*60}")
    print(f"  Accuracy:     {acc:.2%}  (anterior: ~78%)")
    print(f"  Top-3:        {top3:.2%}")
    print(f"  Classes:      {num_classes}")
    print(f"  Modelo:       {cfg.MODEL_NAME} @ {cfg.IMG_SIZE}x{cfg.IMG_SIZE}")
    print(f"  Dropout: {cfg.DROPOUT}, Label Smooth: {cfg.LABEL_SMOOTHING}")
    print(f"  Artefatos:    {output_dir}")
    print(f"\n  -> Rode: python heal_analyzer.py  para testar!\n")


if __name__ == "__main__":
    main()
