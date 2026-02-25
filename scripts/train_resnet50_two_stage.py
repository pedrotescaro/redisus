# -*- coding: utf-8 -*-
"""
REDISUS — Treinamento ResNet50 em Dois Estágios
================================================

Treina os modelos:
  Estágio 1: Normal vs Ferida (binário)
  Estágio 2: Diabética / Pressão / Venosa (3 classes)

Salva os .pth em models/wound_classifier_v2/
"""

import os
import sys
import random
import shutil
import time
from pathlib import Path
from collections import Counter

# Force unbuffered output for subprocess redirection
sys.stdout.reconfigure(line_buffering=True)

# Log to file as well
LOG_FILE = Path(__file__).resolve().parent.parent / "train_resnet50_log.txt"
_log_fh = open(LOG_FILE, "w", encoding="utf-8")

_orig_print = print
def print(*args, **kwargs):
    _orig_print(*args, **kwargs, flush=True)
    kwargs.pop("flush", None)
    _orig_print(*args, **kwargs, file=_log_fh, flush=True)

import cv2
import numpy as np

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import Dataset, DataLoader, WeightedRandomSampler
from torchvision import models, transforms
from PIL import Image

# ============================================================
# CONFIGURAÇÃO
# ============================================================

ROOT_DIR = Path(__file__).resolve().parent.parent
DATASET_DIR = ROOT_DIR / "dataset" / "medetec"
OUTPUT_DIR = ROOT_DIR / "models" / "wound_classifier_v2"

# Mapeamento de pastas → classe do Estágio 2
STAGE2_MAPPING = {
    "diabetic_foot_ulcers": "Diabetic Wounds",
    "pressure_ulcers_1": "Pressure Wounds",
    "pressure_ulcers_2": "Pressure Wounds",
    "venous_arterial_ulcers_1": "Venous Wounds",
    "venous_arterial_ulcers_2": "Venous Wounds",
}

# Pastas que são feridas (para Estágio 1 = "Wound")
ALL_WOUND_FOLDERS = [
    "abdominal_wounds",
    "burns",
    "diabetic_foot_ulcers",
    "epidermolysis_bullosa",
    "extravasation_injuries",
    "haemangiomas",
    "malignant_wounds",
    "meningitis_wounds",
    "miscellaneous_wounds",
    "necrotic_toes",
    "orthopaedic_wounds",
    "pilonidal_sinus",
    "pressure_ulcers_1",
    "pressure_ulcers_2",
    "venous_arterial_ulcers_1",
    "venous_arterial_ulcers_2",
]

STAGE1_CLASSES = ["Normal", "Wound"]
STAGE2_CLASSES = ["Diabetic Wounds", "Pressure Wounds", "Venous Wounds"]

IMAGE_SIZE = 224
IMAGENET_MEAN = [0.485, 0.456, 0.406]
IMAGENET_STD = [0.229, 0.224, 0.225]

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp"}


# ============================================================
# DATASET
# ============================================================

def collect_images(folders, base_dir):
    """Coleta todos os caminhos de imagem das pastas listadas."""
    paths = []
    for folder in folders:
        folder_path = base_dir / folder
        if not folder_path.exists():
            continue
        for f in sorted(folder_path.iterdir()):
            if f.suffix.lower() in IMAGE_EXTENSIONS and not f.name.startswith("mirrored_"):
                paths.append(f)
    return paths


def generate_normal_samples(wound_paths, num_samples=200, size=224):
    """
    Gera 'Normal' samples recortando bordas perilesionais de imagens de feridas.
    Recorta cantos e bordas onde geralmente há pele saudável.
    Também inclui imagens sintéticas de pele.
    """
    normals = []
    crops_per_image = max(1, num_samples // len(wound_paths) + 1)

    for img_path in wound_paths:
        try:
            img = cv2.imread(str(img_path))
            if img is None:
                continue
            h, w = img.shape[:2]
            if h < size or w < size:
                continue

            # Recorta cantos (geralmente pele saudável / fundo)
            crop_regions = [
                (0, 0, size, size),                         # top-left
                (0, w - size, size, w),                     # top-right
                (h - size, 0, h, size),                     # bottom-left
                (h - size, w - size, h, w),                 # bottom-right
            ]

            for y1, x1, y2, x2 in crop_regions[:crops_per_image]:
                crop = img[y1:y2, x1:x2]
                if crop.shape[0] == size and crop.shape[1] == size:
                    normals.append(crop)
                    if len(normals) >= num_samples:
                        return normals
        except Exception:
            continue

    # Complementa com imagens sintéticas de pele (cor uniforme com ruído)
    while len(normals) < num_samples:
        skin_tone = np.random.randint(140, 220)
        variation = np.random.randint(10, 30)
        synthetic = np.full((size, size, 3), skin_tone, dtype=np.uint8)
        noise = np.random.normal(0, variation, synthetic.shape).astype(np.int16)
        synthetic = np.clip(synthetic.astype(np.int16) + noise, 0, 255).astype(np.uint8)
        # Add slight blur for realism
        synthetic = cv2.GaussianBlur(synthetic, (5, 5), 0)
        normals.append(synthetic)

    return normals[:num_samples]


class WoundDataset(Dataset):
    """Dataset unificado para ambos os estágios."""

    def __init__(self, samples, transform=None):
        """
        samples: list of (image_or_path, label_idx)
            image_or_path: str/Path (carrega do disco) ou np.ndarray (já em memória)
        """
        self.samples = samples
        self.transform = transform

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx):
        img_or_path, label = self.samples[idx]

        if isinstance(img_or_path, np.ndarray):
            # Já é imagem BGR em memória
            image_rgb = cv2.cvtColor(img_or_path, cv2.COLOR_BGR2RGB)
            pil_img = Image.fromarray(image_rgb)
        else:
            # Carrega do disco
            try:
                img = cv2.imread(str(img_or_path))
                if img is None:
                    # Fallback: imagem preta
                    img = np.zeros((IMAGE_SIZE, IMAGE_SIZE, 3), dtype=np.uint8)
                image_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                pil_img = Image.fromarray(image_rgb)
            except Exception:
                pil_img = Image.new("RGB", (IMAGE_SIZE, IMAGE_SIZE))

        if self.transform:
            tensor = self.transform(pil_img)
        else:
            tensor = transforms.ToTensor()(pil_img)

        return tensor, label


# ============================================================
# MODELO
# ============================================================

def build_resnet50(num_classes, pretrained=True):
    """Constrói ResNet50 com transfer learning (igual ao notebook)."""
    if pretrained:
        model = models.resnet50(weights=models.ResNet50_Weights.IMAGENET1K_V1)
    else:
        model = models.resnet50(weights=None)

    # Congela camadas iniciais (feature extraction)
    for param in model.parameters():
        param.requires_grad = False

    # Descongela layer4 e fc
    for param in model.layer4.parameters():
        param.requires_grad = True

    num_ftrs = model.fc.in_features
    model.fc = nn.Linear(num_ftrs, num_classes)

    return model


# ============================================================
# TREINAMENTO
# ============================================================

def train_one_epoch(model, loader, criterion, optimizer, device):
    model.train()
    running_loss = 0.0
    correct = 0
    total = 0

    for inputs, labels in loader:
        inputs = inputs.to(device)
        labels = labels.to(device)

        optimizer.zero_grad()
        outputs = model(inputs)
        loss = criterion(outputs, labels)
        loss.backward()
        optimizer.step()

        running_loss += loss.item() * inputs.size(0)
        _, predicted = torch.max(outputs, 1)
        total += labels.size(0)
        correct += (predicted == labels).sum().item()

    epoch_loss = running_loss / total
    epoch_acc = correct / total
    return epoch_loss, epoch_acc


def validate(model, loader, criterion, device):
    model.eval()
    running_loss = 0.0
    correct = 0
    total = 0

    with torch.no_grad():
        for inputs, labels in loader:
            inputs = inputs.to(device)
            labels = labels.to(device)

            outputs = model(inputs)
            loss = criterion(outputs, labels)

            running_loss += loss.item() * inputs.size(0)
            _, predicted = torch.max(outputs, 1)
            total += labels.size(0)
            correct += (predicted == labels).sum().item()

    epoch_loss = running_loss / total if total > 0 else 0
    epoch_acc = correct / total if total > 0 else 0
    return epoch_loss, epoch_acc


def train_model(model, train_loader, val_loader, device, num_epochs, lr, model_name, save_path=None):
    """Treina um modelo com early stopping e salva o melhor."""
    criterion = nn.CrossEntropyLoss()
    optimizer = torch.optim.AdamW(
        filter(lambda p: p.requires_grad, model.parameters()),
        lr=lr, weight_decay=0.01
    )
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=num_epochs)

    best_val_acc = 0.0
    best_state = None
    patience = 8
    no_improve = 0

    print(f"\n{'='*60}")
    print(f"  TREINANDO: {model_name}")
    print(f"  Epochs: {num_epochs} | LR: {lr} | Device: {device}")
    print(f"  Train: {len(train_loader.dataset)} | Val: {len(val_loader.dataset)}")
    print(f"{'='*60}")

    for epoch in range(num_epochs):
        t0 = time.time()
        train_loss, train_acc = train_one_epoch(model, train_loader, criterion, optimizer, device)
        val_loss, val_acc = validate(model, val_loader, criterion, device)
        scheduler.step()

        elapsed = time.time() - t0
        print(f"  Epoch {epoch+1:02d}/{num_epochs} | "
              f"Train Loss: {train_loss:.4f} Acc: {train_acc:.4f} | "
              f"Val Loss: {val_loss:.4f} Acc: {val_acc:.4f} | "
              f"{elapsed:.1f}s")

        if val_acc > best_val_acc:
            best_val_acc = val_acc
            best_state = {k: v.cpu().clone() for k, v in model.state_dict().items()}
            no_improve = 0
            # Save immediately on improvement
            if save_path and best_state:
                torch.save(best_state, str(save_path))
                print(f"    -> Salvo checkpoint: {save_path.name} (acc={best_val_acc:.4f})")
        else:
            no_improve += 1
            if no_improve >= patience:
                print(f"  Early stopping na epoch {epoch+1} (melhor val_acc: {best_val_acc:.4f})")
                break

    if best_state is not None:
        model.load_state_dict(best_state)
    print(f"  Melhor Val Accuracy: {best_val_acc:.4f}")
    return model, best_val_acc


def create_splits(samples, val_ratio=0.2):
    """Cria splits treino/validação estratificados."""
    random.shuffle(samples)

    # Agrupa por classe
    by_class = {}
    for item in samples:
        _, label = item
        by_class.setdefault(label, []).append(item)

    train_samples = []
    val_samples = []

    for cls, items in by_class.items():
        random.shuffle(items)
        n_val = max(1, int(len(items) * val_ratio))
        val_samples.extend(items[:n_val])
        train_samples.extend(items[n_val:])

    return train_samples, val_samples


# ============================================================
# MAIN
# ============================================================

def main():
    print("=" * 60)
    print("  REDISUS — Treinamento ResNet50 Dois Estágios")
    print("=" * 60)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Device: {device}")
    print(f"Dataset: {DATASET_DIR}")
    print(f"Output:  {OUTPUT_DIR}")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Transforms
    train_transform = transforms.Compose([
        transforms.Resize((IMAGE_SIZE, IMAGE_SIZE)),
        transforms.RandomHorizontalFlip(0.5),
        transforms.RandomVerticalFlip(0.3),
        transforms.RandomRotation(15),
        transforms.ColorJitter(brightness=0.2, contrast=0.2, saturation=0.2, hue=0.05),
        transforms.ToTensor(),
        transforms.Normalize(IMAGENET_MEAN, IMAGENET_STD),
    ])

    val_transform = transforms.Compose([
        transforms.Resize((IMAGE_SIZE, IMAGE_SIZE)),
        transforms.ToTensor(),
        transforms.Normalize(IMAGENET_MEAN, IMAGENET_STD),
    ])

    # ════════════════════════════════════════════
    # ESTÁGIO 2: Tipo de Ferida (3 classes)
    # ════════════════════════════════════════════
    print("\n--- Preparando Estágio 2 (Diabética / Pressão / Venosa) ---")

    s2_samples = []
    for folder, class_name in STAGE2_MAPPING.items():
        class_idx = STAGE2_CLASSES.index(class_name)
        imgs = collect_images([folder], DATASET_DIR)
        for img_path in imgs:
            s2_samples.append((img_path, class_idx))

    print(f"  Total de imagens Estágio 2: {len(s2_samples)}")
    counts = Counter(label for _, label in s2_samples)
    for idx, cls_name in enumerate(STAGE2_CLASSES):
        print(f"    {cls_name}: {counts.get(idx, 0)}")

    s2_train, s2_val = create_splits(s2_samples, val_ratio=0.2)

    # Weighted sampling para balancear classes
    train_labels = [label for _, label in s2_train]
    class_counts = Counter(train_labels)
    weights = [1.0 / class_counts[label] for label in train_labels]
    sampler = WeightedRandomSampler(weights, num_samples=len(s2_train), replacement=True)

    s2_train_ds = WoundDataset(s2_train, transform=train_transform)
    s2_val_ds = WoundDataset(s2_val, transform=val_transform)

    s2_train_loader = DataLoader(s2_train_ds, batch_size=16, sampler=sampler, num_workers=0)
    s2_val_loader = DataLoader(s2_val_ds, batch_size=16, shuffle=False, num_workers=0)

    s2_path = OUTPUT_DIR / "modelo_estagio2_semAugmentation.pth"
    model_s2 = build_resnet50(len(STAGE2_CLASSES), pretrained=True).to(device)
    model_s2, s2_acc = train_model(
        model_s2, s2_train_loader, s2_val_loader, device,
        num_epochs=12, lr=1e-4,
        model_name="Estágio 2 — Tipo de Ferida",
        save_path=s2_path
    )

    # Salva final (garante que existe)
    torch.save(model_s2.state_dict(), str(s2_path))
    print(f"  ✓ Salvo: {s2_path}")

    # Copia com nome alternativo
    s2_alt = OUTPUT_DIR / "modelo_estagio2.pth"
    shutil.copy2(str(s2_path), str(s2_alt))
    print(f"  ✓ Cópia: {s2_alt}")

    # ════════════════════════════════════════════
    # ESTÁGIO 1: Normal vs Ferida (binário)
    # ════════════════════════════════════════════
    print("\n--- Preparando Estágio 1 (Normal vs Ferida) ---")

    # Coleta imagens de feridas
    wound_paths = collect_images(ALL_WOUND_FOLDERS, DATASET_DIR)
    print(f"  Imagens de ferida: {len(wound_paths)}")

    # Gera amostras normais a partir das bordas das imagens
    num_normals = min(len(wound_paths), 300)
    print(f"  Gerando {num_normals} amostras 'Normal' (recortes perilesionais + sintético)...")
    normal_crops = generate_normal_samples(wound_paths, num_samples=num_normals)
    print(f"  Amostras Normal geradas: {len(normal_crops)}")

    s1_samples = []
    # Normal = 0
    for crop in normal_crops:
        s1_samples.append((crop, 0))
    # Wound = 1
    for path in wound_paths:
        s1_samples.append((path, 1))

    print(f"  Total Estágio 1: {len(s1_samples)} (Normal: {len(normal_crops)}, Wound: {len(wound_paths)})")

    s1_train, s1_val = create_splits(s1_samples, val_ratio=0.2)

    train_labels_s1 = [label for _, label in s1_train]
    cc = Counter(train_labels_s1)
    weights_s1 = [1.0 / cc[label] for label in train_labels_s1]
    sampler_s1 = WeightedRandomSampler(weights_s1, num_samples=len(s1_train), replacement=True)

    s1_train_ds = WoundDataset(s1_train, transform=train_transform)
    s1_val_ds = WoundDataset(s1_val, transform=val_transform)

    s1_train_loader = DataLoader(s1_train_ds, batch_size=16, sampler=sampler_s1, num_workers=0)
    s1_val_loader = DataLoader(s1_val_ds, batch_size=16, shuffle=False, num_workers=0)

    s1_path = OUTPUT_DIR / "modelo_estagio1.pth"
    model_s1 = build_resnet50(len(STAGE1_CLASSES), pretrained=True).to(device)
    model_s1, s1_acc = train_model(
        model_s1, s1_train_loader, s1_val_loader, device,
        num_epochs=6, lr=1e-4,
        model_name="Estágio 1 — Normal vs Ferida",
        save_path=s1_path
    )

    # Salva
    s1_path = OUTPUT_DIR / "modelo_estagio1.pth"
    torch.save(model_s1.state_dict(), str(s1_path))
    print(f"  ✓ Salvo: {s1_path}")

    # ════════════════════════════════════════════
    # RESUMO
    # ════════════════════════════════════════════
    print("\n" + "=" * 60)
    print("  TREINAMENTO CONCLUÍDO")
    print("=" * 60)
    print(f"  Estágio 1 (Normal/Ferida):  Val Acc = {s1_acc:.4f}")
    print(f"  Estágio 2 (Tipo de Ferida): Val Acc = {s2_acc:.4f}")
    print(f"\n  Modelos salvos em: {OUTPUT_DIR}")
    print(f"    - modelo_estagio1.pth")
    print(f"    - modelo_estagio2_semAugmentation.pth")
    print(f"    - modelo_estagio2.pth")
    print(f"\n  O heal_analyzer.py agora carregará automaticamente.")
    print("=" * 60)


if __name__ == "__main__":
    main()
