"""
REDISUS - Criação da Estrutura de Diretórios para Treinamento

Cria a hierarquia de pastas esperada pelos scripts:
  - train_yolo_wound.py   → dataset/yolo_wounds/
  - train_unet_tissue.py  → dataset/tissue_segmentation/

Uso:
    python scripts/setup_dataset_structure.py
    python scripts/setup_dataset_structure.py --test-split 0.1
"""
import argparse
import json
from pathlib import Path
from datetime import datetime

from loguru import logger


# ==============================================================================
#  Estrutura YOLO (detecção de ferida)
# ==============================================================================
#
#  dataset/yolo_wounds/
#  ├── data.yaml            ← lido por Ultralytics
#  ├── train/
#  │   ├── images/          ← .jpg / .png (640×640 recomendado)
#  │   └── labels/          ← .txt  (class x_center y_center w h) normalizado
#  ├── val/
#  │   ├── images/
#  │   └── labels/
#  └── test/                ← opcional, para avaliação final
#      ├── images/
#      └── labels/
#
# ==============================================================================
#  Estrutura U-Net (segmentação de tecidos)
# ==============================================================================
#
#  dataset/tissue_segmentation/
#  ├── train/
#  │   ├── images/          ← .jpg / .png (256×256 ou 512×512)
#  │   └── masks/           ← .png single-channel, pixels 0-4
#  ├── val/
#  │   ├── images/
#  │   └── masks/
#  └── test/
#      ├── images/
#      └── masks/
#
#  Classes da máscara (valores de pixel):
#    0 = Background
#    1 = Granulação   (tecido saudável, vermelho)
#    2 = Esfacelo     (amarelo/branco)
#    3 = Necrose      (preto)
#    4 = Pele perilesional
# ==============================================================================

YOLO_BASE = Path("dataset/yolo_wounds")
UNET_BASE = Path("dataset/tissue_segmentation")

YOLO_DIRS = [
    YOLO_BASE / "train" / "images",
    YOLO_BASE / "train" / "labels",
    YOLO_BASE / "val" / "images",
    YOLO_BASE / "val" / "labels",
    YOLO_BASE / "test" / "images",
    YOLO_BASE / "test" / "labels",
]

UNET_DIRS = [
    UNET_BASE / "train" / "images",
    UNET_BASE / "train" / "masks",
    UNET_BASE / "val" / "images",
    UNET_BASE / "val" / "masks",
    UNET_BASE / "test" / "images",
    UNET_BASE / "test" / "masks",
]


def create_yolo_data_yaml(base: Path, num_classes: int = 1) -> Path:
    """Gera data.yaml no formato esperado pelo Ultralytics YOLOv8."""
    yaml_path = base / "data.yaml"
    content = f"""# REDISUS - YOLOv8 Wound Detection Dataset
# Gerado por setup_dataset_structure.py em {datetime.now().isoformat()}
#
# INSTRUÇÕES:
#   1. Coloque imagens de feridas em train/images/ e val/images/
#   2. Crie labels .txt correspondentes em train/labels/ e val/labels/
#      Formato por linha: <class_id> <x_center> <y_center> <width> <height>
#      Valores normalizados [0, 1].  class_id = 0 (wound)
#   3. Ou use:  python scripts/prepare_yolo_dataset.py

path: {base.absolute()}
train: train/images
val: val/images
test: test/images

nc: {num_classes}
names:
  0: wound
"""
    yaml_path.write_text(content, encoding="utf-8")
    logger.info(f"data.yaml criado: {yaml_path}")
    return yaml_path


def create_unet_readme(base: Path) -> Path:
    """Cria README com instruções para popular o dataset U-Net."""
    readme = base / "README_DATASET.md"
    content = """# Dataset de Segmentação de Tecidos (U-Net)

## Estrutura esperada

```
tissue_segmentation/
├── train/
│   ├── images/   ← imagens RGB (.jpg ou .png)
│   └── masks/    ← máscaras single-channel (.png)
├── val/
│   ├── images/
│   └── masks/
└── test/
    ├── images/
    └── masks/
```

## Formato das Máscaras

Cada máscara é uma imagem **single-channel (grayscale)** onde o valor de cada
pixel indica a classe do tecido:

| Valor | Classe           | Cor clínica          |
|-------|------------------|----------------------|
| 0     | Background       | —                    |
| 1     | Granulação       | Vermelho vivo        |
| 2     | Esfacelo         | Amarelo/branco       |
| 3     | Necrose          | Preto/marrom escuro  |
| 4     | Pele perilesional| Tom de pele normal   |

## Convenção de nomes

A máscara deve ter o **mesmo nome-base** da imagem com extensão `.png`:

```
images/ferida_001.jpg  →  masks/ferida_001.png
images/ferida_002.png  →  masks/ferida_002.png
```

## Resolução recomendada

- Treinamento: **256×256** ou **512×512** (configurável via `--imgsz`)
- Use o script `scripts/preprocess_dataset.py` para redimensionar automaticamente.

## Dicas para anotação

- Use ferramentas como **LabelMe**, **CVAT** ou **Supervisely** para criar
  máscaras de segmentação.
- Exporte como PNG single-channel com valores 0-4.
- Garanta que cada imagem tenha uma máscara correspondente.
"""
    readme.write_text(content, encoding="utf-8")
    logger.info(f"README criado: {readme}")
    return readme


def create_split_stats(base: Path, splits: list) -> Path:
    """Cria arquivo de estatísticas (preenchido após popular os dados)."""
    stats = {
        "created_at": datetime.now().isoformat(),
        "splits": {},
    }
    for split in splits:
        img_dir = base / split / "images"
        images = (
            list(img_dir.glob("*.jpg"))
            + list(img_dir.glob("*.jpeg"))
            + list(img_dir.glob("*.png"))
        ) if img_dir.exists() else []
        stats["splits"][split] = {"num_images": len(images)}

    stats_path = base / "dataset_stats.json"
    stats_path.write_text(json.dumps(stats, indent=2), encoding="utf-8")
    return stats_path


def setup(include_test: bool = True):
    """Cria toda a estrutura de diretórios."""
    logger.info("=" * 60)
    logger.info("REDISUS - Setup da Estrutura de Dataset")
    logger.info("=" * 60)

    # --- YOLO ---
    logger.info("\n[YOLO] Criando estrutura para detecção de feridas...")
    dirs_to_create = YOLO_DIRS if include_test else YOLO_DIRS[:4]
    for d in dirs_to_create:
        d.mkdir(parents=True, exist_ok=True)
        logger.info(f"  ✓ {d}")

    create_yolo_data_yaml(YOLO_BASE)

    # --- U-Net ---
    logger.info("\n[U-Net] Criando estrutura para segmentação de tecidos...")
    dirs_to_create = UNET_DIRS if include_test else UNET_DIRS[:4]
    for d in dirs_to_create:
        d.mkdir(parents=True, exist_ok=True)
        logger.info(f"  ✓ {d}")

    create_unet_readme(UNET_BASE)

    # --- Resumo ---
    logger.info("\n" + "=" * 60)
    logger.info("Estrutura criada com sucesso!")
    logger.info("")
    logger.info("Próximos passos:")
    logger.info("  1. Popule os diretórios com imagens e anotações")
    logger.info("     - YOLO: use 'python scripts/prepare_yolo_dataset.py'")
    logger.info("     - U-Net: anote máscaras com LabelMe/CVAT")
    logger.info("  2. Pré-processe: 'python scripts/preprocess_dataset.py'")
    logger.info("  3. Treine YOLO: 'python scripts/train_yolo_wound.py'")
    logger.info("  4. Treine U-Net: 'python scripts/train_unet_tissue.py'")
    logger.info("=" * 60)


def main():
    parser = argparse.ArgumentParser(
        description="Cria estrutura de diretórios para treinamento YOLO + U-Net"
    )
    parser.add_argument(
        "--no-test", action="store_true",
        help="Não criar diretório test/ (apenas train/ e val/)"
    )
    args = parser.parse_args()

    setup(include_test=not args.no_test)


if __name__ == "__main__":
    main()
