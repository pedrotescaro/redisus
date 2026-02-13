"""
REDISUS - Preparação de Dataset YOLO para Detecção de Feridas

Converte imagens do dataset medetec para formato YOLO:
- Cria estrutura train/val com images/ e labels/
- Gera bounding boxes usando detecção OpenCV (ou anotações manuais se existirem)
- Aplica split train/val automático

Uso:
    python scripts/prepare_yolo_dataset.py
    python scripts/prepare_yolo_dataset.py --split 0.8 --output dataset/yolo_wounds
"""
import argparse
import json
import random
import shutil
from pathlib import Path
from typing import List, Tuple, Optional, Dict

import cv2
import numpy as np
from loguru import logger


def detect_wound_bbox(image: np.ndarray, min_area: float = 0.01) -> Optional[Tuple[float, float, float, float]]:
    """
    Detecta bounding box da ferida usando segmentação por cor.
    
    Args:
        image: Imagem BGR
        min_area: Área mínima relativa da ferida (0-1)
        
    Returns:
        Tupla (x_center, y_center, width, height) normalizada [0-1] ou None
    """
    h, w = image.shape[:2]
    
    # Converte para HSV
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    
    # Máscaras para diferentes cores de ferida
    masks = []
    
    # Vermelho (granulação) - dois ranges devido ao wrap-around do H
    red_lower1 = np.array([0, 50, 50])
    red_upper1 = np.array([10, 255, 255])
    red_lower2 = np.array([160, 50, 50])
    red_upper2 = np.array([180, 255, 255])
    mask_red = cv2.inRange(hsv, red_lower1, red_upper1) | cv2.inRange(hsv, red_lower2, red_upper2)
    masks.append(mask_red)
    
    # Amarelo (esfacelo)
    yellow_lower = np.array([15, 50, 50])
    yellow_upper = np.array([35, 255, 255])
    mask_yellow = cv2.inRange(hsv, yellow_lower, yellow_upper)
    masks.append(mask_yellow)
    
    # Marrom/Preto (necrose) - baixa saturação e valor
    # Para necrose, usamos threshold em escala de cinza
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    _, mask_dark = cv2.threshold(gray, 60, 255, cv2.THRESH_BINARY_INV)
    masks.append(mask_dark)
    
    # Rosa/Marrom claro (bordas, pele lesionada)
    pink_lower = np.array([0, 20, 100])
    pink_upper = np.array([20, 150, 255])
    mask_pink = cv2.inRange(hsv, pink_lower, pink_upper)
    masks.append(mask_pink)
    
    # Combina todas as máscaras
    combined_mask = np.zeros((h, w), dtype=np.uint8)
    for mask in masks:
        combined_mask = cv2.bitwise_or(combined_mask, mask)
    
    # Operações morfológicas para limpar ruído
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
    combined_mask = cv2.morphologyEx(combined_mask, cv2.MORPH_CLOSE, kernel, iterations=2)
    combined_mask = cv2.morphologyEx(combined_mask, cv2.MORPH_OPEN, kernel, iterations=1)
    
    # Encontra contornos
    contours, _ = cv2.findContours(combined_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    if not contours:
        return None
    
    # Filtra por área mínima
    min_area_pixels = min_area * h * w
    valid_contours = [c for c in contours if cv2.contourArea(c) >= min_area_pixels]
    
    if not valid_contours:
        return None
    
    # Pega o maior contorno ou combina todos
    if len(valid_contours) == 1:
        x, y, bw, bh = cv2.boundingRect(valid_contours[0])
    else:
        # Combina contornos próximos
        all_points = np.vstack(valid_contours)
        x, y, bw, bh = cv2.boundingRect(all_points)
    
    # Adiciona margem de 5%
    margin = 0.05
    x = max(0, x - int(bw * margin))
    y = max(0, y - int(bh * margin))
    bw = min(w - x, int(bw * (1 + 2 * margin)))
    bh = min(h - y, int(bh * (1 + 2 * margin)))
    
    # Converte para formato YOLO (normalizado, centro)
    x_center = (x + bw / 2) / w
    y_center = (y + bh / 2) / h
    width = bw / w
    height = bh / h
    
    # Valida valores
    if width < 0.05 or height < 0.05:  # Muito pequeno
        return None
    if width > 0.95 or height > 0.95:  # Muito grande (provavelmente erro)
        return None
    
    return (x_center, y_center, width, height)


def prepare_yolo_dataset(
    source_dir: str,
    output_dir: str,
    train_split: float = 0.8,
    min_images_per_class: int = 3,
    skip_detection_errors: bool = True
) -> Dict:
    """
    Prepara dataset YOLO a partir das imagens do medetec.
    
    Args:
        source_dir: Diretório fonte (dataset/medetec)
        output_dir: Diretório de saída (dataset/yolo_wounds)
        train_split: Proporção para treino (0-1)
        min_images_per_class: Mínimo de imagens por classe para incluir
        skip_detection_errors: Se True, pula imagens sem detecção
        
    Returns:
        Estatísticas do dataset
    """
    source_path = Path(source_dir)
    output_path = Path(output_dir)
    
    # Cria estrutura de diretórios
    train_img_dir = output_path / "train" / "images"
    train_label_dir = output_path / "train" / "labels"
    val_img_dir = output_path / "val" / "images"
    val_label_dir = output_path / "val" / "labels"
    
    for d in [train_img_dir, train_label_dir, val_img_dir, val_label_dir]:
        d.mkdir(parents=True, exist_ok=True)
    
    # Coleta todas as imagens
    all_images = []
    image_extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.webp'}
    
    logger.info(f"Buscando imagens em: {source_path}")
    
    for category_dir in source_path.iterdir():
        if not category_dir.is_dir():
            continue
        if category_dir.name.startswith('.') or category_dir.name == '__pycache__':
            continue
            
        category_images = []
        for img_path in category_dir.iterdir():
            if img_path.suffix.lower() in image_extensions:
                category_images.append({
                    'path': img_path,
                    'category': category_dir.name
                })
        
        if len(category_images) >= min_images_per_class:
            all_images.extend(category_images)
            logger.info(f"  {category_dir.name}: {len(category_images)} imagens")
    
    logger.info(f"Total de imagens encontradas: {len(all_images)}")
    
    if not all_images:
        logger.error("Nenhuma imagem encontrada!")
        return {}
    
    # Shuffle e split
    random.shuffle(all_images)
    split_idx = int(len(all_images) * train_split)
    train_images = all_images[:split_idx]
    val_images = all_images[split_idx:]
    
    logger.info(f"Split: {len(train_images)} treino, {len(val_images)} validação")
    
    # Processa imagens
    stats = {
        'total': len(all_images),
        'train': 0,
        'val': 0,
        'detection_success': 0,
        'detection_failed': 0,
        'categories': {}
    }
    
    def process_split(images: List[Dict], img_dir: Path, label_dir: Path, split_name: str):
        processed = 0
        for i, img_info in enumerate(images):
            img_path = img_info['path']
            category = img_info['category']
            
            # Carrega imagem
            image = cv2.imread(str(img_path))
            if image is None:
                logger.warning(f"Erro ao carregar: {img_path}")
                continue
            
            # Detecta bounding box
            bbox = detect_wound_bbox(image)
            
            if bbox is None:
                stats['detection_failed'] += 1
                if skip_detection_errors:
                    continue
                # Se não pular, usa bbox da imagem inteira com margem
                bbox = (0.5, 0.5, 0.8, 0.8)
            else:
                stats['detection_success'] += 1
            
            # Nome do arquivo (único)
            base_name = f"{category}_{img_path.stem}_{i:04d}"
            
            # Copia imagem
            new_img_path = img_dir / f"{base_name}.jpg"
            cv2.imwrite(str(new_img_path), image)
            
            # Cria label YOLO
            x_center, y_center, width, height = bbox
            label_path = label_dir / f"{base_name}.txt"
            with open(label_path, 'w') as f:
                f.write(f"0 {x_center:.6f} {y_center:.6f} {width:.6f} {height:.6f}\n")
            
            processed += 1
            
            # Atualiza stats por categoria
            if category not in stats['categories']:
                stats['categories'][category] = {'train': 0, 'val': 0}
            stats['categories'][category][split_name] += 1
            
            if (i + 1) % 50 == 0:
                logger.info(f"  {split_name}: {i + 1}/{len(images)} processadas")
        
        return processed
    
    logger.info("Processando conjunto de treino...")
    stats['train'] = process_split(train_images, train_img_dir, train_label_dir, 'train')
    
    logger.info("Processando conjunto de validação...")
    stats['val'] = process_split(val_images, val_img_dir, val_label_dir, 'val')
    
    # Atualiza data.yaml
    data_yaml_path = output_path / "data.yaml"
    data_yaml_content = f"""# REDISUS - YOLOv8 Wound Detection Dataset
# Gerado automaticamente em {__import__('datetime').datetime.now().isoformat()}

path: {output_path.absolute()}
train: train/images
val: val/images

# Classes
nc: 1
names:
  0: wound

# Estatísticas
# Total: {stats['train'] + stats['val']} imagens
# Treino: {stats['train']}
# Validação: {stats['val']}
"""
    
    with open(data_yaml_path, 'w') as f:
        f.write(data_yaml_content)
    
    logger.info(f"data.yaml atualizado: {data_yaml_path}")
    
    # Salva estatísticas
    stats_path = output_path / "dataset_stats.json"
    with open(stats_path, 'w') as f:
        json.dump(stats, f, indent=2)
    
    logger.info(f"Estatísticas salvas: {stats_path}")
    
    return stats


def visualize_detection(
    source_dir: str,
    num_samples: int = 5,
    output_dir: str = "output/detection_preview"
):
    """Visualiza detecções para verificação manual"""
    source_path = Path(source_dir)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Coleta algumas imagens
    images = []
    for category_dir in source_path.iterdir():
        if category_dir.is_dir() and not category_dir.name.startswith('.'):
            for img_path in category_dir.iterdir():
                if img_path.suffix.lower() in {'.jpg', '.jpeg', '.png'}:
                    images.append(img_path)
                    if len(images) >= num_samples * 5:
                        break
    
    random.shuffle(images)
    images = images[:num_samples]
    
    for img_path in images:
        image = cv2.imread(str(img_path))
        if image is None:
            continue
        
        h, w = image.shape[:2]
        bbox = detect_wound_bbox(image)
        
        # Desenha bbox
        vis = image.copy()
        if bbox:
            x_center, y_center, bw, bh = bbox
            x1 = int((x_center - bw/2) * w)
            y1 = int((y_center - bh/2) * h)
            x2 = int((x_center + bw/2) * w)
            y2 = int((y_center + bh/2) * h)
            cv2.rectangle(vis, (x1, y1), (x2, y2), (0, 255, 0), 2)
            cv2.putText(vis, "wound", (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        else:
            cv2.putText(vis, "NO DETECTION", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
        
        output_file = output_path / f"{img_path.parent.name}_{img_path.name}"
        cv2.imwrite(str(output_file), vis)
        logger.info(f"Preview salvo: {output_file}")


def main():
    parser = argparse.ArgumentParser(description="Prepara dataset YOLO para detecção de feridas")
    parser.add_argument(
        "--source", "-s",
        default="dataset/medetec",
        help="Diretório fonte com imagens"
    )
    parser.add_argument(
        "--output", "-o",
        default="dataset/yolo_wounds",
        help="Diretório de saída YOLO"
    )
    parser.add_argument(
        "--split",
        type=float,
        default=0.8,
        help="Proporção para treino (default: 0.8)"
    )
    parser.add_argument(
        "--preview",
        action="store_true",
        help="Gera preview de detecções para verificação"
    )
    parser.add_argument(
        "--preview-samples",
        type=int,
        default=10,
        help="Número de amostras para preview"
    )
    parser.add_argument(
        "--keep-all",
        action="store_true",
        help="Manter imagens sem detecção usando bbox padrão (0.5, 0.5, 0.8, 0.8)"
    )
    
    args = parser.parse_args()
    
    if args.preview:
        logger.info("Gerando preview de detecções...")
        visualize_detection(args.source, args.preview_samples)
    else:
        logger.info("Preparando dataset YOLO...")
        stats = prepare_yolo_dataset(
            args.source,
            args.output,
            train_split=args.split,
            skip_detection_errors=not args.keep_all
        )
        
        if stats:
            logger.info("=" * 50)
            logger.info("Dataset preparado com sucesso!")
            logger.info(f"  Treino: {stats['train']} imagens")
            logger.info(f"  Validação: {stats['val']} imagens")
            logger.info(f"  Detecções bem-sucedidas: {stats['detection_success']}")
            logger.info(f"  Detecções falhas: {stats['detection_failed']}")
            logger.info("=" * 50)
            logger.info(f"Próximo passo: python scripts/train_yolo_wound.py")


if __name__ == "__main__":
    main()
