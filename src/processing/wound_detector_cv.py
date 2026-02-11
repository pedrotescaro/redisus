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
    YELLOW_LOWER = np.array([15, 60, 60])
    YELLOW_UPPER = np.array([35, 255, 255])
    
    # Tons escuros (necrose)
    DARK_LOWER = np.array([0, 0, 0])
    DARK_UPPER = np.array([180, 255, 50])
    
    # Tons rosados (granulação saudável)
    PINK_LOWER = np.array([0, 30, 100])
    PINK_UPPER = np.array([15, 150, 255])
    
    # Pele (para exclusão)
    SKIN_LOWER = np.array([0, 20, 70])
    SKIN_UPPER = np.array([25, 150, 255])


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
                    min_biological_score=0.25,
                    min_perilesional_score=0.15,
                    max_finger_score=0.55,
                    max_device_score=0.45
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
        
        # Escuro (necrose)
        mask_dark = cv2.inRange(hsv, ColorRanges.DARK_LOWER, ColorRanges.DARK_UPPER)
        
        # Rosa (granulação saudável)
        mask_pink = cv2.inRange(hsv, ColorRanges.PINK_LOWER, ColorRanges.PINK_UPPER)
        
        # Combina máscaras
        mask_wound = cv2.bitwise_or(mask_red, mask_yellow)
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
        
        # Entropia local - complexidade da textura
        # Usa histograma local
        entropy_map = np.zeros((h, w), dtype=np.float32)
        block_size = 16
        for y in range(0, h - block_size, block_size // 2):
            for x in range(0, w - block_size, block_size // 2):
                block = gray[y:y+block_size, x:x+block_size]
                hist = cv2.calcHist([block], [0], None, [32], [0, 256])
                hist = hist / (hist.sum() + 1e-6)
                entropy = -np.sum(hist * np.log2(hist + 1e-6))
                entropy_map[y:y+block_size, x:x+block_size] = entropy
        
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
        
        # Rosa/vermelho claro
        mask_pink = cv2.inRange(hsv, ColorRanges.PINK_LOWER, ColorRanges.PINK_UPPER)
        
        color_mask = cv2.bitwise_or(mask_red, mask_yellow)
        color_mask = cv2.bitwise_or(color_mask, mask_pink)
        color_score = color_mask.astype(np.float32) / 255.0
        
        # Suaviza mascara de cor
        color_score = cv2.GaussianBlur(color_score, (11, 11), 0)
        
        # 4. EXCLUSAO DE PELE SAUDAVEL
        # Detecta pele uniforme (sem textura) para excluir
        skin_lower = np.array([0, 20, 70])
        skin_upper = np.array([25, 150, 255])
        skin_mask = cv2.inRange(hsv, skin_lower, skin_upper)
        
        # Pele saudavel tem baixa variancia de textura
        smooth_skin = (texture_score < 0.2) & (skin_mask > 0)
        exclusion_mask = smooth_skin.astype(np.float32)
        exclusion_mask = cv2.GaussianBlur(exclusion_mask, (21, 21), 0)
        
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
        
        Reduz ruído e detecções intermitentes.
        """
        # Adiciona ao histórico
        self._detection_history.append(detections)
        if len(self._detection_history) > self._history_size:
            self._detection_history.pop(0)
            
        if len(self._detection_history) < 3:
            return detections
            
        # Para cada detecção atual, verifica consistência com histórico
        stabilized = []
        for det in detections:
            # Conta quantos frames tiveram detecção próxima
            consistent_count = 0
            for past_dets in self._detection_history[:-1]:
                for past_det in past_dets:
                    if self._iou(det.bbox, past_det.bbox) > 0.3:
                        consistent_count += 1
                        break
                        
            # Só mantém se consistente em múltiplos frames
            if consistent_count >= len(self._detection_history) // 2:
                # Aumenta confiança de detecções estáveis
                det.confidence = min(det.confidence * 1.2, 1.0)
                stabilized.append(det)
            elif det.confidence > 0.7:
                # Mantém detecções de alta confiança mesmo se novas
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
                    import tflite_runtime.interpreter as tflite
                except ImportError:
                    import tensorflow.lite as tflite
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
