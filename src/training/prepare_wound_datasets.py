#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
===============================================================================
REDISUS - PREPARACAO DE DATASETS PUBLICOS DE FERIDAS
===============================================================================

Utilitario para download, organizacao e preparacao dos principais datasets
publicos de feridas para uso nos pipelines de treino/fine-tuning do REDISUS.

Datasets suportados:
  1. FUSeg (Foot Ulcer Segmentation Challenge)
     - 1210 imagens (1010 train / 200 test) com mascaras de segmentacao
     - Fonte: MICCAI Challenge (fusc.grand-challenge.org)

  2. AZH Chronic Wound Dataset
     - Feridas cronicas anotadas por profissionais
     - Fonte: uwm-bigdata/wound-segmentation (GitHub)

  3. Medetec Wound Database
     - ~594 imagens em 15 categorias (venous, arterial, pressure, burns...)
     - Fonte: medetec.co.uk

  4. DFUC 2020/2021 (Diabetic Foot Ulcer Challenge)
     - Deteccao e classificacao de ulceras diabeticas
     - Fonte: dfu-challenge.github.io

  5. Wseg Dataset (WSNet)
     - 2686 imagens com mascaras de segmentacao
     - Fonte: Hugging Face (subbareddy248/Wseg_dataset)

Formato de saida padronizado:
    data/datasets/<nome>/
        images/          <- imagens RGB originais
        masks/           <- mascaras binarias (PNG, 0=bg, 255=ferida)
        classification/  <- subpastas por classe (para classificacao)
            venous/
            arterial/
            ...
        metadata.json    <- info sobre o dataset

Uso:
    python prepare_wound_datasets.py --dataset fuseg --output data/datasets
    python prepare_wound_datasets.py --dataset all --output data/datasets
    python prepare_wound_datasets.py --list
===============================================================================
"""

import argparse
import hashlib
import json
import os
import shutil
import sys
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np


# ---------------------------------------------------------------------------
# Registro de Datasets
# ---------------------------------------------------------------------------

DATASETS_REGISTRY = {
    "fuseg": {
        "name": "FUSeg (Foot Ulcer Segmentation Challenge)",
        "description": "1210 imagens de ulceras de pe com mascaras de segmentacao",
        "source": "https://github.com/uwm-bigdata/wound-segmentation",
        "task": "segmentation",
        "size": "~200MB",
        "license": "Research use",
        "classes": ["wound"],
        "format": "images + binary masks",
    },
    "azh": {
        "name": "AZH Chronic Wound Dataset",
        "description": "Feridas cronicas anotadas por profissionais de saude",
        "source": "https://github.com/uwm-bigdata/wound-segmentation",
        "task": "segmentation",
        "size": "~150MB",
        "license": "Research use",
        "classes": ["wound"],
        "format": "images + binary masks",
    },
    "medetec": {
        "name": "Medetec Wound Database",
        "description": "~594 imagens em 15 categorias de feridas",
        "source": "http://www.medetec.co.uk/files/medetec-image-databases.html",
        "task": "classification",
        "size": "~100MB",
        "license": "Free for research",
        "classes": [
            "venous_leg_ulcer",
            "arterial_ulcer",
            "pressure_ulcer",
            "diabetic_ulcer",
            "surgical_wound",
            "burn",
            "mixed_ulcer",
        ],
        "format": "folders by category",
    },
    "wseg": {
        "name": "Wseg Dataset (WSNet - WACV 2023)",
        "description": "2686 imagens com mascaras de segmentacao de feridas",
        "source": "https://huggingface.co/datasets/subbareddy248/Wseg_dataset",
        "task": "segmentation",
        "size": "~500MB",
        "license": "MIT",
        "classes": ["wound"],
        "format": "images + binary masks",
    },
}


def list_datasets():
    """Lista todos os datasets disponiveis."""
    print("=" * 65)
    print("  REDISUS - Datasets Publicos de Feridas Disponiveis")
    print("=" * 65)

    for key, info in DATASETS_REGISTRY.items():
        print(f"\n  [{key}] {info['name']}")
        print(f"  Descricao:  {info['description']}")
        print(f"  Tarefa:     {info['task']}")
        print(f"  Tamanho:    {info['size']}")
        print(f"  Licenca:    {info['license']}")
        print(f"  Classes:    {', '.join(info['classes'])}")
        print(f"  Fonte:      {info['source']}")

    print("\n" + "=" * 65)
    print("Uso: python prepare_wound_datasets.py --dataset <nome> --output data/datasets")
    print("     python prepare_wound_datasets.py --dataset all")


# ---------------------------------------------------------------------------
# Utilitarios
# ---------------------------------------------------------------------------

def ensure_dir(path: Path):
    path.mkdir(parents=True, exist_ok=True)
    return path


def image_stats(img_dir: Path) -> Dict:
    """Calcula estatisticas basicas das imagens em um diretorio."""
    valid_exts = {".jpg", ".jpeg", ".png", ".bmp", ".tiff"}
    files = [f for f in img_dir.rglob("*") if f.suffix.lower() in valid_exts]

    widths, heights = [], []
    for f in files:
        img = cv2.imread(str(f))
        if img is not None:
            h, w = img.shape[:2]
            widths.append(w)
            heights.append(h)

    if not widths:
        return {"count": 0}

    return {
        "count": len(widths),
        "width_min": int(min(widths)),
        "width_max": int(max(widths)),
        "width_mean": int(np.mean(widths)),
        "height_min": int(min(heights)),
        "height_max": int(max(heights)),
        "height_mean": int(np.mean(heights)),
    }


def validate_masks(img_dir: Path, mask_dir: Path) -> Dict:
    """Valida alinhamento entre imagens e mascaras."""
    valid_exts = {".jpg", ".jpeg", ".png", ".bmp"}

    images = {f.stem for f in img_dir.iterdir() if f.suffix.lower() in valid_exts}
    masks = {f.stem for f in mask_dir.iterdir() if f.suffix.lower() in valid_exts}

    matched = images & masks
    img_only = images - masks
    mask_only = masks - images

    return {
        "matched_pairs": len(matched),
        "images_without_mask": len(img_only),
        "masks_without_image": len(mask_only),
        "samples_missing_mask": sorted(list(img_only))[:10],
    }


def standardize_masks(mask_dir: Path, output_dir: Path):
    """
    Padroniza mascaras: converte para binario (0 ou 255), PNG, escala de cinza.
    """
    ensure_dir(output_dir)
    valid_exts = {".jpg", ".jpeg", ".png", ".bmp", ".tiff"}

    count = 0
    for f in sorted(mask_dir.iterdir()):
        if f.suffix.lower() not in valid_exts:
            continue

        mask = cv2.imread(str(f), cv2.IMREAD_GRAYSCALE)
        if mask is None:
            continue

        # Binariza: > 127 = ferida (255), <= 127 = background (0)
        binary = np.where(mask > 127, 255, 0).astype(np.uint8)

        # Salva como PNG
        out_path = output_dir / f"{f.stem}.png"
        cv2.imwrite(str(out_path), binary)
        count += 1

    return count


def create_classification_split(
    images_dir: Path,
    output_dir: Path,
    class_mapping: Optional[Dict[str, str]] = None,
):
    """
    Organiza imagens em subpastas por classe para ImageFolder.

    Se class_mapping for None, tenta inferir classe do nome do arquivo
    ou do nome da pasta pai.
    """
    ensure_dir(output_dir)
    valid_exts = {".jpg", ".jpeg", ".png", ".bmp"}

    count = 0
    for f in images_dir.rglob("*"):
        if f.suffix.lower() not in valid_exts:
            continue

        # Tenta determinar classe
        if class_mapping and f.stem in class_mapping:
            cls = class_mapping[f.stem]
        elif f.parent.name != images_dir.name:
            cls = f.parent.name.lower().replace(" ", "_")
        else:
            cls = "unknown"

        cls_dir = ensure_dir(output_dir / cls)
        shutil.copy2(str(f), str(cls_dir / f.name))
        count += 1

    return count


def train_val_split(
    source_dir: Path,
    output_dir: Path,
    val_ratio: float = 0.2,
    seed: int = 42,
):
    """
    Divide um diretorio images/ + masks/ em train/ e val/.
    """
    np.random.seed(seed)

    img_dir = source_dir / "images"
    mask_dir = source_dir / "masks"

    if not img_dir.exists():
        print(f"  [AVISO] Diretorio nao encontrado: {img_dir}")
        return

    valid_exts = {".jpg", ".jpeg", ".png", ".bmp"}
    all_images = sorted([f for f in img_dir.iterdir() if f.suffix.lower() in valid_exts])

    indices = np.random.permutation(len(all_images))
    val_size = int(len(all_images) * val_ratio)
    val_indices = set(indices[:val_size])

    for split in ["train", "val"]:
        ensure_dir(output_dir / split / "images")
        if mask_dir.exists():
            ensure_dir(output_dir / split / "masks")

    for i, img_path in enumerate(all_images):
        split = "val" if i in val_indices else "train"

        # Copia imagem
        shutil.copy2(str(img_path), str(output_dir / split / "images" / img_path.name))

        # Copia mascara correspondente
        if mask_dir.exists():
            for ext in [".png", ".jpg", img_path.suffix]:
                mask_path = mask_dir / f"{img_path.stem}{ext}"
                if mask_path.exists():
                    shutil.copy2(
                        str(mask_path),
                        str(output_dir / split / "masks" / f"{img_path.stem}.png"),
                    )
                    break

    print(f"  Split criado: {len(all_images) - val_size} train / {val_size} val")


# ---------------------------------------------------------------------------
# Preparadores por dataset
# ---------------------------------------------------------------------------

def prepare_fuseg(source_dir: Path, output_dir: Path):
    """
    Prepara o dataset FUSeg.

    Espera a estrutura clonada do repositorio uwm-bigdata/wound-segmentation:
        source_dir/
            Foot Ulcer Segmentation Challenge/
                train/
                    images/
                    labels/
                test/
                    images/
                    labels/
    """
    print("\n[FUSeg] Preparando dataset...")

    # Procura a pasta do challenge
    fuseg_dir = None
    for candidate in [
        source_dir / "Foot Ulcer Segmentation Challenge",
        source_dir / "FUSeg",
        source_dir,
    ]:
        if (candidate / "train" / "images").exists():
            fuseg_dir = candidate
            break

    if fuseg_dir is None:
        print("  [ERRO] Estrutura FUSeg nao encontrada.")
        print("  Clone: git clone https://github.com/uwm-bigdata/wound-segmentation")
        print(f"  E coloque em: {source_dir}/")
        return False

    out = ensure_dir(output_dir / "fuseg")

    for split in ["train", "test"]:
        src_imgs = fuseg_dir / split / "images"
        src_masks = fuseg_dir / split / "labels"

        if not src_imgs.exists():
            continue

        split_out = "val" if split == "test" else "train"
        dst_imgs = ensure_dir(out / split_out / "images")
        dst_masks = ensure_dir(out / split_out / "masks")

        # Copia imagens
        img_count = 0
        for f in sorted(src_imgs.iterdir()):
            if f.suffix.lower() in {".jpg", ".jpeg", ".png"}:
                shutil.copy2(str(f), str(dst_imgs / f.name))
                img_count += 1

        # Padroniza mascaras
        mask_count = 0
        if src_masks.exists():
            mask_count = standardize_masks(src_masks, dst_masks)

        print(f"  {split_out}: {img_count} imagens, {mask_count} mascaras")

    # Validacao
    val_info = validate_masks(
        out / "train" / "images", out / "train" / "masks"
    )
    print(f"  Validacao (train): {val_info['matched_pairs']} pares validos")

    # Metadata
    _save_metadata(out, "fuseg", "segmentation")
    print("  [OK] FUSeg preparado")
    return True


def prepare_local_segmentation(source_dir: Path, output_dir: Path, name: str = "custom"):
    """
    Prepara um dataset local de segmentacao no formato padrao.

    Aceita:
        source_dir/images/ + source_dir/masks/
    ou:
        source_dir/train/images/ + source_dir/train/labels/
    """
    print(f"\n[{name}] Preparando dataset de segmentacao local...")

    out = ensure_dir(output_dir / name)

    # Detecta formato
    if (source_dir / "train" / "images").exists():
        # Formato FUSeg-like
        for split in ["train", "test", "val"]:
            src_imgs = source_dir / split / "images"
            src_masks = source_dir / split / ("labels" if (source_dir / split / "labels").exists() else "masks")

            if not src_imgs.exists():
                continue

            dst_imgs = ensure_dir(out / split / "images")
            dst_masks = ensure_dir(out / split / "masks")

            for f in sorted(src_imgs.iterdir()):
                if f.suffix.lower() in {".jpg", ".jpeg", ".png", ".bmp"}:
                    shutil.copy2(str(f), str(dst_imgs / f.name))

            if src_masks.exists():
                standardize_masks(src_masks, dst_masks)

    elif (source_dir / "images").exists():
        # Formato simples images/ + masks/
        img_dir = source_dir / "images"
        mask_dir = source_dir / "masks"

        dst_imgs = ensure_dir(out / "images")
        dst_masks = ensure_dir(out / "masks")

        for f in sorted(img_dir.iterdir()):
            if f.suffix.lower() in {".jpg", ".jpeg", ".png", ".bmp"}:
                shutil.copy2(str(f), str(dst_imgs / f.name))

        if mask_dir.exists():
            standardize_masks(mask_dir, dst_masks)

        # Cria split train/val
        train_val_split(out, out, val_ratio=0.2)

    else:
        print(f"  [ERRO] Formato nao reconhecido em {source_dir}")
        return False

    _save_metadata(out, name, "segmentation")
    print(f"  [OK] {name} preparado")
    return True


def prepare_local_classification(source_dir: Path, output_dir: Path, name: str = "custom_cls"):
    """
    Prepara um dataset local de classificacao (ImageFolder).

    Aceita:
        source_dir/
            classe_1/
                img1.jpg
                img2.jpg
            classe_2/
                ...
    """
    print(f"\n[{name}] Preparando dataset de classificacao local...")

    out = ensure_dir(output_dir / name)

    # Verifica se tem subpastas (classes)
    subdirs = [d for d in source_dir.iterdir() if d.is_dir() and not d.name.startswith(".")]
    if not subdirs:
        print(f"  [ERRO] Nenhuma subpasta de classe encontrada em {source_dir}")
        return False

    valid_exts = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
    class_counts = {}

    for cls_dir in sorted(subdirs):
        cls_name = cls_dir.name
        dst_cls = ensure_dir(out / "all" / cls_name)

        count = 0
        for f in sorted(cls_dir.iterdir()):
            if f.suffix.lower() in valid_exts:
                shutil.copy2(str(f), str(dst_cls / f.name))
                count += 1

        class_counts[cls_name] = count
        print(f"  Classe '{cls_name}': {count} imagens")

    # Cria split train/val por classe
    np.random.seed(42)
    for cls_name in class_counts:
        src_cls = out / "all" / cls_name
        imgs = sorted([f for f in src_cls.iterdir() if f.suffix.lower() in valid_exts])
        indices = np.random.permutation(len(imgs))
        val_size = max(1, int(len(imgs) * 0.2))

        ensure_dir(out / "train" / cls_name)
        ensure_dir(out / "val" / cls_name)

        for i, idx in enumerate(indices):
            split = "val" if i < val_size else "train"
            shutil.copy2(str(imgs[idx]), str(out / split / cls_name / imgs[idx].name))

    total = sum(class_counts.values())
    print(f"  Total: {total} imagens em {len(class_counts)} classes")

    _save_metadata(out, name, "classification", extra={"classes": class_counts})
    print(f"  [OK] {name} preparado")
    return True


# ---------------------------------------------------------------------------
# Conversao entre formatos
# ---------------------------------------------------------------------------

def segmentation_to_classification(
    seg_dir: Path,
    output_dir: Path,
    etiology_labels: Optional[Dict[str, str]] = None,
):
    """
    Converte dataset de segmentacao em classificacao.

    Se etiology_labels nao for fornecido, todas as imagens sao classificadas
    como 'wound' (binario: wound vs no_wound).
    """
    print("\n[Conversao] Segmentacao -> Classificacao...")

    img_dir = seg_dir / "images"
    mask_dir = seg_dir / "masks"

    if not img_dir.exists():
        # Tenta train/images
        img_dir = seg_dir / "train" / "images"
        mask_dir = seg_dir / "train" / "masks"

    if not img_dir.exists():
        print(f"  [ERRO] Diretorio de imagens nao encontrado em {seg_dir}")
        return False

    out = ensure_dir(output_dir)
    wound_dir = ensure_dir(out / "wound")
    no_wound_dir = ensure_dir(out / "no_wound")

    valid_exts = {".jpg", ".jpeg", ".png", ".bmp"}
    wound_count = 0
    no_wound_count = 0

    for img_path in sorted(img_dir.iterdir()):
        if img_path.suffix.lower() not in valid_exts:
            continue

        # Verifica se tem mascara com ferida
        has_wound = False
        if mask_dir.exists():
            for ext in [".png", ".jpg", img_path.suffix]:
                mask_path = mask_dir / f"{img_path.stem}{ext}"
                if mask_path.exists():
                    mask = cv2.imread(str(mask_path), cv2.IMREAD_GRAYSCALE)
                    if mask is not None and np.any(mask > 127):
                        has_wound = True
                    break

        if etiology_labels and img_path.stem in etiology_labels:
            cls = etiology_labels[img_path.stem]
            cls_dir = ensure_dir(out / cls)
            shutil.copy2(str(img_path), str(cls_dir / img_path.name))
        elif has_wound:
            shutil.copy2(str(img_path), str(wound_dir / img_path.name))
            wound_count += 1
        else:
            shutil.copy2(str(img_path), str(no_wound_dir / img_path.name))
            no_wound_count += 1

    print(f"  Wound: {wound_count}, No wound: {no_wound_count}")
    return True


# ---------------------------------------------------------------------------
# Metadata
# ---------------------------------------------------------------------------

def _save_metadata(output_dir: Path, name: str, task: str, extra: Optional[Dict] = None):
    """Salva metadata do dataset preparado."""
    stats = image_stats(output_dir)

    metadata = {
        "name": name,
        "task": task,
        "prepared_at": datetime.now().isoformat(),
        "prepared_by": "REDISUS prepare_wound_datasets.py",
        "image_stats": stats,
        "directory_structure": _dir_tree(output_dir, max_depth=3),
    }

    if extra:
        metadata.update(extra)

    info = DATASETS_REGISTRY.get(name, {})
    if info:
        metadata["source"] = info.get("source", "")
        metadata["license"] = info.get("license", "")
        metadata["description"] = info.get("description", "")

    with open(output_dir / "metadata.json", "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)


def _dir_tree(path: Path, max_depth: int = 3, _depth: int = 0) -> Dict:
    """Gera representacao em arvore do diretorio."""
    if _depth >= max_depth:
        return {"...": "max depth reached"}

    tree = {}
    try:
        for item in sorted(path.iterdir()):
            if item.name.startswith(".") or item.name == "__pycache__":
                continue
            if item.is_dir():
                children = list(item.iterdir())
                file_count = sum(1 for c in children if c.is_file())
                dir_count = sum(1 for c in children if c.is_dir())
                if dir_count > 0:
                    tree[item.name] = _dir_tree(item, max_depth, _depth + 1)
                else:
                    tree[item.name] = f"{file_count} files"
            elif item.suffix == ".json":
                tree[item.name] = "metadata"
    except PermissionError:
        tree["error"] = "permission denied"

    return tree


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="REDISUS - Preparacao de Datasets Publicos de Feridas"
    )
    parser.add_argument(
        "--dataset",
        type=str,
        default=None,
        choices=list(DATASETS_REGISTRY.keys()) + ["all", "local_seg", "local_cls"],
        help="Dataset para preparar (ou 'all' para todos, 'local_seg/local_cls' para local)"
    )
    parser.add_argument("--source", type=str, default=None,
                        help="Diretorio fonte com os dados brutos (clonados/baixados)")
    parser.add_argument("--output", type=str, default="data/datasets",
                        help="Diretorio de saida para datasets preparados")
    parser.add_argument("--name", type=str, default="custom",
                        help="Nome para dataset local")
    parser.add_argument("--split", action="store_true",
                        help="Criar split train/val automatico")
    parser.add_argument("--val-ratio", type=float, default=0.2,
                        help="Proporcao do split de validacao (padrao: 0.2)")
    parser.add_argument("--list", action="store_true",
                        help="Lista datasets disponiveis")
    parser.add_argument("--validate", type=str, default=None,
                        help="Valida um dataset ja preparado")

    args = parser.parse_args()

    if args.list:
        list_datasets()
        return

    if args.validate:
        validate_dir = Path(args.validate)
        print(f"Validando: {validate_dir}")
        stats = image_stats(validate_dir)
        print(f"  Imagens: {stats}")

        for subdir in ["images", "masks", "train/images", "train/masks"]:
            p = validate_dir / subdir
            if p.exists():
                count = sum(1 for f in p.iterdir() if f.is_file())
                print(f"  {subdir}: {count} arquivos")

        if (validate_dir / "images").exists() and (validate_dir / "masks").exists():
            val = validate_masks(validate_dir / "images", validate_dir / "masks")
            print(f"  Pares validos: {val['matched_pairs']}")
            if val["images_without_mask"] > 0:
                print(f"  Sem mascara: {val['images_without_mask']}")
        return

    if args.dataset is None:
        parser.print_help()
        return

    output_dir = Path(args.output)
    ensure_dir(output_dir)

    if args.dataset == "fuseg":
        source = Path(args.source) if args.source else Path("data/raw/fuseg")
        prepare_fuseg(source, output_dir)

    elif args.dataset == "local_seg":
        source = Path(args.source) if args.source else None
        if source is None:
            print("ERRO: --source obrigatorio para dataset local")
            return
        prepare_local_segmentation(source, output_dir, args.name)

    elif args.dataset == "local_cls":
        source = Path(args.source) if args.source else None
        if source is None:
            print("ERRO: --source obrigatorio para dataset local")
            return
        prepare_local_classification(source, output_dir, args.name)

    elif args.dataset == "all":
        print("Preparando todos os datasets disponiveis...")
        print("NOTA: Os datasets devem ser baixados manualmente antes.")
        print(f"Coloque-os em subpastas de: data/raw/\n")

        for ds_name in DATASETS_REGISTRY:
            raw_dir = Path(f"data/raw/{ds_name}")
            if raw_dir.exists():
                if DATASETS_REGISTRY[ds_name]["task"] == "segmentation":
                    prepare_local_segmentation(raw_dir, output_dir, ds_name)
                else:
                    prepare_local_classification(raw_dir, output_dir, ds_name)
            else:
                print(f"  [{ds_name}] IGNORADO - fonte nao encontrada em {raw_dir}")

    else:
        # Dataset especifico do registro
        source = Path(args.source) if args.source else Path(f"data/raw/{args.dataset}")
        info = DATASETS_REGISTRY[args.dataset]
        if info["task"] == "segmentation":
            prepare_local_segmentation(source, output_dir, args.dataset)
        else:
            prepare_local_classification(source, output_dir, args.dataset)

    print("\nPreparacao concluida!")
    print(f"Datasets em: {output_dir.resolve()}")
    print("\nProximo passo:")
    print("  Fine-tuning MedSAM:     python src/training/medsam_finetuning.py --data_dir <dataset>")
    print("  Fine-tuning DermaIntel: python src/training/ensemble_finetuning.py --model dermaintel --data_dir <dataset>")
    print("  Fine-tuning BiomedCLIP: python src/training/ensemble_finetuning.py --model biomedclip --data_dir <dataset>")


if __name__ == "__main__":
    main()
