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
