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
        # Preto/marrom escuro — exclui H 80-140 (azul hospitalar/verde cirúrgico)
        "lower": [np.array([0, 0, 0]), np.array([140, 0, 0]),
                  np.array([5, 30, 15]),
                  np.array([0, 5, 10]), np.array([8, 15, 25])],
        "upper": [np.array([80, 255, 40]), np.array([180, 255, 40]),
                  np.array([30, 200, 70]),
                  np.array([180, 35, 60]), np.array([25, 150, 75])]
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
