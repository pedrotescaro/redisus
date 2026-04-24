#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
===============================================================================
REDISUS - MEDSAM FINE-TUNING PARA SEGMENTACAO DE FERIDAS
===============================================================================

Fine-tuning do MedSAM (Medical Segment Anything Model) para segmentacao
precisa de feridas usando datasets clinicos locais com mascaras anotadas.

Estrategia:
  - Congela image encoder (ViT-B) do SAM
  - Fine-tuna apenas o mask decoder + prompt encoder
  - Usa bounding box como prompt (compativel com deteccao YOLO)
  - Loss: BCE + Dice combinados (padrao para segmentacao medica)

Datasets suportados:
  - FUSeg (Foot Ulcer Segmentation Challenge): 1210 imagens
  - AZH Chronic Wound Dataset
  - Formato customizado: pasta images/ + masks/ (PNG binarias)

Requisitos:
    pip install torch torchvision segment-anything monai

Uso:
    python medsam_finetuning.py --data_dir ./data/fuseg --epochs 50
    python medsam_finetuning.py --data_dir ./data/wound_masks --checkpoint models/medsam_vit_b.pth
===============================================================================
"""

import argparse
import json
import os
import time
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Dict, List, Optional, Tuple

import cv2
import numpy as np

if TYPE_CHECKING:
    import torch

SEED = 42


# ---------------------------------------------------------------------------
# Dataset
# ---------------------------------------------------------------------------

class WoundSegmentationDataset:
    """
    Dataset para segmentacao de feridas.

    Formato esperado:
        data_dir/
            images/       <- imagens originais (JPG/PNG)
            masks/        <- mascaras binarias (PNG, 0=bg, 255=ferida)

    Ou formato FUSeg:
        data_dir/
            train/
                images/
                labels/
            test/
                images/
                labels/
    """

    def __init__(
        self,
        root_dir: str,
        img_size: int = 1024,
        is_train: bool = True,
        augment: bool = True,
    ):
        self.root = Path(root_dir)
        self.img_size = img_size
        self.is_train = is_train
        self.augment = augment and is_train

        self.image_paths: List[Path] = []
        self.mask_paths: List[Path] = []

        self._discover_files()
        print(f"[Dataset] {len(self.image_paths)} pares imagem/mascara encontrados "
              f"({'train' if is_train else 'val'})")

    def _discover_files(self):
        """Descobre pares imagem/mascara no diretorio."""
        valid_exts = {".jpg", ".jpeg", ".png", ".bmp", ".tiff"}

        # Tenta formato FUSeg primeiro
        split = "train" if self.is_train else "test"
        fuseg_img = self.root / split / "images"
        fuseg_mask = self.root / split / "labels"
        if fuseg_img.exists() and fuseg_mask.exists():
            self._load_paired(fuseg_img, fuseg_mask, valid_exts)
            return

        # Formato padrao: images/ + masks/
        img_dir = self.root / "images"
        mask_dir = self.root / "masks"
        if img_dir.exists() and mask_dir.exists():
            self._load_paired(img_dir, mask_dir, valid_exts)
            return

        # Tenta diretorio flat com sufixo _mask
        for f in sorted(self.root.iterdir()):
            if f.suffix.lower() not in valid_exts:
                continue
            if "_mask" in f.stem:
                continue
            mask_candidates = [
                f.parent / f"{f.stem}_mask{f.suffix}",
                f.parent / f"{f.stem}_mask.png",
            ]
            for mc in mask_candidates:
                if mc.exists():
                    self.image_paths.append(f)
                    self.mask_paths.append(mc)
                    break

    def _load_paired(self, img_dir: Path, mask_dir: Path, valid_exts: set):
        """Carrega pares correspondentes de dois diretorios."""
        img_files = sorted([
            f for f in img_dir.iterdir()
            if f.suffix.lower() in valid_exts
        ])
        for img_path in img_files:
            # Procura mascara correspondente
            for ext in [".png", ".jpg", ".bmp", img_path.suffix]:
                mask_path = mask_dir / f"{img_path.stem}{ext}"
                if mask_path.exists():
                    self.image_paths.append(img_path)
                    self.mask_paths.append(mask_path)
                    break

    def __len__(self):
        return len(self.image_paths)

    def __getitem__(self, idx):
        import torch

        # Carrega imagem e mascara
        img = cv2.imread(str(self.image_paths[idx]))
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        mask = cv2.imread(str(self.mask_paths[idx]), cv2.IMREAD_GRAYSCALE)

        # Binariza mascara
        mask = (mask > 127).astype(np.uint8)

        # Augmentation
        if self.augment:
            img, mask = self._augment(img, mask)

        # Resize para tamanho do SAM
        img_resized = cv2.resize(img, (self.img_size, self.img_size))
        mask_resized = cv2.resize(mask, (self.img_size, self.img_size),
                                  interpolation=cv2.INTER_NEAREST)

        # Gera bounding box prompt a partir da mascara
        bbox = self._mask_to_bbox(mask_resized)

        # Normaliza imagem [0,1]
        img_tensor = torch.tensor(img_resized, dtype=torch.float32).permute(2, 0, 1) / 255.0
        mask_tensor = torch.tensor(mask_resized, dtype=torch.float32).unsqueeze(0)
        bbox_tensor = torch.tensor(bbox, dtype=torch.float32)

        return img_tensor, mask_tensor, bbox_tensor

    def _augment(self, img: np.ndarray, mask: np.ndarray):
        """Augmentation geometrica + cor."""
        # Flip horizontal
        if np.random.random() > 0.5:
            img = np.fliplr(img).copy()
            mask = np.fliplr(mask).copy()

        # Flip vertical
        if np.random.random() > 0.5:
            img = np.flipud(img).copy()
            mask = np.flipud(mask).copy()

        # Rotacao aleatoria
        if np.random.random() > 0.5:
            angle = np.random.uniform(-15, 15)
            h, w = img.shape[:2]
            M = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
            img = cv2.warpAffine(img, M, (w, h), borderMode=cv2.BORDER_REFLECT)
            mask = cv2.warpAffine(mask, M, (w, h), flags=cv2.INTER_NEAREST,
                                  borderMode=cv2.BORDER_CONSTANT)

        # Jitter de cor (so na imagem)
        if np.random.random() > 0.5:
            brightness = np.random.uniform(0.8, 1.2)
            img = np.clip(img * brightness, 0, 255).astype(np.uint8)

        return img, mask

    @staticmethod
    def _mask_to_bbox(mask: np.ndarray) -> List[int]:
        """Extrai bounding box da mascara binaria."""
        ys, xs = np.where(mask > 0)
        if len(xs) == 0 or len(ys) == 0:
            h, w = mask.shape
            return [w // 4, h // 4, 3 * w // 4, 3 * h // 4]
        x1, x2 = int(xs.min()), int(xs.max())
        y1, y2 = int(ys.min()), int(ys.max())

        # Adiciona margem de 5%
        w = x2 - x1
        h = y2 - y1
        margin_x = int(w * 0.05)
        margin_y = int(h * 0.05)
        x1 = max(0, x1 - margin_x)
        y1 = max(0, y1 - margin_y)
        x2 = min(mask.shape[1], x2 + margin_x)
        y2 = min(mask.shape[0], y2 + margin_y)

        return [x1, y1, x2, y2]


# ---------------------------------------------------------------------------
# Loss Functions
# ---------------------------------------------------------------------------

def dice_loss(pred: "torch.Tensor", target: "torch.Tensor", smooth: float = 1.0):
    """Dice Loss para segmentacao binaria."""
    pred_flat = pred.reshape(-1)
    target_flat = target.reshape(-1)
    intersection = (pred_flat * target_flat).sum()
    return 1 - (2.0 * intersection + smooth) / (
        pred_flat.sum() + target_flat.sum() + smooth
    )


def combined_loss(pred: "torch.Tensor", target: "torch.Tensor"):
    """BCE + Dice Loss combinados (padrao MedSAM)."""
    import torch.nn.functional as F

    bce = F.binary_cross_entropy_with_logits(pred, target)
    pred_sigmoid = pred.sigmoid()
    dice = dice_loss(pred_sigmoid, target)
    return bce + dice


# ---------------------------------------------------------------------------
# MedSAM Fine-Tuning
# ---------------------------------------------------------------------------

def finetune_medsam(
    data_dir: str,
    checkpoint_path: str = "models/medsam_vit_b.pth",
    output_dir: str = "models/finetuned/medsam_wound",
    epochs: int = 50,
    batch_size: int = 4,
    learning_rate: float = 1e-4,
    img_size: int = 1024,
    patience: int = 10,
):
    """
    Fine-tuning do MedSAM para segmentacao de feridas.

    Congela o image encoder e treina apenas mask decoder + prompt encoder.
    """
    import torch
    from torch.utils.data import DataLoader
    from segment_anything import sam_model_registry

    print("=" * 60)
    print("  REDISUS - Fine-Tuning MedSAM (Segmentacao de Feridas)")
    print("=" * 60)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Device: {device}")

    # Carrega MedSAM
    ckpt = Path(checkpoint_path)
    if not ckpt.exists():
        print(f"ERRO: Checkpoint nao encontrado: {ckpt}")
        print("Baixe de: https://huggingface.co/medsam/medsam_vit_b")
        return

    print(f"Carregando MedSAM: {ckpt.name}")
    sam = sam_model_registry["vit_b"](checkpoint=str(ckpt))
    sam.to(device)

    # Congela image encoder (ViT-B)
    for param in sam.image_encoder.parameters():
        param.requires_grad = False
    print("Image encoder congelado (ViT-B)")

    # Parametros treinaveis: mask_decoder + prompt_encoder
    trainable_params = []
    for name, param in sam.named_parameters():
        if param.requires_grad:
            trainable_params.append(param)

    total_params = sum(p.numel() for p in sam.parameters())
    train_params = sum(p.numel() for p in trainable_params)
    print(f"Parametros: {total_params / 1e6:.1f}M total, "
          f"{train_params / 1e6:.1f}M treinaveis ({train_params / total_params:.1%})")

    # Datasets
    train_ds = WoundSegmentationDataset(data_dir, img_size, is_train=True, augment=True)
    val_ds = WoundSegmentationDataset(data_dir, img_size, is_train=False, augment=False)

    if len(train_ds) == 0:
        print("ERRO: Nenhuma imagem encontrada no dataset!")
        return

    # Se nao tem split separado, usa 80/20
    if len(val_ds) == 0:
        from torch.utils.data import random_split
        val_size = max(1, int(len(train_ds) * 0.2))
        train_size = len(train_ds) - val_size
        train_ds, val_ds = random_split(
            train_ds, [train_size, val_size],
            generator=torch.Generator().manual_seed(SEED),
        )

    train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True,
                              num_workers=2, pin_memory=True)
    val_loader = DataLoader(val_ds, batch_size=batch_size, shuffle=False,
                            num_workers=2, pin_memory=True)

    # Optimizer
    optimizer = torch.optim.AdamW(trainable_params, lr=learning_rate, weight_decay=0.01)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs)

    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    best_val_dice = 0.0
    patience_counter = 0
    history = {"train_loss": [], "val_loss": [], "val_dice": []}

    for epoch in range(epochs):
        # --- Train ---
        sam.train()
        # Mantemos o encoder em eval (BatchNorm/Dropout fixos)
        sam.image_encoder.eval()

        running_loss = 0.0
        for batch_idx, (images, masks, bboxes) in enumerate(train_loader):
            images = images.to(device)
            masks = masks.to(device)
            bboxes = bboxes.to(device)

            # Forward: encode image
            with torch.no_grad():
                image_embeddings = sam.image_encoder(images)

            # Encode prompts (bounding boxes)
            sparse_embeddings, dense_embeddings = sam.prompt_encoder(
                points=None,
                boxes=bboxes,
                masks=None,
            )

            # Predict masks
            low_res_masks, iou_predictions = sam.mask_decoder(
                image_embeddings=image_embeddings,
                image_pe=sam.prompt_encoder.get_dense_pe(),
                sparse_prompt_embeddings=sparse_embeddings,
                dense_prompt_embeddings=dense_embeddings,
                multimask_output=False,
            )

            # Resize predição para tamanho da mascara GT
            pred_masks = torch.nn.functional.interpolate(
                low_res_masks,
                size=(img_size, img_size),
                mode="bilinear",
                align_corners=False,
            )

            loss = combined_loss(pred_masks, masks)

            optimizer.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(trainable_params, max_norm=1.0)
            optimizer.step()

            running_loss += loss.item()

        train_loss = running_loss / max(len(train_loader), 1)

        # --- Validation ---
        sam.eval()
        val_loss = 0.0
        val_dice_total = 0.0
        val_count = 0

        with torch.no_grad():
            for images, masks, bboxes in val_loader:
                images = images.to(device)
                masks = masks.to(device)
                bboxes = bboxes.to(device)

                image_embeddings = sam.image_encoder(images)

                sparse_embeddings, dense_embeddings = sam.prompt_encoder(
                    points=None,
                    boxes=bboxes,
                    masks=None,
                )

                low_res_masks, _ = sam.mask_decoder(
                    image_embeddings=image_embeddings,
                    image_pe=sam.prompt_encoder.get_dense_pe(),
                    sparse_prompt_embeddings=sparse_embeddings,
                    dense_prompt_embeddings=dense_embeddings,
                    multimask_output=False,
                )

                pred_masks = torch.nn.functional.interpolate(
                    low_res_masks,
                    size=(img_size, img_size),
                    mode="bilinear",
                    align_corners=False,
                )

                loss = combined_loss(pred_masks, masks)
                val_loss += loss.item()

                # Dice score
                pred_binary = (pred_masks.sigmoid() > 0.5).float()
                intersection = (pred_binary * masks).sum(dim=(2, 3))
                union = pred_binary.sum(dim=(2, 3)) + masks.sum(dim=(2, 3))
                batch_dice = ((2.0 * intersection + 1) / (union + 1)).mean()
                val_dice_total += batch_dice.item()
                val_count += 1

        val_loss = val_loss / max(len(val_loader), 1)
        val_dice = val_dice_total / max(val_count, 1)

        scheduler.step()

        history["train_loss"].append(train_loss)
        history["val_loss"].append(val_loss)
        history["val_dice"].append(val_dice)

        print(
            f"Epoch {epoch + 1}/{epochs} "
            f"| Train Loss: {train_loss:.4f} "
            f"| Val Loss: {val_loss:.4f} "
            f"| Val Dice: {val_dice:.4f} "
            f"| LR: {scheduler.get_last_lr()[0]:.2e}"
        )

        # Checkpoint
        if val_dice > best_val_dice + 0.001:
            best_val_dice = val_dice
            patience_counter = 0

            # Salva apenas mask_decoder e prompt_encoder (encoder congelado)
            torch.save({
                "mask_decoder": sam.mask_decoder.state_dict(),
                "prompt_encoder": sam.prompt_encoder.state_dict(),
                "val_dice": val_dice,
                "epoch": epoch + 1,
            }, out_path / "medsam_wound_finetuned.pth")
            print(f"  -> Melhor modelo salvo (Dice={val_dice:.4f})")
        else:
            patience_counter += 1
            if patience_counter >= patience:
                print(f"  -> Early stopping (patience={patience})")
                break

    # Metadata
    metadata = {
        "base_model": "medsam_vit_b",
        "finetuned_on": str(data_dir),
        "best_val_dice": best_val_dice,
        "epochs_trained": len(history["train_loss"]),
        "img_size": img_size,
        "frozen_components": ["image_encoder"],
        "trained_components": ["mask_decoder", "prompt_encoder"],
        "loss": "BCE + Dice",
        "config": {
            "learning_rate": learning_rate,
            "batch_size": batch_size,
            "patience": patience,
        },
        "timestamp": datetime.now().isoformat(),
    }

    with open(out_path / "training_metadata.json", "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)

    print(f"\nFine-tuning concluido! Melhor Val Dice: {best_val_dice:.4f}")
    print(f"Modelo salvo em: {out_path}")
    print(
        "\nPara usar o modelo fine-tuned, carregue o SAM base e substitua os pesos:\n"
        "  ckpt = torch.load('medsam_wound_finetuned.pth')\n"
        "  sam.mask_decoder.load_state_dict(ckpt['mask_decoder'])\n"
        "  sam.prompt_encoder.load_state_dict(ckpt['prompt_encoder'])"
    )

    return history


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="REDISUS - Fine-tuning MedSAM para segmentacao de feridas"
    )
    parser.add_argument("--data_dir", type=str, required=True,
                        help="Diretorio com images/ e masks/")
    parser.add_argument("--checkpoint", type=str, default="models/medsam_vit_b.pth",
                        help="Checkpoint base do MedSAM")
    parser.add_argument("--output_dir", type=str, default="models/finetuned/medsam_wound")
    parser.add_argument("--epochs", type=int, default=50)
    parser.add_argument("--batch_size", type=int, default=4)
    parser.add_argument("--lr", type=float, default=1e-4)
    parser.add_argument("--img_size", type=int, default=1024)
    parser.add_argument("--patience", type=int, default=10)
    args = parser.parse_args()

    finetune_medsam(
        data_dir=args.data_dir,
        checkpoint_path=args.checkpoint,
        output_dir=args.output_dir,
        epochs=args.epochs,
        batch_size=args.batch_size,
        learning_rate=args.lr,
        img_size=args.img_size,
        patience=args.patience,
    )


if __name__ == "__main__":
    main()
