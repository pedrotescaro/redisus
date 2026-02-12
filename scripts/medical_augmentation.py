"""
REDISUS - Data Augmentation para Imagens Médicas de Feridas

Módulo de augmentação SEGURA para imagens clínicas.

PRINCÍPIO-CHAVE: Em imagens de feridas, a COR é DIAGNÓSTICA:
  • Vermelho vivo  → Granulação (tecido saudável)
  • Amarelo/branco → Esfacelo
  • Preto/marrom   → Necrose
  • Rosa/pele      → Perilesional

Portanto, augmentações de cor devem ser MUITO conservativas,
enquanto augmentações geométricas são livres (orientação não importa).

Uso standalone:
    python scripts/medical_augmentation.py --input dataset/tissue_segmentation/train \\
        --output dataset/tissue_segmentation_aug/train --factor 3

Como módulo nos scripts de treinamento:
    from scripts.medical_augmentation import (
        get_yolo_train_augmentation,
        get_unet_train_augmentation,
        get_unet_val_augmentation,
    )
"""
import argparse
import random
from pathlib import Path
from typing import Optional, Tuple

import cv2
import numpy as np
from loguru import logger

try:
    import albumentations as A
    from albumentations.pytorch import ToTensorV2
    HAS_ALBUM = True
except ImportError:
    HAS_ALBUM = False


# ══════════════════════════════════════════════════════════════════════════════
#  GUIA DE AUGMENTAÇÃO PARA FERIDAS (referência rápida)
# ══════════════════════════════════════════════════════════════════════════════
#
#  ┌────────────────────────┬───────────┬─────────────────────────────────────┐
#  │ Técnica                │ Segurança │ Justificativa clínica               │
#  ├────────────────────────┼───────────┼─────────────────────────────────────┤
#  │ HorizontalFlip         │ ✅ SEGURO │ Orientação não é diagnóstica        │
#  │ VerticalFlip           │ ✅ SEGURO │ Idem                                │
#  │ Rotate90               │ ✅ SEGURO │ Idem                                │
#  │ Rotação ±15°           │ ✅ SEGURO │ Ângulo moderado, sem distorção      │
#  │ Shift/Scale ±10%       │ ✅ SEGURO │ Simula variação de distância câmera │
#  │ ElasticTransform       │ ⚠️ MODER. │ alpha≤30: simula deformação tecido  │
#  │ GaussNoise σ≤20       │ ✅ SEGURO │ Simula ruído de câmera/iluminação   │
#  │ GaussianBlur k≤5       │ ✅ SEGURO │ Simula foco impreciso              │
#  │ Brightness ±10%        │ ⚠️ MODER. │ Simula iluminação, sem exagerar     │
#  │ Contrast ±10%          │ ⚠️ MODER. │ Não altera percepção de cor         │
#  │ CLAHE                  │ ✅ SEGURO │ Melhora contraste local             │
#  │ Hue shift              │ ❌ EVITAR │ ALTERA COR DIAGNÓSTICA!             │
#  │ Saturation forte       │ ❌ EVITAR │ Muda percepção de tecido            │
#  │ ColorJitter forte      │ ❌ EVITAR │ Mistura canais de cor               │
#  │ Cutout/Erasing         │ ❌ EVITAR │ Remove informação clínica da lesão  │
#  │ Mixup forte            │ ❌ EVITAR │ Funde texturas de tecidos distintos │
#  │ Perspective forte      │ ❌ EVITAR │ Deforma morfologia da ferida        │
#  │ GridDistortion forte   │ ❌ EVITAR │ Altera bordas da lesão              │
#  └────────────────────────┴───────────┴─────────────────────────────────────┘
#
# ══════════════════════════════════════════════════════════════════════════════


def get_unet_train_augmentation(
    input_size: Tuple[int, int] = (256, 256),
    level: str = "moderate",
) -> "A.Compose":
    """
    Pipeline de augmentação para treinamento U-Net (segmentação de tecidos).

    Args:
        input_size: (H, W) — resolução de entrada do modelo
        level: "light", "moderate", "aggressive"
            - light: apenas flip + resize (baseline)
            - moderate: flip + rotação + elastic + brilho leve (RECOMENDADO)
            - aggressive: tudo acima + mais variação (risco de distorção)

    Returns:
        albumentations.Compose com transforms imagem+máscara sincronizadas
    """
    if not HAS_ALBUM:
        raise ImportError("albumentations necessário: pip install albumentations")

    # --- Nível LIGHT (baseline seguro) ---
    if level == "light":
        return A.Compose([
            A.Resize(input_size[0], input_size[1]),
            A.HorizontalFlip(p=0.5),
            A.VerticalFlip(p=0.5),
            A.Normalize(mean=(0.485, 0.456, 0.406), std=(0.229, 0.224, 0.225)),
            ToTensorV2(),
        ])

    # --- Nível MODERATE (recomendado para datasets médicos) ---
    if level == "moderate":
        return A.Compose([
            A.Resize(input_size[0], input_size[1]),

            # Geométricas (SEGURAS — orientação não é diagnóstica)
            A.HorizontalFlip(p=0.5),
            A.VerticalFlip(p=0.5),
            A.RandomRotate90(p=0.5),
            A.ShiftScaleRotate(
                shift_limit=0.05,      # Translação ±5%
                scale_limit=0.10,      # Zoom ±10%
                rotate_limit=15,       # Rotação ±15°
                border_mode=cv2.BORDER_REFLECT,  # Reflete bordas (melhor que preto)
                p=0.5,
            ),

            # Deformação elástica (simula deformação natural do tecido)
            A.ElasticTransform(
                alpha=30,              # Intensidade da deformação
                sigma=6,               # Suavidade
                p=0.3,
            ),

            # Cor — MUITO CONSERVATIVA
            A.RandomBrightnessContrast(
                brightness_limit=0.10,  # ±10% brilho
                contrast_limit=0.10,    # ±10% contraste
                p=0.3,
            ),

            # Ruído (simula câmera de baixa qualidade / celular)
            A.GaussNoise(var_limit=(5, 20), p=0.3),
            A.GaussianBlur(blur_limit=(3, 5), p=0.2),

            # Normalização ImageNet (encoder pré-treinado)
            A.Normalize(mean=(0.485, 0.456, 0.406), std=(0.229, 0.224, 0.225)),
            ToTensorV2(),
        ])

    # --- Nível AGGRESSIVE (usar com cautela) ---
    if level == "aggressive":
        return A.Compose([
            A.Resize(input_size[0], input_size[1]),

            # Geométricas estendidas
            A.HorizontalFlip(p=0.5),
            A.VerticalFlip(p=0.5),
            A.RandomRotate90(p=0.5),
            A.ShiftScaleRotate(
                shift_limit=0.08,
                scale_limit=0.15,
                rotate_limit=20,
                border_mode=cv2.BORDER_REFLECT,
                p=0.6,
            ),
            A.ElasticTransform(alpha=50, sigma=8, p=0.3),
            A.GridDistortion(num_steps=5, distort_limit=0.1, p=0.2),

            # Cor — ainda conservativa mas com mais variedade
            A.RandomBrightnessContrast(
                brightness_limit=0.15,
                contrast_limit=0.15,
                p=0.4,
            ),
            A.CLAHE(clip_limit=2.0, tile_grid_size=(8, 8), p=0.2),

            # NÃO tocar em Hue! Saturação mínima.
            A.HueSaturationValue(
                hue_shift_limit=3,     # MÍNIMO — quase nada
                sat_shift_limit=10,    # Pouco
                val_shift_limit=10,    # Pouco
                p=0.15,
            ),

            # Ruído
            A.GaussNoise(var_limit=(5, 30), p=0.3),
            A.GaussianBlur(blur_limit=(3, 7), p=0.2),

            A.Normalize(mean=(0.485, 0.456, 0.406), std=(0.229, 0.224, 0.225)),
            ToTensorV2(),
        ])

    raise ValueError(f"Nível desconhecido: {level}. Use 'light', 'moderate' ou 'aggressive'.")


def get_unet_val_augmentation(
    input_size: Tuple[int, int] = (256, 256),
) -> "A.Compose":
    """Pipeline de validação: apenas resize + normalização (ZERO augmentação)."""
    if not HAS_ALBUM:
        raise ImportError("albumentations necessário")

    return A.Compose([
        A.Resize(input_size[0], input_size[1]),
        A.Normalize(mean=(0.485, 0.456, 0.406), std=(0.229, 0.224, 0.225)),
        ToTensorV2(),
    ])


def get_yolo_augmentation_config(level: str = "moderate") -> dict:
    """
    Retorna hiperparâmetros de augmentação para o Ultralytics YOLOv8.

    O YOLO tem augmentação built-in — basta passar no model.train().
    Estes valores são usados em train_yolo_wound.py.

    Returns:
        Dict com parâmetros para model.train(**params)
    """
    configs = {
        "light": {
            "hsv_h": 0.003,    # Hue ≈ 0 (preserva cor diagnóstica)
            "hsv_s": 0.15,
            "hsv_v": 0.15,
            "degrees": 10.0,
            "scale": 0.2,
            "flipud": 0.5,
            "fliplr": 0.5,
            "mosaic": 0.5,     # Mosaic reduzido
            "mixup": 0.0,      # Sem mixup
        },
        "moderate": {
            "hsv_h": 0.005,    # Hue quase zero
            "hsv_s": 0.3,
            "hsv_v": 0.2,
            "degrees": 15.0,
            "scale": 0.3,
            "flipud": 0.5,
            "fliplr": 0.5,
            "mosaic": 1.0,     # Mosaic ajuda datasets pequenos
            "mixup": 0.1,      # Mixup leve
        },
        "aggressive": {
            "hsv_h": 0.008,
            "hsv_s": 0.4,
            "hsv_v": 0.3,
            "degrees": 20.0,
            "scale": 0.4,
            "flipud": 0.5,
            "fliplr": 0.5,
            "mosaic": 1.0,
            "mixup": 0.2,
        },
    }

    if level not in configs:
        raise ValueError(f"Nível desconhecido: {level}")

    return configs[level]


# ══════════════════════════════════════════════════════════════════════════════
#  Augmentação offline (gerar imagens extras no disco)
# ══════════════════════════════════════════════════════════════════════════════

def augment_offline(
    input_dir: str,
    output_dir: str,
    factor: int = 3,
    level: str = "moderate",
    input_size: Tuple[int, int] = (256, 256),
    has_masks: bool = True,
    seed: int = 42,
):
    """
    Gera versões augmentadas no disco para aumentar o dataset.

    Útil para datasets MUITO pequenos (<50 imagens).
    Para datasets maiores, prefira augmentação online (no DataLoader).

    Args:
        input_dir: Diretório com images/ (e masks/ se has_masks)
        output_dir: Diretório de saída
        factor: Quantas versões augmentadas gerar por imagem
        level: Nível de augmentação
        input_size: Resolução de saída
        has_masks: Se True, augmenta também as máscaras (sincronizado)
        seed: Seed para reprodutibilidade
    """
    random.seed(seed)
    np.random.seed(seed)

    inp = Path(input_dir)
    out = Path(output_dir)

    img_in = inp / "images"
    mask_in = inp / "masks"
    img_out = out / "images"
    mask_out = out / "masks"

    img_out.mkdir(parents=True, exist_ok=True)
    if has_masks:
        mask_out.mkdir(parents=True, exist_ok=True)

    # Pipeline SEM normalização e SEM ToTensorV2 (salvamos como imagem)
    transform = A.Compose([
        A.Resize(input_size[0], input_size[1]),
        A.HorizontalFlip(p=0.5),
        A.VerticalFlip(p=0.5),
        A.RandomRotate90(p=0.5),
        A.ShiftScaleRotate(
            shift_limit=0.05, scale_limit=0.1, rotate_limit=15,
            border_mode=cv2.BORDER_REFLECT, p=0.5,
        ),
        A.ElasticTransform(alpha=30, sigma=6, p=0.3),
        A.RandomBrightnessContrast(
            brightness_limit=0.1, contrast_limit=0.1, p=0.3
        ),
        A.GaussNoise(var_limit=(5, 20), p=0.3),
    ])

    images = sorted([p for p in img_in.iterdir() if p.suffix.lower() in {".jpg", ".jpeg", ".png"}])
    logger.info(f"Augmentação offline: {len(images)} imagens × {factor} = {len(images) * factor} extras")

    total = 0
    for img_path in images:
        image = cv2.imread(str(img_path))
        if image is None:
            continue
        image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

        mask = None
        if has_masks:
            mask_path = mask_in / (img_path.stem + ".png")
            if mask_path.exists():
                mask = cv2.imread(str(mask_path), cv2.IMREAD_GRAYSCALE)

        # Copia original
        cv2.imwrite(str(img_out / img_path.name), cv2.cvtColor(image, cv2.COLOR_RGB2BGR))
        if mask is not None:
            cv2.imwrite(str(mask_out / (img_path.stem + ".png")), mask)

        # Gera versões augmentadas
        for i in range(factor):
            if mask is not None:
                augmented = transform(image=image, mask=mask)
                aug_img = augmented["image"]
                aug_mask = augmented["mask"]
            else:
                augmented = transform(image=image)
                aug_img = augmented["image"]
                aug_mask = None

            aug_name = f"{img_path.stem}_aug{i:02d}"
            cv2.imwrite(
                str(img_out / f"{aug_name}.png"),
                cv2.cvtColor(aug_img, cv2.COLOR_RGB2BGR)
            )
            if aug_mask is not None:
                cv2.imwrite(str(mask_out / f"{aug_name}.png"), aug_mask)

            total += 1

    logger.info(f"Geradas {total} imagens augmentadas em {out}")
    return total


# ══════════════════════════════════════════════════════════════════════════════
#  CLI
# ══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="REDISUS - Augmentação offline de imagens médicas de feridas"
    )
    parser.add_argument(
        "--input", "-i", required=True,
        help="Diretório com images/ e masks/"
    )
    parser.add_argument(
        "--output", "-o", required=True,
        help="Diretório de saída"
    )
    parser.add_argument(
        "--factor", "-f", type=int, default=3,
        help="Fator de multiplicação (default: 3)"
    )
    parser.add_argument(
        "--level", choices=["light", "moderate", "aggressive"], default="moderate",
        help="Nível de augmentação (default: moderate)"
    )
    parser.add_argument(
        "--imgsz", type=int, default=256,
        help="Resolução de saída (default: 256)"
    )
    parser.add_argument(
        "--no-masks", action="store_true",
        help="Não processar máscaras"
    )
    parser.add_argument(
        "--seed", type=int, default=42,
        help="Seed para reprodutibilidade"
    )

    args = parser.parse_args()

    augment_offline(
        input_dir=args.input,
        output_dir=args.output,
        factor=args.factor,
        level=args.level,
        input_size=(args.imgsz, args.imgsz),
        has_masks=not args.no_masks,
        seed=args.seed,
    )


if __name__ == "__main__":
    main()
