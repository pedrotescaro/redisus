"""
REDISUS - Utilitários de Imagem

Funções auxiliares para processamento e visualização de imagens.
"""
import cv2
import numpy as np
from typing import List, Tuple, Optional


def resize_with_aspect_ratio(
    image: np.ndarray,
    width: Optional[int] = None,
    height: Optional[int] = None,
    inter: int = cv2.INTER_AREA
) -> np.ndarray:
    """
    Redimensiona imagem mantendo aspect ratio.
    
    Args:
        image: Imagem de entrada
        width: Largura desejada (None para calcular automaticamente)
        height: Altura desejada (None para calcular automaticamente)
        inter: Método de interpolação
        
    Returns:
        Imagem redimensionada
    """
    h, w = image.shape[:2]
    
    if width is None and height is None:
        return image
    
    if width is None:
        ratio = height / float(h)
        dim = (int(w * ratio), height)
    else:
        ratio = width / float(w)
        dim = (width, int(h * ratio))
    
    return cv2.resize(image, dim, interpolation=inter)


def create_side_by_side(
    images: List[np.ndarray],
    labels: Optional[List[str]] = None,
    spacing: int = 10
) -> np.ndarray:
    """
    Cria visualização lado a lado de múltiplas imagens.
    
    Args:
        images: Lista de imagens
        labels: Labels opcionais para cada imagem
        spacing: Espaçamento entre imagens
        
    Returns:
        Imagem combinada
    """
    if not images:
        return np.zeros((100, 100, 3), dtype=np.uint8)
    
    # Encontra altura máxima
    max_height = max(img.shape[0] for img in images)
    
    # Redimensiona e converte para BGR se necessário
    processed = []
    for img in images:
        # Resize para mesma altura
        if img.shape[0] != max_height:
            ratio = max_height / img.shape[0]
            new_width = int(img.shape[1] * ratio)
            img = cv2.resize(img, (new_width, max_height))
        
        # Converte para 3 canais se necessário
        if len(img.shape) == 2:
            img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
        
        processed.append(img)
    
    # Calcula largura total
    total_width = sum(img.shape[1] for img in processed) + spacing * (len(processed) - 1)
    
    # Cria canvas
    canvas = np.zeros((max_height + 30 if labels else max_height, total_width, 3), dtype=np.uint8)
    
    # Posiciona imagens
    x = 0
    for i, img in enumerate(processed):
        canvas[:max_height, x:x+img.shape[1]] = img
        
        if labels and i < len(labels):
            cv2.putText(
                canvas,
                labels[i],
                (x + 10, max_height + 20),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (255, 255, 255),
                1
            )
        
        x += img.shape[1] + spacing
    
    return canvas


def apply_colormap(
    mask: np.ndarray,
    colormap: np.ndarray
) -> np.ndarray:
    """
    Aplica colormap a uma máscara de segmentação.
    
    Args:
        mask: Máscara com valores de classe (0, 1, 2, ...)
        colormap: Array (num_classes, 3) com cores RGB
        
    Returns:
        Imagem colorida
    """
    colored = colormap[mask]
    return colored.astype(np.uint8)


def draw_legend(
    image: np.ndarray,
    labels: List[str],
    colors: List[Tuple[int, int, int]],
    position: str = "top-right"
) -> np.ndarray:
    """
    Desenha legenda na imagem.
    
    Args:
        image: Imagem de entrada
        labels: Lista de labels
        colors: Lista de cores (BGR)
        position: Posição ("top-right", "top-left", "bottom-right", "bottom-left")
        
    Returns:
        Imagem com legenda
    """
    result = image.copy()
    h, w = result.shape[:2]
    
    # Dimensões da legenda
    legend_h = 25 * len(labels) + 20
    legend_w = max(len(label) for label in labels) * 10 + 40
    
    # Posição
    if "top" in position:
        y = 10
    else:
        y = h - legend_h - 10
    
    if "right" in position:
        x = w - legend_w - 10
    else:
        x = 10
    
    # Background
    overlay = result.copy()
    cv2.rectangle(overlay, (x, y), (x + legend_w, y + legend_h), (0, 0, 0), -1)
    cv2.addWeighted(overlay, 0.7, result, 0.3, 0, result)
    
    # Items
    for i, (label, color) in enumerate(zip(labels, colors)):
        item_y = y + 20 + i * 25
        
        # Quadrado de cor
        cv2.rectangle(
            result,
            (x + 10, item_y - 10),
            (x + 25, item_y + 5),
            color,
            -1
        )
        
        # Label
        cv2.putText(
            result,
            label,
            (x + 35, item_y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (255, 255, 255),
            1
        )
    
    return result


def enhance_image(
    image: np.ndarray,
    brightness: float = 0,
    contrast: float = 1.0,
    saturation: float = 1.0
) -> np.ndarray:
    """
    Ajusta brilho, contraste e saturação de uma imagem.
    
    Args:
        image: Imagem BGR
        brightness: Ajuste de brilho (-100 a 100)
        contrast: Multiplicador de contraste (0.5 a 2.0)
        saturation: Multiplicador de saturação (0.0 a 2.0)
        
    Returns:
        Imagem ajustada
    """
    result = image.astype(np.float32)
    
    # Brilho e contraste
    result = contrast * result + brightness
    result = np.clip(result, 0, 255)
    
    # Saturação
    if saturation != 1.0:
        hsv = cv2.cvtColor(result.astype(np.uint8), cv2.COLOR_BGR2HSV).astype(np.float32)
        hsv[:, :, 1] = np.clip(hsv[:, :, 1] * saturation, 0, 255)
        result = cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2BGR)
    
    return result.astype(np.uint8)


def calculate_image_quality_score(image: np.ndarray) -> dict:
    """
    Calcula métricas de qualidade de uma imagem.
    
    Returns:
        Dict com scores de qualidade
    """
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    
    # Blur score (variância do Laplaciano)
    laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
    
    # Brightness
    brightness = np.mean(gray)
    
    # Contrast
    contrast = np.std(gray)
    
    # Overall score (0-100)
    blur_score = min(100, laplacian_var / 10)
    brightness_score = 100 - abs(brightness - 127) / 1.27  # Ideal: 127
    contrast_score = min(100, contrast / 0.64)
    
    overall = (blur_score + brightness_score + contrast_score) / 3
    
    return {
        "overall": round(overall, 1),
        "sharpness": round(blur_score, 1),
        "brightness": round(brightness_score, 1),
        "contrast": round(contrast_score, 1),
        "is_acceptable": overall > 50
    }
