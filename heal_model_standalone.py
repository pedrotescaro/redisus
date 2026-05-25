# -*- coding: utf-8 -*-
from __future__ import annotations
"""
======================================================================
1. README / DOCUMENTACAO
======================================================================
HEAL+ / REDISUS — Analisador Clínico de Feridas (Standalone)

Este script consolida o pipeline explicável de visão computacional 
para análise de feridas em um único arquivo. Ele atua como um motor 
autônomo e headless, sem dependências de PyQt6 ou infraestrutura web.

AVISO CLÍNICO E ÉTICO OBRIGATÓRIO:
Este script realiza uma análise assistiva/experimental para apoio, 
validação e discussão com especialista. Ele não substitui avaliação 
clínica, diagnóstico médico ou decisão terapêutica profissional.

DEPENDÊNCIAS (Python 3.9+ recomendado):
    pip install opencv-python numpy
    pip install torch torchvision (Opcional, apenas se for usar --use-dl)

COMO EXECUTAR:
    Exemplo imagem única:
      python heal_model_standalone.py --input "imagens/paciente1.jpg" --output "outputs/"

    Exemplo pasta de imagens:
      python heal_model_standalone.py --input "imagens_teste/" --output "outputs/"

    Exemplo com Deep Learning Opcional (se existirem modelos/checkpoints):
      python heal_model_standalone.py --input "imagens/" --output "outputs/" --use-dl

CORES DO MAPA DE TECIDOS:
    - Vermelho Intenso: Granulação (Tecido viável, cicatrização)
    - Amarelo/Bege: Esfacelo (Fibrina/Tecido desvitalizado aderido)
    - Preto/Marrom Escuro: Necrose (Escara de coagulação)
    - Rosa Claro: Epitelização (Fechamento e regeneração final)

======================================================================
2. IMPORTS
======================================================================
"""
import os
import sys
import io
import time
import json
import csv
import logging
import argparse
import traceback
from pathlib import Path
from typing import Dict, Optional, Tuple, List, Any, Mapping
from dataclasses import dataclass, field
import cv2
import numpy as np

# Torch is optional for DL pipeline
try:
    import torch
    from torchvision import transforms as _tv_transforms
    _TORCH_AVAILABLE = True
except ImportError:
    _TORCH_AVAILABLE = False

try:
    from PIL import Image, ImageDraw, ImageFont
    _PIL_AVAILABLE = True
except ImportError:
    _PIL_AVAILABLE = False

logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

# ======================================================================
# 3. DATACLASSES E 4. CONFIGURACOES CLINICAS (Incluidos da extracao)
# ======================================================================

# ============================================================
# Extracted from: src/processing/image_processor.py
# ============================================================

"""
REDISUS - Sistema de Diagnóstico de Feridas
Processador de Imagens

Implementa pipeline de pré-processamento e normalização de imagens
para análise de feridas.
"""
import cv2
import numpy as np
from dataclasses import dataclass
from typing import Tuple, Optional, List, Callable
from enum import Enum
from loguru import logger


class ColorSpace(Enum):
    """Espaços de cor suportados"""
    BGR = "bgr"
    RGB = "rgb"
    HSV = "hsv"
    LAB = "lab"
    GRAY = "gray"


@dataclass
class ImageQuality:
    """Métricas de qualidade da imagem"""
    brightness: float  # 0-1
    contrast: float    # 0-1
    sharpness: float   # 0-1
    is_blurry: bool
    is_overexposed: bool
    is_underexposed: bool
    quality_score: float  # 0-1
    issues: List[str]


class ImageProcessor:
    """
    Processador de imagens para análise de feridas.
    
    Funcionalidades:
    - Correção de iluminação
    - Normalização de cor
    - Redução de ruído
    - Realce de contraste
    - Verificação de qualidade
    """
    
    def __init__(self):
        # CLAHE para equalização adaptativa
        self.clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        
    def normalize(
        self,
        image: np.ndarray,
        target_size: Optional[Tuple[int, int]] = None,
        normalize_values: bool = True
    ) -> np.ndarray:
        """
        Normaliza imagem para processamento.
        
        Args:
            image: Imagem BGR
            target_size: Tamanho alvo (width, height)
            normalize_values: Se deve normalizar para [0, 1]
            
        Returns:
            Imagem normalizada
        """
        output = image.copy()
        
        # Resize se necessário
        if target_size:
            output = cv2.resize(output, target_size)
            
        # Normaliza valores
        if normalize_values:
            output = output.astype(np.float32) / 255.0
            
        return output
    
    def denoise(
        self,
        image: np.ndarray,
        strength: float = 10.0
    ) -> np.ndarray:
        """
        Remove ruído da imagem.
        
        Args:
            image: Imagem BGR
            strength: Força do denoising
            
        Returns:
            Imagem sem ruído
        """
        return cv2.fastNlMeansDenoisingColored(
            image,
            None,
            strength,
            strength,
            7,
            21
        )
    
    def enhance_contrast(
        self,
        image: np.ndarray,
        method: str = "clahe"
    ) -> np.ndarray:
        """
        Melhora contraste da imagem.
        
        Args:
            image: Imagem BGR
            method: "clahe", "histogram", "adaptive"
            
        Returns:
            Imagem com contraste melhorado
        """
        if method == "clahe":
            # Aplica CLAHE no canal L do LAB
            lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
            lab[:, :, 0] = self.clahe.apply(lab[:, :, 0])
            return cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)
            
        elif method == "histogram":
            # Equalização de histograma simples
            ycrcb = cv2.cvtColor(image, cv2.COLOR_BGR2YCrCb)
            ycrcb[:, :, 0] = cv2.equalizeHist(ycrcb[:, :, 0])
            return cv2.cvtColor(ycrcb, cv2.COLOR_YCrCb2BGR)
            
        elif method == "adaptive":
            # Normalização adaptativa
            return cv2.normalize(image, None, 0, 255, cv2.NORM_MINMAX)
            
        return image
    
    def correct_illumination(
        self,
        image: np.ndarray,
        blur_size: int = 51
    ) -> np.ndarray:
        """
        Corrige iluminação não uniforme.
        
        Usa divisão por background estimado.
        
        Args:
            image: Imagem BGR
            blur_size: Tamanho do blur para estimar background
            
        Returns:
            Imagem com iluminação corrigida
        """
        # Converte para LAB
        lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
        l_channel = lab[:, :, 0].astype(np.float32)
        
        # Estima background com blur grande
        background = cv2.GaussianBlur(l_channel, (blur_size, blur_size), 0)
        
        # Divide pelo background
        corrected = l_channel / (background + 1e-6) * 127.5
        corrected = np.clip(corrected, 0, 255).astype(np.uint8)
        
        lab[:, :, 0] = corrected
        return cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)
    
    def white_balance(self, image: np.ndarray) -> np.ndarray:
        """
        Aplica correção de balanço de branco.
        
        Usa método gray-world.
        """
        # Calcula média de cada canal
        b, g, r = cv2.split(image.astype(np.float32))
        
        r_avg = np.mean(r)
        g_avg = np.mean(g)
        b_avg = np.mean(b)
        
        # Calcula fatores de correção
        gray_avg = (r_avg + g_avg + b_avg) / 3
        
        r = r * (gray_avg / (r_avg + 1e-6))
        g = g * (gray_avg / (g_avg + 1e-6))
        b = b * (gray_avg / (b_avg + 1e-6))
        
        # Limita valores
        r = np.clip(r, 0, 255)
        g = np.clip(g, 0, 255)
        b = np.clip(b, 0, 255)
        
        return cv2.merge([b, g, r]).astype(np.uint8)
    
    def sharpen(
        self,
        image: np.ndarray,
        strength: float = 1.0
    ) -> np.ndarray:
        """
        Aumenta nitidez da imagem.
        
        Args:
            image: Imagem BGR
            strength: Força do sharpening (0-2)
            
        Returns:
            Imagem mais nítida
        """
        # Kernel de sharpening
        kernel = np.array([
            [-1, -1, -1],
            [-1,  9, -1],
            [-1, -1, -1]
        ]) * strength
        
        kernel[1, 1] = 1 + (8 * strength)
        
        return cv2.filter2D(image, -1, kernel)
    
    def assess_quality(self, image: np.ndarray) -> ImageQuality:
        """
        Avalia qualidade da imagem para diagnóstico.
        
        Args:
            image: Imagem BGR
            
        Returns:
            ImageQuality com métricas e issues
        """
        issues = []
        
        # Converte para grayscale
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        # Brilho (média de intensidade)
        brightness = np.mean(gray) / 255.0
        
        is_underexposed = brightness < 0.25
        is_overexposed = brightness > 0.85
        
        if is_underexposed:
            issues.append("Imagem muito escura")
        if is_overexposed:
            issues.append("Imagem muito clara/superexposta")
            
        # Contraste (desvio padrão)
        contrast = np.std(gray) / 127.5
        contrast = min(contrast, 1.0)
        
        if contrast < 0.2:
            issues.append("Baixo contraste")
            
        # Nitidez (variância do Laplaciano)
        laplacian = cv2.Laplacian(gray, cv2.CV_64F)
        sharpness = np.var(laplacian) / 1000
        sharpness = min(sharpness, 1.0)
        
        is_blurry = sharpness < 0.15
        
        if is_blurry:
            issues.append("Imagem desfocada")
            
        # Score geral
        quality_score = (
            0.3 * (0.5 - abs(brightness - 0.5)) * 2 +  # Brilho ideal = 0.5
            0.3 * contrast +
            0.4 * sharpness
        )
        quality_score = max(0, min(quality_score, 1.0))
        
        if quality_score < 0.4:
            issues.append("Qualidade geral baixa para diagnóstico")
            
        return ImageQuality(
            brightness=brightness,
            contrast=contrast,
            sharpness=sharpness,
            is_blurry=is_blurry,
            is_overexposed=is_overexposed,
            is_underexposed=is_underexposed,
            quality_score=quality_score,
            issues=issues
        )
    
    def convert_color(
        self,
        image: np.ndarray,
        target_space: ColorSpace
    ) -> np.ndarray:
        """Converte para espaço de cor especificado"""
        conversions = {
            ColorSpace.RGB: cv2.COLOR_BGR2RGB,
            ColorSpace.HSV: cv2.COLOR_BGR2HSV,
            ColorSpace.LAB: cv2.COLOR_BGR2LAB,
            ColorSpace.GRAY: cv2.COLOR_BGR2GRAY,
        }
        
        if target_space == ColorSpace.BGR:
            return image
            
        if target_space in conversions:
            return cv2.cvtColor(image, conversions[target_space])
            
        return image


class PreprocessingPipeline:
    """
    Pipeline configurável de pré-processamento.
    
    Permite encadear múltiplas operações de forma flexível.
    
    Uso:
        pipeline = PreprocessingPipeline()
        pipeline.add_step("denoise", strength=10)
        pipeline.add_step("enhance_contrast", method="clahe")
        pipeline.add_step("resize", size=(512, 512))
        
        processed = pipeline.apply(image)
    """
    
    def __init__(self):
        self.processor = ImageProcessor()
        self._steps: List[Tuple[str, dict]] = []
        
    def add_step(self, operation: str, **kwargs):
        """
        Adiciona passo ao pipeline.
        
        Operações disponíveis:
        - resize: size=(w, h)
        - denoise: strength=10
        - enhance_contrast: method="clahe"
        - correct_illumination: blur_size=51
        - white_balance: (sem parâmetros)
        - sharpen: strength=1.0
        - normalize: normalize_values=True
        """
        self._steps.append((operation, kwargs))
        return self  # Permite encadeamento
    
    def clear(self):
        """Limpa todos os passos"""
        self._steps.clear()
        return self
    
    def apply(self, image: np.ndarray) -> np.ndarray:
        """
        Aplica pipeline completo na imagem.
        
        Args:
            image: Imagem BGR
            
        Returns:
            Imagem processada
        """
        output = image.copy()
        
        for operation, kwargs in self._steps:
            try:
                if operation == "resize":
                    size = kwargs.get("size", (512, 512))
                    output = cv2.resize(output, size)
                    
                elif operation == "denoise":
                    strength = kwargs.get("strength", 10)
                    output = self.processor.denoise(output, strength)
                    
                elif operation == "enhance_contrast":
                    method = kwargs.get("method", "clahe")
                    output = self.processor.enhance_contrast(output, method)
                    
                elif operation == "correct_illumination":
                    blur_size = kwargs.get("blur_size", 51)
                    output = self.processor.correct_illumination(output, blur_size)
                    
                elif operation == "white_balance":
                    output = self.processor.white_balance(output)
                    
                elif operation == "sharpen":
                    strength = kwargs.get("strength", 1.0)
                    output = self.processor.sharpen(output, strength)
                    
                elif operation == "normalize":
                    target_size = kwargs.get("size")
                    normalize_values = kwargs.get("normalize_values", True)
                    output = self.processor.normalize(output, target_size, normalize_values)
                    
            except Exception as e:
                logger.warning(f"Erro na operação '{operation}': {e}")
                
        return output
    
    @staticmethod
    def create_medical_pipeline() -> "PreprocessingPipeline":
        """
        Cria pipeline otimizado para imagens médicas.
        """
        pipeline = PreprocessingPipeline()
        pipeline.add_step("denoise", strength=7)
        pipeline.add_step("correct_illumination", blur_size=51)
        pipeline.add_step("white_balance")
        pipeline.add_step("enhance_contrast", method="clahe")
        return pipeline
    
    @staticmethod
    def create_realtime_pipeline() -> "PreprocessingPipeline":
        """
        Cria pipeline leve para tempo real.
        """
        pipeline = PreprocessingPipeline()
        pipeline.add_step("enhance_contrast", method="clahe")
        return pipeline


def extract_roi(
    image: np.ndarray,
    bbox: Tuple[int, int, int, int],
    padding: int = 20
) -> np.ndarray:
    """
    Extrai região de interesse com padding.
    
    Args:
        image: Imagem BGR
        bbox: (x1, y1, x2, y2)
        padding: Pixels de padding ao redor
        
    Returns:
        ROI extraída
    """
    h, w = image.shape[:2]
    x1, y1, x2, y2 = bbox
    
    # Adiciona padding
    x1 = max(0, x1 - padding)
    y1 = max(0, y1 - padding)
    x2 = min(w, x2 + padding)
    y2 = min(h, y2 + padding)
    
    return image[y1:y2, x1:x2].copy()


def resize_with_aspect_ratio(
    image: np.ndarray,
    max_size: int = 1024,
    min_size: int = 256
) -> np.ndarray:
    """
    Redimensiona mantendo aspect ratio.
    
    Args:
        image: Imagem
        max_size: Tamanho máximo do maior lado
        min_size: Tamanho mínimo do menor lado
        
    Returns:
        Imagem redimensionada
    """
    h, w = image.shape[:2]
    
    # Calcula escala
    max_dim = max(h, w)
    min_dim = min(h, w)
    
    scale = 1.0
    
    if max_dim > max_size:
        scale = max_size / max_dim
    elif min_dim < min_size:
        scale = min_size / min_dim
        
    if scale != 1.0:
        new_w = int(w * scale)
        new_h = int(h * scale)
        return cv2.resize(image, (new_w, new_h))
        
    return image


# ============================================================
# Extracted from: src/processing/preprocessing_filters.py
# ============================================================

"""Experimental OpenCV preprocessing filters for wound images.

These helpers are intentionally separate from the production analysis path.
They support comparative experiments requested for HEAL+ / REDISUS without
making any filter mandatory before clinical validation.
"""


from collections import OrderedDict
from pathlib import Path
from typing import Callable

import cv2
import numpy as np

ImageTransform = Callable[[np.ndarray], np.ndarray]

SUPPORTED_IMAGE_EXTENSIONS = {
    ".bmp",
    ".jpeg",
    ".jpg",
    ".png",
    ".tif",
    ".tiff",
    ".webp",
}


def _ensure_odd_positive(value: int, *, name: str) -> int:
    if value <= 0 or value % 2 == 0:
        raise ValueError(f"{name} must be a positive odd integer.")
    return value


def _ensure_odd_kernel(ksize: tuple[int, int]) -> tuple[int, int]:
    if len(ksize) != 2:
        raise ValueError("ksize must contain exactly two integers.")
    return (
        _ensure_odd_positive(int(ksize[0]), name="ksize[0]"),
        _ensure_odd_positive(int(ksize[1]), name="ksize[1]"),
    )


def load_image_bgr(path: str | Path) -> np.ndarray:
    """Load an image with OpenCV preserving the BGR convention used locally."""
    image_path = Path(path)
    image = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
    if image is None:
        raise FileNotFoundError(f"Could not load image: {image_path}")
    return image


def save_image(path: str | Path, image: np.ndarray) -> None:
    """Save an image and create parent directories when needed."""
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(output_path), image):
        raise OSError(f"Could not save image: {output_path}")


def bgr_to_rgb(image: np.ndarray) -> np.ndarray:
    return cv2.cvtColor(image, cv2.COLOR_BGR2RGB)


def rgb_to_bgr(image: np.ndarray) -> np.ndarray:
    return cv2.cvtColor(image, cv2.COLOR_RGB2BGR)


def ensure_bgr_for_analysis(image: np.ndarray) -> np.ndarray:
    """Convert grayscale outputs back to BGR for analyzers expecting 3 channels."""
    if image.ndim == 2:
        return cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
    return image


def apply_median_filter(image: np.ndarray, ksize: int = 5) -> np.ndarray:
    """Apply a median low-pass filter with cv2.medianBlur."""
    return cv2.medianBlur(image, _ensure_odd_positive(int(ksize), name="ksize"))


def apply_gaussian_filter(
    image: np.ndarray,
    ksize: tuple[int, int] = (5, 5),
    sigma: float = 0,
) -> np.ndarray:
    """Apply a Gaussian low-pass filter with cv2.GaussianBlur."""
    return cv2.GaussianBlur(image, _ensure_odd_kernel(ksize), sigma)


def apply_histogram_equalization_gray(image: np.ndarray) -> np.ndarray:
    """Equalize a BGR image after converting it to grayscale."""
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    return cv2.equalizeHist(gray)


def apply_histogram_equalization_color(image: np.ndarray) -> np.ndarray:
    """Equalize only the luminance channel in YCrCb to preserve wound colors."""
    ycrcb = cv2.cvtColor(image, cv2.COLOR_BGR2YCrCb)
    y, cr, cb = cv2.split(ycrcb)
    y_eq = cv2.equalizeHist(y)
    ycrcb_eq = cv2.merge((y_eq, cr, cb))
    return cv2.cvtColor(ycrcb_eq, cv2.COLOR_YCrCb2BGR)


def apply_clahe_color(
    image: np.ndarray,
    clip_limit: float = 2.0,
    tile_grid_size: tuple[int, int] = (8, 8),
) -> np.ndarray:
    """Apply CLAHE on the LAB luminance channel."""
    lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=tile_grid_size)
    l_clahe = clahe.apply(l)
    lab_clahe = cv2.merge((l_clahe, a, b))
    return cv2.cvtColor(lab_clahe, cv2.COLOR_LAB2BGR)


def apply_median_equalized(image: np.ndarray, ksize: int = 5) -> np.ndarray:
    return apply_histogram_equalization_color(apply_median_filter(image, ksize=ksize))


def apply_gaussian_equalized(
    image: np.ndarray,
    ksize: tuple[int, int] = (5, 5),
    sigma: float = 0,
) -> np.ndarray:
    return apply_histogram_equalization_color(apply_gaussian_filter(image, ksize=ksize, sigma=sigma))


def apply_median_clahe(image: np.ndarray, ksize: int = 5) -> np.ndarray:
    return apply_clahe_color(apply_median_filter(image, ksize=ksize))


def apply_gaussian_clahe(
    image: np.ndarray,
    ksize: tuple[int, int] = (5, 5),
    sigma: float = 0,
) -> np.ndarray:
    return apply_clahe_color(apply_gaussian_filter(image, ksize=ksize, sigma=sigma))


def get_preprocessing_methods() -> "OrderedDict[str, ImageTransform]":
    """Return all experimental variants in the order used by reports."""
    return OrderedDict(
        [
            ("original", lambda image: image.copy()),
            ("median", apply_median_filter),
            ("gaussian", apply_gaussian_filter),
            ("equalized_gray", apply_histogram_equalization_gray),
            ("equalized_color", apply_histogram_equalization_color),
            ("clahe_color", apply_clahe_color),
            ("median_equalized", apply_median_equalized),
            ("gaussian_equalized", apply_gaussian_equalized),
            ("median_clahe", apply_median_clahe),
            ("gaussian_clahe", apply_gaussian_clahe),
        ]
    )


def iter_image_files(input_dir: str | Path) -> list[Path]:
    """Find supported image files recursively, sorted for reproducibility."""
    root = Path(input_dir)
    return sorted(
        path
        for path in root.rglob("*")
        if path.is_file() and path.suffix.lower() in SUPPORTED_IMAGE_EXTENSIONS
    )


# ============================================================
# Extracted from: src/processing/false_positive_filter.py
# ============================================================

"""
REDISUS - Sistema de Diagnostico de Feridas
Filtro de Falsos Positivos

Este modulo implementa validacao contextual para eliminar deteccoes
incorretas em elementos nao-biologicos (dedos, dispositivos, fundos).

Estrategias implementadas:
1. Analise de contexto perilesional
2. Deteccao de pele saudavel vs ferida
3. Filtros de forma (dedos vs feridas)
4. Deteccao de bordas artificiais (dispositivos)
5. Validacao de textura biologica
"""
import cv2
import numpy as np
from dataclasses import dataclass
from typing import List, Tuple, Optional, Dict, Any
from enum import Enum
from loguru import logger


class RejectionReason(Enum):
    """Motivos de rejeicao de deteccao"""
    FINGER_SHAPE = "finger_shape"
    DEVICE_EDGE = "device_edge"
    HEALTHY_SKIN = "healthy_skin"
    NO_PERILESIONAL = "no_perilesional"
    ARTIFICIAL_TEXTURE = "artificial_texture"
    TOO_UNIFORM = "too_uniform"
    GEOMETRIC_SHAPE = "geometric_shape"
    LOW_BIOLOGICAL_SCORE = "low_biological_score"


@dataclass
class ValidationResult:
    """Resultado da validacao de uma deteccao"""
    is_valid: bool
    confidence_adjustment: float  # Multiplicador de confianca
    rejection_reasons: List[RejectionReason]
    biological_score: float  # 0-1, quanto parece biologico
    context_score: float  # 0-1, contexto perilesional
    features: Dict[str, Any]


class SkinDetector:
    """
    Detector de pele saudavel para distinguir de feridas.
    
    Usa multiplos espacos de cor e regras para identificar
    pele humana saudavel vs tecido lesionado.
    """
    
    # Intervalos de pele em diferentes espacos de cor
    # YCrCb - mais robusto a iluminacao
    SKIN_YCRCB_MIN = np.array([0, 133, 77], dtype=np.uint8)
    SKIN_YCRCB_MAX = np.array([255, 173, 127], dtype=np.uint8)
    
    # HSV - tons de pele
    SKIN_HSV_MIN = np.array([0, 15, 60], dtype=np.uint8)
    SKIN_HSV_MAX = np.array([25, 170, 255], dtype=np.uint8)
    
    @classmethod
    def detect_skin_mask(cls, image: np.ndarray) -> np.ndarray:
        """
        Detecta mascara de pele na imagem.
        
        Args:
            image: Imagem BGR
            
        Returns:
            Mascara binaria de pele
        """
        # Converte para YCrCb
        ycrcb = cv2.cvtColor(image, cv2.COLOR_BGR2YCrCb)
        mask_ycrcb = cv2.inRange(ycrcb, cls.SKIN_YCRCB_MIN, cls.SKIN_YCRCB_MAX)
        
        # Converte para HSV
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        mask_hsv = cv2.inRange(hsv, cls.SKIN_HSV_MIN, cls.SKIN_HSV_MAX)
        
        # Combina (AND para maior precisao)
        mask = cv2.bitwise_and(mask_ycrcb, mask_hsv)
        
        # Limpa mascara
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        
        return mask
    
    @classmethod
    def is_mostly_healthy_skin(
        cls,
        roi: np.ndarray,
        mask: Optional[np.ndarray] = None,
        threshold: float = 0.7
    ) -> Tuple[bool, float]:
        """
        Verifica se ROI e majoritariamente pele saudavel.
        
        Args:
            roi: Regiao de interesse BGR
            mask: Mascara da deteccao (opcional)
            threshold: Limiar para considerar pele saudavel
            
        Returns:
            (is_healthy, skin_ratio)
        """
        skin_mask = cls.detect_skin_mask(roi)
        
        if mask is not None:
            # Garante que a mascara tenha o mesmo tamanho que a ROI
            if mask.shape[:2] != roi.shape[:2]:
                analysis_mask = cv2.resize(
                    mask, (roi.shape[1], roi.shape[0]),
                    interpolation=cv2.INTER_NEAREST
                )
            else:
                analysis_mask = mask
        else:
            analysis_mask = np.ones(roi.shape[:2], dtype=np.uint8) * 255
            
        # Calcula proporcao de pele
        skin_pixels = cv2.countNonZero(cv2.bitwise_and(skin_mask, analysis_mask))
        total_pixels = cv2.countNonZero(analysis_mask)
        
        if total_pixels == 0:
            return True, 1.0
            
        skin_ratio = skin_pixels / total_pixels
        
        return skin_ratio >= threshold, skin_ratio


class FingerDetector:
    """
    Detector de dedos para evitar falsos positivos.
    
    Dedos tem caracteristicas geometricas especificas:
    - Alta razao de aspecto (elongados)
    - Bordas paralelas
    - Cor uniforme de pele
    """
    
    @classmethod
    def is_finger_shape(
        cls,
        contour: np.ndarray,
        roi: np.ndarray
    ) -> Tuple[bool, float, Dict]:
        """
        Verifica se contorno tem forma de dedo.
        
        Args:
            contour: Contorno da deteccao
            roi: ROI da imagem
            
        Returns:
            (is_finger, finger_score, features)
        """
        features = {}
        
        if contour is None or len(contour) < 5:
            return False, 0.0, features
            
        # Calcula propriedades geometricas
        area = cv2.contourArea(contour)
        if area < 100:
            return False, 0.0, features
            
        # Bounding rect e rotated rect
        x, y, w, h = cv2.boundingRect(contour)
        rect = cv2.minAreaRect(contour)
        (cx, cy), (rw, rh), angle = rect
        
        # Razao de aspecto
        aspect_ratio = max(w, h) / (min(w, h) + 1e-6)
        features["aspect_ratio"] = aspect_ratio
        
        # Dedos tipicamente tem razao > 2.5
        elongated = aspect_ratio > 2.5
        
        # Solidez (area / area do convex hull)
        hull = cv2.convexHull(contour)
        hull_area = cv2.contourArea(hull)
        solidity = area / (hull_area + 1e-6)
        features["solidity"] = solidity
        
        # Dedos tem alta solidez (forma regular)
        high_solidity = solidity > 0.85
        
        # Circularidade
        perimeter = cv2.arcLength(contour, True)
        circularity = 4 * np.pi * area / (perimeter ** 2 + 1e-6)
        features["circularity"] = circularity
        
        # Dedos tem baixa circularidade
        low_circularity = circularity < 0.5
        
        # Convexidade
        hull_perimeter = cv2.arcLength(hull, True)
        convexity = hull_perimeter / (perimeter + 1e-6)
        features["convexity"] = convexity
        
        # Verifica bordas paralelas (caracteristica de dedos)
        # Usa Hough Lines na ROI
        gray_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY) if len(roi.shape) == 3 else roi
        edges = cv2.Canny(gray_roi, 50, 150)
        lines = cv2.HoughLinesP(edges, 1, np.pi/180, 30, minLineLength=20, maxLineGap=10)
        
        parallel_lines = 0
        if lines is not None and len(lines) > 1:
            angles = []
            for line in lines:
                x1, y1, x2, y2 = line[0]
                angle = np.arctan2(y2 - y1, x2 - x1) * 180 / np.pi
                angles.append(angle % 180)
                
            # Verifica angulos similares (bordas paralelas)
            angles = np.array(angles)
            for i, a1 in enumerate(angles):
                for a2 in angles[i+1:]:
                    if abs(a1 - a2) < 15 or abs(a1 - a2 - 180) < 15:
                        parallel_lines += 1
                        
        has_parallel_edges = parallel_lines >= 2
        features["parallel_edges"] = parallel_lines
        
        # Verifica uniformidade de cor (dedos sao uniformes)
        if len(roi.shape) == 3:
            hsv_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
            h_std = np.std(hsv_roi[:, :, 0])
            s_std = np.std(hsv_roi[:, :, 1])
            color_uniformity = 1.0 / (1 + h_std/30 + s_std/30)
        else:
            color_uniformity = 1.0 / (1 + np.std(roi)/30)
        features["color_uniformity"] = color_uniformity
        
        uniform_color = color_uniformity > 0.5
        
        # Score de dedo
        finger_score = (
            (0.25 if elongated else 0) +
            (0.15 if high_solidity else 0) +
            (0.15 if low_circularity else 0) +
            (0.20 if has_parallel_edges else 0) +
            (0.25 if uniform_color else 0)
        )
        features["finger_score"] = finger_score
        
        # Exige score mais alto para confirmar dedo (evita falsos)
        is_finger = finger_score >= 0.75
        
        return is_finger, finger_score, features


class DeviceDetector:
    """
    Detector de dispositivos (celulares, equipamentos).
    
    Dispositivos tem:
    - Bordas retas e geometricas
    - Cores artificiais (preto, branco, metalico)
    - Textura uniforme artificial
    """
    
    # Cores artificiais comuns em BGR
    ARTIFICIAL_COLORS = [
        # Preto
        {"lower": np.array([0, 0, 0]), "upper": np.array([50, 50, 50])},
        # Branco
        {"lower": np.array([200, 200, 200]), "upper": np.array([255, 255, 255])},
        # Cinza metalico
        {"lower": np.array([100, 100, 100]), "upper": np.array([160, 160, 160])},
    ]
    
    @classmethod
    def is_device_edge(
        cls,
        roi: np.ndarray,
        contour: Optional[np.ndarray] = None
    ) -> Tuple[bool, float, Dict]:
        """
        Verifica se ROI parece borda de dispositivo.
        
        Args:
            roi: Regiao de interesse BGR
            contour: Contorno (opcional)
            
        Returns:
            (is_device, device_score, features)
        """
        features = {}
        
        # Verifica cores artificiais
        artificial_ratio = 0.0
        for color_range in cls.ARTIFICIAL_COLORS:
            mask = cv2.inRange(roi, color_range["lower"], color_range["upper"])
            ratio = cv2.countNonZero(mask) / (roi.shape[0] * roi.shape[1])
            artificial_ratio = max(artificial_ratio, ratio)
        features["artificial_color_ratio"] = artificial_ratio
        
        # Verifica bordas retas
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY) if len(roi.shape) == 3 else roi
        edges = cv2.Canny(gray, 50, 150)
        
        lines = cv2.HoughLinesP(edges, 1, np.pi/180, 30, minLineLength=30, maxLineGap=5)
        
        straight_lines = 0
        if lines is not None:
            for line in lines:
                x1, y1, x2, y2 = line[0]
                length = np.sqrt((x2-x1)**2 + (y2-y1)**2)
                if length > 30:
                    straight_lines += 1
        features["straight_lines"] = straight_lines
        
        # Verifica cantos retos (90 graus)
        right_angles = 0
        if contour is not None and len(contour) > 4:
            epsilon = 0.02 * cv2.arcLength(contour, True)
            approx = cv2.approxPolyDP(contour, epsilon, True)
            
            if len(approx) == 4:
                # Quadrilatero - provavelmente dispositivo
                right_angles = 4
            features["approx_vertices"] = len(approx)
        features["right_angles"] = right_angles
        
        # Verifica textura (dispositivos tem textura muito uniforme ou muito regular)
        local_var = cv2.Laplacian(gray, cv2.CV_64F).var()
        features["texture_variance"] = local_var
        
        # Textura muito baixa (uniforme) - threshold mais conservador
        # Feridas reais podem ter alta variancia, entao nao penalizar alta variancia
        artificial_texture = local_var < 30
        
        # Score de dispositivo (pesos rebalanceados, threshold mais alto)
        device_score = (
            (0.3 if artificial_ratio > 0.4 else artificial_ratio * 0.7) +
            (0.25 if straight_lines >= 6 else straight_lines * 0.03) +
            (0.25 if right_angles >= 4 else 0) +
            (0.2 if artificial_texture else 0)
        )
        features["device_score"] = device_score
        
        # Exige score mais alto para confirmar dispositivo
        is_device = device_score >= 0.65
        
        return is_device, device_score, features


class BiologicalTextureAnalyzer:
    """
    Analisador de textura biologica.
    
    Tecidos biologicos (feridas) tem caracteristicas de textura
    distintas de objetos artificiais e pele saudavel.
    """
    
    @classmethod
    def analyze_biological_texture(
        cls,
        roi: np.ndarray,
        mask: Optional[np.ndarray] = None
    ) -> Tuple[float, Dict]:
        """
        Analisa se textura parece biologica (ferida).
        
        Args:
            roi: Regiao de interesse BGR
            mask: Mascara da area (opcional)
            
        Returns:
            (biological_score, features)
        """
        features = {}
        
        if roi is None or roi.size == 0:
            return 0.0, features
        
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY) if len(roi.shape) == 3 else roi
        
        # Garante que a mascara tem tamanho identico ao gray
        if mask is not None:
            if mask.shape[:2] != gray.shape[:2]:
                mask = cv2.resize(
                    mask, (gray.shape[1], gray.shape[0]),
                    interpolation=cv2.INTER_NEAREST
                )
            if mask.dtype != np.uint8:
                mask = mask.astype(np.uint8)
            # Mascara vazia -> None (evita histograma vazio)
            if cv2.countNonZero(mask) == 0:
                mask = None
        
        # 1. Variancia local (feridas tem textura irregular)
        kernel_size = 7
        local_mean = cv2.blur(gray.astype(np.float32), (kernel_size, kernel_size))
        local_sq_mean = cv2.blur((gray.astype(np.float32) ** 2), (kernel_size, kernel_size))
        local_var = np.clip(local_sq_mean - local_mean ** 2, 0, None)
        
        mean_var = np.mean(local_var)
        std_var = np.std(local_var)
        features["mean_local_variance"] = mean_var
        features["std_local_variance"] = std_var
        
        # Feridas tem variancia media moderada e variacao
        texture_irregularity = min(1.0, (mean_var / 500) * (1 + std_var / 200))
        
        # 2. Entropia (complexidade da textura)
        hist = cv2.calcHist([gray], [0], mask, [64], [0, 256])
        hist = hist / (hist.sum() + 1e-6)
        entropy = -np.sum(hist * np.log2(hist + 1e-6))
        features["entropy"] = entropy
        
        # Feridas tem entropia moderada a alta
        entropy_score = min(1.0, entropy / 5.0)
        
        # 3. Gradiente (transicoes de cor)
        gradient_x = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
        gradient_y = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
        gradient_mag = np.sqrt(gradient_x**2 + gradient_y**2)
        
        mean_gradient = np.mean(gradient_mag)
        features["mean_gradient"] = mean_gradient
        
        # Feridas tem gradientes moderados
        gradient_score = min(1.0, mean_gradient / 50)
        
        # 4. Cor biologica (tons de vermelho, rosa, amarelo)
        if len(roi.shape) == 3:
            hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
            h = hsv[:, :, 0]
            s = hsv[:, :, 1]
            
            # Mascara de tons biologicos (vermelho, laranja, amarelo, rosa)
            biological_hue = ((h < 30) | (h > 160)) & (s > 30)
            biological_ratio = np.mean(biological_hue)
            features["biological_color_ratio"] = biological_ratio
        else:
            biological_ratio = 0.5
            
        # 5. Score final
        biological_score = (
            texture_irregularity * 0.25 +
            entropy_score * 0.2 +
            gradient_score * 0.2 +
            biological_ratio * 0.35
        )
        features["biological_score"] = biological_score
        
        return biological_score, features


class PerilesionalAnalyzer:
    """
    Analisador de tecido perilesional.
    
    Feridas reais tem pele ao redor (perilesional).
    Se nao ha contexto de pele, provavelmente e falso positivo.
    """
    
    @classmethod
    def analyze_perilesional(
        cls,
        frame: np.ndarray,
        bbox: Tuple[int, int, int, int],
        expansion_ratio: float = 0.5
    ) -> Tuple[float, Dict]:
        """
        Analisa presenca de tecido perilesional.
        
        Args:
            frame: Frame completo BGR
            bbox: Bounding box da deteccao (x1, y1, x2, y2)
            expansion_ratio: Quanto expandir para buscar perilesional
            
        Returns:
            (perilesional_score, features)
        """
        features = {}
        x1, y1, x2, y2 = bbox
        h, w = frame.shape[:2]
        
        # Calcula area expandida
        box_w = x2 - x1
        box_h = y2 - y1
        expand_w = int(box_w * expansion_ratio)
        expand_h = int(box_h * expansion_ratio)
        
        # Area externa (perilesional)
        outer_x1 = max(0, x1 - expand_w)
        outer_y1 = max(0, y1 - expand_h)
        outer_x2 = min(w, x2 + expand_w)
        outer_y2 = min(h, y2 + expand_h)
        
        # Extrai area externa
        outer_region = frame[outer_y1:outer_y2, outer_x1:outer_x2].copy()
        
        # Cria mascara excluindo a deteccao
        mask = np.ones(outer_region.shape[:2], dtype=np.uint8) * 255
        inner_x1 = x1 - outer_x1
        inner_y1 = y1 - outer_y1
        inner_x2 = inner_x1 + box_w
        inner_y2 = inner_y1 + box_h
        mask[inner_y1:inner_y2, inner_x1:inner_x2] = 0
        
        # Verifica se area externa tem pele
        skin_mask = SkinDetector.detect_skin_mask(outer_region)
        perilesional_mask = cv2.bitwise_and(skin_mask, mask)
        
        perilesional_pixels = cv2.countNonZero(perilesional_mask)
        outer_pixels = cv2.countNonZero(mask)
        
        if outer_pixels == 0:
            return 0.0, features
            
        skin_ratio = perilesional_pixels / outer_pixels
        features["perilesional_skin_ratio"] = skin_ratio
        
        # Verifica se ha gradiente de cor (transicao ferida -> pele)
        inner_roi = frame[y1:y2, x1:x2]
        
        if inner_roi.size > 0 and outer_region.size > 0:
            # Cor media interna vs externa
            inner_mean = np.mean(inner_roi, axis=(0, 1))
            
            # Cor media da area perilesional (onde tem pele)
            perilesional_area = cv2.bitwise_and(
                outer_region,
                outer_region,
                mask=perilesional_mask
            )
            if perilesional_pixels > 0:
                outer_mean = np.sum(perilesional_area, axis=(0, 1)) / perilesional_pixels
            else:
                outer_mean = np.mean(outer_region, axis=(0, 1))
                
            # Diferenca de cor
            color_diff = np.linalg.norm(inner_mean - outer_mean)
            features["color_difference"] = color_diff
            
            # Feridas tem diferenca de cor com perilesional
            color_score = min(1.0, color_diff / 100)
        else:
            color_score = 0.0
            
        # Score perilesional
        perilesional_score = (
            skin_ratio * 0.6 +  # Presenca de pele ao redor
            color_score * 0.4   # Diferenca de cor
        )
        features["perilesional_score"] = perilesional_score
        
        return perilesional_score, features


class FalsePositiveFilter:
    """
    Filtro principal de falsos positivos.
    
    Combina todas as analises para validar deteccoes.
    """
    
    def __init__(
        self,
        min_biological_score: float = 0.15,
        min_perilesional_score: float = 0.10,
        max_finger_score: float = 0.70,
        max_device_score: float = 0.60
    ):
        """
        Args:
            min_biological_score: Score minimo de textura biologica
            min_perilesional_score: Score minimo de contexto perilesional
            max_finger_score: Score maximo permitido de dedo
            max_device_score: Score maximo permitido de dispositivo
        """
        self.min_biological_score = min_biological_score
        self.min_perilesional_score = min_perilesional_score
        self.max_finger_score = max_finger_score
        self.max_device_score = max_device_score
        
        logger.info("FalsePositiveFilter inicializado")
        
    def validate_detection(
        self,
        frame: np.ndarray,
        bbox: Tuple[int, int, int, int],
        mask: Optional[np.ndarray] = None,
        contour: Optional[np.ndarray] = None
    ) -> ValidationResult:
        """
        Valida uma deteccao verificando se e falso positivo.
        
        Args:
            frame: Frame completo BGR
            bbox: Bounding box (x1, y1, x2, y2)
            mask: Mascara da deteccao
            contour: Contorno da deteccao
            
        Returns:
            ValidationResult com status da validacao
        """
        x1, y1, x2, y2 = bbox
        h_frame, w_frame = frame.shape[:2]
        # Garante bbox dentro dos limites do frame
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(w_frame, x2), min(h_frame, y2)
        roi = frame[y1:y2, x1:x2]
        
        if roi.size == 0 or (y2 - y1) < 2 or (x2 - x1) < 2:
            return ValidationResult(
                is_valid=False,
                confidence_adjustment=0.0,
                rejection_reasons=[RejectionReason.LOW_BIOLOGICAL_SCORE],
                biological_score=0.0,
                context_score=0.0,
                features={}
            )
        
        # Normaliza a mascara para ter o mesmo tamanho da ROI
        roi_h, roi_w = roi.shape[:2]
        if mask is not None and mask.size > 0:
            if mask.shape[:2] != (roi_h, roi_w):
                mask = cv2.resize(
                    mask, (roi_w, roi_h),
                    interpolation=cv2.INTER_NEAREST
                )
            if mask.dtype != np.uint8:
                mask = mask.astype(np.uint8)
        else:
            mask = None
            
        rejection_reasons = []
        all_features = {}
        
        # 1. Verifica se e dedo
        is_finger, finger_score, finger_features = FingerDetector.is_finger_shape(
            contour, roi
        )
        all_features.update({f"finger_{k}": v for k, v in finger_features.items()})
        
        if is_finger or finger_score > self.max_finger_score:
            rejection_reasons.append(RejectionReason.FINGER_SHAPE)
            
        # 2. Verifica se e dispositivo
        is_device, device_score, device_features = DeviceDetector.is_device_edge(
            roi, contour
        )
        all_features.update({f"device_{k}": v for k, v in device_features.items()})
        
        if is_device or device_score > self.max_device_score:
            rejection_reasons.append(RejectionReason.DEVICE_EDGE)
            
        # 3. Verifica pele saudavel
        is_healthy, skin_ratio = SkinDetector.is_mostly_healthy_skin(roi, mask)
        all_features["healthy_skin_ratio"] = skin_ratio
        
        if is_healthy:
            rejection_reasons.append(RejectionReason.HEALTHY_SKIN)
            
        # 4. Analisa textura biologica
        biological_score, bio_features = BiologicalTextureAnalyzer.analyze_biological_texture(
            roi, mask
        )
        all_features.update({f"bio_{k}": v for k, v in bio_features.items()})
        
        if biological_score < self.min_biological_score:
            rejection_reasons.append(RejectionReason.LOW_BIOLOGICAL_SCORE)
            
        # 5. Analisa contexto perilesional
        perilesional_score, peri_features = PerilesionalAnalyzer.analyze_perilesional(
            frame, bbox
        )
        all_features.update({f"peri_{k}": v for k, v in peri_features.items()})
        
        if perilesional_score < self.min_perilesional_score:
            rejection_reasons.append(RejectionReason.NO_PERILESIONAL)
            
        # Calcula ajuste de confianca
        # Quanto mais validacoes falham, menor a confianca
        base_adjustment = 1.0
        
        if RejectionReason.FINGER_SHAPE in rejection_reasons:
            base_adjustment *= 0.3
        if RejectionReason.DEVICE_EDGE in rejection_reasons:
            base_adjustment *= 0.2
        if RejectionReason.HEALTHY_SKIN in rejection_reasons:
            base_adjustment *= 0.4
        if RejectionReason.LOW_BIOLOGICAL_SCORE in rejection_reasons:
            base_adjustment *= 0.5
        if RejectionReason.NO_PERILESIONAL in rejection_reasons:
            base_adjustment *= 0.7
            
        # Bonus para alta pontuacao biologica
        if biological_score > 0.6:
            base_adjustment *= 1.2
        if perilesional_score > 0.5:
            base_adjustment *= 1.1
            
        confidence_adjustment = min(1.5, max(0.1, base_adjustment))
        
        # Decisao final
        # Rejeicoes criticas podem ser sobrepostas por alta pontuacao biologica
        critical_rejections = {
            RejectionReason.FINGER_SHAPE,
            RejectionReason.DEVICE_EDGE
        }
        
        has_critical = bool(set(rejection_reasons) & critical_rejections)
        
        # Alta pontuacao biologica (>= 0.45) permite sobrepor rejeicoes criticas
        # Isso evita que feridas reais sejam descartadas por forma similar a dedo/dispositivo
        bio_override = biological_score >= 0.45
        
        is_valid = (
            (not has_critical or bio_override) and
            biological_score >= self.min_biological_score and
            len(rejection_reasons) <= 3
        )
        
        return ValidationResult(
            is_valid=is_valid,
            confidence_adjustment=confidence_adjustment,
            rejection_reasons=rejection_reasons,
            biological_score=biological_score,
            context_score=perilesional_score,
            features=all_features
        )
    
    def filter_detections(
        self,
        frame: np.ndarray,
        detections: List[Any],  # List[DetectionResult]
        apply_adjustment: bool = True
    ) -> List[Any]:
        """
        Filtra lista de deteccoes removendo falsos positivos.
        
        Args:
            frame: Frame completo BGR
            detections: Lista de DetectionResult
            apply_adjustment: Se deve ajustar confianca
            
        Returns:
            Lista filtrada de deteccoes validas
        """
        filtered = []
        _reject_count = getattr(self, '_reject_count', 0)
        
        for det in detections:
            validation = self.validate_detection(
                frame,
                det.bbox,
                det.mask,
                det.contour
            )
            
            if validation.is_valid:
                if apply_adjustment:
                    det.confidence *= validation.confidence_adjustment
                    det.confidence = min(1.0, det.confidence)
                    
                # Adiciona info de validacao
                det.features["validation"] = {
                    "biological_score": validation.biological_score,
                    "context_score": validation.context_score,
                    "confidence_adjustment": validation.confidence_adjustment
                }
                
                filtered.append(det)
            else:
                _reject_count += 1
                # Log apenas a cada 50 rejeicoes para nao poluir console
                if _reject_count % 50 == 1:
                    logger.debug(
                        f"Deteccao rejeitada (#{_reject_count}): {[r.value for r in validation.rejection_reasons]}"
                    )
        
        self._reject_count = _reject_count
                
        return filtered


# ============================================================
# Extracted from: src/processing/image_enhancer.py
# ============================================================

"""
===============================================================================
REDISUS - PROCESSADOR DE IMAGEM AVANÇADO
===============================================================================

Módulo avançado para análise e correção de imagens de feridas:
- Análise detalhada de iluminação (luz ambiente, direção, intensidade)
- Correção automática de contraste adaptativa
- Detecção de saturação e clipping
- Normalização para deep learning

Autor: REDISUS Team
===============================================================================
"""

import cv2
import numpy as np
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from enum import Enum
from loguru import logger


class LightingCondition(Enum):
    """Condições de iluminação detectadas"""
    OPTIMAL = "optimal"           # Iluminação adequada para diagnóstico
    UNDEREXPOSED = "underexposed" # Muito escura
    OVEREXPOSED = "overexposed"   # Muito clara/saturada
    UNEVEN = "uneven"             # Iluminação não uniforme
    WARM = "warm"                 # Luz amarelada/quente
    COOL = "cool"                 # Luz azulada/fria
    MIXED = "mixed"               # Múltiplas fontes de luz
    FLASH = "flash"               # Flash detectado (reflexos)


@dataclass
class LightingAnalysis:
    """Análise detalhada de iluminação da imagem"""
    # Métricas básicas
    mean_brightness: float          # 0-255 média geral
    brightness_std: float           # Variação de brilho
    contrast_ratio: float           # Razão de contraste
    
    # Análise espacial
    uniformity_score: float         # 0-1 (1 = uniforme)
    gradient_direction: Tuple[float, float]  # Direção da luz (x, y)
    gradient_strength: float        # Força do gradiente
    
    # Análise de cor/temperatura
    color_temperature_k: int        # Temperatura de cor estimada (Kelvin)
    white_balance_shift: Tuple[float, float, float]  # Desvio R, G, B
    
    # Problemas detectados
    condition: LightingCondition
    has_clipping_highlights: bool   # Áreas saturadas (brancas)
    has_clipping_shadows: bool      # Áreas sem detalhe (pretas)
    highlight_percentage: float     # % de pixels saturados
    shadow_percentage: float        # % de pixels sem detalhe
    
    # Detecção de flash/reflexos
    has_specular_highlights: bool
    specular_regions: List[Tuple[int, int, int, int]] = field(default_factory=list)
    
    # Recomendações
    corrections_needed: List[str] = field(default_factory=list)
    quality_score: float = 0.0      # 0-1 score geral
    
    def to_dict(self) -> Dict:
        return {
            "mean_brightness": round(self.mean_brightness, 2),
            "brightness_std": round(self.brightness_std, 2),
            "contrast_ratio": round(self.contrast_ratio, 3),
            "uniformity_score": round(self.uniformity_score, 3),
            "gradient_direction": [round(x, 3) for x in self.gradient_direction],
            "gradient_strength": round(self.gradient_strength, 3),
            "color_temperature_k": self.color_temperature_k,
            "condition": self.condition.value,
            "has_clipping_highlights": self.has_clipping_highlights,
            "has_clipping_shadows": self.has_clipping_shadows,
            "highlight_percentage": round(self.highlight_percentage, 2),
            "shadow_percentage": round(self.shadow_percentage, 2),
            "has_specular_highlights": self.has_specular_highlights,
            "quality_score": round(self.quality_score, 3),
            "corrections_needed": self.corrections_needed,
        }


@dataclass
class ContrastAnalysis:
    """Análise de contraste da imagem"""
    global_contrast: float          # Contraste global (std/mean)
    local_contrast_mean: float      # Média de contraste local
    local_contrast_std: float       # Variação de contraste local
    dynamic_range: float            # Range dinâmico (0-1)
    histogram_spread: float         # Distribuição do histograma
    needs_enhancement: bool
    recommended_method: str         # "clahe", "adaptive", "none"


class ImageEnhancer:
    """
    Analisador e corretor avançado de imagens para diagnóstico de feridas.
    
    Este módulo analisa condições de iluminação, detecta problemas de
    qualidade e aplica correções automatizadas para otimizar a imagem
    para análise por deep learning.
    
    Features:
    - Análise completa de iluminação (direção, intensidade, uniformidade)
    - Detecção de temperatura de cor
    - Identificação de reflexos especulares (flash)
    - Correção automática adaptativa
    - Normalização específica para CNNs médicas
    """
    
    def __init__(
        self,
        target_brightness: float = 128.0,
        target_contrast: float = 0.4,
        clahe_clip_limit: float = 2.5,
        clahe_grid_size: Tuple[int, int] = (8, 8)
    ):
        self.target_brightness = target_brightness
        self.target_contrast = target_contrast
        self.clahe = cv2.createCLAHE(
            clipLimit=clahe_clip_limit,
            tileGridSize=clahe_grid_size
        )
        
    def analyze_lighting(self, image: np.ndarray) -> LightingAnalysis:
        """
        Análise completa de iluminação da imagem.
        
        Args:
            image: Imagem BGR
            
        Returns:
            LightingAnalysis com todas as métricas
        """
        h, w = image.shape[:2]
        
        # Converter para diferentes espaços de cor
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        
        l_channel = lab[:, :, 0].astype(np.float32)
        
        # === Métricas básicas ===
        mean_brightness = float(np.mean(l_channel))
        brightness_std = float(np.std(l_channel))
        
        # Contraste usando percentis
        p5, p95 = np.percentile(l_channel, [5, 95])
        contrast_ratio = float((p95 - p5) / 255.0)
        
        # === Análise de uniformidade ===
        # Divide imagem em grid e compara médias
        grid_h, grid_w = 4, 4
        cell_h, cell_w = h // grid_h, w // grid_w
        cell_means = []
        
        for i in range(grid_h):
            for j in range(grid_w):
                cell = l_channel[
                    i * cell_h:(i + 1) * cell_h,
                    j * cell_w:(j + 1) * cell_w
                ]
                cell_means.append(np.mean(cell))
        
        cell_means = np.array(cell_means)
        uniformity_score = 1.0 - (np.std(cell_means) / (np.mean(cell_means) + 1e-6))
        uniformity_score = float(np.clip(uniformity_score, 0, 1))
        
        # === Direção da luz (gradiente espacial) ===
        # Calcula gradiente da luminosidade
        grad_x = cv2.Sobel(l_channel, cv2.CV_64F, 1, 0, ksize=5)
        grad_y = cv2.Sobel(l_channel, cv2.CV_64F, 0, 1, ksize=5)
        
        # Direção média do gradiente
        mean_grad_x = float(np.mean(grad_x))
        mean_grad_y = float(np.mean(grad_y))
        
        # Normaliza para vetor unitário
        grad_mag = np.sqrt(mean_grad_x ** 2 + mean_grad_y ** 2) + 1e-6
        gradient_direction = (mean_grad_x / grad_mag, mean_grad_y / grad_mag)
        gradient_strength = float(grad_mag / 255.0)
        
        # === Temperatura de cor ===
        b, g, r = cv2.split(image.astype(np.float32))
        
        # Razões de cor para estimar temperatura
        r_mean, g_mean, b_mean = np.mean(r), np.mean(g), np.mean(b)
        total_mean = (r_mean + g_mean + b_mean) / 3
        
        white_balance_shift = (
            float(r_mean / total_mean - 1),
            float(g_mean / total_mean - 1),
            float(b_mean / total_mean - 1)
        )
        
        # Estima temperatura de cor (aproximação simplificada)
        # Luz quente: mais vermelho, menos azul
        # Luz fria: mais azul, menos vermelho
        rb_ratio = r_mean / (b_mean + 1e-6)
        
        if rb_ratio > 1.5:
            color_temp_k = 2800  # Luz incandescente
        elif rb_ratio > 1.2:
            color_temp_k = 3200  # Luz halógena
        elif rb_ratio > 0.9:
            color_temp_k = 5500  # Luz natural/flash
        elif rb_ratio > 0.7:
            color_temp_k = 6500  # Luz do dia nublado
        else:
            color_temp_k = 8000  # Luz muito fria
        
        # === Detecção de clipping ===
        highlight_threshold = 250
        shadow_threshold = 5
        
        highlight_mask = gray >= highlight_threshold
        shadow_mask = gray <= shadow_threshold
        
        highlight_percentage = float(np.sum(highlight_mask) / (h * w) * 100)
        shadow_percentage = float(np.sum(shadow_mask) / (h * w) * 100)
        
        has_clipping_highlights = highlight_percentage > 2.0
        has_clipping_shadows = shadow_percentage > 5.0
        
        # === Detecção de reflexos especulares (flash) ===
        # Áreas muito brilhantes e com baixa saturação = reflexo
        v_channel = hsv[:, :, 2]
        s_channel = hsv[:, :, 1]
        
        specular_mask = (v_channel > 240) & (s_channel < 30)
        has_specular = np.sum(specular_mask) > (h * w * 0.005)  # >0.5% da imagem
        
        specular_regions = []
        if has_specular:
            # Encontra contornos de regiões especulares
            contours, _ = cv2.findContours(
                specular_mask.astype(np.uint8),
                cv2.RETR_EXTERNAL,
                cv2.CHAIN_APPROX_SIMPLE
            )
            for cnt in contours[:5]:  # Máximo 5 regiões
                x, y, rw, rh = cv2.boundingRect(cnt)
                if rw * rh > 100:  # Área mínima
                    specular_regions.append((x, y, x + rw, y + rh))
        
        # === Determina condição ===
        corrections_needed = []
        
        if mean_brightness < 80:
            condition = LightingCondition.UNDEREXPOSED
            corrections_needed.append("increase_brightness")
        elif mean_brightness > 200:
            condition = LightingCondition.OVEREXPOSED
            corrections_needed.append("decrease_brightness")
        elif uniformity_score < 0.6:
            condition = LightingCondition.UNEVEN
            corrections_needed.append("correct_illumination")
        elif has_specular:
            condition = LightingCondition.FLASH
            corrections_needed.append("remove_specular")
        elif color_temp_k < 3500:
            condition = LightingCondition.WARM
            corrections_needed.append("white_balance")
        elif color_temp_k > 7000:
            condition = LightingCondition.COOL
            corrections_needed.append("white_balance")
        else:
            condition = LightingCondition.OPTIMAL
        
        if contrast_ratio < 0.3:
            corrections_needed.append("enhance_contrast")
        
        # === Quality score ===
        quality_factors = [
            1.0 - abs(mean_brightness - 128) / 128,  # Brilho ideal ~128
            uniformity_score,
            min(contrast_ratio / 0.4, 1.0),          # Contraste ideal ~0.4
            0.0 if has_clipping_highlights else 1.0,
            0.0 if has_specular else 1.0,
        ]
        quality_score = float(np.mean(quality_factors))
        
        return LightingAnalysis(
            mean_brightness=mean_brightness,
            brightness_std=brightness_std,
            contrast_ratio=contrast_ratio,
            uniformity_score=uniformity_score,
            gradient_direction=gradient_direction,
            gradient_strength=gradient_strength,
            color_temperature_k=color_temp_k,
            white_balance_shift=white_balance_shift,
            condition=condition,
            has_clipping_highlights=has_clipping_highlights,
            has_clipping_shadows=has_clipping_shadows,
            highlight_percentage=highlight_percentage,
            shadow_percentage=shadow_percentage,
            has_specular_highlights=has_specular,
            specular_regions=specular_regions,
            corrections_needed=corrections_needed,
            quality_score=quality_score,
        )
    
    def analyze_contrast(self, image: np.ndarray) -> ContrastAnalysis:
        """
        Análise detalhada de contraste.
        
        Args:
            image: Imagem BGR
            
        Returns:
            ContrastAnalysis
        """
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY).astype(np.float32)
        
        # Contraste global
        global_mean = np.mean(gray)
        global_std = np.std(gray)
        global_contrast = float(global_std / (global_mean + 1e-6))
        
        # Contraste local (usando janelas)
        window_size = 32
        local_contrasts = []
        
        h, w = gray.shape
        for y in range(0, h - window_size, window_size // 2):
            for x in range(0, w - window_size, window_size // 2):
                window = gray[y:y + window_size, x:x + window_size]
                local_std = np.std(window)
                local_mean = np.mean(window)
                if local_mean > 10:  # Ignora regiões muito escuras
                    local_contrasts.append(local_std / local_mean)
        
        local_contrasts = np.array(local_contrasts) if local_contrasts else np.array([0])
        local_contrast_mean = float(np.mean(local_contrasts))
        local_contrast_std = float(np.std(local_contrasts))
        
        # Dynamic range
        p1, p99 = np.percentile(gray, [1, 99])
        dynamic_range = float((p99 - p1) / 255.0)
        
        # Histogram spread
        hist, _ = np.histogram(gray.ravel(), bins=256, range=(0, 256))
        hist = hist / hist.sum()
        non_zero_bins = np.sum(hist > 0.001)
        histogram_spread = float(non_zero_bins / 256.0)
        
        # Determina se precisa enhancement
        needs_enhancement = (
            global_contrast < 0.25 or
            dynamic_range < 0.4 or
            histogram_spread < 0.3
        )
        
        # Recomenda método
        if not needs_enhancement:
            recommended_method = "none"
        elif local_contrast_std > 0.3:
            # Alta variação local = CLAHE para preservar detalhes
            recommended_method = "clahe"
        else:
            # Baixa variação = adaptive histogram
            recommended_method = "adaptive"
        
        return ContrastAnalysis(
            global_contrast=global_contrast,
            local_contrast_mean=local_contrast_mean,
            local_contrast_std=local_contrast_std,
            dynamic_range=dynamic_range,
            histogram_spread=histogram_spread,
            needs_enhancement=needs_enhancement,
            recommended_method=recommended_method,
        )
    
    def auto_correct(
        self,
        image: np.ndarray,
        lighting_analysis: Optional[LightingAnalysis] = None
    ) -> Tuple[np.ndarray, Dict[str, str]]:
        """
        Aplica correções automáticas baseadas na análise.
        
        Args:
            image: Imagem BGR
            lighting_analysis: Análise prévia (opcional, será calculada se None)
            
        Returns:
            Tuple[imagem corrigida, dict de correções aplicadas]
        """
        if lighting_analysis is None:
            lighting_analysis = self.analyze_lighting(image)
        
        corrections_applied = {}
        result = image.copy()
        
        for correction in lighting_analysis.corrections_needed:
            if correction == "increase_brightness":
                result = self._adjust_brightness(result, factor=1.3)
                corrections_applied["brightness"] = "increased +30%"
                
            elif correction == "decrease_brightness":
                result = self._adjust_brightness(result, factor=0.8)
                corrections_applied["brightness"] = "decreased -20%"
                
            elif correction == "correct_illumination":
                result = self._correct_uneven_illumination(result)
                corrections_applied["illumination"] = "corrected"
                
            elif correction == "white_balance":
                result = self._auto_white_balance(result)
                corrections_applied["white_balance"] = "applied"
                
            elif correction == "enhance_contrast":
                result = self._enhance_contrast_adaptive(result)
                corrections_applied["contrast"] = "enhanced (CLAHE)"
                
            elif correction == "remove_specular":
                result = self._reduce_specular_highlights(
                    result,
                    lighting_analysis.specular_regions
                )
                corrections_applied["specular"] = "reduced"
        
        return result, corrections_applied
    
    def _adjust_brightness(
        self,
        image: np.ndarray,
        factor: float = 1.0
    ) -> np.ndarray:
        """Ajusta brilho multiplicando luminosidade."""
        lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB).astype(np.float32)
        lab[:, :, 0] = np.clip(lab[:, :, 0] * factor, 0, 255)
        return cv2.cvtColor(lab.astype(np.uint8), cv2.COLOR_LAB2BGR)
    
    def _correct_uneven_illumination(
        self,
        image: np.ndarray,
        blur_size: int = 55
    ) -> np.ndarray:
        """Corrige iluminação não uniforme usando divisão por background."""
        lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
        l_channel = lab[:, :, 0].astype(np.float32)
        
        # Estima background com blur grande
        background = cv2.GaussianBlur(l_channel, (blur_size, blur_size), 0)
        
        # Normaliza pela iluminação de background
        corrected = l_channel / (background + 1e-6) * 128
        corrected = np.clip(corrected, 0, 255).astype(np.uint8)
        
        lab[:, :, 0] = corrected
        return cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)
    
    def _auto_white_balance(self, image: np.ndarray) -> np.ndarray:
        """Aplica white balance automático (gray world assumption)."""
        result = image.astype(np.float32)
        
        for i in range(3):
            channel_mean = np.mean(result[:, :, i])
            gray_target = np.mean(result)
            result[:, :, i] = result[:, :, i] * (gray_target / (channel_mean + 1e-6))
        
        return np.clip(result, 0, 255).astype(np.uint8)
    
    def _enhance_contrast_adaptive(self, image: np.ndarray) -> np.ndarray:
        """Aplica CLAHE no canal L do LAB."""
        lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
        lab[:, :, 0] = self.clahe.apply(lab[:, :, 0])
        return cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)
    
    def _reduce_specular_highlights(
        self,
        image: np.ndarray,
        regions: List[Tuple[int, int, int, int]]
    ) -> np.ndarray:
        """Reduz reflexos especulares usando inpainting."""
        if not regions:
            return image
        
        mask = np.zeros(image.shape[:2], dtype=np.uint8)
        
        for x1, y1, x2, y2 in regions:
            mask[y1:y2, x1:x2] = 255
        
        # Inpaint usando método Telea
        return cv2.inpaint(image, mask, inpaintRadius=5, flags=cv2.INPAINT_TELEA)
    
    def prepare_for_cnn(
        self,
        image: np.ndarray,
        target_size: Tuple[int, int] = (224, 224),
        normalize: bool = True,
        auto_correct: bool = True
    ) -> Tuple[np.ndarray, Dict]:
        """
        Prepara imagem para inferência em CNN.
        
        Aplica todas as correções necessárias e normaliza para o formato
        esperado pela rede neural.
        
        Args:
            image: Imagem BGR
            target_size: Tamanho alvo (width, height)
            normalize: Se deve normalizar valores para [0, 1]
            auto_correct: Se deve aplicar correções automáticas
            
        Returns:
            Tuple[imagem preparada, metadados do processamento]
        """
        metadata = {
            "original_size": image.shape[:2],
            "corrections_applied": {},
        }
        
        # Análise de iluminação
        lighting = self.analyze_lighting(image)
        metadata["lighting_analysis"] = lighting.to_dict()
        
        # Correções automáticas
        if auto_correct and lighting.corrections_needed:
            image, corrections = self.auto_correct(image, lighting)
            metadata["corrections_applied"] = corrections
        
        # Resize mantendo aspect ratio e adicionando padding
        h, w = image.shape[:2]
        target_h, target_w = target_size[1], target_size[0]
        
        scale = min(target_w / w, target_h / h)
        new_w, new_h = int(w * scale), int(h * scale)
        
        resized = cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_LANCZOS4)
        
        # Padding para atingir tamanho alvo
        canvas = np.zeros((target_h, target_w, 3), dtype=np.uint8)
        pad_y = (target_h - new_h) // 2
        pad_x = (target_w - new_w) // 2
        canvas[pad_y:pad_y + new_h, pad_x:pad_x + new_w] = resized
        
        metadata["scale"] = scale
        metadata["padding"] = (pad_x, pad_y)
        
        # Normalização
        if normalize:
            canvas = canvas.astype(np.float32) / 255.0
        
        return canvas, metadata


def create_medical_enhancer() -> ImageEnhancer:
    """
    Cria enhancer otimizado para imagens médicas de feridas.
    """
    return ImageEnhancer(
        target_brightness=128.0,
        target_contrast=0.4,
        clahe_clip_limit=2.5,
        clahe_grid_size=(8, 8)
    )


# ============================================================
# Extracted from: src/processing/roi_segmentation.py
# ============================================================

import cv2
import numpy as np
import logging

logger = logging.getLogger(__name__)

class ROISegmenter:
    """Segmentador de ROI e máscaras associadas para feridas."""

    @staticmethod
    def create_wound_roi_mask(image: np.ndarray, detections: list) -> np.ndarray:
        h, w = image.shape[:2]
        wound_mask = np.zeros((h, w), dtype=np.uint8)

        if not detections:
            wound_mask[:] = 255
            return wound_mask

        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)

        for det in detections:
            x1, y1, x2, y2 = det.bbox if hasattr(det, 'bbox') else det.get('bbox', [0,0,w,h])
            margin_x = int((x2 - x1) * 0.05)
            margin_y = int((y2 - y1) * 0.05)
            rx1 = max(0, x1 - margin_x)
            ry1 = max(0, y1 - margin_y)
            rx2 = min(w, x2 + margin_x)
            ry2 = min(h, y2 + margin_y)

            roi_hsv = hsv[ry1:ry2, rx1:rx2]

            wound_colors = np.zeros(roi_hsv.shape[:2], dtype=np.uint8)
            wound_colors = cv2.bitwise_or(wound_colors, cv2.inRange(roi_hsv, np.array([0, 40, 40]), np.array([15, 255, 255])))
            wound_colors = cv2.bitwise_or(wound_colors, cv2.inRange(roi_hsv, np.array([155, 40, 40]), np.array([180, 255, 255])))
            wound_colors = cv2.bitwise_or(wound_colors, cv2.inRange(roi_hsv, np.array([10, 18, 70]), np.array([55, 255, 255])))
            wound_colors = cv2.bitwise_or(wound_colors, cv2.inRange(roi_hsv, np.array([30, 12, 68]), np.array([82, 130, 185])))
            wound_colors = cv2.bitwise_or(wound_colors, cv2.inRange(roi_hsv, np.array([0, 0, 0]), np.array([180, 255, 85])))
            wound_colors = cv2.bitwise_or(wound_colors, cv2.inRange(roi_hsv, np.array([0, 8, 160]), np.array([20, 80, 255])))
            wound_colors = cv2.bitwise_or(wound_colors, cv2.inRange(roi_hsv, np.array([150, 8, 160]), np.array([180, 80, 255])))

            bg_mask = np.zeros(roi_hsv.shape[:2], dtype=np.uint8)
            bg_mask = cv2.bitwise_or(bg_mask, cv2.inRange(roi_hsv, np.array([92, 45, 20]), np.array([130, 255, 255])))
            bg_mask = cv2.bitwise_or(bg_mask, cv2.inRange(roi_hsv, np.array([55, 60, 35]), np.array([95, 255, 255])))

            roi_mask = cv2.bitwise_and(wound_colors, cv2.bitwise_not(bg_mask))

            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (11, 11))
            roi_mask = cv2.morphologyEx(roi_mask, cv2.MORPH_CLOSE, kernel, iterations=3)
            kernel_open = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
            roi_mask = cv2.morphologyEx(roi_mask, cv2.MORPH_OPEN, kernel_open, iterations=1)

            roi_filled = np.zeros_like(roi_mask)
            contours, _ = cv2.findContours(roi_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if contours:
                min_contour_area = (rx2 - rx1) * (ry2 - ry1) * 0.01
                for cnt in contours:
                    if cv2.contourArea(cnt) >= min_contour_area:
                        cv2.drawContours(roi_filled, [cnt], -1, 255, cv2.FILLED)
                
                if np.sum(roi_filled > 0) == 0:
                    largest_cnt = max(contours, key=cv2.contourArea)
                    cv2.drawContours(roi_filled, [largest_cnt], -1, 255, cv2.FILLED)

            wound_mask[ry1:ry2, rx1:rx2] = cv2.bitwise_or(wound_mask[ry1:ry2, rx1:rx2], roi_filled)

        return wound_mask

    @staticmethod
    def exclude_surgical_background(image: np.ndarray, wound_mask: np.ndarray) -> np.ndarray:
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        drape_mask = np.zeros(image.shape[:2], dtype=np.uint8)

        drape_mask = cv2.bitwise_or(drape_mask, cv2.inRange(hsv, np.array([90, 30, 20]), np.array([130, 255, 255])))
        drape_mask = cv2.bitwise_or(drape_mask, cv2.inRange(hsv, np.array([35, 30, 30]), np.array([85, 255, 255])))
        drape_mask = cv2.bitwise_or(drape_mask, cv2.inRange(hsv, np.array([0, 0, 40]), np.array([180, 25, 170])))

        drape_ratio = np.sum(drape_mask > 0) / max(drape_mask.size, 1)
        if drape_ratio < 0.05:
            return wound_mask

        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
        drape_mask = cv2.dilate(drape_mask, kernel, iterations=1)

        cleaned = cv2.bitwise_and(wound_mask, cv2.bitwise_not(drape_mask))

        if np.sum(cleaned > 0) < 0.02 * wound_mask.size:
            return wound_mask

        return cleaned

    @staticmethod
    def create_background_mask_spatial(image: np.ndarray, wound_mask: np.ndarray) -> np.ndarray:
        h, w = image.shape[:2]
        background_mask = np.zeros((h, w), dtype=np.uint8)

        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        very_dark = (gray < 20).astype(np.uint8) * 255
        dark_in_roi = cv2.bitwise_and(very_dark, wound_mask)

        dark_count = np.sum(dark_in_roi > 0)
        roi_count = max(np.sum(wound_mask > 0), 1)
        if dark_count < roi_count * 0.02:
            return background_mask

        gray_f = gray.astype(np.float32)
        local_mean = cv2.blur(gray_f, (5, 5))
        local_sqmean = cv2.blur(gray_f ** 2, (5, 5))
        local_var = local_sqmean - local_mean ** 2
        local_var = np.clip(local_var, 0, None)

        low_var = (local_var < 8.0).astype(np.uint8) * 255

        lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
        a_ch = lab[:, :, 1].astype(np.float32)
        b_ch = lab[:, :, 2].astype(np.float32)
        chroma_deviation = np.sqrt((a_ch - 128.0) ** 2 + (b_ch - 128.0) ** 2)

        achromatic = (chroma_deviation < 5.0).astype(np.uint8) * 255

        bg_candidate = cv2.bitwise_and(dark_in_roi, low_var)
        bg_candidate = cv2.bitwise_and(bg_candidate, achromatic)

        contours, _ = cv2.findContours(bg_candidate, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        border_margin = 3
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area > roi_count * 0.15:
                cv2.drawContours(background_mask, [cnt], -1, 255, cv2.FILLED)
                continue

            x, y, cw, ch = cv2.boundingRect(cnt)
            touches_border = (
                x <= border_margin or
                y <= border_margin or
                (x + cw) >= (w - border_margin) or
                (y + ch) >= (h - border_margin)
            )
            if touches_border and area > 50:
                cv2.drawContours(background_mask, [cnt], -1, 255, cv2.FILLED)
                continue

            cnt_mask = np.zeros((h, w), dtype=np.uint8)
            cv2.drawContours(cnt_mask, [cnt], -1, 255, cv2.FILLED)
            region_var = local_var[cnt_mask > 0]
            if len(region_var) > 10 and np.mean(region_var) < 2.0:
                cv2.drawContours(background_mask, [cnt], -1, 255, cv2.FILLED)

        if np.sum(background_mask > 0) > 0:
            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
            background_mask = cv2.dilate(background_mask, kernel, iterations=1)
            background_mask = cv2.bitwise_and(background_mask, wound_mask)

        return background_mask

    @staticmethod
    def create_zone_masks(wound_mask: np.ndarray, border_width_px: int = 15) -> tuple:
        h, w = wound_mask.shape[:2]
        wound_area = np.sum(wound_mask > 0)
        equiv_radius = np.sqrt(wound_area / np.pi) if wound_area > 0 else 0
        adaptive_width = int(np.clip(equiv_radius * 0.15, 3, border_width_px))

        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * adaptive_width + 1, 2 * adaptive_width + 1))
        eroded = cv2.erode(wound_mask, kernel, iterations=1)

        core_zone = eroded
        peripheral_zone = cv2.bitwise_and(wound_mask, cv2.bitwise_not(core_zone))
        dilated = cv2.dilate(wound_mask, kernel, iterations=1)
        outer_ring = cv2.bitwise_and(dilated, cv2.bitwise_not(wound_mask))

        return peripheral_zone, core_zone, outer_ring


# ============================================================
# Extracted from: src/processing/tissue_analyzer.py
# ============================================================

"""
REDISUS - Sistema de Diagnóstico de Feridas
Analisador de Tecidos com OpenCV

Análise de composição tecidual usando técnicas de visão computacional:
- Segmentação por cor
- Análise de textura
- Classificação de tecidos
"""
import cv2
import numpy as np
from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple, List
from enum import Enum
from loguru import logger


class TissueType(Enum):
    """Tipos de tecido em feridas"""
    GRANULATION = "granulation"     # Vermelho vivo - cicatrização ativa
    SLOUGH = "slough"               # Amarelo/branco - tecido desvitalizado
    NECROSIS = "necrosis"           # Preto/marrom - tecido morto
    EPITHELIALIZATION = "epithelialization"  # Rosa - regeneração
    PERIWOUND = "periwound"         # Pele ao redor
    FIBRIN = "fibrin"               # Amarelo claro
    ESCHAR = "eschar"               # Escara seca


@dataclass
class TissueResult:
    """Resultado da análise de tecidos"""
    tissue_mask: np.ndarray
    tissue_percentages: Dict[str, float]
    dominant_tissue: str
    wound_area_pixels: int
    color_map: np.ndarray
    health_score: float  # 0-100
    features: Dict = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return {
            "tissue_percentages": self.tissue_percentages,
            "dominant_tissue": self.dominant_tissue,
            "wound_area_pixels": self.wound_area_pixels,
            "health_score": self.health_score
        }


# Intervalos HSV para cada tipo de tecido (v2 — recalibrados)
TISSUE_HSV_RANGES = {
    TissueType.GRANULATION: {
        "lower": [np.array([0, 100, 80]), np.array([160, 100, 80]),
                  np.array([0, 60, 100]), np.array([165, 60, 100]),
                  np.array([0, 80, 60]), np.array([158, 80, 60])],
        "upper": [np.array([10, 255, 255]), np.array([180, 255, 255]),
                  np.array([8, 200, 255]), np.array([180, 200, 255]),
                  np.array([12, 255, 150]), np.array([180, 255, 150])]
    },
    TissueType.SLOUGH: {
        "lower": [np.array([15, 50, 140]), np.array([0, 0, 185]),
                  np.array([15, 20, 120]), np.array([30, 30, 130]),
                  np.array([12, 25, 160])],
        "upper": [np.array([38, 255, 255]), np.array([30, 55, 255]),
                  np.array([40, 100, 200]), np.array([50, 180, 230]),
                  np.array([28, 90, 240])]
    },
    TissueType.NECROSIS: {
        # Preto/marrom escuro — exclui H 80-140 (azul/verde cirúrgico)
        "lower": [np.array([0, 0, 0]), np.array([140, 0, 0]),
                  np.array([5, 25, 15]),
                  np.array([0, 5, 5]),
                  np.array([8, 15, 20])],
        "upper": [np.array([80, 255, 40]), np.array([180, 255, 40]),
                  np.array([25, 200, 60]),
                  np.array([180, 30, 50]),
                  np.array([30, 120, 65])]
    },
    TissueType.EPITHELIALIZATION: {
        "lower": [np.array([0, 15, 170]), np.array([155, 15, 170]),
                  np.array([0, 8, 195]), np.array([2, 25, 185])],
        "upper": [np.array([15, 70, 255]), np.array([175, 70, 255]),
                  np.array([12, 45, 255]), np.array([18, 80, 255])]
    },
    TissueType.FIBRIN: {
        "lower": [np.array([20, 50, 180]), np.array([18, 30, 170])],
        "upper": [np.array([40, 150, 255]), np.array([35, 120, 245])]
    },
}

# Cores para visualização (BGR)
TISSUE_COLORS = {
    TissueType.GRANULATION: (60, 60, 220),      # Vermelho
    TissueType.SLOUGH: (80, 220, 220),          # Amarelo
    TissueType.NECROSIS: (40, 40, 40),          # Preto
    TissueType.EPITHELIALIZATION: (200, 180, 255),  # Rosa
    TissueType.PERIWOUND: (80, 200, 80),        # Verde
    TissueType.FIBRIN: (100, 200, 250),         # Amarelo claro
    TissueType.ESCHAR: (30, 30, 60),            # Marrom escuro
}


class TissueAnalyzerCV:
    """
    Analisador de tecidos usando OpenCV.
    
    Analisa a composição tecidual da ferida para avaliar
    o estágio de cicatrização e necessidade de desbridamento.
    
    Tecidos identificados:
    - Granulação: Tecido vermelho vivo, sinal de cicatrização ativa
    - Esfacelo: Tecido amarelado, necessita desbridamento
    - Necrose: Tecido escuro/preto, tecido morto
    - Epitelização: Rosa claro, regeneração da pele
    - Fibrina: Amarelo claro, proteína de coagulação
    
    Uso:
        analyzer = TissueAnalyzerCV()
        result = analyzer.analyze(wound_roi)
        print(f"Granulação: {result.tissue_percentages['granulation']:.1f}%")
    """
    
    def __init__(
        self,
        use_ml_model: bool = False,
        model_path: Optional[str] = None
    ):
        """
        Args:
            use_ml_model: Se deve usar modelo ML quando disponível
            model_path: Caminho para modelo de segmentação
        """
        self.use_ml_model = use_ml_model
        self.model_path = model_path
        self._model = None
        
        # Kernels morfológicos
        self._kernel_small = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        self._kernel_medium = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
        
    def analyze(
        self,
        image: np.ndarray,
        wound_mask: Optional[np.ndarray] = None
    ) -> TissueResult:
        """
        Analisa composição tecidual da ferida.
        
        Args:
            image: Imagem BGR da ferida (ou ROI)
            wound_mask: Máscara opcional da região da ferida
            
        Returns:
            TissueResult com análise completa
        """
        if image is None or image.size == 0:
            return self._empty_result(image.shape[:2] if image is not None else (1, 1))
            
        h, w = image.shape[:2]
        
        # Se não tem máscara, analisa imagem toda
        if wound_mask is None:
            wound_mask = np.ones((h, w), dtype=np.uint8) * 255
            
        # Pré-processamento v2: bilateral (preserva bordas) + CLAHE
        denoised = cv2.bilateralFilter(image, d=9, sigmaColor=50, sigmaSpace=50)
        # Normalização de iluminação via CLAHE no canal L do LAB
        lab_img = cv2.cvtColor(denoised, cv2.COLOR_BGR2LAB)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        lab_img[:, :, 0] = clahe.apply(lab_img[:, :, 0])
        denoised = cv2.cvtColor(lab_img, cv2.COLOR_LAB2BGR)
        hsv = cv2.cvtColor(denoised, cv2.COLOR_BGR2HSV)
        
        # Segmenta cada tipo de tecido
        tissue_masks = {}
        for tissue_type in [TissueType.GRANULATION, TissueType.SLOUGH, 
                           TissueType.NECROSIS, TissueType.EPITHELIALIZATION, 
                           TissueType.FIBRIN]:
            mask = self._segment_tissue(hsv, tissue_type, wound_mask)
            tissue_masks[tissue_type] = mask
            
        # Remove sobreposições (prioridade: granulação > necrose > esfacelo > fibrina > epitelização)
        tissue_masks = self._resolve_overlaps(tissue_masks)
        
        # Calcula porcentagens
        total_wound_pixels = np.sum(wound_mask > 0)
        tissue_percentages = {}
        
        for tissue_type, mask in tissue_masks.items():
            pixel_count = np.sum(mask > 0)
            percentage = (pixel_count / max(total_wound_pixels, 1)) * 100
            tissue_percentages[tissue_type.value] = percentage
            
        # Tecido dominante
        dominant = max(tissue_percentages.items(), key=lambda x: x[1])
        dominant_tissue = dominant[0]
        
        # Cria máscara combinada com IDs
        tissue_mask = np.zeros((h, w), dtype=np.uint8)
        for i, (tissue_type, mask) in enumerate(tissue_masks.items(), 1):
            tissue_mask[mask > 0] = i
            
        # Mapa de cores para visualização
        color_map = self._create_color_map(tissue_masks, image.shape)
        
        # Calcula score de saúde
        health_score = self._calculate_health_score(tissue_percentages)
        
        # Features adicionais
        features = self._extract_texture_features(image, wound_mask)
        
        return TissueResult(
            tissue_mask=tissue_mask,
            tissue_percentages=tissue_percentages,
            dominant_tissue=dominant_tissue,
            wound_area_pixels=total_wound_pixels,
            color_map=color_map,
            health_score=health_score,
            features=features
        )
    
    def _segment_tissue(
        self,
        hsv: np.ndarray,
        tissue_type: TissueType,
        wound_mask: np.ndarray
    ) -> np.ndarray:
        """Segmenta um tipo específico de tecido"""
        if tissue_type not in TISSUE_HSV_RANGES:
            return np.zeros(hsv.shape[:2], dtype=np.uint8)
            
        ranges = TISSUE_HSV_RANGES[tissue_type]
        
        # Cria máscara combinada de todos os intervalos
        mask = np.zeros(hsv.shape[:2], dtype=np.uint8)
        
        for lower, upper in zip(ranges["lower"], ranges["upper"]):
            partial_mask = cv2.inRange(hsv, lower, upper)
            mask = cv2.bitwise_or(mask, partial_mask)
            
        # Aplica máscara da ferida
        mask = cv2.bitwise_and(mask, wound_mask)
        
        # Limpa ruído
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, self._kernel_small)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, self._kernel_medium)
        
        return mask
    
    def _resolve_overlaps(
        self,
        tissue_masks: Dict[TissueType, np.ndarray]
    ) -> Dict[TissueType, np.ndarray]:
        """Remove sobreposições entre máscaras de tecido"""
        priority = [
            TissueType.NECROSIS,      # Necrose tem prioridade (mais crítico)
            TissueType.GRANULATION,
            TissueType.SLOUGH,
            TissueType.FIBRIN,
            TissueType.EPITHELIALIZATION
        ]
        
        resolved = {}
        used_pixels = None
        
        for tissue_type in priority:
            if tissue_type not in tissue_masks:
                continue
                
            mask = tissue_masks[tissue_type].copy()
            
            if used_pixels is not None:
                # Remove pixels já usados
                mask = cv2.bitwise_and(mask, cv2.bitwise_not(used_pixels))
                
            resolved[tissue_type] = mask
            
            # Atualiza pixels usados
            if used_pixels is None:
                used_pixels = mask.copy()
            else:
                used_pixels = cv2.bitwise_or(used_pixels, mask)
                
        return resolved
    
    def _create_color_map(
        self,
        tissue_masks: Dict[TissueType, np.ndarray],
        shape: Tuple[int, int, int]
    ) -> np.ndarray:
        """Cria mapa de cores para visualização"""
        color_map = np.zeros(shape, dtype=np.uint8)
        color_map[:] = (128, 128, 128)  # Background cinza
        
        for tissue_type, mask in tissue_masks.items():
            color = TISSUE_COLORS.get(tissue_type, (128, 128, 128))
            color_map[mask > 0] = color
            
        return color_map
    
    def _calculate_health_score(
        self,
        tissue_percentages: Dict[str, float]
    ) -> float:
        """
        Calcula score de saúde da ferida (0-100).
        
        Baseado na proporção de tecidos:
        - Granulação alta = bom
        - Necrose alta = ruim
        - Esfacelo = moderado
        """
        granulation = tissue_percentages.get("granulation", 0)
        epithelialization = tissue_percentages.get("epithelialization", 0)
        slough = tissue_percentages.get("slough", 0)
        necrosis = tissue_percentages.get("necrosis", 0)
        
        # Pontuação positiva para tecidos saudáveis
        positive_score = granulation * 1.0 + epithelialization * 1.5
        
        # Pontuação negativa para tecidos problemáticos
        negative_score = necrosis * 1.5 + slough * 0.5
        
        # Score final
        score = 50 + (positive_score - negative_score) * 0.5
        
        return max(0, min(100, score))
    
    def _extract_texture_features(
        self,
        image: np.ndarray,
        wound_mask: np.ndarray
    ) -> Dict:
        """Extrai características de textura"""
        features = {}
        
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        # Aplica máscara
        gray_masked = cv2.bitwise_and(gray, wound_mask)
        
        # Estatísticas básicas
        non_zero = gray_masked[wound_mask > 0]
        if len(non_zero) > 0:
            features["mean_intensity"] = float(np.mean(non_zero))
            features["std_intensity"] = float(np.std(non_zero))
            features["min_intensity"] = float(np.min(non_zero))
            features["max_intensity"] = float(np.max(non_zero))
            
        # Textura (variância local)
        kernel_size = 5
        local_mean = cv2.blur(gray.astype(np.float32), (kernel_size, kernel_size))
        local_sq_mean = cv2.blur((gray.astype(np.float32) ** 2), (kernel_size, kernel_size))
        local_var = local_sq_mean - local_mean ** 2
        
        var_masked = local_var[wound_mask > 0]
        if len(var_masked) > 0:
            features["texture_variance"] = float(np.mean(var_masked))
            
        # Entropia (homogeneidade)
        hist = cv2.calcHist([gray_masked], [0], wound_mask, [256], [0, 256])
        hist = hist.flatten() / (np.sum(hist) + 1e-6)
        hist = hist[hist > 0]
        
        if len(hist) > 0:
            features["entropy"] = float(-np.sum(hist * np.log2(hist + 1e-10)))
            
        return features
    
    def _empty_result(self, shape: Tuple[int, int]) -> TissueResult:
        """Retorna resultado vazio"""
        return TissueResult(
            tissue_mask=np.zeros(shape, dtype=np.uint8),
            tissue_percentages={t.value: 0.0 for t in TissueType},
            dominant_tissue="none",
            wound_area_pixels=0,
            color_map=np.zeros((*shape, 3), dtype=np.uint8),
            health_score=0,
            features={}
        )
    
    def visualize_result(
        self,
        original: np.ndarray,
        result: TissueResult,
        alpha: float = 0.5
    ) -> np.ndarray:
        """
        Cria visualização do resultado.
        
        Args:
            original: Imagem original
            result: Resultado da análise
            alpha: Transparência do overlay
            
        Returns:
            Imagem com overlay de tecidos
        """
        output = original.copy()
        
        # Overlay do mapa de cores
        cv2.addWeighted(result.color_map, alpha, output, 1 - alpha, 0, output)
        
        # Adiciona legenda
        output = self._draw_legend(output, result.tissue_percentages)
        
        # Adiciona score de saúde
        cv2.putText(
            output,
            f"Score: {result.health_score:.0f}/100",
            (output.shape[1] - 150, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (255, 255, 255),
            2
        )
        
        return output
    
    def _draw_legend(
        self,
        image: np.ndarray,
        percentages: Dict[str, float]
    ) -> np.ndarray:
        """Desenha legenda de tecidos"""
        output = image.copy()
        h, w = image.shape[:2]
        
        y = 30
        for tissue_name, percentage in sorted(percentages.items(), key=lambda x: -x[1]):
            if percentage < 1:
                continue
                
            # Encontra tipo de tecido correspondente
            tissue_type = None
            for t in TissueType:
                if t.value == tissue_name:
                    tissue_type = t
                    break
                    
            if tissue_type:
                color = TISSUE_COLORS.get(tissue_type, (128, 128, 128))
            else:
                color = (128, 128, 128)
                
            # Quadrado colorido
            cv2.rectangle(output, (10, y - 12), (25, y + 3), color, -1)
            cv2.rectangle(output, (10, y - 12), (25, y + 3), (255, 255, 255), 1)
            
            # Texto
            text = f"{tissue_name}: {percentage:.1f}%"
            cv2.putText(output, text, (30, y), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1)
            
            y += 22
            
        return output


# ============================================================
# Extracted from: src/processing/wound_classifier_cv.py
# ============================================================

"""
REDISUS - Sistema de Diagnóstico de Feridas
Classificador de Feridas com OpenCV

Classifica o tipo de ferida baseado em características visuais:
- Úlcera venosa
- Úlcera arterial
- Pé diabético (neuropática)
- Lesão por pressão
- Ferida cirúrgica
"""
import cv2
import numpy as np
from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple, List
from enum import Enum
from pathlib import Path
from loguru import logger


class WoundEtiology(Enum):
    """Etiologias de feridas"""
    VENOUS_ULCER = "venous_ulcer"
    ARTERIAL_ULCER = "arterial_ulcer"
    DIABETIC_FOOT = "diabetic_foot"
    PRESSURE_INJURY = "pressure_injury"
    SURGICAL_WOUND = "surgical_wound"
    TRAUMATIC = "traumatic"
    BURN = "burn"
    UNKNOWN = "unknown"


ETIOLOGY_INFO = {
    WoundEtiology.VENOUS_ULCER: {
        "name": "Úlcera Venosa",
        "description": "Ferida causada por insuficiência venosa, geralmente nas pernas",
        "characteristics": ["Bordas irregulares", "Localização em MMII", "Edema perilesional"],
        "typical_location": "Maléolo medial, terço inferior da perna"
    },
    WoundEtiology.ARTERIAL_ULCER: {
        "name": "Úlcera Arterial",
        "description": "Ferida causada por insuficiência arterial, dor intensa",
        "characteristics": ["Bordas bem definidas", "Base pálida", "Dor intensa"],
        "typical_location": "Dedos, calcâneo, proeminências ósseas"
    },
    WoundEtiology.DIABETIC_FOOT: {
        "name": "Pé Diabético",
        "description": "Ferida neuropática em pacientes diabéticos",
        "characteristics": ["Calosidades", "Deformidades", "Localização plantar"],
        "typical_location": "Região plantar, dedos, pontos de pressão"
    },
    WoundEtiology.PRESSURE_INJURY: {
        "name": "Lesão por Pressão",
        "description": "Lesão causada por pressão prolongada em proeminências ósseas",
        "characteristics": ["Localização em proeminência óssea", "Formato regular", "Bordas bem definidas"],
        "typical_location": "Sacro, calcâneos, trocânteres, occipital"
    },
    WoundEtiology.SURGICAL_WOUND: {
        "name": "Ferida Cirúrgica",
        "description": "Ferida resultante de procedimento cirúrgico",
        "characteristics": ["Bordas regulares", "Formato linear ou elíptico", "Presença de suturas"],
        "typical_location": "Variável conforme procedimento"
    },
    WoundEtiology.TRAUMATIC: {
        "name": "Ferida Traumática",
        "description": "Ferida causada por trauma mecânico",
        "characteristics": ["Bordas irregulares", "Histórico de trauma", "Formato variável"],
        "typical_location": "Extremidades, face, mãos"
    },
    WoundEtiology.BURN: {
        "name": "Queimadura",
        "description": "Lesão térmica, química ou elétrica",
        "characteristics": ["Eritema", "Bolhas", "Alteração de cor"],
        "typical_location": "Variável conforme agente causal"
    },
    WoundEtiology.UNKNOWN: {
        "name": "Não Identificado",
        "description": "Etiologia não determinada pela análise visual",
        "characteristics": [],
        "typical_location": "N/A"
    }
}


@dataclass
class ClassificationResult:
    """Resultado da classificação de ferida"""
    etiology: WoundEtiology
    confidence: float
    probabilities: Dict[str, float]
    features: Dict[str, float] = field(default_factory=dict)
    needs_review: bool = False
    
    @property
    def name(self) -> str:
        return ETIOLOGY_INFO[self.etiology]["name"]
    
    @property
    def description(self) -> str:
        return ETIOLOGY_INFO[self.etiology]["description"]
    
    def to_dict(self) -> Dict:
        return {
            "etiology": self.etiology.value,
            "name": self.name,
            "confidence": self.confidence,
            "probabilities": self.probabilities,
            "description": self.description,
            "needs_review": self.needs_review
        }


class WoundClassifierCV:
    """
    Classificador de feridas usando OpenCV e regras heurísticas.
    
    Este classificador usa características visuais extraídas para
    determinar a etiologia provável da ferida. Pode ser complementado
    com modelo ML quando disponível.
    
    Características analisadas:
    - Cor e distribuição de cores
    - Forma e bordas
    - Textura
    - Proporção de tecidos
    
    Uso:
        classifier = WoundClassifierCV()
        result = classifier.classify(wound_image, tissue_result)
        print(f"Etiologia: {result.name} ({result.confidence:.1%})")
    """
    
    def __init__(
        self,
        model_path: Optional[str] = None,
        use_keras_model: bool = False
    ):
        """
        Args:
            model_path: Caminho para modelo ML (opcional)
            use_keras_model: Se deve usar modelo Keras quando disponível
        """
        self.model_path = model_path
        self.use_keras_model = use_keras_model
        self._model = None
        self._model_loaded = False
        
        # Tenta carregar modelo se especificado
        if model_path and use_keras_model:
            self._load_model()
            
    def _load_model(self) -> bool:
        """Carrega modelo Keras/TensorFlow"""
        if not self.model_path:
            return False
            
        path = Path(self.model_path)
        if not path.exists():
            logger.warning(f"Modelo não encontrado: {path}")
            return False
            
        try:
            import tensorflow as tf
            self._model = tf.keras.models.load_model(str(path))
            self._model_loaded = True
            logger.info(f"Modelo carregado: {path.name}")
            return True
        except Exception as e:
            logger.error(f"Erro ao carregar modelo: {e}")
            return False
            
    def classify(
        self,
        image: np.ndarray,
        tissue_percentages: Optional[Dict[str, float]] = None,
        wound_mask: Optional[np.ndarray] = None
    ) -> ClassificationResult:
        """
        Classifica a etiologia da ferida.
        
        Args:
            image: Imagem BGR da ferida
            tissue_percentages: Porcentagens de tecido (opcional)
            wound_mask: Máscara da ferida (opcional)
            
        Returns:
            ClassificationResult com classificação
        """
        if image is None or image.size == 0:
            return self._unknown_result()
            
        # Usa modelo ML se disponível
        if self._model_loaded and self._model is not None:
            return self._classify_with_model(image)
            
        # Extrai características
        features = self._extract_features(image, tissue_percentages, wound_mask)
        
        # Classifica com regras heurísticas
        probabilities = self._calculate_probabilities(features)
        
        # Determina etiologia mais provável
        best_etiology = max(probabilities.items(), key=lambda x: x[1])
        etiology = WoundEtiology(best_etiology[0])
        confidence = best_etiology[1]
        
        # Determina se precisa revisão
        sorted_probs = sorted(probabilities.values(), reverse=True)
        needs_review = confidence < 0.6 or (len(sorted_probs) > 1 and sorted_probs[0] - sorted_probs[1] < 0.15)
        
        return ClassificationResult(
            etiology=etiology,
            confidence=confidence,
            probabilities=probabilities,
            features=features,
            needs_review=needs_review
        )
    
    def _extract_features(
        self,
        image: np.ndarray,
        tissue_percentages: Optional[Dict[str, float]],
        wound_mask: Optional[np.ndarray]
    ) -> Dict[str, float]:
        """Extrai características para classificação"""
        features = {}
        
        h, w = image.shape[:2]
        
        # Se não tem máscara, cria uma básica
        if wound_mask is None:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            _, wound_mask = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            
        # Características de cor
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        hsv_masked = hsv.copy()
        hsv_masked[wound_mask == 0] = 0
        
        # Médias de H, S, V na região da ferida
        non_zero = wound_mask > 0
        if np.sum(non_zero) > 0:
            features["mean_hue"] = np.mean(hsv[non_zero, 0])
            features["mean_saturation"] = np.mean(hsv[non_zero, 1])
            features["mean_value"] = np.mean(hsv[non_zero, 2])
            features["std_hue"] = np.std(hsv[non_zero, 0])
        else:
            features["mean_hue"] = 0
            features["mean_saturation"] = 0
            features["mean_value"] = 0
            features["std_hue"] = 0
            
        # Características de forma
        contours, _ = cv2.findContours(wound_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        if contours:
            largest = max(contours, key=cv2.contourArea)
            area = cv2.contourArea(largest)
            perimeter = cv2.arcLength(largest, True)
            
            # Circularidade
            features["circularity"] = 4 * np.pi * area / (perimeter ** 2 + 1e-6)
            
            # Aspect ratio
            x, y, bw, bh = cv2.boundingRect(largest)
            features["aspect_ratio"] = max(bw, bh) / (min(bw, bh) + 1e-6)
            
            # Convexidade
            hull = cv2.convexHull(largest)
            hull_area = cv2.contourArea(hull)
            features["convexity"] = area / (hull_area + 1e-6)
            
            # Posição relativa (pode indicar tipo de ferida)
            features["relative_y"] = (y + bh/2) / h  # 0=topo, 1=base
            
            # Compacidade das bordas (regularidade)
            features["border_regularity"] = self._calculate_border_regularity(largest)
            
        else:
            features["circularity"] = 0
            features["aspect_ratio"] = 1
            features["convexity"] = 0
            features["relative_y"] = 0.5
            features["border_regularity"] = 0
            
        # Porcentagens de tecido (se fornecidas)
        if tissue_percentages:
            features["granulation"] = tissue_percentages.get("granulation", 0)
            features["slough"] = tissue_percentages.get("slough", 0)
            features["necrosis"] = tissue_percentages.get("necrosis", 0)
            features["epithelialization"] = tissue_percentages.get("epithelialization", 0)
        else:
            features["granulation"] = 0
            features["slough"] = 0
            features["necrosis"] = 0
            features["epithelialization"] = 0
            
        return features
    
    def _calculate_border_regularity(self, contour: np.ndarray) -> float:
        """
        Calcula regularidade da borda.
        
        Bordas mais regulares têm valor mais alto.
        """
        # Aproxima contorno
        epsilon = 0.02 * cv2.arcLength(contour, True)
        approx = cv2.approxPolyDP(contour, epsilon, True)
        
        # Número de vértices (menos = mais regular)
        n_vertices = len(approx)
        
        # Normaliza (4-20 vértices é o range típico)
        regularity = 1 - min(max((n_vertices - 4) / 16, 0), 1)
        
        return regularity
    
    def _calculate_probabilities(
        self,
        features: Dict[str, float]
    ) -> Dict[str, float]:
        """
        Calcula probabilidades para cada etiologia.
        
        Usa sistema de regras baseado nas características.
        """
        scores = {e.value: 0.0 for e in WoundEtiology if e != WoundEtiology.UNKNOWN}
        
        # Extrai features
        circularity = features.get("circularity", 0)
        border_reg = features.get("border_regularity", 0)
        granulation = features.get("granulation", 0)
        necrosis = features.get("necrosis", 0)
        slough = features.get("slough", 0)
        aspect_ratio = features.get("aspect_ratio", 1)
        convexity = features.get("convexity", 0)
        mean_hue = features.get("mean_hue", 0)
        relative_y = features.get("relative_y", 0.5)
        
        # --- Úlcera Venosa ---
        # Bordas irregulares, alta granulação, localização em MI
        scores[WoundEtiology.VENOUS_ULCER.value] = (
            (1 - border_reg) * 0.2 +  # Bordas irregulares
            (granulation / 100) * 0.3 +  # Alta granulação
            (1 - circularity) * 0.2 +  # Formato irregular
            relative_y * 0.15 +  # Localização inferior
            min(aspect_ratio / 2, 1) * 0.15  # Formato alongado
        )
        
        # --- Úlcera Arterial ---
        # Bordas definidas, base pálida (baixa saturação), pouca granulação
        pale_score = max(0, 1 - features.get("mean_saturation", 128) / 200)
        scores[WoundEtiology.ARTERIAL_ULCER.value] = (
            border_reg * 0.25 +  # Bordas bem definidas
            pale_score * 0.25 +  # Base pálida
            (1 - granulation / 100) * 0.2 +  # Pouca granulação
            (necrosis / 100) * 0.15 +  # Pode ter necrose
            circularity * 0.15  # Formato mais regular
        )
        
        # --- Pé Diabético ---
        # Bordas calosas, localização plantar, pode ter necrose
        scores[WoundEtiology.DIABETIC_FOOT.value] = (
            (necrosis / 100) * 0.25 +  # Frequente necrose
            (1 - granulation / 100) * 0.2 +  # Cicatrização lenta
            circularity * 0.2 +  # Formato mais circular
            relative_y * 0.15 +  # Localização em pés
            convexity * 0.2  # Margens mais regulares
        )
        
        # --- Lesão por Pressão ---
        # Alta circularidade, bordas definidas, localização em proeminência
        scores[WoundEtiology.PRESSURE_INJURY.value] = (
            circularity * 0.3 +  # Alta circularidade
            border_reg * 0.25 +  # Bordas bem definidas
            (necrosis / 100) * 0.2 +  # Pode ter necrose central
            convexity * 0.15 +  # Formato regular
            (1 if aspect_ratio < 1.5 else 0.5) * 0.1  # Proporções regulares
        )
        
        # --- Ferida Cirúrgica ---
        # Bordas muito regulares, formato linear, alta convexidade
        linear_score = max(0, (aspect_ratio - 2) / 3) if aspect_ratio > 2 else 0
        scores[WoundEtiology.SURGICAL_WOUND.value] = (
            border_reg * 0.35 +  # Bordas muito regulares
            linear_score * 0.25 +  # Formato linear
            convexity * 0.2 +  # Alta convexidade
            (granulation / 100) * 0.1 +  # Geralmente boa granulação
            (1 - necrosis / 100) * 0.1  # Pouca necrose
        )
        
        # --- Traumática ---
        scores[WoundEtiology.TRAUMATIC.value] = (
            (1 - border_reg) * 0.3 +  # Bordas irregulares
            (1 - convexity) * 0.2 +  # Formato irregular
            (granulation / 100) * 0.2 +  # Pode ter granulação
            (1 - circularity) * 0.15 +
            0.15  # Base
        )
        
        # --- Queimadura ---
        # Coloração característica, pode ser extensa
        burn_hue_score = 1 if 0 <= mean_hue <= 20 or mean_hue >= 160 else 0.3
        epithelization_factor = (features.get("epithelialization", 0) / 100) * 0.2 if features.get("epithelialization", 0) > 0 else 0
        scores[WoundEtiology.BURN.value] = (
            burn_hue_score * 0.3 +  # Coloração avermelhada
            (1 - circularity) * 0.2 +  # Formato irregular
            epithelization_factor +
            0.3  # Base
        )
        
        # Normaliza para probabilidades
        total = sum(scores.values())
        if total > 0:
            probabilities = {k: v / total for k, v in scores.items()}
        else:
            # Distribuição uniforme se não houver scores
            probabilities = {k: 1/len(scores) for k in scores.keys()}
            
        return probabilities
    
    def _classify_with_model(self, image: np.ndarray) -> ClassificationResult:
        """Classifica usando modelo ML"""
        try:
            # Pré-processa imagem
            img_resized = cv2.resize(image, (224, 224))
            img_rgb = cv2.cvtColor(img_resized, cv2.COLOR_BGR2RGB)
            img_normalized = img_rgb.astype(np.float32) / 255.0
            img_batch = np.expand_dims(img_normalized, axis=0)
            
            # Inferência
            predictions = self._model.predict(img_batch, verbose=0)[0]
            
            # Mapeia para etiologias
            etiologies = list(WoundEtiology)[:-1]  # Exclui UNKNOWN
            probabilities = {}
            
            for i, etiology in enumerate(etiologies):
                if i < len(predictions):
                    probabilities[etiology.value] = float(predictions[i])
                else:
                    probabilities[etiology.value] = 0.0
                    
            # Encontra melhor
            best = max(probabilities.items(), key=lambda x: x[1])
            etiology = WoundEtiology(best[0])
            confidence = best[1]
            
            return ClassificationResult(
                etiology=etiology,
                confidence=confidence,
                probabilities=probabilities,
                needs_review=confidence < 0.6
            )
            
        except Exception as e:
            logger.error(f"Erro na classificação com modelo: {e}")
            return self._unknown_result()
    
    def _unknown_result(self) -> ClassificationResult:
        """Retorna resultado desconhecido"""
        return ClassificationResult(
            etiology=WoundEtiology.UNKNOWN,
            confidence=0.0,
            probabilities={e.value: 0.0 for e in WoundEtiology},
            needs_review=True
        )


# ============================================================
# Extracted from: src/processing/wound_detector_cv.py
# ============================================================

"""
REDISUS - Sistema de Diagnostico de Feridas
Detector de Feridas com OpenCV

Este modulo implementa deteccao de feridas em tempo real usando
tecnicas classicas de visao computacional e modelos de ML quando disponiveis.

Tecnicas utilizadas:
- Segmentacao por cor (HSV)
- Analise morfologica
- Deteccao de contornos
- Classificacao de texturas
- Filtragem de falsos positivos
- Integracao com modelos YOLO/TensorFlow quando disponiveis
"""
import time
from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Dict, Any
from enum import Enum
from pathlib import Path

import cv2
import numpy as np
from loguru import logger


class DetectionMethod(Enum):
    """Metodos de deteccao disponiveis"""
    COLOR_SEGMENTATION = "color"
    EDGE_DETECTION = "edge"
    TEXTURE_ANALYSIS = "texture"
    COMBINED = "combined"
    TEXTURE_PRIORITY = "texture_priority"  # Prioriza textura sobre cor
    ML_MODEL = "ml"


@dataclass
class DetectionResult:
    """Resultado de uma detecção de ferida"""
    bbox: Tuple[int, int, int, int]  # (x1, y1, x2, y2)
    confidence: float
    mask: Optional[np.ndarray] = None
    contour: Optional[np.ndarray] = None
    wound_type: str = "wound"
    area_pixels: int = 0
    center: Tuple[int, int] = (0, 0)
    features: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def width(self) -> int:
        return self.bbox[2] - self.bbox[0]
    
    @property
    def height(self) -> int:
        return self.bbox[3] - self.bbox[1]
    
    def to_dict(self) -> Dict:
        return {
            "bbox": self.bbox,
            "confidence": self.confidence,
            "wound_type": self.wound_type,
            "area_pixels": self.area_pixels,
            "center": self.center,
            "features": self.features
        }


class ColorRanges:
    """Intervalos de cor HSV para diferentes tipos de tecido"""
    
    # Tons avermelhados (granulação, ferida aberta)
    RED_LOWER_1 = np.array([0, 70, 50])
    RED_UPPER_1 = np.array([10, 255, 255])
    RED_LOWER_2 = np.array([170, 70, 50])
    RED_UPPER_2 = np.array([180, 255, 255])
    
    # Tons amarelados (esfacelo, pus)
    YELLOW_LOWER = np.array([12, 25, 70])
    YELLOW_UPPER = np.array([60, 255, 255])

    # Tons oliva / amarelo-acinzentados de esfacelo umido
    OLIVE_SLOUGH_LOWER = np.array([30, 12, 68])
    OLIVE_SLOUGH_UPPER = np.array([82, 135, 185])
    
    # Tons escuros (necrose)
    DARK_LOWER = np.array([0, 0, 0])
    DARK_UPPER = np.array([180, 255, 85])
    
    # Tons rosados (granulação saudável)
    PINK_LOWER = np.array([0, 30, 100])
    PINK_UPPER = np.array([15, 150, 255])
    
    # Pele (para exclusão) — todos os tons de Fitzpatrick I-VI
    # V mínimo 30 (era 70) para incluir peles escuras (Fitzpatrick V-VI)
    SKIN_LOWER = np.array([0, 15, 30])
    SKIN_UPPER = np.array([30, 180, 255])
    # Faixa adicional para pele muito escura (baixa saturação)
    SKIN_DARK_LOWER = np.array([0, 10, 25])
    SKIN_DARK_UPPER = np.array([25, 100, 110])


class WoundDetectorCV:
    """
    Detector de feridas usando OpenCV.
    
    Combina multiplas tecnicas para deteccao robusta:
    1. Segmentacao por cor (HSV) para identificar tecidos
    2. Deteccao de bordas para definir contornos
    3. Analise morfologica para refinar mascaras
    4. Analise de textura para classificacao
    5. Filtragem de falsos positivos (dedos, dispositivos, pele saudavel)
    
    Pode integrar com modelos ML quando disponiveis.
    
    Uso:
        detector = WoundDetectorCV()
        
        while True:
            frame = camera.read()
            detections = detector.detect(frame)
            
            for det in detections:
                cv2.rectangle(frame, det.bbox[:2], det.bbox[2:], (0,255,0), 2)
    """
    
    # Configuracoes padrao
    DEFAULT_MIN_AREA = 1500  # Area minima aumentada para reduzir falsos positivos
    DEFAULT_MAX_AREA = 500000  # Area maxima em pixels
    DEFAULT_CONFIDENCE_THRESHOLD = 0.45  # Limiar aumentado
    
    def __init__(
        self,
        method: DetectionMethod = DetectionMethod.TEXTURE_PRIORITY,
        min_area: int = DEFAULT_MIN_AREA,
        max_area: int = DEFAULT_MAX_AREA,
        confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD,
        model_path: Optional[str] = None,
        enable_false_positive_filter: bool = True,
        texture_weight: float = 0.5,
        color_weight: float = 0.3
    ):
        """
        Args:
            method: Metodo de deteccao
            min_area: Area minima da deteccao
            max_area: Area maxima da deteccao
            confidence_threshold: Limiar de confianca
            model_path: Caminho para modelo ML (opcional)
            enable_false_positive_filter: Ativa filtro de falsos positivos
            texture_weight: Peso da analise de textura (0-1)
            color_weight: Peso da analise de cor (0-1)
        """
        self.method = method
        self.min_area = min_area
        self.max_area = max_area
        self.confidence_threshold = confidence_threshold
        self.model_path = model_path
        self.enable_false_positive_filter = enable_false_positive_filter
        self.texture_weight = texture_weight
        self.color_weight = color_weight
        
        # Modelo ML (carregado sob demanda)
        self._ml_model = None
        self._ml_loaded = False
        
        # Filtro de falsos positivos
        self._fp_filter = None
        if enable_false_positive_filter:
            try:
                from .false_positive_filter import FalsePositiveFilter
                self._fp_filter = FalsePositiveFilter(
                    min_biological_score=0.20,
                    min_perilesional_score=0.10,
                    max_finger_score=0.65,
                    max_device_score=0.55
                )
            except ImportError:
                logger.warning("Filtro de falsos positivos nao disponivel")
        
        # Kernels morfologicos
        self._kernel_small = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        self._kernel_medium = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (11, 11))
        self._kernel_large = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (21, 21))
        
        # Historico para estabilizacao
        self._detection_history: List[List[DetectionResult]] = []
        self._history_size = 5
        
        # Metricas
        self._inference_times: List[float] = []
        self._false_positives_filtered = 0
        
        logger.info(f"WoundDetectorCV inicializado (metodo: {method.value}, fp_filter: {enable_false_positive_filter})")
        
    def detect(self, frame: np.ndarray) -> List[DetectionResult]:
        """
        Detecta feridas em um frame.
        
        Args:
            frame: Imagem BGR
            
        Returns:
            Lista de DetectionResult
        """
        start_time = time.perf_counter()
        
        if frame is None or frame.size == 0:
            return []
            
        # Pre-processamento
        processed = self._preprocess(frame)
        
        # Deteccao baseada no metodo
        if self.method == DetectionMethod.COLOR_SEGMENTATION:
            detections = self._detect_by_color(frame, processed)
        elif self.method == DetectionMethod.EDGE_DETECTION:
            detections = self._detect_by_edges(frame, processed)
        elif self.method == DetectionMethod.TEXTURE_ANALYSIS:
            detections = self._detect_by_texture(frame, processed)
        elif self.method == DetectionMethod.TEXTURE_PRIORITY:
            detections = self._detect_texture_priority(frame, processed)
        elif self.method == DetectionMethod.ML_MODEL and self._load_ml_model():
            detections = self._detect_by_ml(frame)
        else:
            # Metodo combinado (padrao)
            detections = self._detect_combined(frame, processed)
            
        # Filtra por confianca
        detections = [d for d in detections if d.confidence >= self.confidence_threshold]
        
        # Aplica filtro de falsos positivos
        if self._fp_filter is not None and len(detections) > 0:
            original_count = len(detections)
            detections = self._fp_filter.filter_detections(frame, detections)
            self._false_positives_filtered += (original_count - len(detections))
        
        # Estabiliza com historico
        detections = self._stabilize_detections(detections)
        
        # Metricas
        inference_time = (time.perf_counter() - start_time) * 1000
        self._inference_times.append(inference_time)
        if len(self._inference_times) > 100:
            self._inference_times.pop(0)
            
        return detections
    
    def _preprocess(self, frame: np.ndarray) -> Dict[str, np.ndarray]:
        """
        Pré-processa frame para detecção.
        
        Returns:
            Dict com imagens pré-processadas
        """
        # Reduz ruído
        blurred = cv2.GaussianBlur(frame, (5, 5), 0)
        
        # Converte para diferentes espaços de cor
        hsv = cv2.cvtColor(blurred, cv2.COLOR_BGR2HSV)
        lab = cv2.cvtColor(blurred, cv2.COLOR_BGR2LAB)
        gray = cv2.cvtColor(blurred, cv2.COLOR_BGR2GRAY)
        
        # Equalização adaptativa do histograma
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        gray_eq = clahe.apply(gray)
        
        return {
            "original": frame,
            "blurred": blurred,
            "hsv": hsv,
            "lab": lab,
            "gray": gray,
            "gray_eq": gray_eq
        }
    
    def _detect_by_color(
        self,
        frame: np.ndarray,
        processed: Dict[str, np.ndarray]
    ) -> List[DetectionResult]:
        """Detecção baseada em segmentação por cor"""
        hsv = processed["hsv"]
        
        # Cria máscaras para diferentes tecidos
        # Vermelho (ferida, granulação)
        mask_red1 = cv2.inRange(hsv, ColorRanges.RED_LOWER_1, ColorRanges.RED_UPPER_1)
        mask_red2 = cv2.inRange(hsv, ColorRanges.RED_LOWER_2, ColorRanges.RED_UPPER_2)
        mask_red = cv2.bitwise_or(mask_red1, mask_red2)
        
        # Amarelo (esfacelo)
        mask_yellow = cv2.inRange(hsv, ColorRanges.YELLOW_LOWER, ColorRanges.YELLOW_UPPER)
        mask_olive_slough = cv2.inRange(
            hsv, ColorRanges.OLIVE_SLOUGH_LOWER, ColorRanges.OLIVE_SLOUGH_UPPER
        )

        # Escuro (necrose)
        mask_dark = cv2.inRange(hsv, ColorRanges.DARK_LOWER, ColorRanges.DARK_UPPER)
        
        # Rosa (granulação saudável)
        mask_pink = cv2.inRange(hsv, ColorRanges.PINK_LOWER, ColorRanges.PINK_UPPER)
        
        # Combina máscaras
        mask_wound = cv2.bitwise_or(mask_red, mask_yellow)
        mask_wound = cv2.bitwise_or(mask_wound, mask_olive_slough)
        mask_wound = cv2.bitwise_or(mask_wound, mask_dark)
        mask_wound = cv2.bitwise_or(mask_wound, mask_pink)
        
        # Remove pele saudável
        mask_skin = cv2.inRange(hsv, ColorRanges.SKIN_LOWER, ColorRanges.SKIN_UPPER)
        # Não remove completamente, apenas reduz falsos positivos
        
        # Operações morfológicas
        mask_wound = cv2.morphologyEx(mask_wound, cv2.MORPH_CLOSE, self._kernel_medium)
        mask_wound = cv2.morphologyEx(mask_wound, cv2.MORPH_OPEN, self._kernel_small)
        
        # Extrai detecções
        return self._extract_detections(frame, mask_wound, method="color")
    
    def _detect_by_edges(
        self,
        frame: np.ndarray,
        processed: Dict[str, np.ndarray]
    ) -> List[DetectionResult]:
        """Detecção baseada em bordas"""
        gray_eq = processed["gray_eq"]
        
        # Detecção de bordas com Canny
        edges = cv2.Canny(gray_eq, 50, 150)
        
        # Dilata para conectar bordas próximas
        edges = cv2.dilate(edges, self._kernel_small, iterations=2)
        
        # Preenche buracos
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        mask = np.zeros(gray_eq.shape, dtype=np.uint8)
        cv2.drawContours(mask, contours, -1, 255, -1)
        
        return self._extract_detections(frame, mask, method="edge")
    
    def _detect_by_texture(
        self,
        frame: np.ndarray,
        processed: Dict[str, np.ndarray]
    ) -> List[DetectionResult]:
        """Detecção baseada em análise de textura"""
        gray = processed["gray"]
        
        # Calcula variância local (textura)
        kernel_size = 15
        local_mean = cv2.blur(gray.astype(np.float32), (kernel_size, kernel_size))
        local_sq_mean = cv2.blur((gray.astype(np.float32) ** 2), (kernel_size, kernel_size))
        local_var = local_sq_mean - local_mean ** 2
        local_var = np.clip(local_var, 0, None)
        
        # Normaliza
        local_var_norm = cv2.normalize(local_var, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
        
        # Limiariza regiões de alta textura
        _, mask = cv2.threshold(local_var_norm, 50, 255, cv2.THRESH_BINARY)
        
        # Limpa
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, self._kernel_medium)
        
        return self._extract_detections(frame, mask, method="texture")
    
    def _detect_combined(
        self,
        frame: np.ndarray,
        processed: Dict[str, np.ndarray]
    ) -> List[DetectionResult]:
        """
        Deteccao combinada usando multiplos metodos.
        
        Combina:
        - Segmentacao por cor (peso 0.5)
        - Deteccao de bordas (peso 0.3)
        - Analise de textura (peso 0.2)
        """
        # Obtem mascaras de cada metodo
        color_dets = self._detect_by_color(frame, processed)
        
        # Cria mascara combinada
        h, w = frame.shape[:2]
        combined_mask = np.zeros((h, w), dtype=np.float32)
        
        # Adiciona contribuicoes de cada deteccao
        for det in color_dets:
            if det.mask is not None:
                combined_mask += det.mask.astype(np.float32) * self.color_weight
            else:
                x1, y1, x2, y2 = det.bbox
                combined_mask[y1:y2, x1:x2] += self.color_weight
                
        # Adiciona analise de textura
        gray = processed["gray"]
        kernel_size = 11
        local_mean = cv2.blur(gray.astype(np.float32), (kernel_size, kernel_size))
        local_sq_mean = cv2.blur((gray.astype(np.float32) ** 2), (kernel_size, kernel_size))
        local_var = np.clip(local_sq_mean - local_mean ** 2, 0, None)
        local_var_norm = local_var / (local_var.max() + 1e-6)
        
        combined_mask += local_var_norm * self.texture_weight
        
        # Normaliza e limiariza
        combined_mask = np.clip(combined_mask, 0, 1)
        mask_final = (combined_mask > 0.35).astype(np.uint8) * 255
        
        # Limpa mascara
        mask_final = cv2.morphologyEx(mask_final, cv2.MORPH_CLOSE, self._kernel_large)
        mask_final = cv2.morphologyEx(mask_final, cv2.MORPH_OPEN, self._kernel_medium)
        
        # Extrai deteccoes finais
        detections = self._extract_detections(frame, mask_final, method="combined")
        
        # Adiciona analise de cor para cada deteccao
        for det in detections:
            det.features = self._analyze_wound_features(frame, det)
            det.wound_type = self._classify_wound_type(det.features)
            
        return detections
    
    def _detect_texture_priority(
        self,
        frame: np.ndarray,
        processed: Dict[str, np.ndarray]
    ) -> List[DetectionResult]:
        """
        Deteccao priorizando textura sobre cor.
        
        Este metodo e mais robusto contra falsos positivos causados
        por pele saudavel ou objetos com cores similares a feridas.
        
        Pesos:
        - Textura irregular: 0.5
        - Gradiente (bordas): 0.25
        - Cor de ferida: 0.25
        """
        h, w = frame.shape[:2]
        gray = processed["gray"]
        hsv = processed["hsv"]
        
        # 1. ANALISE DE TEXTURA (peso 0.5)
        # Variancia local - feridas tem textura irregular
        kernel_size = 9
        local_mean = cv2.blur(gray.astype(np.float32), (kernel_size, kernel_size))
        local_sq_mean = cv2.blur((gray.astype(np.float32) ** 2), (kernel_size, kernel_size))
        local_var = np.clip(local_sq_mean - local_mean ** 2, 0, None)
        
        # Normaliza variancia
        texture_score = local_var / (np.percentile(local_var, 95) + 1e-6)
        texture_score = np.clip(texture_score, 0, 1)
        
        # Entropia local RAPIDA (aproximacao vetorizada)
        # entropy ~ log2(variancia + 1) — proxy eficiente sem loop
        entropy_map = np.log2(local_var + 1.0)
        entropy_norm = entropy_map / (np.max(entropy_map) + 1e-6)
        
        # Combina metricas de textura
        texture_mask = (texture_score * 0.6 + entropy_norm * 0.4)
        
        # 2. ANALISE DE GRADIENTE (peso 0.25)
        # Detecta bordas irregulares (caracteristica de feridas)
        gradient_x = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
        gradient_y = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
        gradient_mag = np.sqrt(gradient_x**2 + gradient_y**2)
        gradient_norm = gradient_mag / (np.percentile(gradient_mag, 95) + 1e-6)
        gradient_norm = np.clip(gradient_norm, 0, 1)
        
        # Variancia do gradiente (bordas irregulares vs retas)
        grad_var = cv2.blur((gradient_norm ** 2), (15, 15)) - cv2.blur(gradient_norm, (15, 15)) ** 2
        grad_var_norm = grad_var / (np.max(grad_var) + 1e-6)
        
        # 3. ANALISE DE COR (peso 0.25, reduzido)
        # Tons biologicos de ferida
        # Vermelho
        mask_red1 = cv2.inRange(hsv, ColorRanges.RED_LOWER_1, ColorRanges.RED_UPPER_1)
        mask_red2 = cv2.inRange(hsv, ColorRanges.RED_LOWER_2, ColorRanges.RED_UPPER_2)
        mask_red = cv2.bitwise_or(mask_red1, mask_red2)
        
        # Amarelo (esfacelo)
        mask_yellow = cv2.inRange(hsv, ColorRanges.YELLOW_LOWER, ColorRanges.YELLOW_UPPER)
        mask_olive_slough = cv2.inRange(
            hsv, ColorRanges.OLIVE_SLOUGH_LOWER, ColorRanges.OLIVE_SLOUGH_UPPER
        )

        # Escuro (necrose)
        mask_dark = cv2.inRange(hsv, ColorRanges.DARK_LOWER, ColorRanges.DARK_UPPER)

        # Rosa/vermelho claro
        mask_pink = cv2.inRange(hsv, ColorRanges.PINK_LOWER, ColorRanges.PINK_UPPER)

        color_mask = cv2.bitwise_or(mask_red, mask_yellow)
        color_mask = cv2.bitwise_or(color_mask, mask_olive_slough)
        color_mask = cv2.bitwise_or(color_mask, mask_dark)
        color_mask = cv2.bitwise_or(color_mask, mask_pink)
        color_score = color_mask.astype(np.float32) / 255.0
        
        # Suaviza mascara de cor
        color_score = cv2.GaussianBlur(color_score, (11, 11), 0)
        
        # 4. EXCLUSAO DE PELE SAUDAVEL (todos os tons, Fitzpatrick I-VI)
        # Detecta pele uniforme (sem textura) para excluir
        skin_lower = np.array([0, 15, 30])  # V=30 inclui pele escura
        skin_upper = np.array([30, 180, 255])
        skin_mask = cv2.inRange(hsv, skin_lower, skin_upper)
        # Faixa adicional para pele muito escura (Fitzpatrick VI)
        skin_dark = cv2.inRange(hsv, np.array([0, 10, 25]), np.array([25, 100, 110]))
        skin_mask = cv2.bitwise_or(skin_mask, skin_dark)
        
        # Pele saudavel tem baixa variancia de textura
        smooth_skin = (texture_score < 0.2) & (skin_mask > 0)
        exclusion_mask = smooth_skin.astype(np.float32)
        exclusion_mask = cv2.GaussianBlur(exclusion_mask, (21, 21), 0)
        
        # 4.1 EXCLUSAO DE CAMPO CIRURGICO (lencol azul/verde/cinza de maca)
        # Evita que sombras do drape sejam detectadas como ferida
        drape_blue = cv2.inRange(hsv,
                                 np.array([92, 45, 20]), np.array([130, 255, 255]))
        drape_green = cv2.inRange(hsv,
                                  np.array([55, 60, 35]), np.array([95, 255, 255]))
        drape_gray = cv2.inRange(hsv,
                                 np.array([0, 0, 40]), np.array([180, 22, 170]))
        drape_mask = cv2.bitwise_or(drape_blue, drape_green)
        drape_mask = cv2.bitwise_or(drape_mask, drape_gray)
        drape_score = drape_mask.astype(np.float32) / 255.0
        drape_score = cv2.GaussianBlur(drape_score, (15, 15), 0)
        # Soma  a exclusao de drape a mascara de exclusao
        exclusion_mask = np.clip(exclusion_mask + drape_score * 0.85, 0, 1)
        
        # 5. COMBINA SCORES
        combined = (
            texture_mask * 0.45 +          # Textura irregular
            grad_var_norm * 0.2 +          # Bordas irregulares
            gradient_norm * 0.1 +          # Presenca de bordas
            color_score * 0.25             # Cor de ferida (peso reduzido)
        )
        
        # Aplica exclusao
        combined = combined * (1 - exclusion_mask * 0.7)
        
        # Normaliza
        combined = np.clip(combined, 0, 1)
        
        # Limiariza
        threshold = 0.35
        mask_final = (combined > threshold).astype(np.uint8) * 255
        
        # Operacoes morfologicas
        mask_final = cv2.morphologyEx(mask_final, cv2.MORPH_CLOSE, self._kernel_large)
        mask_final = cv2.morphologyEx(mask_final, cv2.MORPH_OPEN, self._kernel_medium)
        
        # Remove regioes muito pequenas
        mask_final = cv2.morphologyEx(mask_final, cv2.MORPH_OPEN, self._kernel_small)
        
        # Extrai deteccoes
        detections = self._extract_detections(frame, mask_final, method="texture_priority")
        
        # Analisa cada deteccao
        for det in detections:
            det.features = self._analyze_wound_features(frame, det)
            det.features["texture_score"] = float(np.mean(texture_mask[det.bbox[1]:det.bbox[3], det.bbox[0]:det.bbox[2]]))
            det.features["color_score"] = float(np.mean(color_score[det.bbox[1]:det.bbox[3], det.bbox[0]:det.bbox[2]]))
            det.wound_type = self._classify_wound_type(det.features)
            
        return detections
    
    def _extract_detections(
        self,
        frame: np.ndarray,
        mask: np.ndarray,
        method: str = "unknown"
    ) -> List[DetectionResult]:
        """
        Extrai detecções a partir de uma máscara binária.
        
        Args:
            frame: Frame original
            mask: Máscara binária
            method: Método usado
            
        Returns:
            Lista de DetectionResult
        """
        detections = []
        
        # Encontra contornos
        contours, _ = cv2.findContours(
            mask.astype(np.uint8),
            cv2.RETR_EXTERNAL,
            cv2.CHAIN_APPROX_SIMPLE
        )
        
        for contour in contours:
            area = cv2.contourArea(contour)
            
            # Filtra por área
            if area < self.min_area or area > self.max_area:
                continue
                
            # Bounding box
            x, y, w, h = cv2.boundingRect(contour)
            bbox = (x, y, x + w, y + h)
            
            # Centro
            M = cv2.moments(contour)
            if M["m00"] > 0:
                cx = int(M["m10"] / M["m00"])
                cy = int(M["m01"] / M["m00"])
            else:
                cx, cy = x + w // 2, y + h // 2
                
            # Calcula confiança baseada em múltiplos fatores
            confidence = self._calculate_confidence(frame, contour, area, bbox)
            
            # Cria máscara individual
            det_mask = np.zeros(mask.shape, dtype=np.uint8)
            cv2.drawContours(det_mask, [contour], -1, 255, -1)
            
            detection = DetectionResult(
                bbox=bbox,
                confidence=confidence,
                mask=det_mask,
                contour=contour,
                area_pixels=int(area),
                center=(cx, cy)
            )
            
            detections.append(detection)
            
        # Ordena por confiança
        detections.sort(key=lambda x: x.confidence, reverse=True)
        
        return detections
    
    def _calculate_confidence(
        self,
        frame: np.ndarray,
        contour: np.ndarray,
        area: float,
        bbox: Tuple[int, int, int, int]
    ) -> float:
        """
        Calcula confiança da detecção baseada em múltiplos fatores.
        """
        confidence = 0.5  # Base
        
        # Fator de área (áreas médias têm maior confiança)
        optimal_area = 10000  # Área "ideal"
        area_ratio = min(area / optimal_area, optimal_area / max(area, 1))
        confidence += 0.15 * area_ratio
        
        # Fator de formato (mais circular = maior confiança para feridas)
        perimeter = cv2.arcLength(contour, True)
        circularity = 4 * np.pi * area / (perimeter ** 2 + 1e-6)
        confidence += 0.15 * min(circularity, 1.0)
        
        # Fator de cor (verifica se há cores típicas de ferida)
        x1, y1, x2, y2 = bbox
        roi = frame[y1:y2, x1:x2]
        if roi.size > 0:
            hsv_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
            
            # Verifica tons avermelhados
            mask_red = cv2.inRange(hsv_roi, ColorRanges.RED_LOWER_1, ColorRanges.RED_UPPER_1)
            mask_red2 = cv2.inRange(hsv_roi, ColorRanges.RED_LOWER_2, ColorRanges.RED_UPPER_2)
            red_ratio = (np.sum(mask_red) + np.sum(mask_red2)) / (roi.size + 1)
            confidence += 0.2 * min(red_ratio * 10, 1.0)
            
        return min(confidence, 1.0)
    
    def _analyze_wound_features(
        self,
        frame: np.ndarray,
        detection: DetectionResult
    ) -> Dict[str, Any]:
        """
        Analisa características da ferida detectada.
        """
        features = {}
        
        x1, y1, x2, y2 = detection.bbox
        roi = frame[y1:y2, x1:x2]
        
        if roi.size == 0:
            return features
            
        # Análise de cor
        hsv_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
        
        # Porcentagem de cada tipo de tecido
        total_pixels = roi.shape[0] * roi.shape[1]
        
        # Vermelho (granulação)
        mask_red = cv2.inRange(hsv_roi, ColorRanges.RED_LOWER_1, ColorRanges.RED_UPPER_1)
        mask_red2 = cv2.inRange(hsv_roi, ColorRanges.RED_LOWER_2, ColorRanges.RED_UPPER_2)
        features["red_ratio"] = (np.sum(mask_red > 0) + np.sum(mask_red2 > 0)) / total_pixels
        
        # Amarelo (esfacelo)
        mask_yellow = cv2.inRange(hsv_roi, ColorRanges.YELLOW_LOWER, ColorRanges.YELLOW_UPPER)
        features["yellow_ratio"] = np.sum(mask_yellow > 0) / total_pixels
        
        # Escuro (necrose)
        mask_dark = cv2.inRange(hsv_roi, ColorRanges.DARK_LOWER, ColorRanges.DARK_UPPER)
        features["dark_ratio"] = np.sum(mask_dark > 0) / total_pixels
        
        # Cor média
        mean_color = cv2.mean(roi)[:3]
        features["mean_color_bgr"] = mean_color
        
        # Estatísticas de cor
        features["color_std"] = np.std(roi)
        
        # Análise de forma
        if detection.contour is not None:
            # Circularidade
            perimeter = cv2.arcLength(detection.contour, True)
            features["circularity"] = 4 * np.pi * detection.area_pixels / (perimeter ** 2 + 1e-6)
            
            # Convexidade
            hull = cv2.convexHull(detection.contour)
            hull_area = cv2.contourArea(hull)
            features["convexity"] = detection.area_pixels / (hull_area + 1e-6)
            
            # Aspect ratio
            _, _, w, h = cv2.boundingRect(detection.contour)
            features["aspect_ratio"] = max(w, h) / (min(w, h) + 1e-6)
            
        return features
    
    def _classify_wound_type(self, features: Dict[str, Any]) -> str:
        """
        Classifica tipo de ferida baseado nas características.
        
        Esta é uma classificação simplificada por regras.
        Em produção, usar modelo ML treinado.
        """
        red_ratio = features.get("red_ratio", 0)
        yellow_ratio = features.get("yellow_ratio", 0)
        dark_ratio = features.get("dark_ratio", 0)
        circularity = features.get("circularity", 0)
        
        # Regras simplificadas
        if dark_ratio > 0.3:
            return "necrotic_wound"
        elif yellow_ratio > 0.25:
            return "infected_wound"
        elif red_ratio > 0.4 and circularity > 0.5:
            return "pressure_injury"
        elif red_ratio > 0.3:
            return "granulating_wound"
        elif circularity < 0.3:
            return "surgical_wound"
        else:
            return "wound"
    
    def _stabilize_detections(
        self,
        detections: List[DetectionResult]
    ) -> List[DetectionResult]:
        """
        Estabiliza detecções usando histórico temporal.

        Reduz ruído e detecções intermitentes, mas permite novas
        detecções de alta confiança imediatamente.
        """
        # Adiciona ao histórico
        self._detection_history.append(detections)
        if len(self._detection_history) > self._history_size:
            self._detection_history.pop(0)

        if len(self._detection_history) < 2:
            return detections

        # Para cada detecção atual, verifica consistência com histórico
        stabilized = []
        for det in detections:
            # Conta quantos frames tiveram detecção próxima
            consistent_count = 0
            for past_dets in self._detection_history[:-1]:
                for past_det in past_dets:
                    if self._iou(det.bbox, past_det.bbox) > 0.25:
                        consistent_count += 1
                        break

            # Mantém se consistente em pelo menos 1 frame anterior
            if consistent_count >= 1:
                # Aumenta confiança de detecções estáveis
                det.confidence = min(det.confidence * 1.15, 1.0)
                stabilized.append(det)
            elif det.confidence > 0.55:
                # Mantém detecções de confiança moderada-alta mesmo se novas
                stabilized.append(det)

        return stabilized
    
    def _iou(
        self,
        bbox1: Tuple[int, int, int, int],
        bbox2: Tuple[int, int, int, int]
    ) -> float:
        """Calcula Intersection over Union entre duas bboxes"""
        x1 = max(bbox1[0], bbox2[0])
        y1 = max(bbox1[1], bbox2[1])
        x2 = min(bbox1[2], bbox2[2])
        y2 = min(bbox1[3], bbox2[3])
        
        intersection = max(0, x2 - x1) * max(0, y2 - y1)
        
        area1 = (bbox1[2] - bbox1[0]) * (bbox1[3] - bbox1[1])
        area2 = (bbox2[2] - bbox2[0]) * (bbox2[3] - bbox2[1])
        
        union = area1 + area2 - intersection
        
        return intersection / (union + 1e-6)
    
    def _load_ml_model(self) -> bool:
        """Carrega modelo ML se disponível"""
        if self._ml_loaded:
            return self._ml_model is not None
            
        self._ml_loaded = True
        
        if not self.model_path:
            return False
            
        path = Path(self.model_path)
        if not path.exists():
            logger.warning(f"Modelo não encontrado: {path}")
            return False
            
        try:
            suffix = path.suffix.lower()
            
            if suffix == ".onnx":
                import onnxruntime as ort
                self._ml_model = ort.InferenceSession(str(path))
                logger.info(f"Modelo ONNX carregado: {path.name}")
                
            elif suffix in [".pt", ".pth"]:
                # PyTorch / Ultralytics
                try:
                    from ultralytics import YOLO
                    self._ml_model = YOLO(str(path))
                    logger.info(f"Modelo YOLO carregado: {path.name}")
                except ImportError:
                    logger.warning("Ultralytics não instalado")
                    return False
                    
            elif suffix in [".tflite"]:
                try:
                    import tflite_runtime.interpreter as tflite  # type: ignore[import-not-found]
                except ImportError:
                    import tensorflow.lite as tflite  # type: ignore[import-not-found]
                self._ml_model = tflite.Interpreter(model_path=str(path))
                self._ml_model.allocate_tensors()
                logger.info(f"Modelo TFLite carregado: {path.name}")
                
            return True
            
        except Exception as e:
            logger.error(f"Erro ao carregar modelo: {e}")
            return False
    
    def _detect_by_ml(self, frame: np.ndarray) -> List[DetectionResult]:
        """Detecção usando modelo ML"""
        if self._ml_model is None:
            return []
            
        # TODO: Implementar inferência específica para cada tipo de modelo
        # Por enquanto retorna método combinado
        return self._detect_combined(frame, self._preprocess(frame))
    
    @property
    def avg_inference_time(self) -> float:
        """Tempo médio de inferência em ms"""
        if not self._inference_times:
            return 0.0
        return np.mean(self._inference_times)
    
    def warmup(self, iterations: int = 3):
        """Aquece o detector"""
        dummy = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
        for _ in range(iterations):
            self.detect(dummy)
        self._inference_times.clear()
        logger.info("Detector aquecido")


# ============================================================
# Extracted from: src/processing/dl_tissue_pipeline.py
# ============================================================

"""Deep Learning tissue pipeline for the ClinicalWoundAnalyzer.

Two-stage inference:
  1. Wound-mask segmentation (DeepLabV3-ResNet50, binary) — isolates the wound ROI
  2. Tissue segmentation (DeepLabV3-ResNet50, 5-class) — classifies tissues inside the cropped ROI

When both models are available the pipeline replaces the heuristic HSV/LAB
tissue classification used by ``_segment_clinical_v3``.  When models are
missing the pipeline raises ``DLPipelineUnavailable`` so the caller can
fall back transparently.
"""


import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import cv2
import numpy as np

logger = logging.getLogger(__name__)

LEGACY_ROOT = Path(__file__).resolve().parents[2]

# Default model directories (match training output paths)
WOUND_MASK_MODEL_DIR = LEGACY_ROOT / "models" / "wound_mask_deeplabv3"
WOUND_MASK_CHECKPOINT = "wound_mask_deeplabv3_384.pth"

TISSUE_SEG_MODEL_DIR = LEGACY_ROOT / "models" / "tissue_segmentation_deeplabv3"
TISSUE_SEG_CHECKPOINT = "tissue_segmentation_deeplabv3_384.pth"

# Tissue class mapping (from src.core.config.TissueType)
#   0 = Background, 1 = Granulation, 2 = Slough, 3 = Necrosis, 4 = Periwound
# The ClinicalWoundAnalyzer uses 4 clinical tissue keys:
#   necrosis, slough, granulation, epithelialization
# Mapping: periwound → excluded (not wound tissue), epithelialization is
# detected separately via gradient analysis on the peripheral zone.
DL_CLASS_TO_CLINICAL = {
    1: "granulation",
    2: "slough",
    3: "necrosis",
    # 4 (periwound) is excluded from wound tissue percentages
}

# Colors for tissue overlay (BGR, matching ClinicalWoundAnalyzer conventions)
TISSUE_OVERLAY_COLORS = {
    "necrosis": (30, 30, 60),
    "slough": (80, 220, 220),
    "granulation": (60, 60, 220),
    "epithelialization": (200, 180, 255),
}


class DLPipelineUnavailable(Exception):
    """Raised when DL models are not available for inference."""


@dataclass
class DLTissuePipelineResult:
    """Result from the DL tissue pipeline."""
    wound_mask: np.ndarray            # uint8, 0/255 binary mask
    tissue_mask: np.ndarray           # uint8, indexed [0..4] on full image
    tissue_percentages: Dict[str, float]  # clinical keys → percentage
    seg_map: np.ndarray               # BGR color-coded segmentation map
    tissue_overlay: np.ndarray        # original blended with seg_map
    crop_bbox: Tuple[int, int, int, int]  # (x1, y1, x2, y2) of the crop
    wound_area_pixels: int
    inference_time_ms: float
    metadata: Dict[str, Any] = field(default_factory=dict)


class _DeepLabV3Inference:
    """Lightweight wrapper for a DeepLabV3-ResNet50 checkpoint (state_dict)."""

    def __init__(
        self,
        checkpoint_path: Path,
        num_classes: int,
        input_size: int = 384,
        threshold: float = 0.5,
    ):
        self._checkpoint_path = checkpoint_path
        self._num_classes = num_classes
        self._input_size = input_size
        self._threshold = threshold
        self._model = None
        self._device = None
        self._available = False

    @property
    def available(self) -> bool:
        return self._available

    def load(self) -> bool:
        """Attempt to load the model. Returns True on success."""
        if not self._checkpoint_path.exists():
            logger.info(
                "[DL-Pipeline] Checkpoint não encontrado: %s", self._checkpoint_path
            )
            return False
        try:
            import torch
            from torchvision import models as tv_models

            self._device = torch.device(
                "cuda" if torch.cuda.is_available() else "cpu"
            )

            # Build architecture
            model = tv_models.segmentation.deeplabv3_resnet50(
                num_classes=self._num_classes,
            )
            # Load weights from checkpoint
            ckpt = torch.load(
                str(self._checkpoint_path),
                map_location=self._device,
                weights_only=False,
            )
            state_dict = ckpt.get("model_state_dict", ckpt)
            model.load_state_dict(state_dict)
            model.to(self._device).eval()
            self._model = model
            self._available = True
            logger.info(
                "[DL-Pipeline] Modelo carregado: %s (%s)",
                self._checkpoint_path.name,
                self._device,
            )
            return True
        except Exception as exc:
            logger.warning(
                "[DL-Pipeline] Falha ao carregar %s: %s",
                self._checkpoint_path.name,
                exc,
            )
            return False

    def predict(self, image_rgb: np.ndarray) -> np.ndarray:
        """Run inference on a single RGB image.

        Args:
            image_rgb: H×W×3 uint8 RGB image.

        Returns:
            For binary (num_classes=1): H×W uint8 mask (0/255).
            For multiclass: H×W uint8 class indices.
        """
        if not self._available or self._model is None:
            raise DLPipelineUnavailable("Modelo não carregado")

        import torch

        h_orig, w_orig = image_rgb.shape[:2]

        # Resize to model input
        resized = cv2.resize(
            image_rgb, (self._input_size, self._input_size),
            interpolation=cv2.INTER_AREA,
        )
        # Normalize [0,1] and transpose to CHW
        tensor = resized.astype(np.float32) / 255.0
        tensor = np.transpose(tensor, (2, 0, 1))  # (3, H, W)
        tensor = torch.from_numpy(tensor).unsqueeze(0).to(self._device)

        with torch.no_grad():
            output = self._model(tensor)["out"]  # (1, C, H, W)

            if self._num_classes == 1:
                # Binary segmentation
                prob = output.sigmoid().squeeze(0).squeeze(0).cpu().numpy()
                mask_small = (prob >= self._threshold).astype(np.uint8) * 255
            else:
                # Multi-class segmentation
                mask_small = output.argmax(dim=1).squeeze(0).cpu().numpy().astype(np.uint8)

        # Resize back to original resolution
        mask_full = cv2.resize(
            mask_small, (w_orig, h_orig), interpolation=cv2.INTER_NEAREST,
        )
        return mask_full


class DLTissuePipeline:
    """Two-stage DL pipeline: wound-mask → crop → tissue segmentation.

    Usage::

        pipeline = DLTissuePipeline()
        if pipeline.available:
            result = pipeline.analyze(image_bgr)
    """

    def __init__(
        self,
        wound_mask_dir: Optional[Path] = None,
        tissue_seg_dir: Optional[Path] = None,
        *,
        input_size: int = 384,
        crop_margin_ratio: float = 0.12,
        wound_threshold: float = 0.5,
    ):
        wound_dir = wound_mask_dir or WOUND_MASK_MODEL_DIR
        tissue_dir = tissue_seg_dir or TISSUE_SEG_MODEL_DIR

        self._wound_model = _DeepLabV3Inference(
            checkpoint_path=wound_dir / WOUND_MASK_CHECKPOINT,
            num_classes=1,
            input_size=input_size,
            threshold=wound_threshold,
        )
        self._tissue_model = _DeepLabV3Inference(
            checkpoint_path=tissue_dir / TISSUE_SEG_CHECKPOINT,
            num_classes=5,
            input_size=input_size,
        )
        self._crop_margin_ratio = crop_margin_ratio
        self._input_size = input_size
        self._available = False
        self._load()

    def _load(self) -> None:
        wound_ok = self._wound_model.load()
        tissue_ok = self._tissue_model.load()
        self._available = wound_ok and tissue_ok
        if self._available:
            print(
                f"[HEAL+] DL Tissue Pipeline: wound-mask ✓, tissue-seg ✓ "
                f"(input={self._input_size}px)"
            )
        else:
            reasons = []
            if not wound_ok:
                reasons.append("wound-mask")
            if not tissue_ok:
                reasons.append("tissue-seg")
            print(
                f"[HEAL+] DL Tissue Pipeline indisponível "
                f"(modelos faltando: {', '.join(reasons)}). Usando heurística."
            )

    @property
    def available(self) -> bool:
        return self._available

    def analyze(
        self,
        image_bgr: np.ndarray,
        *,
        epi_mask: Optional[np.ndarray] = None,
    ) -> DLTissuePipelineResult:
        """Run the full two-stage DL pipeline.

        Args:
            image_bgr: Original BGR image.
            epi_mask: Optional epithelialization mask (uint8, 0/255) from
                gradient-based detector. If provided, it is blended into the
                tissue percentages.

        Returns:
            DLTissuePipelineResult with wound mask, tissue mask, percentages,
            and visual overlays.

        Raises:
            DLPipelineUnavailable: If models are not loaded.
        """
        if not self._available:
            raise DLPipelineUnavailable("Pipeline DL não disponível")

        t0 = time.perf_counter()

        # Convert to RGB for model inference
        image_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)

        # --- Stage 1: Wound mask ---
        wound_mask = self._wound_model.predict(image_rgb)  # uint8, 0/255
        wound_area = int(np.sum(wound_mask > 0))

        h, w = image_bgr.shape[:2]

        if wound_area == 0:
            # No wound detected — return empty result
            empty = np.zeros((h, w), dtype=np.uint8)
            return DLTissuePipelineResult(
                wound_mask=wound_mask,
                tissue_mask=empty,
                tissue_percentages={},
                seg_map=np.full((h, w, 3), 80, dtype=np.uint8),
                tissue_overlay=image_bgr.copy(),
                crop_bbox=(0, 0, w, h),
                wound_area_pixels=0,
                inference_time_ms=(time.perf_counter() - t0) * 1000,
                metadata={"reason": "wound_mask_empty"},
            )

        # --- Crop to wound ROI ---
        crop_image, crop_mask, crop_bbox = self._crop_to_mask(
            image_rgb, wound_mask, margin_ratio=self._crop_margin_ratio,
        )

        # --- Stage 2: Tissue segmentation on cropped region ---
        tissue_mask_crop = self._tissue_model.predict(crop_image)  # uint8, [0..4]

        # Project crop back to full image
        tissue_mask_full = np.zeros((h, w), dtype=np.uint8)
        x1, y1, x2, y2 = crop_bbox
        crop_h, crop_w = y2 - y1, x2 - x1
        if tissue_mask_crop.shape[:2] != (crop_h, crop_w):
            tissue_mask_crop = cv2.resize(
                tissue_mask_crop, (crop_w, crop_h),
                interpolation=cv2.INTER_NEAREST,
            )
        tissue_mask_full[y1:y2, x1:x2] = tissue_mask_crop
        # Zero out areas outside wound mask
        tissue_mask_full[wound_mask == 0] = 0

        # --- Calculate clinical tissue percentages ---
        tissue_pcts = self._calculate_tissue_percentages(
            tissue_mask_full, wound_mask, epi_mask=epi_mask,
        )

        # --- Build visual overlays ---
        seg_map, tissue_overlay = self._build_overlays(
            image_bgr, tissue_mask_full, wound_mask, epi_mask=epi_mask,
        )

        inference_ms = (time.perf_counter() - t0) * 1000

        return DLTissuePipelineResult(
            wound_mask=wound_mask,
            tissue_mask=tissue_mask_full,
            tissue_percentages=tissue_pcts,
            seg_map=seg_map,
            tissue_overlay=tissue_overlay,
            crop_bbox=crop_bbox,
            wound_area_pixels=wound_area,
            inference_time_ms=inference_ms,
            metadata={
                "pipeline": "dl_two_stage",
                "wound_model": WOUND_MASK_CHECKPOINT,
                "tissue_model": TISSUE_SEG_CHECKPOINT,
                "input_size": self._input_size,
                "crop_margin_ratio": self._crop_margin_ratio,
            },
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _crop_to_mask(
        image: np.ndarray,
        mask: np.ndarray,
        *,
        margin_ratio: float = 0.12,
        min_size: int = 48,
    ) -> Tuple[np.ndarray, np.ndarray, Tuple[int, int, int, int]]:
        """Crop image and mask to the bounding box of nonzero mask pixels.

        Replicates ``segmentation_dataset.crop_to_mask`` without importing
        the training module at runtime.
        """
        ys, xs = np.where(mask > 0)
        if len(xs) == 0 or len(ys) == 0:
            h, w = mask.shape[:2]
            return image.copy(), mask.copy(), (0, 0, w, h)

        x1_raw, x2_raw = int(xs.min()), int(xs.max())
        y1_raw, y2_raw = int(ys.min()), int(ys.max())
        box_w = max(x2_raw - x1_raw + 1, min_size)
        box_h = max(y2_raw - y1_raw + 1, min_size)
        margin_x = max(int(box_w * margin_ratio), 4)
        margin_y = max(int(box_h * margin_ratio), 4)

        x1 = max(0, x1_raw - margin_x)
        y1 = max(0, y1_raw - margin_y)
        x2 = min(image.shape[1], x2_raw + margin_x + 1)
        y2 = min(image.shape[0], y2_raw + margin_y + 1)

        return image[y1:y2, x1:x2].copy(), mask[y1:y2, x1:x2].copy(), (x1, y1, x2, y2)

    @staticmethod
    def _calculate_tissue_percentages(
        tissue_mask: np.ndarray,
        wound_mask: np.ndarray,
        *,
        epi_mask: Optional[np.ndarray] = None,
    ) -> Dict[str, float]:
        """Map DL class indices to clinical tissue percentages."""
        wound_pixels = max(int(np.sum(wound_mask > 0)), 1)

        pcts: Dict[str, float] = {
            "necrosis": 0.0,
            "slough": 0.0,
            "granulation": 0.0,
            "epithelialization": 0.0,
        }

        for class_idx, clinical_key in DL_CLASS_TO_CLINICAL.items():
            count = int(np.sum(
                (tissue_mask == class_idx) & (wound_mask > 0)
            ))
            pcts[clinical_key] = float(count / wound_pixels * 100.0)

        # Blend in epithelialization from gradient detector
        if epi_mask is not None:
            epi_pixels = int(np.sum(
                (epi_mask > 0) & (wound_mask > 0)
            ))
            epi_pct = float(epi_pixels / wound_pixels * 100.0)
            # Epithelialization takes pixels from other tissues proportionally
            if epi_pct > 0:
                pcts["epithelialization"] = epi_pct
                # Deduct proportionally from existing tissues
                total_other = sum(
                    v for k, v in pcts.items() if k != "epithelialization"
                )
                if total_other > 0:
                    scale = max(0, (total_other - epi_pct)) / total_other
                    for key in ("necrosis", "slough", "granulation"):
                        pcts[key] *= scale

        return pcts

    @staticmethod
    def _build_overlays(
        image_bgr: np.ndarray,
        tissue_mask: np.ndarray,
        wound_mask: np.ndarray,
        *,
        epi_mask: Optional[np.ndarray] = None,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Build seg_map and tissue_overlay for ClinicalReport."""
        h, w = image_bgr.shape[:2]
        seg_map = np.full((h, w, 3), 80, dtype=np.uint8)

        # Paint DL tissue classes
        for class_idx, clinical_key in DL_CLASS_TO_CLINICAL.items():
            color = TISSUE_OVERLAY_COLORS.get(clinical_key, (128, 128, 128))
            seg_map[tissue_mask == class_idx] = color

        # Paint epithelialization from gradient detector
        if epi_mask is not None:
            color = TISSUE_OVERLAY_COLORS["epithelialization"]
            seg_map[epi_mask > 0] = color

        # Blend overlay
        overlay = image_bgr.copy()
        cv2.addWeighted(seg_map, 0.45, overlay, 0.55, 0, overlay)

        # Draw wound mask contour
        contours, _ = cv2.findContours(
            wound_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE,
        )
        cv2.drawContours(overlay, contours, -1, (0, 255, 0), 2)

        return seg_map, overlay


# ============================================================
# Extracted from: src/processing/clinical_wound_analyzer_core.py
# ============================================================

"""Headless clinical wound analyzer shared by API and desktop runtime.

This module is a transitional extraction from heal_analyzer.py. It keeps the
"""


import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List, Mapping, Optional, Tuple

import cv2
import numpy as np

try:
    from PIL import Image, ImageDraw, ImageFont
    _PIL_AVAILABLE = True
except ImportError:
    _PIL_AVAILABLE = False

LEGACY_ROOT = Path(__file__).resolve().parents[2]


# ============================================================
# HELPER: Texto UTF-8 no OpenCV (via PIL)
# ============================================================

def cv2_put_text_utf8(
    img: np.ndarray,
    text: str,
    pos: Tuple[int, int],
    font_size: int = 16,
    color: Tuple[int, int, int] = (255, 255, 255),
    bg_color: Optional[Tuple[int, int, int]] = None,
    font_path: Optional[str] = None
) -> np.ndarray:
    """
    Desenha texto com suporte a UTF-8/acentos usando PIL.
    
    Args:
        img: Imagem BGR do OpenCV
        text: Texto a desenhar (suporta acentos)
        pos: Posição (x, y) do canto superior esquerdo
        font_size: Tamanho da fonte em pixels
        color: Cor BGR do texto
        bg_color: Cor BGR do fundo (opcional)
        font_path: Caminho para fonte .ttf (opcional)
    
    Returns:
        Imagem com texto desenhado
    """
    if not _PIL_AVAILABLE:
        # Fallback: usa cv2.putText sem acentos
        cv2.putText(img, text.encode('ascii', 'replace').decode(), pos,
                    cv2.FONT_HERSHEY_SIMPLEX, font_size/30, color[::-1], 1)
        return img
    
    # Converte BGR -> RGB para PIL
    img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    pil_img = Image.fromarray(img_rgb)
    draw = ImageDraw.Draw(pil_img)
    
    # Carrega fonte
    try:
        if font_path and Path(font_path).exists():
            font = ImageFont.truetype(font_path, font_size)
        else:
            # Tenta fontes comuns do Windows
            for fallback in ['segoeui.ttf', 'arial.ttf', 'tahoma.ttf']:
                try:
                    font = ImageFont.truetype(fallback, font_size)
                    break
                except OSError:
                    continue
            else:
                font = ImageFont.load_default()
    except Exception:
        font = ImageFont.load_default()
    
    # Calcula tamanho do texto para background
    bbox = draw.textbbox(pos, text, font=font)
    
    # Desenha background se especificado
    if bg_color is not None:
        padding = 2
        draw.rectangle(
            [bbox[0] - padding, bbox[1] - padding, bbox[2] + padding, bbox[3] + padding],
            fill=bg_color[::-1]  # BGR -> RGB
        )
    
    # Desenha texto (cor BGR -> RGB)
    draw.text(pos, text, font=font, fill=color[::-1])
    
    # Converte de volta para BGR
    result = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
    return result


# ============================================================
# Módulos do projeto
# ============================================================

logger = logging.getLogger(__name__)

# Escalas clínicas validadas
try:
    from src.clinical.scales import (
        PushScore, PushExudateScore, PushTissueScore,
        BWATScore, BWATItem, BWAT_ITEMS,
        BradenScore, BradenCategory, BRADEN_CATEGORIES,
        ScaleCalculator,
    )
    HAS_CLINICAL_SCALES = True
except ImportError:
    HAS_CLINICAL_SCALES = False

# Módulos avançados de processamento de imagem
try:
    HAS_IMAGE_ENHANCER = True
except ImportError:
    HAS_IMAGE_ENHANCER = False

# Detector de parte do corpo
try:
    from src.detection.body_part_detector import (
        BodyPartDetector, BodyRegion, BodyPartPrediction,
        REGION_INFO, create_body_part_detector
    )
    HAS_BODY_DETECTOR = True
except ImportError:
    HAS_BODY_DETECTOR = False

try:
    from src.diagnosis.tissue_segmenter import UNetSegmenter
    from src.diagnosis.etiology_classifier import EtiologyClassifier
    from src.diagnosis.wound_analyzer import WoundAnalyzer
    HAS_DL_MODULES = True
except ImportError:
    HAS_DL_MODULES = False

# Classificador ResNet50 de dois estágios (do notebook de treinamento)
try:
    from src.diagnosis.resnet_wound_classifier import (
        TwoStageWoundClassifier, TwoStageResult, GradCAM,
        create_two_stage_classifier, WOUND_TYPE_PT,
        WOUND_CLINICAL_ACTIONS, WOUND_TO_ETIOLOGY,
    )
    HAS_RESNET_CLASSIFIER = True
except ImportError:
    HAS_RESNET_CLASSIFIER = False


DL_CLASS_TO_REDISUS = {
    "abdominal_wounds": {4: 1.0},
    "diabetic_ulcers": {2: 1.0},
    "pilonidal_sinus": {4: 1.0},
    "pressure_ulcers": {3: 1.0},
    "surgical_wounds": {4: 1.0},
    # A classe original junta ulceras venosas e arteriais; o mapeamento
    # redistribui esse suporte para o ensemble sem inventar uma classe extra.
    "venous_arterial_ulcers": {0: 0.6, 1: 0.4},
}


# ============================================================
# TAXONOMIA CLÍNICA — Estomaterapia
# ============================================================

@dataclass
class TissueClassification:
    """Classificação tecidual clínica."""
    name: str
    name_en: str
    percentage: float
    color_bgr: Tuple[int, int, int]
    color_hex: str
    description: str
    clinical_action: str


@dataclass
class BorderAnalysis:
    """Análise das bordas da ferida."""
    maceration: bool
    inflammation: bool
    regular_borders: bool
    description: str


@dataclass
class ClinicalReport:
    """Laudo clínico completo."""
    is_valid_wound: bool
    rejection_reason: str = ""

    # Classificação principal
    primary_tissue: str = ""
    primary_justification: str = ""

    # Tecidos identificados
    tissues: List[TissueClassification] = field(default_factory=list)

    # Bordas
    border_analysis: Optional[BorderAnalysis] = None

    # Métricas
    wound_area_px: int = 0
    health_score: float = 0.0
    processing_time_ms: float = 0.0

    # Deep Learning prediction (quando disponível)
    dl_prediction: Optional[Dict] = None

    # Classificação ResNet50 dois estágios (Normal/Ferida + Tipo)
    resnet_prediction: Optional[Dict] = None
    grad_cam_overlay: Optional[np.ndarray] = None

    # Escalas clínicas (PUSH, BWAT) - calculadas automaticamente
    push_score: Optional[Dict] = None
    bwat_score: Optional[Dict] = None

    # Análise de iluminação (quando disponível)
    lighting_analysis: Optional[Dict] = None
    image_corrections: Optional[Dict] = None
    
    # Detecção de parte do corpo (quando disponível)
    body_part: Optional[Dict] = None

    # Zonas espaciais da ferida (periferia, core, anel externo)
    wound_zones: Optional[Dict] = None
    roi: Optional[Dict] = None
    rois: Optional[List[Dict]] = None

    # Ensemble Multi-Modelo (camada adicional de IA pré-treinada)
    ensemble_classification: Optional[Dict] = None
    ensemble_agreement: Optional[Dict] = None
    ensemble_infection: Optional[Dict] = None
    ensemble_severity: Optional[float] = None
    ensemble_models_loaded: Optional[Dict] = None

    # Pipeline DL de segmentação tecidual (quando disponível)
    dl_tissue_pipeline: Optional[Dict] = None

    # Imagens processadas
    original: Optional[np.ndarray] = None
    detection_overlay: Optional[np.ndarray] = None
    segmentation_map: Optional[np.ndarray] = None
    tissue_overlay: Optional[np.ndarray] = None
    tissue_analysis_trace: Optional[Dict] = None


# Definição clínica dos tecidos
CLINICAL_TISSUES = {
    "necrosis": {
        "name": "Necrose de Coagulação (Escara)",
        "name_en": "Coagulation Necrosis (Eschar)",
        "color_bgr": (30, 30, 60),
        "color_hex": "#3C1E1E",
        "description": (
            "Tecido preto ou marrom-escuro, endurecido, seco ou úmido (couro), "
            "que indica morte celular por falta de suprimento sanguíneo. "
            "Pode estar aderido ou solto no leito da ferida."
        ),
        "clinical_action": (
            "Necessita de desbridamento (autolítico, enzimático, instrumental ou cirúrgico) "
            "para remoção do tecido desvitalizado e promoção da cicatrização."
        ),
    },
    "slough": {
        "name": "Esfacelo (Fibrina)",
        "name_en": "Slough (Fibrin)",
        "color_bgr": (80, 220, 220),
        "color_hex": "#DCC850",
        "description": (
            "Tecido amarelado, esbranquiçado ou acinzentado, de consistência viscosa "
            "ou fibrosa, que adere ao leito da ferida. Composto por fibrina, "
            "leucócitos, bactérias e restos celulares."
        ),
        "clinical_action": (
            "Avaliar necessidade de desbridamento autolítico (hidrogel) ou enzimático. "
            "Manter o leito úmido para facilitar a remoção fisiológica."
        ),
    },
    "granulation": {
        "name": "Tecido de Granulação",
        "name_en": "Granulation Tissue",
        "color_bgr": (60, 60, 220),
        "color_hex": "#DC3C3C",
        "description": (
            "Tecido vermelho vivo/brilhante, úmido, com aspecto granulado ('em amora'). "
            "Rico em neovasos e fibroblastos, indicando processo de cicatrização ativo "
            "na fase proliferativa."
        ),
        "clinical_action": (
            "Proteger o tecido neoformado. Utilizar coberturas que mantenham meio úmido "
            "(espuma, alginato, hidrofibra). Evitar trauma na troca de curativos."
        ),
    },
    "epithelialization": {
        "name": "Epitelização",
        "name_en": "Epithelialization",
        "color_bgr": (200, 180, 255),
        "color_hex": "#FFB4C8",
        "description": (
            "Tecido rosa claro ou translúcido que avança das bordas para o centro "
            "da ferida, selando a superfície. Indica fase final da cicatrização "
            "com migração de queratinócitos."
        ),
        "clinical_action": (
            "Proteger o epitélio neoformado com coberturas não aderentes. "
            "Evitar qualquer trauma. Monitorar fechamento completo."
        ),
    },
}

# ============================================================
# INTERVALOS CLÍNICOS REFINADOS v2 — Multi-espaço de cor
# ============================================================
# HSV: matiz-saturação-valor (boa discriminação de cores puras)
# LAB: luminosidade-a*-b* (boa separação perceptual, eixo a*=vermelho/verde)
# YCrCb: luminância-crominância (boa para detecção de pele/tecido)

CLINICAL_HSV_RANGES = {
    "necrosis": [
        # 1. Preto/muito escuro — V ≤ 40, exceto azul/verde cirúrgico
        (np.array([0, 0, 0]), np.array([80, 255, 40])),
        (np.array([140, 0, 0]), np.array([180, 255, 40])),
        # 2. Marrom escuro necrótico — tom marrom (H 5-25), V 15-60
        #    S ≥ 25 para separar de cinza acromático
        (np.array([5, 25, 15]), np.array([25, 200, 60])),
        # 3. Escara seca acromática — S < 30, V < 50
        (np.array([0, 5, 5]), np.array([180, 30, 50])),
        # 4. Marrom acinzentado (necrose úmida) — H 8-30, S moderada
        (np.array([8, 15, 20]), np.array([30, 120, 65])),
    ],
    "slough": [
        # Amarelo fibrina puro
        (np.array([18, 60, 140]), np.array([35, 255, 255])),
        # Branco amarelado (fibrina clara)
        (np.array([0, 0, 195]), np.array([30, 55, 255])),
        # Cinza-amarelado
        (np.array([15, 20, 130]), np.array([35, 90, 210])),
        # Amarelo-esverdeado (fibrina contaminada)
        (np.array([30, 40, 130]), np.array([45, 180, 230])),
        # Bege claro (fibrina seca)
        (np.array([12, 15, 150]), np.array([25, 80, 230])),
        # Oliva / verde-amarelado de esfacelo umido
        (np.array([30, 18, 80]), np.array([72, 135, 185])),
        # Cinza-esverdeado de tecido desvitalizado
        (np.array([32, 10, 68]), np.array([82, 95, 170])),
    ],
    "granulation": [
        # Vermelho vivo intenso — S ≥ 130 (requer alta saturação)
        (np.array([0, 130, 90]), np.array([10, 255, 255])),
        (np.array([165, 130, 90]), np.array([180, 255, 255])),
        # Vermelho moderado — S ≥ 100 (mais restrito para não pegar pele/epi)
        (np.array([0, 100, 110]), np.array([8, 220, 255])),
        (np.array([170, 100, 110]), np.array([180, 220, 255])),
        # Vermelho escuro (granulação madura) — S ≥ 110
        (np.array([0, 110, 60]), np.array([10, 255, 150])),
        (np.array([162, 110, 60]), np.array([180, 255, 150])),
    ],
    "epithelialization": [
        # Rosa claro — S baixa (15-50), V alta (≥ 190)
        (np.array([0, 15, 190]), np.array([10, 50, 255])),
        (np.array([165, 15, 190]), np.array([180, 50, 255])),
        # Rosa pálido quase branco — S muito baixa
        (np.array([0, 8, 210]), np.array([8, 35, 255])),
        (np.array([168, 8, 210]), np.array([180, 35, 255])),
    ],
}

# Intervalos no espaço LAB para refinamento
# L: luminosidade (0=preto, 255=branco)
# A: verde(-) → vermelho(+)
# B: azul(-) → amarelo(+)
CLINICAL_LAB_RANGES = {
    "necrosis": [
        # Muito escuro com crominância neutra (escara/necrose)
        # L < 45 — pele escura saudável geralmente L > 50
        (np.array([0, 100, 100]), np.array([45, 150, 150])),
        # Marrom necrótico (L baixo-médio, a+/b+ moderados)
        (np.array([10, 128, 120]), np.array([55, 165, 165])),
        # Necrose úmida/esverdeada (L baixo, b desviado)
        (np.array([5, 120, 105]), np.array([40, 145, 135])),
    ],
    "slough": [
        # Amarelo claro (L alto, b muito positivo)
        (np.array([150, 110, 150]), np.array([240, 140, 200])),
        # Bege/branco-amarelado
        (np.array([170, 118, 135]), np.array([250, 135, 165])),
        # Oliva / amarelo-acinzentado
        (np.array([105, 112, 134]), np.array([175, 132, 155])),
        # Esfacelo umido um pouco mais escuro
        (np.array([90, 110, 130]), np.array([160, 128, 148])),
    ],
    "granulation": [
        # Vermelho (a muito positivo, L médio)
        (np.array([40, 150, 115]), np.array([180, 220, 165])),
        # Vermelho escuro
        (np.array([25, 145, 110]), np.array([100, 200, 150])),
    ],
    "epithelialization": [
        # Rosa (L alto, a levemente positivo, b neutro)
        (np.array([175, 130, 120]), np.array([240, 150, 140])),
    ],
}


# ============================================================
# MOTOR DE ANÁLISE CLÍNICA
# ============================================================

class ClinicalWoundAnalyzer:
    """
    Motor de análise clínica de feridas v2.

    Atua como especialista em Estomaterapia — classifica texturas
    segundo a taxonomia de tecidos viáveis e inviáveis, analisa
    bordas/perilesão e gera laudo técnico.

    v2: Multi-espaço de cor (HSV + LAB), textura LBP, modelo DL
    integrado (quando disponível), calibração de confiança.
    """

    MIN_WOUND_AREA_RATIO = 0.005   # Mínimo 0.5% da imagem
    MAX_SKIN_RATIO = 0.97          # Se > 97% for pele → inválido

    # Escala de Fitzpatrick aproximada por luminosidade LAB
    # Usada para adaptar limiares de necrose ao tom de pele do paciente
    FITZPATRICK_L_THRESHOLDS = {
        # L médio do periwound -> Fitzpatrick aproximado
        # I-II: L > 180, III: L 150-180, IV: L 110-150, V: L 70-110, VI: L < 70
        "very_light": 180,  # I-II
        "light": 150,       # III
        "medium": 110,      # IV
        "dark": 70,         # V
        # VI: L < 70
    }

    def __init__(self):
        self.detector = WoundDetectorCV(
            method=DetectionMethod.TEXTURE_PRIORITY,
            min_area=1200,
            confidence_threshold=0.40,
            enable_false_positive_filter=True,
            texture_weight=0.5,
            color_weight=0.25,
        )
        self.tissue_analyzer = TissueAnalyzerCV()
        self.classifier = WoundClassifierCV()

        self.image_enhancer = create_medical_enhancer() if HAS_IMAGE_ENHANCER else None
        self.body_detector = create_body_part_detector() if HAS_BODY_DETECTOR else None

        # Deep Learning model (carregado sob demanda)
        self._dl_model = None
        self._dl_metadata = None
        self._dl_available = False
        self._load_dl_model()

        # Classificador ResNet50 de dois estágios (do notebook)
        self._resnet_classifier = None
        self._resnet_available = False
        self._load_resnet_classifier()

        # Ensemble Multi-Modelo (camada adicional de IA pré-treinada)
        self._ensemble = None
        self._ensemble_available = False
        self._last_tissue_analysis_trace = None
        self._load_ensemble()

    def _load_resnet_classifier(self):
        """Carrega o classificador ResNet50 de dois estágios."""
        if not HAS_RESNET_CLASSIFIER:
            print("[HEAL+] Módulo ResNet50 não disponível")
            return
        try:
            self._resnet_classifier = create_two_stage_classifier()
            self._resnet_available = self._resnet_classifier.available
            if self._resnet_available:
                status = self._resnet_classifier.get_status()
                print(f"[HEAL+] ResNet50 Two-Stage: S1={status['stage1_available']}, S2={status['stage2_available']} ({status['device']})")
            else:
                print("[HEAL+] ResNet50: Modelos não encontrados (classificação por heurística)")
        except Exception as e:
            print(f"[HEAL+] Erro ao carregar ResNet50: {e}")
            self._resnet_available = False

    def _load_dl_model(self):
        """Tenta carregar modelo DL treinado (PyTorch) para classificação."""
        # PyTorch model paths (traced/TorchScript preferred - self-contained)
        model_paths = [
            LEGACY_ROOT / "models" / "wound_classifier_v2" / "wound_classifier_v2_traced.pt",
            LEGACY_ROOT / "models" / "wound_classifier_v2" / "wound_classifier_v2_full.pt",
            LEGACY_ROOT / "models" / "wound_classifier_v2" / "wound_classifier_v2.pt",
        ]
        meta_paths = [
            LEGACY_ROOT / "models" / "wound_classifier_v2" / "model_metadata_v2.json",
            LEGACY_ROOT / "models" / "wound_classifier" / "model_metadata.json",
        ]

        for mp in model_paths:
            if mp.exists():
                try:
                    import torch
                    if "traced" in mp.name:
                        self._dl_model = torch.jit.load(str(mp), map_location="cpu")
                    elif "full" in mp.name:
                        self._dl_model = torch.load(str(mp), map_location="cpu", weights_only=False)
                    else:
                        # state_dict — needs metadata to reconstruct model
                        # skip if no metadata loaded yet; will try full model first
                        continue
                    self._dl_model.eval()
                    self._dl_available = True
                    print(f"[HEAL+] Modelo DL PyTorch carregado: {mp.name}")
                    break
                except Exception as e:
                    print(f"[HEAL+] Erro DL ({mp.name}): {e}")

        for mp in meta_paths:
            if mp.exists():
                try:
                    import json
                    with open(mp, encoding='utf-8') as f:
                        self._dl_metadata = json.load(f)
                    print(f"[HEAL+] Metadados: {mp.name}")
                    break
                except Exception:
                    pass

    def _load_ensemble(self):
        """Carrega o ensemble multi-modelo (DermaIntel + MedSAM + BiomedCLIP)."""
        try:
            from src.ai_layer import (
                EnsembleOrchestrator,
                DermaIntelClassifier,
                MedSAMSegmenter,
                BiomedCLIPAnalyzer,
            )
            self._ensemble = EnsembleOrchestrator(
                dermaintel=DermaIntelClassifier(),
                medsam=MedSAMSegmenter(),
                biomedclip=BiomedCLIPAnalyzer(),
            )
            status = self._ensemble.load_all_models()
            loaded = sum(1 for v in status.values() if v)
            self._ensemble_available = loaded > 0
            print(f"[HEAL+] Ensemble multi-modelo: {loaded}/3 modelos ({status})")
        except Exception as e:
            print(f"[HEAL+] Ensemble indisponível: {e}")
            self._ensemble_available = False

    def _predict_ensemble(
        self,
        image: np.ndarray,
        detections=None,
        dl_probs: Optional[Dict[int, float]] = None,
        wound_mask: Optional[np.ndarray] = None,
    ) -> Optional[Dict]:
        """Predição via ensemble multi-modelo (quando disponível).

        Args:
            image: imagem BGR
            detections: lista de detecções (com bbox)
            dl_probs: probabilidades do modelo DL base (5 classes REDISUS)
            wound_mask: máscara de segmentação do pipeline base
        """
        if not self._ensemble_available or self._ensemble is None:
            return None
        try:
            # Determina bbox a partir das detecções
            bbox = None
            if detections:
                best = max(detections, key=lambda d: d.get("confidence", d.get("score", 0))
                           if isinstance(d, dict) else getattr(d, "confidence", 0))
                if isinstance(best, dict):
                    bbox = best.get("bbox")
                else:
                    bbox = getattr(best, "bbox", None)

            result = self._ensemble.predict(
                image=image,
                bbox=bbox,
                efficientnet_probs=dl_probs,
                unet_mask=wound_mask,
            )

            # Converte para dicts simples para armazenar no ClinicalReport
            cls = result.classification
            agr = cls.agreement

            return {
                "ensemble": {
                    "classification": {
                        "class_id": cls.class_id,
                        "class_name": cls.class_name,
                        "confidence": cls.confidence,
                        "all_probabilities": cls.all_probabilities,
                    },
                    "agreement": {
                        "models_agree": agr.models_agree,
                        "agreement_score": agr.agreement_score,
                        "individual_predictions": agr.individual_predictions,
                        "confidence_boost": agr.confidence_boost,
                    },
                    "models_loaded": result.models_loaded,
                },
                "infection": result.infection_scores,
                "infection_risk": result.infection_risk,
                "severity": result.severity_index,
                "severity_scores": result.severity_scores,
            }
        except Exception as e:
            print(f"[HEAL+] Ensemble prediction error: {e}")
            return None

    @staticmethod
    def _map_classifier_probs_to_redisus(
        all_probs: Optional[Dict[str, float]],
    ) -> Tuple[Optional[Dict[int, float]], float]:
        """Mapeia a saida 11-classes do EfficientNet para 5 classes REDISUS."""
        if not all_probs:
            return None, 0.0

        mapped = {i: 0.0 for i in range(5)}
        supported_mass = 0.0

        for class_name, raw_prob in all_probs.items():
            try:
                prob = float(raw_prob)
            except (TypeError, ValueError):
                continue
            if prob <= 0.0:
                continue

            class_map = DL_CLASS_TO_REDISUS.get(str(class_name))
            if not class_map:
                continue

            supported_mass += prob
            for class_id, share in class_map.items():
                mapped[class_id] += prob * float(share)

        total = sum(mapped.values())
        if total <= 1e-8:
            return None, supported_mass

        normalized = {
            class_id: float(value / total)
            for class_id, value in mapped.items()
            if value > 1e-8
        }
        return normalized, supported_mass

    def _predict_dl(self, image: np.ndarray) -> Optional[Dict]:
        """Predição com modelo DL PyTorch (se disponível)."""
        if not self._dl_available or self._dl_model is None:
            return None
        try:
            import torch
            from torchvision import transforms

            meta = self._dl_metadata or {}
            input_shape = meta.get("input_shape", [300, 300, 3])
            h, w = input_shape[0], input_shape[1]

            # Preprocessing: ImageNet normalization
            preprocess_meta = meta.get("preprocessing", {})
            mean = preprocess_meta.get("normalize_mean", [0.485, 0.456, 0.406])
            std = preprocess_meta.get("normalize_std", [0.229, 0.224, 0.225])

            transform = transforms.Compose([
                transforms.ToPILImage(),
                transforms.Resize((h, w)),
                transforms.ToTensor(),
                transforms.Normalize(mean=mean, std=std),
            ])

            img_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            img_tensor = transform(img_rgb).unsqueeze(0)  # [1, 3, H, W]

            # TTA — Test Time Augmentation (4 flips)
            with torch.no_grad():
                predictions = []
                # Original
                out = torch.softmax(self._dl_model(img_tensor), dim=1)
                predictions.append(out)
                # Horizontal flip
                out = torch.softmax(self._dl_model(torch.flip(img_tensor, [3])), dim=1)
                predictions.append(out)
                # Vertical flip
                out = torch.softmax(self._dl_model(torch.flip(img_tensor, [2])), dim=1)
                predictions.append(out)
                # Both flips
                out = torch.softmax(self._dl_model(torch.flip(img_tensor, [2, 3])), dim=1)
                predictions.append(out)

                # Média TTA
                avg_pred = torch.stack(predictions).mean(dim=0).squeeze(0).numpy()

            class_idx = int(np.argmax(avg_pred))
            confidence = float(avg_pred[class_idx])

            class_names = meta.get("class_names", [])
            display_names = meta.get("class_display_names", {})

            class_name = class_names[class_idx] if class_idx < len(class_names) else f"class_{class_idx}"
            display_name = display_names.get(class_name, class_name.replace("_", " ").title())

            # Top-3 predictions
            top3_idx = np.argsort(avg_pred)[-3:][::-1]
            top3 = []
            for idx in top3_idx:
                name = class_names[idx] if idx < len(class_names) else f"class_{idx}"
                dname = display_names.get(name, name.replace("_", " ").title())
                top3.append({"class": name, "display": dname, "confidence": float(avg_pred[idx])})

            all_probs = {
                class_names[i]: float(avg_pred[i])
                for i in range(len(class_names))
                if i < len(avg_pred)
            }
            redisus_probs, supported_mass = self._map_classifier_probs_to_redisus(all_probs)

            return {
                "class_name": class_name,
                "display_name": display_name,
                "confidence": confidence,
                "top3": top3,
                "all_probs": all_probs,
                "redisus_probs": redisus_probs,
                "redisus_supported_mass": float(supported_mass),
            }
        except Exception as e:
            print(f"[HEAL+] Erro predicao DL: {e}")
            return None

    # -------------------------------------------------------
    @staticmethod
    def _normalize_manual_roi_mask(
        manual_roi_mask: Optional[np.ndarray],
        *,
        target_shape: Tuple[int, int],
    ) -> Optional[np.ndarray]:
        if manual_roi_mask is None:
            return None

        mask = np.asarray(manual_roi_mask)
        if mask.size == 0:
            return None

        if mask.ndim == 3:
            mask = mask[:, :, 0]

        target_h, target_w = target_shape
        if mask.shape != (target_h, target_w):
            mask = cv2.resize(mask, (target_w, target_h), interpolation=cv2.INTER_NEAREST)

        if mask.dtype != np.uint8:
            mask = np.clip(mask, 0, 255).astype(np.uint8)

        mask = np.where(mask > 0, 255, 0).astype(np.uint8)
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=1)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)
        return mask if np.any(mask > 0) else None

    @classmethod
    def _normalize_manual_roi_masks(
        cls,
        manual_roi_masks: Optional[List[np.ndarray]],
        *,
        target_shape: Tuple[int, int],
    ) -> List[np.ndarray]:
        normalized_masks: List[np.ndarray] = []
        for manual_roi_mask in manual_roi_masks or []:
            normalized = cls._normalize_manual_roi_mask(
                manual_roi_mask,
                target_shape=target_shape,
            )
            if normalized is not None:
                normalized_masks.append(normalized)
        return normalized_masks

    @staticmethod
    def _combine_manual_roi_masks(
        manual_roi_masks: List[np.ndarray],
    ) -> Optional[np.ndarray]:
        if not manual_roi_masks:
            return None

        combined = np.zeros_like(manual_roi_masks[0], dtype=np.uint8)
        for manual_roi_mask in manual_roi_masks:
            combined = cv2.bitwise_or(combined, manual_roi_mask)

        return combined if np.any(combined > 0) else None

    @staticmethod
    def _mask_bbox(wound_mask: np.ndarray) -> Optional[Tuple[int, int, int, int]]:
        points = cv2.findNonZero(wound_mask)
        if points is None:
            return None

        x, y, w, h = cv2.boundingRect(points)
        return x, y, x + w, y + h

    @classmethod
    def _detections_from_mask(cls, wound_mask: np.ndarray):
        bbox = cls._mask_bbox(wound_mask)
        if bbox is None:
            return []
        return [SimpleNamespace(bbox=bbox, confidence=1.0)]

    @classmethod
    def _detections_from_masks(cls, wound_masks: List[np.ndarray]):
        detections = []
        for index, wound_mask in enumerate(wound_masks, start=1):
            bbox = cls._mask_bbox(wound_mask)
            if bbox is None:
                continue
            detections.append(
                SimpleNamespace(
                    bbox=bbox,
                    confidence=1.0,
                    roi_index=index,
                )
            )
        return detections

    @staticmethod
    def _apply_focus_mask(image: np.ndarray, wound_mask: Optional[np.ndarray]) -> np.ndarray:
        if wound_mask is None or not np.any(wound_mask > 0):
            return image

        mask = (wound_mask > 0).astype(np.uint8)
        mask_3 = mask[:, :, None]
        blurred = cv2.GaussianBlur(image, (0, 0), sigmaX=7, sigmaY=7)
        darkened = np.clip(blurred.astype(np.float32) * 0.18, 0, 255).astype(np.uint8)
        return np.where(mask_3 > 0, image, darkened)

    @classmethod
    def _build_roi_report_entry(
        cls,
        *,
        source: str,
        wound_mask: np.ndarray,
        image_shape: Tuple[int, int, int] | Tuple[int, int],
        roi_metadata: Optional[Mapping[str, Any]] = None,
    ) -> Dict[str, Any]:
        height, width = image_shape[:2]
        area_px = int(np.sum(wound_mask > 0))
        area_ratio = float(area_px / max(height * width, 1))
        bbox = cls._mask_bbox(wound_mask)

        roi_entry: Dict[str, Any] = dict(roi_metadata or {})
        roi_entry["source"] = source
        roi_entry["confirmed"] = bool(roi_entry.get("confirmed", source == "manual"))
        roi_entry["analysis_width"] = int(width)
        roi_entry["analysis_height"] = int(height)
        roi_entry["area_px"] = area_px
        roi_entry["area_ratio"] = round(area_ratio, 6)

        if bbox is not None:
            x1, y1, x2, y2 = bbox
            max_x = max(width - 1, 1)
            max_y = max(height - 1, 1)
            roi_entry["analysis_bounding_box"] = {
                "x": round(x1 / max_x, 6),
                "y": round(y1 / max_y, 6),
                "width": round((x2 - x1) / max(width, 1), 6),
                "height": round((y2 - y1) / max(height, 1), 6),
            }

        return roi_entry

    @classmethod
    def _build_detection_overlay(
        cls,
        image: np.ndarray,
        *,
        wound_mask: np.ndarray,
        detections: list,
        manual_roi: bool,
    ) -> np.ndarray:
        overlay = image.copy()
        contour_color = (16, 185, 129) if manual_roi else (0, 255, 0)

        contours, _ = cv2.findContours(wound_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if contours:
            cv2.drawContours(overlay, contours, -1, contour_color, 2)

        for index, det in enumerate(detections, start=1):
            x1, y1, x2, y2 = det.bbox
            roi_index = getattr(det, "roi_index", index)
            if manual_roi and len(detections) > 1:
                label = f"ROI {roi_index}"
            else:
                label = "ROI manual" if manual_roi else "Ferida"
            cv2.rectangle(overlay, (x1, y1), (x2, y2), contour_color, 2)
            cv2.putText(
                overlay,
                f"{label} {det.confidence:.0%}",
                (x1, max(18, y1 - 6)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.45,
                contour_color,
                1,
            )

        return overlay

    def analyze(
        self,
        image: np.ndarray,
        *,
        manual_roi_mask: Optional[np.ndarray] = None,
        manual_roi_masks: Optional[List[np.ndarray]] = None,
        roi_metadata: Optional[Mapping[str, Any]] = None,
        roi_metadata_list: Optional[List[Mapping[str, Any]]] = None,
    ) -> ClinicalReport:
        """Pipeline completo de análise clínica."""
        t0 = time.perf_counter()
        report = ClinicalReport(is_valid_wound=True)
        if image is None or not isinstance(image, np.ndarray) or image.size == 0 or image.ndim != 3:
            report.is_valid_wound = False
            report.rejection_reason = "Input Inválido — imagem vazia ou malformada."
            report.processing_time_ms = (time.perf_counter() - t0) * 1000
            return report
        report.original = image.copy()
        manual_roi_sources = list(manual_roi_masks or [])
        if not manual_roi_sources and manual_roi_mask is not None:
            manual_roi_sources = [manual_roi_mask]
        normalized_manual_roi_masks = self._normalize_manual_roi_masks(
            manual_roi_sources,
            target_shape=image.shape[:2],
        )
        combined_manual_roi_mask = self._combine_manual_roi_masks(
            normalized_manual_roi_masks,
        )
        validation_image = self._apply_focus_mask(image, combined_manual_roi_mask)

        # 1. Validação — é uma ferida?
        if not self._validate_wound_image(validation_image):
            report.is_valid_wound = False
            report.rejection_reason = (
                "Input Inválido — A imagem fornecida não apresenta características "
                "compatíveis com ferida cutânea humana."
            )
            report.processing_time_ms = (time.perf_counter() - t0) * 1000
            return report

        # 2. Redimensiona se necessário
        h, w = image.shape[:2]
        if max(h, w) > 1024:
            scale = 1024 / max(h, w)
            image = cv2.resize(image, (int(w * scale), int(h * scale)))
            normalized_manual_roi_masks = self._normalize_manual_roi_masks(
                normalized_manual_roi_masks,
                target_shape=image.shape[:2],
            )
            combined_manual_roi_mask = self._combine_manual_roi_masks(
                normalized_manual_roi_masks,
            )

        # 2.1 Análise de iluminação e correção automática
        if self.image_enhancer is not None:
            try:
                lighting = self.image_enhancer.analyze_lighting(image)
                report.lighting_analysis = lighting.to_dict()
                
                # Aplica correções se necessário
                if lighting.corrections_needed:
                    image, corrections = self.image_enhancer.auto_correct(image, lighting)
                    report.image_corrections = corrections
            except Exception as e:
                print(f"[HEAL+] Erro análise de iluminação: {e}")
        
        # 2.2 Detecção de parte do corpo
        if self.body_detector is not None:
            try:
                body_part = self.body_detector.detect(image)
                report.body_part = body_part.to_dict()
            except Exception as e:
                print(f"[HEAL+] Erro detecção parte do corpo: {e}")

        # 3. Delimitação principal da região de ferida
        manual_roi_applied = combined_manual_roi_mask is not None
        if manual_roi_applied:
            wound_mask = combined_manual_roi_mask.copy()
            detections = self._detections_from_masks(normalized_manual_roi_masks)
            if not detections:
                detections = self._detections_from_mask(wound_mask)
        else:
            detections = self.detector.detect(image)
            # 3.1 Cria máscara ROI precisa por contorno (não mais bbox retangular)
            wound_mask = self._create_wound_roi_mask(image, detections)

        # 3.2 Remove fundo cirúrgico (lençol azul/verde/cinza) da máscara
        wound_mask = self._exclude_surgical_background(image, wound_mask)

        # 3.3 Classificação espacial de background — separa fundo de câmera
        # de tecido necrótico usando variância local, crominância e conectividade
        background_mask = self._create_background_mask_spatial(image, wound_mask)
        wound_mask_clean = cv2.bitwise_and(wound_mask, cv2.bitwise_not(background_mask))
        # Se a limpeza removeu quase tudo, ignora (provavelmente não tem fundo)
        if np.sum(wound_mask_clean > 0) > 0.05 * np.sum(wound_mask > 0):
            wound_mask = wound_mask_clean

        # 3.4 Separação em zonas espaciais (periferia, core, anel externo)
        peripheral_zone, core_zone, outer_ring = self._create_zone_masks(wound_mask)
        report.wound_zones = {
            "peripheral_area_px": int(np.sum(peripheral_zone > 0)),
            "core_area_px": int(np.sum(core_zone > 0)),
            "outer_ring_area_px": int(np.sum(outer_ring > 0)),
            "border_width_adaptive": True,
        }
        if manual_roi_applied:
            roi_entries: List[Dict[str, Any]] = []
            for index, manual_mask in enumerate(normalized_manual_roi_masks):
                entry_metadata = None
                if roi_metadata_list and index < len(roi_metadata_list):
                    entry_metadata = roi_metadata_list[index]
                elif index == 0 and roi_metadata:
                    entry_metadata = roi_metadata
                roi_entries.append(
                    self._build_roi_report_entry(
                        source="manual",
                        wound_mask=manual_mask,
                        image_shape=image.shape,
                        roi_metadata=entry_metadata,
                    )
                )
            report.rois = roi_entries
            if len(roi_entries) == 1:
                report.roi = dict(roi_entries[0])
            else:
                roi_summary = dict(roi_metadata or {})
                roi_summary["selection_count"] = len(roi_entries)
                roi_summary["tools"] = [
                    str(entry.get("tool"))
                    for entry in roi_entries
                    if entry.get("tool")
                ]
                report.roi = self._build_roi_report_entry(
                    source="manual",
                    wound_mask=wound_mask,
                    image_shape=image.shape,
                    roi_metadata=roi_summary,
                )
        else:
            report.roi = self._build_roi_report_entry(
                source="automatic",
                wound_mask=wound_mask,
                image_shape=image.shape,
                roi_metadata=roi_metadata,
            )

        report.detection_overlay = self._build_detection_overlay(
            image,
            wound_mask=wound_mask,
            detections=detections,
            manual_roi=manual_roi_applied,
        )
        report.wound_area_px = int(np.sum(wound_mask > 0))
        if report.wound_area_px <= 0:
            report.is_valid_wound = False
            report.rejection_reason = (
                "A delimitacao da ferida nao gerou uma area valida para analise."
            )
            report.processing_time_ms = (time.perf_counter() - t0) * 1000
            return report

        # 4. Segmentação tecidual clínica v3 (HSV + LAB + zonas + gradiente)
        tissue_pcts, seg_map, tissue_overlay = self._segment_clinical_v3(
            image, wound_mask, peripheral_zone, core_zone, outer_ring
        )
        report.segmentation_map = seg_map
        report.tissue_overlay = tissue_overlay
        report.tissue_analysis_trace = dict(self._last_tissue_analysis_trace or {})

        # 5. Monta lista de tecidos
        for key in ["necrosis", "slough", "granulation", "epithelialization"]:
            pct = tissue_pcts.get(key, 0.0)
            info = CLINICAL_TISSUES[key]
            report.tissues.append(TissueClassification(
                name=info["name"],
                name_en=info["name_en"],
                percentage=pct,
                color_bgr=info["color_bgr"],
                color_hex=info["color_hex"],
                description=info["description"],
                clinical_action=info["clinical_action"],
            ))

        # 6. Classificação principal
        dominant = max(report.tissues, key=lambda t: t.percentage)
        report.primary_tissue = dominant.name
        report.primary_justification = self._build_justification(dominant, tissue_pcts)

        # 7. Análise de bordas
        report.border_analysis = self._analyze_borders(image, wound_mask)

        # 8. Score de saúde
        report.health_score = self._compute_health_score(tissue_pcts)

        # 9. Escalas clínicas (PUSH e BWAT)
        if HAS_CLINICAL_SCALES:
            try:
                # PUSH Score
                border_dict = None
                if report.border_analysis:
                    border_dict = {
                        "maceration": report.border_analysis.maceration,
                        "inflammation": report.border_analysis.inflammation,
                        "regular_borders": report.border_analysis.regular_borders,
                    }
                
                push = ScaleCalculator.calculate_push_from_analysis(
                    tissue_percentages=tissue_pcts,
                    wound_area_px=report.wound_area_px,
                )
                report.push_score = push.to_dict()
                
                # BWAT Score (itens auto-preenchíveis)
                bwat = ScaleCalculator.calculate_bwat_from_analysis(
                    tissue_percentages=tissue_pcts,
                    wound_area_px=report.wound_area_px,
                    border_analysis=border_dict,
                )
                report.bwat_score = bwat.to_dict()
            except Exception as e:
                print(f"[HEAL+] Erro ao calcular escalas clínicas: {e}")

        analysis_focus_image = self._apply_focus_mask(image, wound_mask)

        # 10. Deep Learning — classificação etiológica (se disponível)
        dl_result = self._predict_dl(analysis_focus_image)
        if dl_result:
            report.dl_prediction = dl_result

        # 11. ResNet50 Two-Stage — classificação Normal/Ferida + Tipo
        resnet_result = self._predict_resnet(analysis_focus_image)
        if resnet_result:
            report.resnet_prediction = resnet_result
            # Se Grad-CAM foi gerado, inclui no report
            if isinstance(resnet_result, dict) and resnet_result.get('grad_cam_overlay') is not None:
                report.grad_cam_overlay = resnet_result.pop('grad_cam_overlay')

        # 12. Ensemble Multi-Modelo — camada adicional de IA pré-treinada
        #     Passa probabilidades DL e máscara de segmentação para fusão cruzada
        dl_probs = None
        if dl_result:
            mapped_probs = dl_result.get("redisus_probs")
            supported_mass = float(dl_result.get("redisus_supported_mass") or 0.0)
            if isinstance(mapped_probs, dict) and supported_mass >= 0.40:
                dl_probs = mapped_probs
        ensemble_result = self._predict_ensemble(
            analysis_focus_image, detections, dl_probs=dl_probs, wound_mask=wound_mask,
        )
        if ensemble_result:
            ens = ensemble_result.get("ensemble", {})
            report.ensemble_classification = ens.get("classification")
            report.ensemble_agreement = ens.get("agreement")
            report.ensemble_infection = ensemble_result.get("infection")
            report.ensemble_severity = ensemble_result.get("severity")
            report.ensemble_models_loaded = ens.get("models_loaded")

        report.processing_time_ms = (time.perf_counter() - t0) * 1000
        return report

    def _predict_resnet(self, image: np.ndarray) -> Optional[Dict]:
        """Classificação ResNet50 de dois estágios com Grad-CAM."""
        if not self._resnet_available or self._resnet_classifier is None:
            return None
        try:
            result = self._resnet_classifier.predict(
                image, use_tta=True, generate_gradcam=True
            )
            if not result.model_available:
                return None

            output = result.to_dict()

            # Inclui Grad-CAM overlay no resultado
            if result.grad_cam_overlay is not None:
                output['grad_cam_overlay'] = result.grad_cam_overlay

            # Mapeia para etiologia do sistema
            if result.stage2 and result.final_class in WOUND_TO_ETIOLOGY:
                output['mapped_etiology'] = WOUND_TO_ETIOLOGY[result.final_class]

            # Ação clínica recomendada
            if result.final_class in WOUND_CLINICAL_ACTIONS:
                output['clinical_action'] = WOUND_CLINICAL_ACTIONS[result.final_class]

            return output
        except Exception as e:
            print(f"[HEAL+] Erro ResNet50: {e}")
            return None

    # -------------------------------------------------------
    @staticmethod
    def _exclude_surgical_background(
        image: np.ndarray, wound_mask: np.ndarray
    ) -> np.ndarray:
        """
        Detecta e exclui fundo cirúrgico (lençol azul, verde, cinza de maca)
        da máscara de ferida para evitar que o segmentador confunda sombras do
        campo cirúrgico com necrose ou esfacelo.

        Detecta:
        - Azul hospitalar:  H 90-130, S > 30, V qualquer
        - Verde cirúrgico:  H 35-85,  S > 30, V > 30
        - Cinza de maca:    S < 25,   V 40-170 (acromático)
        - Branco de gaze:   S < 20,   V > 200
        """
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)

        drape_mask = np.zeros(image.shape[:2], dtype=np.uint8)

        # Azul hospitalar (lençol, campo cirúrgico)
        drape_mask = cv2.bitwise_or(
            drape_mask,
            cv2.inRange(hsv, np.array([90, 30, 20]), np.array([130, 255, 255]))
        )
        # Verde cirúrgico
        drape_mask = cv2.bitwise_or(
            drape_mask,
            cv2.inRange(hsv, np.array([55, 60, 35]), np.array([95, 255, 255]))
        )
        # Cinza acromático (maca, superfície metálica)
        drape_mask = cv2.bitwise_or(
            drape_mask,
            cv2.inRange(hsv, np.array([0, 0, 40]), np.array([180, 25, 170]))
        )

        # Só exclui se a região de drape cobre uma fração significativa
        # (evita excluir pixels legítimos em imagens sem campo cirúrgico)
        drape_ratio = np.sum(drape_mask > 0) / max(drape_mask.size, 1)
        if drape_ratio < 0.05:
            # Quase nada detectado — provavelmente não tem campo cirúrgico
            return wound_mask

        # Dilata levemente para pegar bordas de transição
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
        drape_mask = cv2.dilate(drape_mask, kernel, iterations=1)

        # Remove do wound_mask
        cleaned = cv2.bitwise_and(wound_mask, cv2.bitwise_not(drape_mask))

        # Garante que ainda resta área útil (não remove tudo)
        if np.sum(cleaned > 0) < 0.02 * wound_mask.size:
            # Se removeu quase tudo, ignora a exclusão
            return wound_mask

        return cleaned

    # -------------------------------------------------------
    def _validate_wound_image(self, image: np.ndarray) -> bool:
        """Verifica se a imagem provavelmente contém uma ferida."""
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)

        # Verifica se é completamente monoton (tela preta, branca, etc.)
        std_val = np.std(hsv[:, :, 2])
        if std_val < 8:
            return False

        # Verifica se tem variação de matiz suficiente
        std_hue = np.std(hsv[:, :, 0])
        if std_hue < 3 and np.std(hsv[:, :, 1]) < 10:
            return False

        # Verifica se é uma foto (não um diagrama/texto)
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, 50, 150)
        edge_ratio = np.sum(edges > 0) / edges.size
        # Textos/diagramas têm muitas bordas finas
        if edge_ratio > 0.35:
            return False

        # Busca por cores compatíveis com ferida/pele
        # Vermelhos + rosados + amarelos + escuros + tons de pele
        wound_colors = np.zeros(image.shape[:2], dtype=np.uint8)
        ranges = [
            (np.array([0, 30, 40]), np.array([25, 255, 255])),    # tons de pele/vermelho
            (np.array([155, 30, 40]), np.array([180, 255, 255])), # vermelho wrap
            (np.array([0, 0, 0]), np.array([180, 255, 60])),     # escuro/necrose
            (np.array([15, 30, 100]), np.array([40, 255, 255])), # amarelo
        ]
        for lower, upper in ranges:
            wound_colors = cv2.bitwise_or(wound_colors, cv2.inRange(hsv, lower, upper))

        wound_ratio = np.sum(wound_colors > 0) / wound_colors.size
        if wound_ratio < 0.05:
            return False

        return True

    # -------------------------------------------------------
    # MÃ‰TODOS DE ROI E ZONAS ESPACIAIS (v3)
    # -------------------------------------------------------

    def _create_wound_roi_mask(
        self, image: np.ndarray, detections: list
    ) -> np.ndarray:
        """
        Cria máscara ROI precisa do leito da ferida usando contorno real
        em vez de bounding boxes retangulares.
        """
        h, w = image.shape[:2]
        wound_mask = np.zeros((h, w), dtype=np.uint8)

        if not detections:
            wound_mask[:] = 255
            return wound_mask

        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)

        def build_roi_mask(rx1: int, ry1: int, rx2: int, ry2: int) -> np.ndarray:
            roi_hsv = hsv[ry1:ry2, rx1:rx2]

            wound_colors = np.zeros(roi_hsv.shape[:2], dtype=np.uint8)
            wound_colors = cv2.bitwise_or(wound_colors, cv2.inRange(
                roi_hsv, np.array([0, 40, 40]), np.array([15, 255, 255])))
            wound_colors = cv2.bitwise_or(wound_colors, cv2.inRange(
                roi_hsv, np.array([155, 40, 40]), np.array([180, 255, 255])))
            wound_colors = cv2.bitwise_or(wound_colors, cv2.inRange(
                roi_hsv, np.array([10, 18, 70]), np.array([55, 255, 255])))
            wound_colors = cv2.bitwise_or(wound_colors, cv2.inRange(
                roi_hsv, np.array([30, 12, 68]), np.array([82, 130, 185])))
            wound_colors = cv2.bitwise_or(wound_colors, cv2.inRange(
                roi_hsv, np.array([0, 0, 0]), np.array([180, 255, 85])))
            wound_colors = cv2.bitwise_or(wound_colors, cv2.inRange(
                roi_hsv, np.array([0, 8, 160]), np.array([20, 80, 255])))
            wound_colors = cv2.bitwise_or(wound_colors, cv2.inRange(
                roi_hsv, np.array([150, 8, 160]), np.array([180, 80, 255])))

            bg_mask = np.zeros(roi_hsv.shape[:2], dtype=np.uint8)
            bg_mask = cv2.bitwise_or(bg_mask, cv2.inRange(
                roi_hsv, np.array([92, 45, 20]), np.array([130, 255, 255])))
            bg_mask = cv2.bitwise_or(bg_mask, cv2.inRange(
                roi_hsv, np.array([55, 60, 35]), np.array([95, 255, 255])))

            roi_mask = cv2.bitwise_and(wound_colors, cv2.bitwise_not(bg_mask))

            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (11, 11))
            roi_mask = cv2.morphologyEx(roi_mask, cv2.MORPH_CLOSE, kernel, iterations=3)
            kernel_open = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
            roi_mask = cv2.morphologyEx(roi_mask, cv2.MORPH_OPEN, kernel_open, iterations=1)

            roi_filled = np.zeros_like(roi_mask)
            contours, _ = cv2.findContours(
                roi_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
            )
            if contours:
                min_contour_area = (rx2 - rx1) * (ry2 - ry1) * 0.01
                for cnt in contours:
                    if cv2.contourArea(cnt) >= min_contour_area:
                        cv2.drawContours(roi_filled, [cnt], -1, 255, cv2.FILLED)
                
                # Se ainda ficou vazio, pega o maior
                if np.sum(roi_filled > 0) == 0:
                    largest_cnt = max(contours, key=cv2.contourArea)
                    cv2.drawContours(roi_filled, [largest_cnt], -1, 255, cv2.FILLED)

            return roi_filled

        for det in detections:
            x1, y1, x2, y2 = det.bbox
            margin_x = int((x2 - x1) * 0.05)
            margin_y = int((y2 - y1) * 0.05)
            rx1 = max(0, x1 - margin_x)
            ry1 = max(0, y1 - margin_y)
            rx2 = min(w, x2 + margin_x)
            ry2 = min(h, y2 + margin_y)

            roi_filled = build_roi_mask(rx1, ry1, rx2, ry2)
            wound_mask[ry1:ry2, rx1:rx2] = cv2.bitwise_or(
                wound_mask[ry1:ry2, rx1:rx2], roi_filled
            )

        if len(detections) >= 2:
            x1 = max(0, min(det.bbox[0] for det in detections))
            y1 = max(0, min(det.bbox[1] for det in detections))
            x2 = min(w, max(det.bbox[2] for det in detections))
            y2 = min(h, max(det.bbox[3] for det in detections))
            merged_filled = build_roi_mask(x1, y1, x2, y2)
            wound_mask[y1:y2, x1:x2] = cv2.bitwise_or(
                wound_mask[y1:y2, x1:x2],
                merged_filled,
            )

        return wound_mask

    @staticmethod
    def _create_zone_masks(
        wound_mask: np.ndarray,
        border_width_px: int = 15
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Separa a máscara da ferida em zonas espaciais:

        - peripheral_zone: anel de borda interna (transição ferida → pele sã)
        - core_zone: centro/miolo do leito da ferida
        - outer_ring: anel externo (para detectar epitelização avançando)

        A largura do buffer é adaptativa: usa min(border_width_px,
        ~15% do raio equivalente) para não engolir feridas pequenas.

        Args:
            wound_mask: Máscara binária da ferida (255 = ferida)
            border_width_px: Largura base do anel de borda em pixels

        Returns:
            (peripheral_zone, core_zone, outer_ring) — todas uint8, 0/255
        """
        h, w = wound_mask.shape[:2]

        # Raio equivalente para adaptar largura do buffer
        wound_area = np.sum(wound_mask > 0)
        equiv_radius = np.sqrt(wound_area / np.pi) if wound_area > 0 else 0

        # Buffer adaptativo: máx 15% do raio, mín 3px, máx border_width_px
        adaptive_width = int(np.clip(equiv_radius * 0.15, 3, border_width_px))

        # Erosão para criar zona central (core)
        kernel = cv2.getStructuringElement(
            cv2.MORPH_ELLIPSE,
            (2 * adaptive_width + 1, 2 * adaptive_width + 1)
        )
        eroded = cv2.erode(wound_mask, kernel, iterations=1)

        # core = interior erodido
        core_zone = eroded

        # peripheral = wound_mask - core (anel interno da borda)
        peripheral_zone = cv2.bitwise_and(
            wound_mask, cv2.bitwise_not(core_zone)
        )

        # outer_ring = dilatação - wound_mask (anel externo)
        dilated = cv2.dilate(wound_mask, kernel, iterations=1)
        outer_ring = cv2.bitwise_and(
            dilated, cv2.bitwise_not(wound_mask)
        )

        return peripheral_zone, core_zone, outer_ring

    # -------------------------------------------------------
    # CLASSIFICAÃ‡ÃƒO ESPACIAL DE BACKGROUND
    # -------------------------------------------------------

    @staticmethod
    def _create_background_mask_spatial(
        image: np.ndarray,
        wound_mask: np.ndarray,
    ) -> np.ndarray:
        """
        Classifica pixels escuros como 'background' vs 'necrose' usando
        contexto espacial em vez de apenas valor de pixel.

        Racional clínico:
          Fundo de câmera fotográfica e necrose de coagulação (escara) são
          ambos muito escuros (V ≈ 0). Porém, diferem em:
            1. Variância local — fundo é uniformemente preto (var ≈ 0),
               enquanto tecido necrótico tem micro-textura (var > 0).
            2. Crominância — fundo puro é acromático (a*≈128, b*≈128),
               enquanto necrose geralmente tem tint marrom/vermelho.
            3. Conectividade — fundo tende a formar regiões grandes e
               contíguas que tocam as bordas da imagem; necrose forma
               ilhas menores dentro do perímetro anatômico.
            4. Posição relativa — fundo de câmera frequentemente toca
               as bordas da imagem; necrose está centrada no leito.

        Pipeline:
          1) Identifica pixels muito escuros (V < 20) dentro do wound_mask
          2) Calcula variância local (5×5) — background: var < threshold
          3) Calcula desvio cromático (chroma) — background: chroma ≈ 0
          4) Conectividade: regiões escuras > 30% do wound_mask E tocando
             borda da imagem → provável background leaking
          5) Score combinado → máscara de background

        Args:
            image: Imagem BGR original
            wound_mask: Máscara binária da ferida (255 = ferida)

        Returns:
            background_mask: Máscara onde 255 = pixel de background, 0 = tecido
        """
        h, w = image.shape[:2]
        background_mask = np.zeros((h, w), dtype=np.uint8)

        # 1. Pixels muito escuros dentro do wound_mask
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        very_dark = (gray < 20).astype(np.uint8) * 255
        dark_in_roi = cv2.bitwise_and(very_dark, wound_mask)

        # Se quase não tem pixels escuros no ROI, retorna vazio
        dark_count = np.sum(dark_in_roi > 0)
        roi_count = max(np.sum(wound_mask > 0), 1)
        if dark_count < roi_count * 0.02:
            return background_mask  # < 2% escuro → não tem background significativo

        # 2. Variância local (5×5) — background tem variância ≈ 0
        gray_f = gray.astype(np.float32)
        local_mean = cv2.blur(gray_f, (5, 5))
        local_sqmean = cv2.blur(gray_f ** 2, (5, 5))
        local_var = local_sqmean - local_mean ** 2
        local_var = np.clip(local_var, 0, None)

        # Background: variância muito baixa (superfície uniforme)
        low_var = (local_var < 8.0).astype(np.uint8) * 255

        # 3. Crominância — background é acromático puro
        lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
        a_ch = lab[:, :, 1].astype(np.float32)
        b_ch = lab[:, :, 2].astype(np.float32)
        chroma_deviation = np.sqrt((a_ch - 128.0) ** 2 + (b_ch - 128.0) ** 2)

        # Acromático = desvio cromático < 5 (praticamente neutro)
        achromatic = (chroma_deviation < 5.0).astype(np.uint8) * 255

        # 4. Candidato a background: escuro + variância baixa + acromático
        bg_candidate = cv2.bitwise_and(dark_in_roi, low_var)
        bg_candidate = cv2.bitwise_and(bg_candidate, achromatic)

        # 5. Análise de conectividade — regiões grandes e/ou tocando borda
        # são mais prováveis de ser background
        contours, _ = cv2.findContours(
            bg_candidate, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )

        border_margin = 3  # pixels da borda da imagem
        for cnt in contours:
            area = cv2.contourArea(cnt)

            # Critério 1: região muito grande (> 15% do wound_mask) → background
            if area > roi_count * 0.15:
                cv2.drawContours(background_mask, [cnt], -1, 255, cv2.FILLED)
                continue

            # Critério 2: toca borda da imagem → provável background de câmera
            x, y, cw, ch = cv2.boundingRect(cnt)
            touches_border = (
                x <= border_margin or
                y <= border_margin or
                (x + cw) >= (w - border_margin) or
                (y + ch) >= (h - border_margin)
            )
            if touches_border and area > 50:
                cv2.drawContours(background_mask, [cnt], -1, 255, cv2.FILLED)
                continue

            # Critério 3: região pequena mas extremamente uniforme
            # (variância média dentro da região < 2) → background
            cnt_mask = np.zeros((h, w), dtype=np.uint8)
            cv2.drawContours(cnt_mask, [cnt], -1, 255, cv2.FILLED)
            region_var = local_var[cnt_mask > 0]
            if len(region_var) > 10 and np.mean(region_var) < 2.0:
                cv2.drawContours(background_mask, [cnt], -1, 255, cv2.FILLED)

        # 6. Dilata levemente para fechar bordas de transição
        if np.sum(background_mask > 0) > 0:
            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
            background_mask = cv2.dilate(background_mask, kernel, iterations=1)
            background_mask = cv2.bitwise_and(background_mask, wound_mask)

        return background_mask

    def _detect_epithelialization_gradient(
        self,
        image: np.ndarray,
        wound_mask: np.ndarray,
        peripheral_zone: np.ndarray,
        outer_ring: np.ndarray,
    ) -> np.ndarray:
        """
        Detecta tecido epitelial usando análise de gradiente na zona de borda.

        A epitelização ocorre especificamente na transição ferida → pele sã:
        - Cor rosa claro / translúcido
        - Gradiente suave (superfície lisa, sem textura granulada)
        - Proximidade com pele íntegra (zona periférica)
        - Baixo contraste local (tecido uniforme)

        Combina:
        1. Detecção por cor HSV/LAB restrita à zona periférica
        2. Análise de gradiente (Scharr) — epitelização tem gradiente baixo
        3. Proximidade com borda (weighted distance transform)

        Returns:
            epithelial_mask: máscara binária dos pixels epiteliais (0/255)
        """
        h, w = image.shape[:2]

        # Zona de interesse: periferia interna + anel externo
        epi_roi = cv2.bitwise_or(peripheral_zone, outer_ring)

        # 1. Detecção por cor na zona periférica (HSV + LAB)
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)

        color_mask = np.zeros((h, w), dtype=np.uint8)
        for lower, upper in CLINICAL_HSV_RANGES["epithelialization"]:
            color_mask = cv2.bitwise_or(
                color_mask, cv2.inRange(hsv, lower, upper)
            )
        for lower, upper in CLINICAL_LAB_RANGES["epithelialization"]:
            color_mask = cv2.bitwise_or(
                color_mask, cv2.inRange(lab, lower, upper)
            )
        # Restringe estritamente à zona periférica + anel externo
        color_mask = cv2.bitwise_and(color_mask, epi_roi)

        # 2. Análise de gradiente — Scharr (mais preciso que Sobel)
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        gray_smooth = cv2.GaussianBlur(gray, (5, 5), 0)

        grad_x = cv2.Scharr(gray_smooth, cv2.CV_64F, 1, 0)
        grad_y = cv2.Scharr(gray_smooth, cv2.CV_64F, 0, 1)
        gradient_mag = np.sqrt(grad_x ** 2 + grad_y ** 2)

        # Normaliza gradiente para 0-255
        grad_norm = cv2.normalize(
            gradient_mag, None, 0, 255, cv2.NORM_MINMAX
        ).astype(np.uint8)

        # Epitelização = gradiente BAIXO (superfície lisa/translúcida)
        # Threshold adaptativo: 40º percentil na zona de interesse
        peri_grads = grad_norm[epi_roi > 0]
        if len(peri_grads) > 50:
            grad_threshold = np.percentile(peri_grads, 40)
        else:
            grad_threshold = 30

        low_gradient = (grad_norm < grad_threshold).astype(np.uint8) * 255
        low_gradient = cv2.bitwise_and(low_gradient, epi_roi)

        # 3. Distance transform — peso por proximidade da borda
        dist = cv2.distanceTransform(wound_mask, cv2.DIST_L2, 5)
        max_dist = np.max(dist) if np.max(dist) > 0 else 1.0

        # Peso maior para pixels próximos à borda (inverso da distância)
        border_weight = 1.0 - (dist / max_dist)
        border_weight_u8 = (border_weight * 255).astype(np.uint8)

        # Peso alto na borda (>= 80% de peso → V > 200) — mais restrito
        border_strong = (border_weight_u8 > 200).astype(np.uint8) * 255

        # 4. Combinação ponderada:
        #    Cor rosa: 50% (mais peso para cor) | Gradiente baixo: 25% | Borda: 25%
        epi_score = np.zeros((h, w), dtype=np.float32)
        epi_score += (color_mask.astype(np.float32) / 255.0) * 0.50
        epi_score += (low_gradient.astype(np.float32) / 255.0) * 0.25
        epi_score += (border_strong.astype(np.float32) / 255.0) * 0.25

        # Threshold alto: cor é obrigatória + pelo menos 1 outro critério (> 0.70)
        epithelial_mask = np.where(epi_score > 0.70, 255, 0).astype(np.uint8)

        # Restringe estritamente à zona periférica + outer ring
        epithelial_mask = cv2.bitwise_and(epithelial_mask, epi_roi)

        # Limpeza morfológica — open maior para remover ruído
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
        epithelial_mask = cv2.morphologyEx(epithelial_mask, cv2.MORPH_OPEN, kernel)
        epithelial_mask = cv2.morphologyEx(epithelial_mask, cv2.MORPH_CLOSE, kernel)

        return epithelial_mask

    # -------------------------------------------------------
    # SEGMENTAÃ‡ÃƒO TECIDUAL
    # -------------------------------------------------------

    def _segment_clinical(
        self, image: np.ndarray, wound_mask: np.ndarray
    ) -> Tuple[Dict[str, float], np.ndarray, np.ndarray]:
        """Segmenta a ferida segundo taxonomia clínica (v1/v2 — legado)."""
        peripheral, core, outer = self._create_zone_masks(wound_mask)
        return self._segment_clinical_v3(image, wound_mask, peripheral, core, outer)

    def _segment_clinical_v2(
        self, image: np.ndarray, wound_mask: np.ndarray
    ) -> Tuple[Dict[str, float], np.ndarray, np.ndarray]:
        """Compat v2: delega para v3 com zonas auto-calculadas."""
        peripheral, core, outer = self._create_zone_masks(wound_mask)
        return self._segment_clinical_v3(image, wound_mask, peripheral, core, outer)

    @staticmethod
    def _estimate_skin_tone(
        image: np.ndarray,
        wound_mask: np.ndarray,
    ) -> Tuple[float, float, float, str]:
        """
        Estima o tom de pele do paciente amostrand pixel da região perilesional.

        Amostra pixels no anel de 15-40px ao redor da wound_mask que não sejam
        fundo cirúrgico (azul/verde/cinza) nem partes da ferida.

        Returns:
            (L_mean, a_mean, b_mean, fitzpatrick_approx)
            L_mean: luminosidade média LAB do periwound
            a_mean: canal a* médio
            b_mean: canal b* médio
            fitzpatrick_approx: "I-II", "III", "IV", "V", "VI"
        """
        h, w = image.shape[:2]

        # Cria anel perilesional: dilata 40px - dilata 15px
        kernel_inner = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (31, 31))
        kernel_outer = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (81, 81))
        inner_ring = cv2.dilate(wound_mask, kernel_inner)
        outer_ring = cv2.dilate(wound_mask, kernel_outer)
        periwound = cv2.bitwise_and(outer_ring, cv2.bitwise_not(inner_ring))

        # Exclui fundo cirúrgico do periwound
        hsv_raw = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        drape = np.zeros((h, w), dtype=np.uint8)
        # Azul hospitalar
        drape = cv2.bitwise_or(drape, cv2.inRange(
            hsv_raw, np.array([90, 30, 20]), np.array([130, 255, 255])))
        # Verde cirúrgico
        drape = cv2.bitwise_or(drape, cv2.inRange(
            hsv_raw, np.array([55, 60, 35]), np.array([95, 255, 255])))
        # Cinza acromático (maca/fundo)
        drape = cv2.bitwise_or(drape, cv2.inRange(
            hsv_raw, np.array([0, 0, 0]), np.array([180, 20, 100])))

        skin_sample = cv2.bitwise_and(periwound, cv2.bitwise_not(drape))

        # Amostra em LAB
        lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
        skin_pixels = lab[skin_sample > 0]

        if len(skin_pixels) < 50:
            # Fallback: sem dados suficientes, assume pele média
            return 140.0, 128.0, 128.0, "III"

        L_mean = float(np.median(skin_pixels[:, 0]))
        a_mean = float(np.median(skin_pixels[:, 1]))
        b_mean = float(np.median(skin_pixels[:, 2]))

        # Classificação Fitzpatrick aproximada
        if L_mean > 180:
            fitz = "I-II"
        elif L_mean > 150:
            fitz = "III"
        elif L_mean > 110:
            fitz = "IV"
        elif L_mean > 70:
            fitz = "V"
        else:
            fitz = "VI"

        return L_mean, a_mean, b_mean, fitz

    @staticmethod
    def _safe_percentile(values: np.ndarray, q: float, default: float) -> float:
        arr = np.asarray(values, dtype=np.float32).reshape(-1)
        arr = arr[np.isfinite(arr)]
        if arr.size < 32:
            return float(default)
        return float(np.percentile(arr, q))

    def _build_adaptive_tissue_masks(
        self,
        denoised_norm: np.ndarray,
        hsv: np.ndarray,
        lab: np.ndarray,
        wound_mask: np.ndarray,
        peripheral_zone: np.ndarray,
        core_zone: np.ndarray,
        skin_exclude_mask: np.ndarray,
        not_drape_mask: np.ndarray,
        local_var: np.ndarray,
        kernel_s: np.ndarray,
        kernel_m: np.ndarray,
    ) -> Tuple[Dict[str, np.ndarray], Dict[str, object]]:
        h, w = wound_mask.shape[:2]
        adaptive_masks = {
            "necrosis": np.zeros((h, w), dtype=np.uint8),
            "slough": np.zeros((h, w), dtype=np.uint8),
            "granulation": np.zeros((h, w), dtype=np.uint8),
            "epithelialization": np.zeros((h, w), dtype=np.uint8),
        }

        roi = wound_mask > 0
        roi_pixels = int(np.count_nonzero(roi))
        if roi_pixels < 80:
            return adaptive_masks, {
                "criteria": [
                    "ROI pequena: sem reforco adaptativo de cores.",
                ],
                "adaptive_thresholds": {},
            }

        bgr_f = denoised_norm.astype(np.float32)
        blue, green, red = cv2.split(bgr_f)
        hue = hsv[:, :, 0].astype(np.float32)
        sat = hsv[:, :, 1].astype(np.float32)
        val = hsv[:, :, 2].astype(np.float32)
        light = lab[:, :, 0].astype(np.float32)
        a_ch = lab[:, :, 1].astype(np.float32)
        b_ch = lab[:, :, 2].astype(np.float32)

        red_excess = red - np.maximum(green, blue)
        red_gap = red - green
        yellow_signal = (b_ch - 128.0) + 0.35 * (green - blue)
        dark_signal = 0.70 * (255.0 - light) + 0.30 * (255.0 - val)
        pink_signal = (
            0.45 * (a_ch - 128.0)
            + 0.35 * (light - 160.0)
            - 0.20 * np.maximum(sat - 110.0, 0.0)
        )

        roi_values = lambda arr: arr[roi]
        low_texture_thr = self._safe_percentile(roi_values(local_var), 45, 220.0)
        high_texture_thr = self._safe_percentile(roi_values(local_var), 62, 520.0)
        dark_l_thr = min(108.0, self._safe_percentile(roi_values(light), 28, 82.0))
        dark_v_thr = min(95.0, self._safe_percentile(roi_values(val), 25, 72.0) + 6.0)
        red_a_thr = max(144.0, self._safe_percentile(roi_values(a_ch), 60, 146.0))
        red_gap_thr = max(20.0, self._safe_percentile(roi_values(red_gap), 58, 22.0))
        red_excess_thr = max(14.0, self._safe_percentile(roi_values(red_excess), 55, 18.0))
        yellow_b_thr = max(142.0, self._safe_percentile(roi_values(b_ch), 60, 145.0))
        yellow_sig_thr = max(16.0, self._safe_percentile(roi_values(yellow_signal), 60, 18.0))
        light_l_thr = max(105.0, self._safe_percentile(roi_values(light), 40, 118.0))
        sat_soft_thr = max(55.0, min(125.0, self._safe_percentile(roi_values(sat), 56, 95.0) + 10.0))
        pink_l_thr = max(165.0, self._safe_percentile(roi_values(light), 66, 170.0))

        border_zone = peripheral_zone > 0
        pink_signal_thr = self._safe_percentile(pink_signal[border_zone], 55, 6.0)
        dark_signal_thr = self._safe_percentile(roi_values(dark_signal), 72, 120.0)

        base_roi = roi & (not_drape_mask > 0)
        not_skin = skin_exclude_mask == 0
        inner_zone = (core_zone > 0) | (peripheral_zone > 0)

        dark_candidate = (
            (light <= dark_l_thr)
            | (val <= dark_v_thr)
            | (dark_signal >= dark_signal_thr)
        )
        brown_or_olive = (
            ((hue >= 8.0) & (hue <= 55.0) & (sat >= 20.0))
            | ((yellow_signal >= yellow_sig_thr * 0.8) & (a_ch <= red_a_thr + 4.0))
        )
        neutral_dark = (
            (np.abs(a_ch - 128.0) <= 20.0)
            & (np.abs(b_ch - 128.0) <= 26.0)
        )
        anti_red_bias = (
            (red_excess <= red_excess_thr + 8.0)
            | (light < dark_l_thr - 4.0)
        )
        necrosis_bool = (
            base_roi
            & inner_zone
            & not_skin
            & dark_candidate
            & anti_red_bias
            & (brown_or_olive | neutral_dark | (local_var <= low_texture_thr + 90.0))
        )

        yellowish = (b_ch >= yellow_b_thr) | (yellow_signal >= yellow_sig_thr)
        off_white = (sat <= sat_soft_thr) & (light >= light_l_thr)
        olive_slough = (
            (hue >= 30.0)
            & (hue <= 78.0)
            & (sat >= 12.0)
            & (sat <= sat_soft_thr + 28.0)
            & (val >= max(68.0, dark_v_thr - 6.0))
            & (light >= max(92.0, light_l_thr - 18.0))
            & (green >= blue + 2.0)
            & (red >= blue - 8.0)
        )
        slough_bool = (
            base_roi
            & inner_zone
            & (~dark_candidate)
            & (yellowish | off_white | olive_slough)
            & ((light >= light_l_thr - 16.0) | olive_slough)
            & (red_excess < red_excess_thr + 20.0)
            & (local_var <= high_texture_thr + 180.0)
        )

        reddish = (
            (a_ch >= red_a_thr)
            & ((red_excess >= red_excess_thr) | (red_gap >= red_gap_thr))
        )
        granulation_bool = (
            base_roi
            & reddish
            & (~dark_candidate)
            & ((local_var >= high_texture_thr) | (sat >= sat_soft_thr))
            & (yellow_signal < yellow_sig_thr + 8.0)
        )

        pinkish = (
            (light >= pink_l_thr)
            & (a_ch >= 132.0)
            & (sat <= sat_soft_thr)
            & (val >= light_l_thr)
        )
        epithelial_bool = (
            base_roi
            & border_zone
            & pinkish
            & (local_var <= high_texture_thr)
            & (pink_signal >= pink_signal_thr)
        )

        raw_masks = {
            "necrosis": necrosis_bool,
            "slough": slough_bool,
            "granulation": granulation_bool,
            "epithelialization": epithelial_bool,
        }
        for key, bool_mask in raw_masks.items():
            mask = bool_mask.astype(np.uint8) * 255
            mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel_s)
            mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel_m)
            adaptive_masks[key] = mask

        trace = {
            "criteria": [
                "Granulacao: vermelho relativo + a* alto + textura mais vascular dentro do leito.",
                "Esfacelo: amarelo/branco + brilho intermediario + textura menos vascular.",
                "Esfacelo oliva/acinzentado: tons amarelo-esverdeados ou cinza-oliva ainda contam como tecido desvitalizado.",
                "Necrose: baixa luminosidade + tons castanho/oliva escuros + exclusao de pele saudavel.",
                "Epitelizacao: rosa claro + baixa textura + restrita a borda interna da ferida.",
            ],
            "adaptive_thresholds": {
                "dark_l": round(dark_l_thr, 2),
                "dark_v": round(dark_v_thr, 2),
                "red_a": round(red_a_thr, 2),
                "yellow_b": round(yellow_b_thr, 2),
                "low_texture": round(low_texture_thr, 2),
                "high_texture": round(high_texture_thr, 2),
                "sat_soft": round(sat_soft_thr, 2),
                "pink_l": round(pink_l_thr, 2),
            },
            "adaptive_pixels": {
                key: int(np.count_nonzero(mask > 0))
                for key, mask in adaptive_masks.items()
            },
        }
        return adaptive_masks, trace

    def _segment_clinical_v3(
        self,
        image: np.ndarray,
        wound_mask: np.ndarray,
        peripheral_zone: np.ndarray,
        core_zone: np.ndarray,
        outer_ring: np.ndarray,
    ) -> Tuple[Dict[str, float], np.ndarray, np.ndarray]:
        """
        Segmentação clínica v3 — multi-espaço de cor + zonas espaciais + gradiente.

        Pipeline:
        1. Estimação do tom de pele (Fitzpatrick) via periwound
        2. Denoise bilateral (preserva bordas)
        3. CLAHE adaptativo (L + canal a*)
        4. Conversão HSV + LAB
        5. Segmentação por cor restrita estritamente à wound_mask (ROI)
        6. Fusão ponderada HSV (60%) + LAB (40%)
        7. CRIAÃ‡ÃƒO DE MÁSCARA DE PELE SAUDÁVEL para excluir da necrose
        8. Restrição espacial por zonas
        9. Detecção de epitelização por gradiente de borda (Scharr)
        10. Verificação de textura para necrose (necrose real tem textura diferente de pele)
        11. Exclusão de fundo cirúrgico
        12. Resolução de sobreposições com prioridade clínica
        """
        # â”€â”€ 0. Estimação do tom de pele do paciente â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        skin_L, skin_a, skin_b, fitzpatrick = self._estimate_skin_tone(image, wound_mask)
        is_dark_skin = fitzpatrick in ("V", "VI")
        is_medium_skin = fitzpatrick in ("IV", "V")
        logger.debug(
            f"Tom de pele estimado: Fitzpatrick {fitzpatrick} "
            f"(L={skin_L:.0f}, a*={skin_a:.0f}, b*={skin_b:.0f})"
        )

        # â”€â”€ 1. Pré-processamento: denoise + CLAHE â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        denoised = cv2.bilateralFilter(image, d=9, sigmaColor=50, sigmaSpace=50)
        lab_clahe = cv2.cvtColor(denoised, cv2.COLOR_BGR2LAB)
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
        lab_clahe[:, :, 0] = clahe.apply(lab_clahe[:, :, 0])
        clahe_a = cv2.createCLAHE(clipLimit=1.5, tileGridSize=(8, 8))
        lab_clahe[:, :, 1] = clahe_a.apply(lab_clahe[:, :, 1])
        denoised_norm = cv2.cvtColor(lab_clahe, cv2.COLOR_LAB2BGR)

        # Aplica denoise/CLAHE SOMENTE no ROI da ferida (preserva dados originais fora)
        roi_image = cv2.bitwise_and(denoised_norm, denoised_norm, mask=wound_mask)

        hsv = cv2.cvtColor(roi_image, cv2.COLOR_BGR2HSV)
        lab = cv2.cvtColor(roi_image, cv2.COLOR_BGR2LAB)

        h, w = image.shape[:2]
        kernel_s = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        kernel_m = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        kernel_l = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9))

        # â”€â”€ 2. Segmentação HSV — restrita estritamente à wound_mask â”€â”€â”€
        hsv_masks = {}
        for tissue_key, ranges in CLINICAL_HSV_RANGES.items():
            mask = np.zeros((h, w), dtype=np.uint8)
            for lower, upper in ranges:
                mask = cv2.bitwise_or(mask, cv2.inRange(hsv, lower, upper))
            # OBRIGATÃ“RIO: restringe à ROI — ignora todo pixel fora do perímetro
            mask = cv2.bitwise_and(mask, wound_mask)
            mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel_s)
            mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel_m)
            hsv_masks[tissue_key] = mask

        # â”€â”€ 3. Segmentação LAB — restrita à wound_mask â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        lab_masks = {}
        for tissue_key, ranges in CLINICAL_LAB_RANGES.items():
            mask = np.zeros((h, w), dtype=np.uint8)
            for lower, upper in ranges:
                mask = cv2.bitwise_or(mask, cv2.inRange(lab, lower, upper))
            mask = cv2.bitwise_and(mask, wound_mask)
            mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel_s)
            mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel_m)
            lab_masks[tissue_key] = mask

        # â”€â”€ 4. Fusão ponderada HSV (60%) + LAB (40%) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        masks = {}
        for tissue_key in CLINICAL_HSV_RANGES.keys():
            hsv_m = hsv_masks.get(tissue_key, np.zeros((h, w), dtype=np.uint8))
            lab_m = lab_masks.get(tissue_key, np.zeros((h, w), dtype=np.uint8))

            combined = (hsv_m.astype(np.float32) * 0.6 +
                        lab_m.astype(np.float32) * 0.4)
            # Threshold: HSV sozinho (153) passa; LAB sozinho (102) passa;
            # ambos parciais precisam de pelo menos ~40% cada
            mask = np.where(combined > 90, 255, 0).astype(np.uint8)

            mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel_s)
            mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel_l)
            # Restrição final à ROI (nenhum pixel fora do perímetro)
            mask = cv2.bitwise_and(mask, wound_mask)
            masks[tissue_key] = mask

        # â”€â”€ 5. Criação de máscara de pele saudável (skin exclusion) â”€â”€â”€â”€
        # Gera uma máscara PRECISA de pixels que se parecem com pele saudável
        # do paciente (tolerâncias ESTREITAS para não excluir necrose real).
        lab_for_skin = cv2.cvtColor(denoised_norm, cv2.COLOR_BGR2LAB)

        # Tolerâncias ESTREITAS: só exclui pixels MUITO próximos da pele
        # perilesional. Necrose tem cores diferentes mesmo em pele escura.
        if is_dark_skin:
            L_tol, a_tol, b_tol = 18, 10, 10
        elif is_medium_skin:
            L_tol, a_tol, b_tol = 15, 8, 8
        else:
            L_tol, a_tol, b_tol = 12, 7, 7

        skin_lower = np.array([
            max(0, skin_L - L_tol),
            max(0, skin_a - a_tol),
            max(0, skin_b - b_tol)
        ], dtype=np.uint8)
        skin_upper = np.array([
            min(255, skin_L + L_tol),
            min(255, skin_a + a_tol),
            min(255, skin_b + b_tol)
        ], dtype=np.uint8)
        skin_exclude_mask = cv2.inRange(lab_for_skin, skin_lower, skin_upper)
        skin_exclude_mask = cv2.bitwise_and(skin_exclude_mask, wound_mask)

        # Verificação de textura: pele saudável é UNIFORME (variância 50-400)
        # Necrose tem textura irregular OU muito lisa (escara)
        gray_tex = cv2.cvtColor(denoised_norm, cv2.COLOR_BGR2GRAY)
        local_variance = cv2.GaussianBlur(
            (gray_tex.astype(np.float32) ** 2), (11, 11), 0
        ) - cv2.GaussianBlur(gray_tex.astype(np.float32), (11, 11), 0) ** 2
        local_variance = np.clip(local_variance, 0, None)

        # Somente textura típica de pele saudável (moderadamente uniforme)
        smooth_skin = ((local_variance > 50) & (local_variance < 400)).astype(np.uint8) * 255
        skin_exclude_mask = cv2.bitwise_and(skin_exclude_mask, smooth_skin)

        # Limpeza morfológica
        kernel_skin = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        skin_exclude_mask = cv2.morphologyEx(skin_exclude_mask, cv2.MORPH_CLOSE, kernel_skin)
        skin_exclude_mask = cv2.morphologyEx(skin_exclude_mask, cv2.MORPH_OPEN, kernel_skin)

        # Remove pixels de pele saudável da máscara de necrose
        masks["necrosis"] = cv2.bitwise_and(
            masks["necrosis"], cv2.bitwise_not(skin_exclude_mask)
        )

        logger.debug(
            f"Skin exclusion: {np.sum(skin_exclude_mask > 0)} px excluídos da necrose "
            f"(Fitzpatrick {fitzpatrick})"
        )

        # â”€â”€ 5b. Restrição espacial por zonas â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        # Necrose: viés espacial moderado. Em peles escuras, requer
        # confirmação por textura, mas NÃƒO restringimos excessivamente.
        necro_spatial = np.zeros((h, w), dtype=np.float32)
        necro_spatial[core_zone > 0] = 1.0
        if is_dark_skin:
            # Pele escura: periferia com peso moderado (não bloquear)
            necro_spatial[peripheral_zone > 0] = 0.45
        elif is_medium_skin:
            necro_spatial[peripheral_zone > 0] = 0.5
        else:
            necro_spatial[peripheral_zone > 0] = 0.6

        # Boost por luminância CONDICIONAL: somente pixels escuros
        # que NÃƒO são pele saudável do paciente (anti-bias)
        gray_roi = cv2.cvtColor(
            cv2.bitwise_and(denoised_norm, denoised_norm, mask=wound_mask),
            cv2.COLOR_BGR2GRAY
        )
        low_lum = (gray_roi < 45).astype(np.float32)
        not_skin_f = (cv2.bitwise_not(skin_exclude_mask) / 255.0).astype(np.float32)
        # Pixels escuros + não-pele dentro da ROI recebem boost espacial
        lum_boost = low_lum * not_skin_f * (wound_mask.astype(np.float32) / 255.0)
        necro_spatial = np.maximum(necro_spatial, lum_boost * 0.8)

        m_necro = masks["necrosis"].astype(np.float32)
        m_necro_biased = m_necro * necro_spatial
        # Threshold moderado (mesmo para pele escura — a skin exclusion já protege)
        necro_threshold = 100 if is_dark_skin else (90 if is_medium_skin else 80)
        masks["necrosis"] = np.where(m_necro_biased > necro_threshold, 255, 0).astype(np.uint8)
        masks["necrosis"] = cv2.bitwise_and(masks["necrosis"], wound_mask)

        # --- Esfacelo: viés moderado para core + periferia interna ---
        core_bias_slough = np.zeros((h, w), dtype=np.float32)
        core_bias_slough[core_zone > 0] = 1.0
        core_bias_slough[peripheral_zone > 0] = 0.5  # esfacelo pode estar na periferia

        m_slough = masks["slough"].astype(np.float32)
        m_slough_biased = m_slough * core_bias_slough
        masks["slough"] = np.where(m_slough_biased > 100, 255, 0).astype(np.uint8)
        masks["slough"] = cv2.bitwise_and(masks["slough"], wound_mask)

        # Granulação: presente no leito inteiro (core + periferia)
        # Sem viés espacial adicional — já restrita à wound_mask

        # Epitelização: EXCLUSIVAMENTE periférica.
        # Substitui a máscara de cor pura pelo detector de gradiente
        # que combina cor + suavidade + proximidade à borda.
        epi_gradient = self._detect_epithelialization_gradient(
            denoised_norm, wound_mask, peripheral_zone, outer_ring
        )
        # Mescla: usa o anel externo apenas como contexto, mas contabiliza
        # epitelizacao somente na borda interna da propria ferida.
        epi_color_periph = cv2.bitwise_and(masks["epithelialization"], peripheral_zone)

        masks["epithelialization"] = cv2.bitwise_and(
            cv2.bitwise_or(epi_color_periph, epi_gradient),
            peripheral_zone
        )

        # â”€â”€ 6. Refinamento por textura â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        gray = cv2.cvtColor(denoised_norm, cv2.COLOR_BGR2GRAY)
        local_var = cv2.GaussianBlur(
            (gray.astype(np.float32) ** 2), (15, 15), 0
        ) - cv2.GaussianBlur(gray.astype(np.float32), (15, 15), 0) ** 2
        local_var = np.clip(local_var, 0, None)

        low_texture = (local_var < 200).astype(np.uint8)
        high_texture = (local_var > 500).astype(np.uint8)

        # â”€â”€ 7. Exclusão de fundo cirúrgico â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        hsv_raw = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        _drape = np.zeros((h, w), dtype=np.uint8)
        _drape = cv2.bitwise_or(_drape, cv2.inRange(
            hsv_raw, np.array([90, 30, 20]), np.array([130, 255, 255])))
        _drape = cv2.bitwise_or(_drape, cv2.inRange(
            hsv_raw, np.array([55, 60, 35]), np.array([95, 255, 255])))
        _drape = cv2.bitwise_or(_drape, cv2.inRange(
            hsv_raw, np.array([0, 0, 40]), np.array([180, 22, 170])))
        _not_drape = cv2.bitwise_not(_drape)

        adaptive_masks, adaptive_trace = self._build_adaptive_tissue_masks(
            denoised_norm=denoised_norm,
            hsv=hsv,
            lab=lab,
            wound_mask=wound_mask,
            peripheral_zone=peripheral_zone,
            core_zone=core_zone,
            skin_exclude_mask=skin_exclude_mask,
            not_drape_mask=_not_drape,
            local_var=local_var,
            kernel_s=kernel_s,
            kernel_m=kernel_m,
        )
        for key, adaptive_mask in adaptive_masks.items():
            masks[key] = cv2.bitwise_or(masks[key], adaptive_mask)

        for _tk in masks:
            masks[_tk] = cv2.bitwise_and(masks[_tk], _not_drape)

        # â”€â”€ 8. Reforço por textura + luminância (com proteção anti-bias) â”€
        # Combina luminância + textura para reforçar necrose, mas EXCLUI
        # pixels que correspondem ao tom de pele do paciente.

        # 8a. Pixels escuros dentro da ROI que NÃƒO são pele saudável
        dark_px = (gray < 55).astype(np.uint8) * 255
        dark_px = cv2.bitwise_and(dark_px, _not_drape)
        dark_px = cv2.bitwise_and(dark_px, cv2.bitwise_not(skin_exclude_mask))

        # Proteção background residual
        lab_check = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
        a_ch = lab_check[:, :, 1].astype(np.float32)
        b_ch = lab_check[:, :, 2].astype(np.float32)
        chroma_dev = np.sqrt((a_ch - 128) ** 2 + (b_ch - 128) ** 2)
        possible_bg_residual = cv2.bitwise_and(
            ((local_var < 10).astype(np.uint8) * 255),
            ((chroma_dev < 6).astype(np.uint8) * 255)
        )
        possible_bg_residual = cv2.bitwise_and(
            possible_bg_residual,
            ((gray < 15).astype(np.uint8) * 255)
        )

        # 8b. Necrose por luminância: V < 45, dentro do ROI, não-pele, não-bg
        very_dark_roi = (gray < 45).astype(np.uint8) * 255
        very_dark_roi = cv2.bitwise_and(very_dark_roi, wound_mask)
        very_dark_roi = cv2.bitwise_and(very_dark_roi, _not_drape)
        very_dark_roi = cv2.bitwise_and(very_dark_roi, cv2.bitwise_not(skin_exclude_mask))
        very_dark_roi = cv2.bitwise_and(very_dark_roi, cv2.bitwise_not(possible_bg_residual))
        masks["necrosis"] = cv2.bitwise_or(masks["necrosis"], very_dark_roi)

        # 8c. Necrose por textura: baixa textura + escuro + não-pele
        necro_texture_boost = cv2.bitwise_and(
            cv2.bitwise_and(dark_px, wound_mask),
            (low_texture * 255).astype(np.uint8)
        )
        necro_texture_boost = cv2.bitwise_and(
            necro_texture_boost, cv2.bitwise_not(possible_bg_residual)
        )
        necro_texture_boost = cv2.bitwise_and(
            necro_texture_boost, cv2.bitwise_not(skin_exclude_mask)
        )
        # Viés para core + periferia (necrose pode cobrir toda a ferida)
        necro_texture_zone = cv2.bitwise_or(core_zone, peripheral_zone)
        necro_texture_boost = cv2.bitwise_and(necro_texture_boost, necro_texture_zone)
        masks["necrosis"] = cv2.bitwise_or(masks["necrosis"], necro_texture_boost)

        # Granulação: textura alta + vermelho dominante (mais restrito)
        red_channel = denoised_norm[:, :, 2]  # BGR → canal R
        green_channel = denoised_norm[:, :, 1]
        red_dominant = (
            (red_channel.astype(np.int16) - green_channel.astype(np.int16)) > 40
        ).astype(np.uint8) * 255
        # Granulação requer ALTA textura + vermelho forte
        gran_boost = cv2.bitwise_and(
            cv2.bitwise_and(red_dominant, wound_mask),
            (high_texture * 255).astype(np.uint8)
        )
        # Não adicionar granulação onde já tem necrose
        gran_boost = cv2.bitwise_and(gran_boost, cv2.bitwise_not(masks["necrosis"]))
        masks["granulation"] = cv2.bitwise_or(masks["granulation"], gran_boost)

        # â”€â”€ 9. Resolução de sobreposições — prioridade clínica â”€â”€â”€â”€â”€â”€â”€
        priority = ["necrosis", "slough", "granulation", "epithelialization"]
        used = np.zeros((h, w), dtype=np.uint8)
        for key in priority:
            masks[key] = cv2.bitwise_and(masks[key], cv2.bitwise_not(used))
            used = cv2.bitwise_or(used, masks[key])

        # â”€â”€ 10. Métricas e visualização â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        total = max(np.sum(wound_mask > 0), 1)
        pcts = {}
        for key in priority:
            pcts[key] = float(np.sum(masks[key] > 0) / total * 100)

        coverage_pct = min(sum(pcts.values()), 100.0)
        self._last_tissue_analysis_trace = {
            "coverage_pct": round(coverage_pct, 2),
            "unclassified_pct": round(max(0.0, 100.0 - coverage_pct), 2),
            "final_tissue_percentages": {
                key: round(value, 2) for key, value in pcts.items()
            },
            **adaptive_trace,
        }

        # Mapa de segmentação puro
        seg_map = np.zeros((h, w, 3), dtype=np.uint8)
        # Fundo fora da ROI
        seg_map[:] = (40, 40, 40)
        # Não-classificado dentro da ROI
        seg_map[wound_mask > 0] = (128, 128, 128)
        
        colors = {
            "necrosis": (30, 30, 60),
            "slough": (80, 220, 220),
            "granulation": (60, 60, 220),
            "epithelialization": (200, 180, 255),
        }
        for key, mask in masks.items():
            seg_map[mask > 0] = colors[key]

        # Overlay com imagem original e máscara semitransparente
        overlay = image.copy()
        mask_3d = np.stack([wound_mask]*3, axis=2)
        blended = cv2.addWeighted(seg_map, 0.5, overlay, 0.5, 0)
        overlay = np.where(mask_3d > 0, blended, overlay)

        # Contornos no overlay
        contours_roi, _ = cv2.findContours(
            wound_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )
        cv2.drawContours(overlay, contours_roi, -1, (0, 255, 0), 2)

        contours_peri, _ = cv2.findContours(
            core_zone, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )
        cv2.drawContours(overlay, contours_peri, -1, (255, 200, 100), 1)

        return pcts, seg_map, overlay

    # -------------------------------------------------------
    def _analyze_borders(
        self, image: np.ndarray, wound_mask: np.ndarray
    ) -> BorderAnalysis:
        """Analisa bordas e perilesão."""
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)

        # Expansão da máscara para pegar borda perilesional
        kernel_big = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (25, 25))
        expanded = cv2.dilate(wound_mask, kernel_big)
        peri_mask = cv2.bitwise_and(expanded, cv2.bitwise_not(wound_mask))

        peri_region = hsv[peri_mask > 0]

        # Maceração: pele esbranquiçada/amolecida ao redor (S baixo, V alto)
        maceration = False
        if len(peri_region) > 100:
            mean_s = np.mean(peri_region[:, 1])
            mean_v = np.mean(peri_region[:, 2])
            if mean_s < 40 and mean_v > 180:
                maceration = True

        # Inflamação: vermelhidão/calor ao redor (H baixo, S moderada+, V moderado+)
        inflammation = False
        if len(peri_region) > 100:
            red_mask = (peri_region[:, 0] < 15) | (peri_region[:, 0] > 165)
            sat_ok = peri_region[:, 1] > 60
            inflamed_ratio = np.sum(red_mask & sat_ok) / len(peri_region)
            if inflamed_ratio > 0.3:
                inflammation = True

        # Regularidade das bordas
        contours, _ = cv2.findContours(wound_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        regular = True
        if contours:
            largest = max(contours, key=cv2.contourArea)
            perimeter = cv2.arcLength(largest, True)
            area = cv2.contourArea(largest)
            if area > 0:
                circularity = 4 * np.pi * area / (perimeter ** 2)
                regular = circularity > 0.4

        desc_parts = []
        if maceration:
            desc_parts.append("Maceração perilesional presente (pele esbranquiçada)")
        if inflammation:
            desc_parts.append("Sinais de inflamação perilesional (eritema)")
        if not regular:
            desc_parts.append("Bordas irregulares/anfractuosas")
        if not desc_parts:
            desc_parts.append("Bordas sem alterações significativas")

        return BorderAnalysis(
            maceration=maceration,
            inflammation=inflammation,
            regular_borders=regular,
            description="; ".join(desc_parts) + ".",
        )

    # -------------------------------------------------------
    def _build_justification(
        self, dominant: TissueClassification, pcts: Dict[str, float]
    ) -> str:
        """Constrói justificativa clínica baseada no tecido predominante."""
        parts = [f"Classificação principal: {dominant.name} ({dominant.percentage:.1f}%)."]

        key_map = {
            "Necrose de Coagulação (Escara)": "necrosis",
            "Esfacelo (Fibrina)": "slough",
            "Tecido de Granulação": "granulation",
            "Epitelização": "epithelialization",
        }
        key = key_map.get(dominant.name, "")

        if key == "necrosis":
            parts.append(
                "Presença predominante de tecido escurecido (preto/marrom) aderido ao leito, "
                "consistente com necrose de coagulação. A coloração escura e a textura "
                "endurecida são características de morte celular por isquemia."
            )
        elif key == "slough":
            parts.append(
                "Presença predominante de tecido amarelado/esbranquiçado aderido ao leito, "
                "característico de esfacelo (fibrina). A consistência viscosa e a coloração "
                "indicam acúmulo de fibrina, leucócitos e restos celulares."
            )
        elif key == "granulation":
            parts.append(
                "Presença predominante de tecido vermelho vivo/brilhante com aspecto granulado, "
                "indicando processo de cicatrização ativo (fase proliferativa). "
                "O leito apresenta neovascularização compatível com tecido de granulação saudável."
            )
        elif key == "epithelialization":
            parts.append(
                "Presença predominante de tecido rosa claro/translúcido avançando das bordas, "
                "indicando epitelização em curso (fase de maturação). A migração de "
                "queratinócitos sugere evolução favorável da cicatrização."
            )

        # Menciona tecidos secundários relevantes
        secondaries = []
        for k, v in sorted(pcts.items(), key=lambda x: -x[1]):
            if k != key and v > 5:
                name = CLINICAL_TISSUES[k]["name"]
                secondaries.append(f"{name} ({v:.1f}%)")
        if secondaries:
            parts.append(f"Tecidos secundários: {', '.join(secondaries)}.")

        return " ".join(parts)

    # -------------------------------------------------------
    @staticmethod
    def _compute_health_score(pcts: Dict[str, float]) -> float:
        """Score de saúde baseado na composição tecidual.

        Critérios clínicos:
        - Granulação e epitelização são tecidos saudáveis (positivo)
        - Necrose é o pior indicador (penalidade forte)
        - Esfacelo indica desvitalização moderada
        - Tecido não classificado na ferida não conta como saudável
        """
        gran = max(0.0, float(pcts.get("granulation", 0.0)))
        epit = max(0.0, float(pcts.get("epithelialization", 0.0)))
        slough = max(0.0, float(pcts.get("slough", 0.0)))
        necro = max(0.0, float(pcts.get("necrosis", 0.0)))

        total_classified = gran + epit + slough + necro
        if total_classified < 5.0:
            return 45.0

        unclassified = max(0.0, 100.0 - total_classified)
        reparative_load = gran + (1.15 * epit)
        devitalized_load = (1.35 * necro) + (0.85 * slough)

        score = 55.0
        score += 0.55 * (reparative_load - devitalized_load)
        score -= 0.20 * unclassified

        return float(np.clip(score, 0.0, 100.0))


# ============================================================
# THREAD DE ANÁLISE (não trava a UI)
# ============================================================

# ============================================================
# 11. CLI E 12. FUNCAO MAIN()
# ============================================================

def process_image(image_path: Path, output_dir: Path, analyzer: ClinicalWoundAnalyzer, csv_data_list: list):
    logger.info(f"Processando imagem: {image_path.name}")
    
    img = cv2.imread(str(image_path))
    if img is None:
        raise ValueError(f"Não foi possível ler a imagem: {image_path}")
        
    start_t = time.time()
    
    # Executa a análise completa
    report = analyzer.analyze(img)
    
    processing_time = (time.time() - start_t) * 1000
    
    # 1. Copia ou Redimensiona Original
    h, w = img.shape[:2]
    # Se ja foi redimensionado pelo analyzer (maior que 1024), usaremos o report.original
    out_orig_path = output_dir / f"{image_path.stem}_original.jpg"
    cv2.imwrite(str(out_orig_path), report.original)
    
    # Inicializa dict de output
    out_dict = {
        "nome_arquivo": image_path.name,
        "ferida_valida": report.is_valid_wound,
        "tempo_processamento_ms": processing_time,
        "observacoes_tecnicas": report.rejection_reason if not report.is_valid_wound else "Ferida processada com sucesso via Pipeline Explicável CV.",
        "area_estimada_pixels": report.wound_area_px,
        "tecido_predominante": "N/A",
        "score_visual_tecidual": 0.0,
        "percentual_granulacao": 0.0,
        "percentual_necrose": 0.0,
        "percentual_esfacelo": 0.0,
        "percentual_epitelizacao": 0.0,
        "percentual_nao_classificado": 0.0,
        "soma_percentuais_tecidos": 0.0,
        "cobertura_classificacao_pct": 0.0,
        "trace_tecnico": {},
        "caminhos_arquivos_gerados": {
            "original": str(out_orig_path)
        },
        "aviso_clinico": "Análise assistiva/experimental para apoio, validação e discussão com especialista. Não substitui avaliação clínica, diagnóstico médico ou decisão terapêutica profissional."
    }
    
    if report.is_valid_wound:
        # Pega as mascaras geradas
        # 2. Mascara da ferida (ROI)
        roi_mask = report.segmentation_map  # Usa o tecido gerado ou mascara principal
        # Em ClinicalWoundAnalyzer, podemos n ter a mask exposta diretamente no objeto report
        # Entao extraimos da imagem de segmentação se precisar
        if report.roi and 'mask' in report.roi:
            mask_out = report.roi['mask']
        else:
            # Fallback pra encontrar a ROI apartir do original x overlay
            mask_out = np.zeros(report.original.shape[:2], dtype=np.uint8)
            if report.tissue_overlay is not None:
                mask_out = np.where(report.tissue_overlay != report.original, 255, 0).astype(np.uint8)[:,:,0]
        
        out_mask_path = output_dir / f"{image_path.stem}_roi_mask.png"
        cv2.imwrite(str(out_mask_path), mask_out)
        out_dict["caminhos_arquivos_gerados"]["mascara_roi"] = str(out_mask_path)
        
        # 3. Mapa de Tecidos
        if report.tissue_overlay is not None:
            out_tissue_path = output_dir / f"{image_path.stem}_tissue_map.png"
            cv2.imwrite(str(out_tissue_path), report.tissue_overlay)
            out_dict["caminhos_arquivos_gerados"]["mapa_tecidos"] = str(out_tissue_path)
            
        # 4. Overlay com contornos
        out_overlay_path = output_dir / f"{image_path.stem}_overlay.jpg"
        cv2.imwrite(str(out_overlay_path), report.tissue_overlay if report.tissue_overlay is not None else report.original)
        out_dict["caminhos_arquivos_gerados"]["overlay"] = str(out_overlay_path)
        
        maior_tecido = ""
        maior_pct = -1
        
        for t in report.tissues:
            pct = t.percentage
            if "Granula" in t.name:
                out_dict["percentual_granulacao"] = pct
            elif "Necrose" in t.name:
                out_dict["percentual_necrose"] = pct
            elif "Esfacelo" in t.name:
                out_dict["percentual_esfacelo"] = pct
            elif "Epitel" in t.name:
                out_dict["percentual_epitelizacao"] = pct
                
            if pct > maior_pct:
                maior_pct = pct
                maior_tecido = t.name
                
        out_dict["tecido_predominante"] = maior_tecido
        out_dict["score_visual_tecidual"] = report.health_score

        trace = report.tissue_analysis_trace or {}
        out_dict["percentual_nao_classificado"] = trace.get("unclassified_pct", 0.0)
        out_dict["cobertura_classificacao_pct"] = trace.get("coverage_pct", 0.0)
        out_dict["soma_percentuais_tecidos"] = trace.get("coverage_pct", 0.0)

        out_dict["trace_tecnico"] = {
            "area_roi_pixels": report.wound_area_px,
            "quantidade_componentes_roi": 1,
            "roi_bbox": report.roi.get("bbox", []) if report.roi else [],
            "cobertura_classificacao_pct": trace.get("coverage_pct", 0.0),
            "thresholds_usados": trace,
            "observacoes_roi": "ROI extraída combinando bounding boxes e morfologia matemática.",
            "observacoes_segmentacao": "Prioridade: Necrose > Esfacelo > Granulação > Epitelização."
        }

        # Status para CSV
        out_dict["status_processamento"] = "Sucesso"
    else:
        out_dict["status_processamento"] = "Falhou"

    # 5. Salva Relatorio JSON
    out_json = output_dir / f"{image_path.stem}_report.json"
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(out_dict, f, indent=4, ensure_ascii=False)
    out_dict["caminhos_arquivos_gerados"]["json"] = str(out_json)
        
    logger.info(f"Concluído: {image_path.name}")
    csv_data_list.append(out_dict)
    return True

def main():
    # ======================================================================
    # CONFIGURAÇÃO RÁPIDA (Altere aqui se não quiser usar linha de comando)
    # ======================================================================
    CAMINHO_DA_IMAGEM_OU_PASTA = "dataset/co2wounds-v2/imgs/IMG1000.jpg"
    PASTA_DE_SAIDA = "outputs"
    # ======================================================================
    
    # Se o usuario apenas clicou "Run" sem argumentos, abre janela para escolher a foto
    if len(sys.argv) == 1:
        try:
            import tkinter as tk
            from tkinter import filedialog
            root = tk.Tk()
            root.withdraw() # Oculta a janela principal
            root.attributes('-topmost', True) # Forca a janela a ficar na frente
            caminho_escolhido = filedialog.askopenfilename(
                title="HEAL+ | Selecione uma imagem de ferida para analisar",
                filetypes=[("Imagens", "*.jpg *.jpeg *.png *.webp *.tif *.tiff"), ("Todos", "*.*")]
            )
            if caminho_escolhido:
                CAMINHO_DA_IMAGEM_OU_PASTA = caminho_escolhido
        except Exception as e:
            logger.warning(f"Nao foi possivel abrir janela de selecao de arquivo: {e}")

    parser = argparse.ArgumentParser(description="HEAL+ / REDISUS Analisador de Feridas (Standalone)")
    parser.add_argument("--input", default=CAMINHO_DA_IMAGEM_OU_PASTA, help="Caminho para uma imagem ou pasta de imagens")
    parser.add_argument("--output", default=PASTA_DE_SAIDA, help="Pasta de destino para os resultados")
    parser.add_argument("--use-dl", action="store_true", help="Tentar usar o modelo Deep Learning opcional. Fara fallback automatico se falhar.")
    args = parser.parse_args()
    
    input_path = Path(args.input)
    output_path = Path(args.output)
    
    # Cria pasta de saída se nao existir
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Arquivo de log geral
    log_file = output_path / "processing_log.txt"
    file_handler = logging.FileHandler(str(log_file), encoding='utf-8')
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))
    logging.getLogger().addHandler(file_handler)
    
    logger.info("="*50)
    logger.info("Iniciando HEAL+ Standalone Analyzer")
    logger.info("="*50)
    
    # Initialize Core Analyzer
    logger.info("Inicializando ClinicalWoundAnalyzer (Pipeline CV Explicável)...")
    analyzer = ClinicalWoundAnalyzer()
        
    if args.use_dl:
        # Checa se os modelos estao carregados
        if analyzer._dl_available or analyzer._resnet_available or analyzer._ensemble_available:
            logger.info("Modelos de Deep Learning carregados e ativos.")
        else:
            logger.warning("Pipeline DL indisponível. Usando pipeline explicável de visão computacional.")
            print("Pipeline DL indisponível. Usando pipeline explicável de visão computacional.")
    
    valid_exts = {'.jpg', '.jpeg', '.png', '.webp', '.tif', '.tiff'}
    files_to_process = []
    
    if input_path.is_file():
        if input_path.suffix.lower() in valid_exts:
            files_to_process.append(input_path)
        else:
            logger.error(f"Extensao de arquivo nao suportada: {input_path}")
            print(f"Extensao de arquivo nao suportada: {input_path}")
            return
    elif input_path.is_dir():
        for file in input_path.iterdir():
            if file.is_file() and file.suffix.lower() in valid_exts:
                files_to_process.append(file)
    else:
        logger.error(f"Caminho de entrada invalido: {input_path}")
        print(f"Caminho de entrada invalido: {input_path}")
        return
        
    if not files_to_process:
        logger.warning("Nenhuma imagem valida encontrada para processamento.")
        return

    csv_data_list = []
    
    for img_file in files_to_process:
        try:
            process_image(img_file, output_path, analyzer, csv_data_list)
        except Exception as e:
            error_msg = f"Erro ao processar imagem {img_file.name}: {str(e)}"
            logger.error(error_msg)
            logger.error(traceback.format_exc())
            print(error_msg)
            
    # Salva CSV Consolidado
    csv_path = output_path / "resumo_resultados.csv"
    if csv_data_list:
        try:
            file_exists = csv_path.exists()
            with open(csv_path, mode='a', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=[
                    "nome_arquivo", "ferida_valida", "tecido_predominante",
                    "percentual_granulacao", "percentual_necrose",
                    "percentual_esfacelo", "percentual_epitelizacao",
                    "percentual_nao_classificado",
                    "area_estimada_pixels", "score_visual_tecidual", 
                    "tempo_processamento_ms", "status_processamento"
                ], extrasaction='ignore')
                if not file_exists:
                    writer.writeheader()
                for row in csv_data_list:
                    writer.writerow(row)
            logger.info(f"Arquivo consolidado criado/atualizado: {csv_path}")
            print(f"Arquivo consolidado criado/atualizado: {csv_path}")
        except Exception as e:
            logger.error(f"Erro ao salvar CSV consolidado: {str(e)}")
            
    logger.info("Processamento finalizado.")

if __name__ == "__main__":
    main()
