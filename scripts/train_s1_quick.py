# -*- coding: utf-8 -*-
"""Quick Stage 1 training (Normal vs Wound) - minimal version."""
import sys, os, random, time
sys.stdout.reconfigure(line_buffering=True)
from pathlib import Path
from collections import Counter
import cv2, numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import Dataset, DataLoader, WeightedRandomSampler
from torchvision import models, transforms
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
DATASET = ROOT / "dataset" / "medetec"
OUTPUT = ROOT / "models" / "wound_classifier_v2"
OUTPUT.mkdir(parents=True, exist_ok=True)
IMAGE_SIZE = 224
EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp"}

WOUND_FOLDERS = [
    "diabetic_foot_ulcers", "pressure_ulcers_1", "pressure_ulcers_2",
    "venous_arterial_ulcers_1", "venous_arterial_ulcers_2",
    "burns", "malignant_wounds", "miscellaneous_wounds",
    "necrotic_toes", "orthopaedic_wounds",
]

print("=== Stage 1 Training (Normal vs Wound) ===")

# Collect wound images
wound_paths = []
for folder in WOUND_FOLDERS:
    fp = DATASET / folder
    if fp.exists():
        for f in sorted(fp.iterdir()):
            if f.suffix.lower() in EXTS and not f.name.startswith("mirrored_"):
                wound_paths.append(f)
print(f"Wound images: {len(wound_paths)}")

# Generate normal samples (corner crops + synthetic skin)
normal_crops = []
for img_path in wound_paths[:100]:
    try:
        img = cv2.imread(str(img_path))
        if img is None: continue
        h, w = img.shape[:2]
        if h >= IMAGE_SIZE and w >= IMAGE_SIZE:
            normal_crops.append(img[0:IMAGE_SIZE, 0:IMAGE_SIZE])
            if len(normal_crops) >= 200: break
            normal_crops.append(img[h-IMAGE_SIZE:h, w-IMAGE_SIZE:w])
            if len(normal_crops) >= 200: break
    except: pass

# Synthetic skin
while len(normal_crops) < 200:
    tone = np.random.randint(140, 220)
    syn = np.full((IMAGE_SIZE, IMAGE_SIZE, 3), tone, dtype=np.uint8)
    noise = np.random.normal(0, 15, syn.shape).astype(np.int16)
    syn = np.clip(syn.astype(np.int16) + noise, 0, 255).astype(np.uint8)
    syn = cv2.GaussianBlur(syn, (5, 5), 0)
    normal_crops.append(syn)

print(f"Normal samples: {len(normal_crops)}")

class SimpleDS(Dataset):
    def __init__(self, samples, transform):
        self.samples = samples
        self.transform = transform
    def __len__(self): return len(self.samples)
    def __getitem__(self, idx):
        item, label = self.samples[idx]
        if isinstance(item, np.ndarray):
            pil = Image.fromarray(cv2.cvtColor(item, cv2.COLOR_BGR2RGB))
        else:
            img = cv2.imread(str(item))
            if img is None: img = np.zeros((IMAGE_SIZE, IMAGE_SIZE, 3), dtype=np.uint8)
            pil = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
        return self.transform(pil), label

# Build samples
samples = [(c, 0) for c in normal_crops] + [(p, 1) for p in wound_paths]
random.shuffle(samples)
n_val = max(2, int(len(samples) * 0.15))
val_samples = samples[:n_val]
train_samples = samples[n_val:]

train_tf = transforms.Compose([
    transforms.Resize((IMAGE_SIZE, IMAGE_SIZE)),
    transforms.RandomHorizontalFlip(0.5),
    transforms.ToTensor(),
    transforms.Normalize([0.485,0.456,0.406],[0.229,0.224,0.225]),
])
val_tf = transforms.Compose([
    transforms.Resize((IMAGE_SIZE, IMAGE_SIZE)),
    transforms.ToTensor(),
    transforms.Normalize([0.485,0.456,0.406],[0.229,0.224,0.225]),
])

labels = [l for _, l in train_samples]
cc = Counter(labels)
weights = [1.0/cc[l] for l in labels]
sampler = WeightedRandomSampler(weights, len(train_samples), replacement=True)

train_loader = DataLoader(SimpleDS(train_samples, train_tf), batch_size=16, sampler=sampler, num_workers=0)
val_loader = DataLoader(SimpleDS(val_samples, val_tf), batch_size=16, shuffle=False, num_workers=0)

device = torch.device("cpu")
model = models.resnet50(weights=models.ResNet50_Weights.IMAGENET1K_V1)
for p in model.parameters(): p.requires_grad = False
for p in model.layer4.parameters(): p.requires_grad = True
model.fc = nn.Linear(model.fc.in_features, 2)
model = model.to(device)

criterion = nn.CrossEntropyLoss()
optimizer = torch.optim.AdamW(filter(lambda p: p.requires_grad, model.parameters()), lr=1e-4, weight_decay=0.01)

save_path = OUTPUT / "modelo_estagio1.pth"
best_acc = 0.0

print(f"Train: {len(train_samples)} | Val: {len(val_samples)}")

for epoch in range(4):
    t0 = time.time()
    model.train()
    correct = total = 0
    for inputs, labels_b in train_loader:
        inputs, labels_b = inputs.to(device), labels_b.to(device)
        optimizer.zero_grad()
        out = model(inputs)
        loss = criterion(out, labels_b)
        loss.backward()
        optimizer.step()
        _, pred = torch.max(out, 1)
        total += labels_b.size(0)
        correct += (pred == labels_b).sum().item()
    train_acc = correct / total

    model.eval()
    correct = total = 0
    with torch.no_grad():
        for inputs, labels_b in val_loader:
            inputs, labels_b = inputs.to(device), labels_b.to(device)
            out = model(inputs)
            _, pred = torch.max(out, 1)
            total += labels_b.size(0)
            correct += (pred == labels_b).sum().item()
    val_acc = correct / total

    elapsed = time.time() - t0
    print(f"  Epoch {epoch+1}/4 | Train Acc: {train_acc:.4f} | Val Acc: {val_acc:.4f} | {elapsed:.1f}s")

    if val_acc >= best_acc:
        best_acc = val_acc
        torch.save(model.state_dict(), str(save_path))
        print(f"    -> Saved: {save_path.name} (acc={best_acc:.4f})")

print(f"\nDone! Best Val Acc: {best_acc:.4f}")
print(f"Saved: {save_path}")
