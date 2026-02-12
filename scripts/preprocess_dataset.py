"""
REDISUS - Pré-processamento de Dataset para Treinamento

Redimensiona, normaliza e valida imagens/máscaras para os dois pipelines:
  • YOLO  (detecção)    → 640×640, salva JPG com labels .txt copiados
  • U-Net (segmentação) → 256×256 (ou 512×512), salva PNG + máscara PNG

Também gera splits train/val/test a partir de uma pasta flat quando necessário.

Uso:
    # Pré-processar YOLO (resize para 640×640)
    python scripts/preprocess_dataset.py --task yolo --imgsz 640

    # Pré-processar U-Net (resize para 256×256)
    python scripts/preprocess_dataset.py --task unet --imgsz 256

    # Pré-processar ambos
    python scripts/preprocess_dataset.py --task both

    # Criar split a partir de pasta flat + pré-processar
    python scripts/preprocess_dataset.py --task unet --source dataset/raw_wounds --split 0.7 0.15 0.15
"""
import argparse
import json
import random
import shutil
from pathlib import Path
from dataclasses import dataclass
from typing import List, Optional, Tuple

import cv2
import numpy as np
from loguru import logger


# ──────────────────────────────────────────────────────────────────────────────
#  Configuração
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class PreprocessConfig:
    # YOLO
    yolo_input_dir: str = "dataset/yolo_wounds"
    yolo_output_dir: str = "dataset/yolo_wounds_processed"
    yolo_imgsz: int = 640

    # U-Net
    unet_input_dir: str = "dataset/tissue_segmentation"
    unet_output_dir: str = "dataset/tissue_segmentation_processed"
    unet_imgsz: int = 256

    # Qualidade
    jpg_quality: int = 95          # Qualidade JPEG (para YOLO images)
    interpolation_up: int = cv2.INTER_CUBIC    # Upscale
    interpolation_down: int = cv2.INTER_AREA   # Downscale
    mask_interpolation: int = cv2.INTER_NEAREST  # Máscaras = nearest (sem blending)

    # Validação
    num_classes_mask: int = 5  # valores esperados 0-4


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp"}


# ──────────────────────────────────────────────────────────────────────────────
#  Utilitários
# ──────────────────────────────────────────────────────────────────────────────

def is_image(path: Path) -> bool:
    return path.suffix.lower() in IMAGE_EXTENSIONS


def choose_interpolation(src_size: Tuple[int, int], dst_size: int, config: PreprocessConfig) -> int:
    """Seleciona interpolação com base em up ou downscale."""
    src_max = max(src_size)
    return config.interpolation_up if dst_size > src_max else config.interpolation_down


def resize_image(image: np.ndarray, target_size: int, config: PreprocessConfig) -> np.ndarray:
    """
    Redimensiona imagem para (target_size × target_size).
    Usa letterbox (padding) para manter aspect ratio quando necessário.
    Para treinamento, resize direto é preferível (augmentação cuida do resto).
    """
    h, w = image.shape[:2]
    interp = choose_interpolation((h, w), target_size, config)
    resized = cv2.resize(image, (target_size, target_size), interpolation=interp)
    return resized


def resize_mask(mask: np.ndarray, target_size: int) -> np.ndarray:
    """
    Redimensiona máscara usando INTER_NEAREST para preservar valores de classe.
    NUNCA usar interpolação bilinear/bicúbica em máscaras de segmentação!
    """
    resized = cv2.resize(mask, (target_size, target_size), interpolation=cv2.INTER_NEAREST)
    return resized


def normalize_pixel_stats(image: np.ndarray) -> dict:
    """Calcula estatísticas de normalização (para referência, não altera imagem)."""
    img_float = image.astype(np.float32) / 255.0
    return {
        "mean_rgb": img_float.mean(axis=(0, 1)).tolist(),
        "std_rgb": img_float.std(axis=(0, 1)).tolist(),
    }


def validate_mask(mask: np.ndarray, num_classes: int, filename: str) -> bool:
    """Valida que os valores de pixel da máscara estão em [0, num_classes-1]."""
    unique = np.unique(mask)
    invalid = unique[unique >= num_classes]
    if len(invalid) > 0:
        logger.warning(
            f"Máscara {filename} contém valores inválidos: {invalid.tolist()}. "
            f"Esperado: 0-{num_classes - 1}. Esses pixels serão clampados."
        )
        return False
    return True


# ──────────────────────────────────────────────────────────────────────────────
#  Split de dados a partir de pasta flat
# ──────────────────────────────────────────────────────────────────────────────

def split_flat_dataset(
    source_dir: str,
    output_dir: str,
    ratios: Tuple[float, float, float] = (0.7, 0.15, 0.15),
    has_masks: bool = False,
    seed: int = 42,
):
    """
    Divide um diretório flat (images/ + masks/) em train/val/test.

    Args:
        source_dir: Diretório com subpastas images/ (e masks/ se has_masks)
        output_dir: Diretório de saída com train/val/test
        ratios: (train, val, test) — devem somar 1.0
        has_masks: Se True, também copia máscaras correspondentes
        seed: Seed para reprodutibilidade
    """
    assert abs(sum(ratios) - 1.0) < 1e-6, f"Ratios devem somar 1.0, got {sum(ratios)}"

    source = Path(source_dir)
    output = Path(output_dir)

    img_source = source / "images" if (source / "images").exists() else source
    mask_source = source / "masks" if has_masks else None

    # Lista imagens
    images = sorted([p for p in img_source.iterdir() if is_image(p)])
    if not images:
        logger.error(f"Nenhuma imagem encontrada em {img_source}")
        return

    random.seed(seed)
    random.shuffle(images)

    n = len(images)
    n_train = int(n * ratios[0])
    n_val = int(n * ratios[1])

    splits = {
        "train": images[:n_train],
        "val": images[n_train:n_train + n_val],
        "test": images[n_train + n_val:],
    }

    for split_name, split_images in splits.items():
        img_out = output / split_name / "images"
        img_out.mkdir(parents=True, exist_ok=True)

        if has_masks:
            mask_out = output / split_name / "masks"
            mask_out.mkdir(parents=True, exist_ok=True)

        for img_path in split_images:
            shutil.copy2(str(img_path), str(img_out / img_path.name))
            if has_masks and mask_source:
                mask_name = img_path.stem + ".png"
                mask_path = mask_source / mask_name
                if mask_path.exists():
                    shutil.copy2(str(mask_path), str(mask_out / mask_name))

        logger.info(f"  [{split_name}] {len(split_images)} imagens")

    logger.info(f"Split concluído: {output}")


# ──────────────────────────────────────────────────────────────────────────────
#  Pré-processamento YOLO
# ──────────────────────────────────────────────────────────────────────────────

def preprocess_yolo(config: PreprocessConfig, inplace: bool = False):
    """
    Redimensiona imagens YOLO para (imgsz × imgsz).
    Labels .txt permanecem inalterados (valores já são normalizados 0-1).
    """
    input_dir = Path(config.yolo_input_dir)
    output_dir = Path(config.yolo_output_dir) if not inplace else input_dir

    logger.info(f"[YOLO] Pré-processando: {input_dir} → {output_dir}")
    logger.info(f"[YOLO] Resolução alvo: {config.yolo_imgsz}×{config.yolo_imgsz}")

    stats = {"processed": 0, "skipped": 0, "errors": 0}

    for split in ["train", "val", "test"]:
        img_in = input_dir / split / "images"
        label_in = input_dir / split / "labels"

        if not img_in.exists():
            logger.info(f"  [{split}] Diretório não encontrado, pulando.")
            continue

        img_out = output_dir / split / "images"
        label_out = output_dir / split / "labels"
        img_out.mkdir(parents=True, exist_ok=True)
        label_out.mkdir(parents=True, exist_ok=True)

        images = [p for p in img_in.iterdir() if is_image(p)]
        logger.info(f"  [{split}] {len(images)} imagens encontradas")

        for img_path in images:
            try:
                image = cv2.imread(str(img_path))
                if image is None:
                    logger.warning(f"    Erro ao ler: {img_path.name}")
                    stats["errors"] += 1
                    continue

                resized = resize_image(image, config.yolo_imgsz, config)

                # Salva como JPG
                out_name = img_path.stem + ".jpg"
                out_path = img_out / out_name
                cv2.imwrite(
                    str(out_path), resized,
                    [cv2.IMWRITE_JPEG_QUALITY, config.jpg_quality]
                )

                # Copia label correspondente (valores normalizados, não muda)
                label_name = img_path.stem + ".txt"
                label_src = label_in / label_name
                if label_src.exists():
                    shutil.copy2(str(label_src), str(label_out / label_name))

                stats["processed"] += 1

            except Exception as e:
                logger.error(f"    Erro em {img_path.name}: {e}")
                stats["errors"] += 1

    if not inplace:
        # Copia data.yaml atualizando path
        src_yaml = input_dir / "data.yaml"
        if src_yaml.exists():
            content = src_yaml.read_text(encoding="utf-8")
            content = content.replace(
                str(input_dir.absolute()),
                str(output_dir.absolute())
            )
            (output_dir / "data.yaml").write_text(content, encoding="utf-8")

    logger.info(f"[YOLO] Concluído: {stats['processed']} processadas, "
                f"{stats['errors']} erros")
    return stats


# ──────────────────────────────────────────────────────────────────────────────
#  Pré-processamento U-Net
# ──────────────────────────────────────────────────────────────────────────────

def preprocess_unet(config: PreprocessConfig, inplace: bool = False):
    """
    Redimensiona imagens e máscaras para (imgsz × imgsz).
    • Imagens: interpolação bicúbica (downscale) / area (upscale)
    • Máscaras: INTER_NEAREST (preserva classes 0-4)
    • Normalização: feita em runtime pelo albumentations (ImageNet stats)
    """
    input_dir = Path(config.unet_input_dir)
    output_dir = Path(config.unet_output_dir) if not inplace else input_dir

    logger.info(f"[U-Net] Pré-processando: {input_dir} → {output_dir}")
    logger.info(f"[U-Net] Resolução alvo: {config.unet_imgsz}×{config.unet_imgsz}")

    stats = {"processed": 0, "mask_errors": 0, "missing_masks": 0, "errors": 0}
    pixel_stats = []

    for split in ["train", "val", "test"]:
        img_in = input_dir / split / "images"
        mask_in = input_dir / split / "masks"

        if not img_in.exists():
            logger.info(f"  [{split}] Diretório não encontrado, pulando.")
            continue

        img_out = output_dir / split / "images"
        mask_out = output_dir / split / "masks"
        img_out.mkdir(parents=True, exist_ok=True)
        mask_out.mkdir(parents=True, exist_ok=True)

        images = [p for p in img_in.iterdir() if is_image(p)]
        logger.info(f"  [{split}] {len(images)} imagens encontradas")

        for img_path in images:
            try:
                # --- Imagem ---
                image = cv2.imread(str(img_path))
                if image is None:
                    logger.warning(f"    Erro ao ler: {img_path.name}")
                    stats["errors"] += 1
                    continue

                resized_img = resize_image(image, config.unet_imgsz, config)

                # Coleta stats de normalização (apenas train)
                if split == "train":
                    pixel_stats.append(normalize_pixel_stats(resized_img))

                # Salva como PNG (lossless para manter qualidade)
                out_img_path = img_out / (img_path.stem + ".png")
                cv2.imwrite(str(out_img_path), resized_img)

                # --- Máscara ---
                mask_name = img_path.stem + ".png"
                mask_path = mask_in / mask_name
                if not mask_path.exists():
                    # Tenta mesmo nome com extensão original
                    mask_path = mask_in / img_path.name
                if not mask_path.exists():
                    stats["missing_masks"] += 1
                    continue

                mask = cv2.imread(str(mask_path), cv2.IMREAD_GRAYSCALE)
                if mask is None:
                    stats["mask_errors"] += 1
                    continue

                # Valida e clampa valores
                if not validate_mask(mask, config.num_classes_mask, mask_name):
                    mask = np.clip(mask, 0, config.num_classes_mask - 1)
                    stats["mask_errors"] += 1

                resized_mask = resize_mask(mask, config.unet_imgsz)

                out_mask_path = mask_out / mask_name
                cv2.imwrite(str(out_mask_path), resized_mask)

                stats["processed"] += 1

            except Exception as e:
                logger.error(f"    Erro em {img_path.name}: {e}")
                stats["errors"] += 1

    # Calcula estatísticas globais de normalização
    if pixel_stats:
        means = np.array([s["mean_rgb"] for s in pixel_stats])
        stds = np.array([s["std_rgb"] for s in pixel_stats])
        global_stats = {
            "dataset_mean_bgr": means.mean(axis=0).tolist(),
            "dataset_std_bgr": stds.mean(axis=0).tolist(),
            "note": "Valores em BGR (OpenCV). Para RGB, inverta a ordem.",
            "imagenet_mean_rgb": [0.485, 0.456, 0.406],
            "imagenet_std_rgb": [0.229, 0.224, 0.225],
            "recommendation": (
                "Use ImageNet stats para transfer learning com encoder "
                "pré-treinado (EfficientNet). Use dataset stats apenas se "
                "treinar do zero."
            ),
        }
        stats_path = output_dir / "normalization_stats.json"
        stats_path.write_text(json.dumps(global_stats, indent=2), encoding="utf-8")
        logger.info(f"  Estatísticas de normalização salvas: {stats_path}")

    logger.info(f"[U-Net] Concluído: {stats['processed']} processadas, "
                f"{stats['missing_masks']} sem máscara, {stats['errors']} erros")
    return stats


# ──────────────────────────────────────────────────────────────────────────────
#  Verificação rápida de integridade
# ──────────────────────────────────────────────────────────────────────────────

def verify_dataset_integrity(task: str = "both"):
    """Verifica que os datasets estão prontos para treinamento."""
    ok = True

    if task in ("yolo", "both"):
        logger.info("\n[YOLO] Verificando integridade...")
        yolo_base = Path("dataset/yolo_wounds")
        for split in ["train", "val"]:
            img_dir = yolo_base / split / "images"
            lbl_dir = yolo_base / split / "labels"

            imgs = set(p.stem for p in img_dir.glob("*") if is_image(p)) if img_dir.exists() else set()
            lbls = set(p.stem for p in lbl_dir.glob("*.txt")) if lbl_dir.exists() else set()

            matched = imgs & lbls
            no_label = imgs - lbls
            no_image = lbls - imgs

            logger.info(f"  [{split}] {len(matched)} pares OK, "
                        f"{len(no_label)} sem label, {len(no_image)} sem imagem")

            if no_label:
                logger.warning(f"  [{split}] Imagens sem label: {list(no_label)[:5]}...")
            if len(matched) == 0:
                logger.error(f"  [{split}] Nenhum par imagem/label encontrado!")
                ok = False

    if task in ("unet", "both"):
        logger.info("\n[U-Net] Verificando integridade...")
        unet_base = Path("dataset/tissue_segmentation")
        for split in ["train", "val"]:
            img_dir = unet_base / split / "images"
            msk_dir = unet_base / split / "masks"

            imgs = set(p.stem for p in img_dir.glob("*") if is_image(p)) if img_dir.exists() else set()
            masks = set(p.stem for p in msk_dir.glob("*.png")) if msk_dir.exists() else set()

            matched = imgs & masks
            no_mask = imgs - masks

            logger.info(f"  [{split}] {len(matched)} pares OK, {len(no_mask)} sem máscara")

            if len(matched) == 0:
                logger.error(f"  [{split}] Nenhum par imagem/máscara encontrado!")
                ok = False

            # Verifica resolução de amostra
            if matched:
                sample_name = next(iter(matched))
                sample_img = cv2.imread(str(img_dir / (sample_name + ".png")))
                if sample_img is None:
                    sample_img = cv2.imread(str(img_dir / (sample_name + ".jpg")))
                if sample_img is not None:
                    h, w = sample_img.shape[:2]
                    logger.info(f"  [{split}] Resolução amostra: {w}×{h}")

    return ok


# ──────────────────────────────────────────────────────────────────────────────
#  CLI
# ──────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="REDISUS - Pré-processamento de datasets para treinamento"
    )
    parser.add_argument(
        "--task", choices=["yolo", "unet", "both"], default="both",
        help="Qual pipeline pré-processar (default: both)"
    )
    parser.add_argument(
        "--imgsz", type=int, default=None,
        help="Resolução alvo. Default: 640 (YOLO) / 256 (U-Net)"
    )
    parser.add_argument(
        "--inplace", action="store_true",
        help="Sobrescrever arquivos no diretório original (cuidado!)"
    )
    parser.add_argument(
        "--verify", action="store_true",
        help="Apenas verificar integridade do dataset, sem processar"
    )
    parser.add_argument(
        "--source", type=str, default=None,
        help="Diretório fonte flat para split automático"
    )
    parser.add_argument(
        "--split", nargs=3, type=float, default=None,
        metavar=("TRAIN", "VAL", "TEST"),
        help="Proporções do split (ex: 0.7 0.15 0.15)"
    )

    args = parser.parse_args()

    if args.verify:
        verify_dataset_integrity(args.task)
        return

    config = PreprocessConfig()

    # Override resolução se fornecida
    if args.imgsz:
        if args.task in ("yolo", "both"):
            config.yolo_imgsz = args.imgsz
        if args.task in ("unet", "both"):
            config.unet_imgsz = args.imgsz

    # Split automático se --source fornecido
    if args.source and args.split:
        ratios = tuple(args.split)
        logger.info(f"Criando split {ratios} a partir de {args.source}")
        has_masks = args.task in ("unet", "both")
        target_dir = config.unet_input_dir if args.task == "unet" else config.yolo_input_dir
        split_flat_dataset(args.source, target_dir, ratios, has_masks=has_masks)

    # Pré-processamento
    logger.info("=" * 60)
    logger.info("REDISUS - Pré-processamento de Dataset")
    logger.info("=" * 60)

    if args.task in ("yolo", "both"):
        preprocess_yolo(config, inplace=args.inplace)

    if args.task in ("unet", "both"):
        preprocess_unet(config, inplace=args.inplace)

    # Verificação final
    logger.info("\nVerificação final:")
    verify_dataset_integrity(args.task)


if __name__ == "__main__":
    main()
