# -*- coding: utf-8 -*-
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
