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
