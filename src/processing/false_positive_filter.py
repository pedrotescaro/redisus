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
