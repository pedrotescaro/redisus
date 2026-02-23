# -*- coding: utf-8 -*-
"""
===============================================================================
REDISUS - DETECTOR DE PARTE DO CORPO (BODY PART DETECTOR)
===============================================================================

Módulo para detecção automática da região anatômica nas imagens de feridas.

A localização anatômica é crucial para:
- Diagnóstico diferencial (ex: úlcera venosa → pernas, lesão por pressão → sacro)
- Ajuste de probabilidades na classificação etiológica
- Melhor interpretação clínica

Arquitetura:
- CNN leve (MobileNetV3-Small) para classificação de região anatômica
- Classes: perna, pé, braço, mão, tronco, sacro/glúteo, face, outro
- Treinamento com transfer learning

Autor: REDISUS Team
===============================================================================
"""

import cv2
import numpy as np
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from enum import Enum
from pathlib import Path
from loguru import logger

# MediaPipe-based detector (alta precisão para close-ups)
try:
    from .mediapipe_body_detector import MediaPipeBodyDetector
    _HAS_MEDIAPIPE_DETECTOR = True
except ImportError:
    _HAS_MEDIAPIPE_DETECTOR = False


class BodyRegion(Enum):
    """Regiões anatômicas detectáveis"""
    # Membros inferiores
    LOWER_LEG = "lower_leg"         # Perna (abaixo do joelho)
    UPPER_LEG = "upper_leg"         # Coxa
    FOOT = "foot"                   # Pé
    ANKLE = "ankle"                 # Tornozelo
    
    # Membros superiores
    FOREARM = "forearm"             # Antebraço
    UPPER_ARM = "upper_arm"         # Braço
    HAND = "hand"                   # Mão
    
    # Tronco
    ABDOMEN = "abdomen"             # Abdômen
    CHEST = "chest"                 # Tórax
    BACK = "back"                   # Costas
    
    # Regiões de pressão
    SACRUM = "sacrum"               # Sacro
    GLUTEAL = "gluteal"             # Glúteos
    HEEL = "heel"                   # Calcâneo
    TROCHANTER = "trochanter"       # Trocânter
    SCAPULA = "scapula"             # Escápula
    OCCIPUT = "occiput"             # Occipital
    
    # Face
    FACE = "face"                   # Face
    
    # Genérico
    UNKNOWN = "unknown"             # Não identificado


# Informações detalhadas de cada região
REGION_INFO = {
    BodyRegion.LOWER_LEG: {
        "name_pt": "Perna",
        "name_en": "Lower Leg",
        "description": "Região entre joelho e tornozelo",
        "common_wounds": ["venous_ulcer", "arterial_ulcer"],
        "pressure_point": False,
    },
    BodyRegion.UPPER_LEG: {
        "name_pt": "Coxa",
        "name_en": "Upper Leg/Thigh",
        "description": "Região entre quadril e joelho",
        "common_wounds": ["traumatic", "surgical"],
        "pressure_point": False,
    },
    BodyRegion.FOOT: {
        "name_pt": "Pé",
        "name_en": "Foot",
        "description": "Região plantar e dorsal do pé",
        "common_wounds": ["diabetic_foot", "pressure_injury"],
        "pressure_point": True,
    },
    BodyRegion.ANKLE: {
        "name_pt": "Tornozelo",
        "name_en": "Ankle",
        "description": "Região maleolar",
        "common_wounds": ["venous_ulcer", "arterial_ulcer"],
        "pressure_point": True,
    },
    BodyRegion.FOREARM: {
        "name_pt": "Antebraço",
        "name_en": "Forearm",
        "description": "Região entre cotovelo e punho",
        "common_wounds": ["traumatic", "burn"],
        "pressure_point": False,
    },
    BodyRegion.UPPER_ARM: {
        "name_pt": "Braço",
        "name_en": "Upper Arm",
        "description": "Região entre ombro e cotovelo",
        "common_wounds": ["traumatic", "surgical"],
        "pressure_point": False,
    },
    BodyRegion.HAND: {
        "name_pt": "Mão",
        "name_en": "Hand",
        "description": "Mão e dedos",
        "common_wounds": ["traumatic", "burn"],
        "pressure_point": False,
    },
    BodyRegion.ABDOMEN: {
        "name_pt": "Abdômen",
        "name_en": "Abdomen",
        "description": "Região abdominal",
        "common_wounds": ["surgical", "pressure_injury"],
        "pressure_point": False,
    },
    BodyRegion.CHEST: {
        "name_pt": "Tórax",
        "name_en": "Chest",
        "description": "Região torácica anterior",
        "common_wounds": ["surgical", "traumatic"],
        "pressure_point": False,
    },
    BodyRegion.BACK: {
        "name_pt": "Costas",
        "name_en": "Back",
        "description": "Região dorsal",
        "common_wounds": ["pressure_injury", "surgical"],
        "pressure_point": True,
    },
    BodyRegion.SACRUM: {
        "name_pt": "Sacro",
        "name_en": "Sacrum",
        "description": "Região sacral - principal ponto de pressão",
        "common_wounds": ["pressure_injury"],
        "pressure_point": True,
    },
    BodyRegion.GLUTEAL: {
        "name_pt": "Glúteos",
        "name_en": "Gluteal",
        "description": "Região glútea",
        "common_wounds": ["pressure_injury"],
        "pressure_point": True,
    },
    BodyRegion.HEEL: {
        "name_pt": "Calcâneo",
        "name_en": "Heel",
        "description": "Região do calcanhar - ponto de pressão",
        "common_wounds": ["pressure_injury", "diabetic_foot"],
        "pressure_point": True,
    },
    BodyRegion.TROCHANTER: {
        "name_pt": "Trocânter",
        "name_en": "Trochanter",
        "description": "Região trocantérica - lateral do quadril",
        "common_wounds": ["pressure_injury"],
        "pressure_point": True,
    },
    BodyRegion.SCAPULA: {
        "name_pt": "Escápula",
        "name_en": "Scapula",
        "description": "Região escapular",
        "common_wounds": ["pressure_injury"],
        "pressure_point": True,
    },
    BodyRegion.OCCIPUT: {
        "name_pt": "Occipital",
        "name_en": "Occiput",
        "description": "Região occipital da cabeça",
        "common_wounds": ["pressure_injury"],
        "pressure_point": True,
    },
    BodyRegion.FACE: {
        "name_pt": "Face",
        "name_en": "Face",
        "description": "Região facial",
        "common_wounds": ["traumatic", "burn"],
        "pressure_point": False,
    },
    BodyRegion.UNKNOWN: {
        "name_pt": "Não Identificado",
        "name_en": "Unknown",
        "description": "Região não identificada",
        "common_wounds": [],
        "pressure_point": False,
    },
}


# Mapeamento de região para probabilidades ajustadas de etiologia
# Usado para Bayesian adjustment da classificação
REGION_ETIOLOGY_PRIORS = {
    BodyRegion.LOWER_LEG: {
        "venous_ulcer": 0.45,
        "arterial_ulcer": 0.25,
        "diabetic_foot": 0.05,
        "pressure_injury": 0.05,
        "traumatic": 0.15,
        "surgical": 0.05,
    },
    BodyRegion.ANKLE: {
        "venous_ulcer": 0.50,
        "arterial_ulcer": 0.20,
        "diabetic_foot": 0.05,
        "pressure_injury": 0.10,
        "traumatic": 0.10,
        "surgical": 0.05,
    },
    BodyRegion.FOOT: {
        "venous_ulcer": 0.05,
        "arterial_ulcer": 0.15,
        "diabetic_foot": 0.45,
        "pressure_injury": 0.15,
        "traumatic": 0.15,
        "surgical": 0.05,
    },
    BodyRegion.HEEL: {
        "venous_ulcer": 0.02,
        "arterial_ulcer": 0.08,
        "diabetic_foot": 0.25,
        "pressure_injury": 0.55,
        "traumatic": 0.05,
        "surgical": 0.05,
    },
    BodyRegion.SACRUM: {
        "venous_ulcer": 0.01,
        "arterial_ulcer": 0.01,
        "diabetic_foot": 0.01,
        "pressure_injury": 0.90,
        "traumatic": 0.02,
        "surgical": 0.05,
    },
    BodyRegion.GLUTEAL: {
        "venous_ulcer": 0.01,
        "arterial_ulcer": 0.01,
        "diabetic_foot": 0.01,
        "pressure_injury": 0.85,
        "traumatic": 0.05,
        "surgical": 0.07,
    },
    BodyRegion.TROCHANTER: {
        "venous_ulcer": 0.01,
        "arterial_ulcer": 0.01,
        "diabetic_foot": 0.01,
        "pressure_injury": 0.88,
        "traumatic": 0.04,
        "surgical": 0.05,
    },
    BodyRegion.HAND: {
        "venous_ulcer": 0.02,
        "arterial_ulcer": 0.08,
        "diabetic_foot": 0.05,
        "pressure_injury": 0.05,
        "traumatic": 0.60,
        "surgical": 0.20,
    },
}


@dataclass
class BodyPartPrediction:
    """Resultado da detecção de parte do corpo"""
    region: BodyRegion
    confidence: float
    all_probabilities: Dict[str, float]
    region_info: Dict
    is_pressure_point: bool
    etiology_priors: Optional[Dict[str, float]] = None
    is_reliable: bool = True
    reliability_note: str = ""
    
    @property
    def name_pt(self) -> str:
        return self.region_info.get("name_pt", "Desconhecido")
    
    @property
    def name_en(self) -> str:
        return self.region_info.get("name_en", "Unknown")
    
    def to_dict(self) -> Dict:
        return {
            "region": self.region.value,
            "name_pt": self.name_pt,
            "name_en": self.name_en,
            "confidence": round(self.confidence, 3),
            "is_reliable": self.is_reliable,
            "reliability_note": self.reliability_note,
            "is_pressure_point": self.is_pressure_point,
            "common_wounds": self.region_info.get("common_wounds", []),
            "all_probabilities": {
                k: round(v, 3) for k, v in self.all_probabilities.items()
            },
            "etiology_priors": self.etiology_priors,
        }


class BodyPartDetector:
    """
    Detector de região anatômica usando CNN.
    
    Arquitetura:
    - Backbone: MobileNetV3-Small (eficiente para edge devices)
    - Input: 224x224 RGB
    - Output: 18 classes de região anatômica
    
    O detector pode funcionar em dois modos:
    1. Com modelo treinado (alta precisão)
    2. Modo heurístico (baseado em análise de cor e forma - fallback)
    
    Uso:
        detector = BodyPartDetector()
        detector.load_model("models/body_part_detector.onnx")
        
        result = detector.detect(wound_image)
        print(f"Região: {result.name_pt} ({result.confidence:.1%})")
    """
    
    # Classes do modelo
    CLASS_NAMES = [
        "lower_leg", "upper_leg", "foot", "ankle",
        "forearm", "upper_arm", "hand",
        "abdomen", "chest", "back",
        "sacrum", "gluteal", "heel", "trochanter", "scapula", "occiput",
        "face", "unknown"
    ]
    
    INPUT_SIZE = (224, 224)
    
    def __init__(
        self,
        model_path: Optional[str] = None,
        confidence_threshold: float = 0.5,
        use_heuristics: bool = True
    ):
        """
        Args:
            model_path: Caminho para modelo (ONNX ou PyTorch)
            confidence_threshold: Limiar de confiança
            use_heuristics: Se deve usar heurísticas quando modelo não disponível
        """
        self.model_path = model_path
        self.confidence_threshold = confidence_threshold
        self.use_heuristics = use_heuristics
        self.class_names = self.CLASS_NAMES.copy()
        
        self._session = None
        self._model = None
        self._is_loaded = False

        # MediaPipe detector (primário, funciona sem treino)
        self._mp_detector: Optional['MediaPipeBodyDetector'] = None
        if _HAS_MEDIAPIPE_DETECTOR:
            try:
                self._mp_detector = MediaPipeBodyDetector()
                if self._mp_detector.available:
                    logger.info("MediaPipe body detector disponível (primário)")
                else:
                    self._mp_detector = None
            except Exception as exc:
                logger.debug(f"MediaPipe body detector indisponível: {exc}")
                self._mp_detector = None
        
        if model_path:
            self.load_model(model_path)
    
    def load_model(self, model_path: str) -> bool:
        """
        Carrega modelo de detecção.
        
        Args:
            model_path: Caminho para o modelo
            
        Returns:
            True se carregou com sucesso
        """
        path = Path(model_path)
        self._load_metadata_for_model(path)
        
        if not path.exists():
            logger.warning(f"Modelo não encontrado: {path}")
            return False
        
        try:
            if path.suffix.lower() == ".onnx":
                import onnxruntime as ort
                providers = ['CUDAExecutionProvider', 'CPUExecutionProvider']
                self._session = ort.InferenceSession(str(path), providers=providers)
                self._is_loaded = True
                
            elif path.suffix.lower() in [".pt", ".pth"]:
                import torch
                device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
                self._model = torch.load(str(path), map_location=device, weights_only=False)
                self._model.eval()
                self._is_loaded = True
            
            logger.info(f"Modelo de detecção de parte do corpo carregado: {path.name}")
            return True
            
        except Exception as e:
            logger.error(f"Erro ao carregar modelo: {e}")
            return False

    def _load_metadata_for_model(self, model_path: Path):
        """Carrega metadata.json (se existir) para mapear classes do modelo."""
        metadata_candidates = [
            model_path.parent / "metadata.json",
            model_path.parent / "model_metadata.json",
        ]
        for meta_path in metadata_candidates:
            if not meta_path.exists():
                continue
            try:
                import json
                metadata = json.loads(meta_path.read_text(encoding="utf-8"))
                classes = metadata.get("classes") or metadata.get("class_names")
                if isinstance(classes, list) and classes:
                    self.class_names = [str(c) for c in classes]
                    logger.info(f"Classes carregadas do metadata: {len(self.class_names)}")
                return
            except Exception as exc:
                logger.warning(f"Falha ao ler metadata do modelo: {exc}")
    
    def detect(self, image: np.ndarray) -> BodyPartPrediction:
        """
        Detecta a região anatômica na imagem.

        Ordem de prioridade:
          1. MediaPipe (Hand/Face/Pose) — funciona sem treino, alta precisão
          2. Modelo CNN treinado
          3. Heurísticas de cor/forma (fallback)
        
        Args:
            image: Imagem BGR da ferida
            
        Returns:
            BodyPartPrediction com região detectada e confiança
        """
        # 1. Tenta MediaPipe primeiro (melhor para close-ups)
        mp_pred = self._detect_with_mediapipe(image)
        if mp_pred is not None and mp_pred.confidence >= 0.45:
            return mp_pred

        # 2. Tenta modelo CNN treinado
        if self._is_loaded:
            cnn_pred = self._detect_with_model(image)
            cnn_pred = self._apply_reliability_gate(cnn_pred)
            # Se CNN deu resultado confiável, usa ele
            if cnn_pred.is_reliable and cnn_pred.region != BodyRegion.UNKNOWN:
                return cnn_pred
            # Se MediaPipe deu algo (mesmo fraco), prefere MediaPipe
            if mp_pred is not None and mp_pred.region != BodyRegion.UNKNOWN:
                return mp_pred
            return cnn_pred

        # 3. Se MediaPipe achou algo (confiança baixa)
        if mp_pred is not None and mp_pred.region != BodyRegion.UNKNOWN:
            return mp_pred

        # 4. Fallback heurístico
        if self.use_heuristics:
            prediction = self._detect_heuristic(image)
            return self._apply_reliability_gate(prediction)

        return self._unknown_prediction()

    def _detect_with_mediapipe(self, image: np.ndarray) -> Optional[BodyPartPrediction]:
        """Detecção usando MediaPipe Hand/Face/Pose."""
        if self._mp_detector is None:
            return None

        try:
            region_name, confidence, all_probs = self._mp_detector.detect(image)

            if region_name == "unknown" or confidence < 0.15:
                return None

            # Mapeia string → BodyRegion enum
            region = (
                BodyRegion(region_name)
                if region_name in BodyRegion._value2member_map_
                else BodyRegion.UNKNOWN
            )
            region_info = REGION_INFO.get(region, REGION_INFO[BodyRegion.UNKNOWN])

            # Enriquece all_probs com nomes faltantes
            for name in self.class_names:
                if name not in all_probs:
                    all_probs[name] = 0.0

            return BodyPartPrediction(
                region=region,
                confidence=confidence,
                all_probabilities=all_probs,
                region_info=region_info,
                is_pressure_point=region_info.get("pressure_point", False),
                etiology_priors=REGION_ETIOLOGY_PRIORS.get(region),
                is_reliable=confidence >= 0.45,
                reliability_note=(
                    "Detectado via MediaPipe."
                    if confidence >= 0.45
                    else f"MediaPipe baixa confiança ({confidence:.0%})."
                ),
            )
        except Exception as e:
            logger.debug(f"MediaPipe detection erro: {e}")
            return None

    def _apply_reliability_gate(self, prediction: BodyPartPrediction) -> BodyPartPrediction:
        """Converte predições fracas em UNKNOWN para evitar falso rótulo anatômico."""
        probs = prediction.all_probabilities or {}
        sorted_probs = sorted(probs.values(), reverse=True)
        top1 = sorted_probs[0] if sorted_probs else 0.0
        top2 = sorted_probs[1] if len(sorted_probs) > 1 else 0.0
        margin = top1 - top2

        if prediction.region == BodyRegion.UNKNOWN:
            prediction.is_reliable = False
            if not prediction.reliability_note:
                prediction.reliability_note = "Região anatômica não identificada."
            return prediction

        low_conf = prediction.confidence < self.confidence_threshold
        low_margin = margin < 0.08

        if low_conf or low_margin:
            note = (
                f"Baixa confiabilidade (conf={prediction.confidence:.0%}, margem={margin:.0%}). "
                "Necessário modelo treinado específico de região anatômica."
            )
            return self._unknown_prediction(
                confidence=prediction.confidence,
                all_probabilities=prediction.all_probabilities,
                note=note,
            )

        prediction.is_reliable = True
        prediction.reliability_note = "Predição confiável."
        return prediction
    
    def _detect_with_model(self, image: np.ndarray) -> BodyPartPrediction:
        """Detecção usando modelo CNN."""
        # Pré-processamento
        input_tensor = self._preprocess(image)
        
        # Inferência
        if self._session is not None:
            input_name = self._session.get_inputs()[0].name
            outputs = self._session.run(None, {input_name: input_tensor})
            probs = outputs[0][0]
        else:
            import torch
            with torch.no_grad():
                tensor = torch.from_numpy(input_tensor)
                outputs = self._model(tensor)
                probs = torch.softmax(outputs, dim=1)[0].numpy()
        
        # Encontra classe com maior probabilidade
        class_idx = int(np.argmax(probs))
        confidence = float(probs[class_idx])
        
        # Monta resultado
        predicted_label = self.class_names[class_idx] if class_idx < len(self.class_names) else "unknown"
        region = BodyRegion(predicted_label) if predicted_label in BodyRegion._value2member_map_ else BodyRegion.UNKNOWN
        region_info = REGION_INFO.get(region, REGION_INFO[BodyRegion.UNKNOWN])
        
        all_probs = {
            self.class_names[i]: float(probs[i])
            for i in range(min(len(self.class_names), len(probs)))
        }
        
        etiology_priors = REGION_ETIOLOGY_PRIORS.get(region)
        
        return BodyPartPrediction(
            region=region,
            confidence=confidence,
            all_probabilities=all_probs,
            region_info=region_info,
            is_pressure_point=region_info.get("pressure_point", False),
            etiology_priors=etiology_priors,
        )
    
    def _detect_heuristic(self, image: np.ndarray) -> BodyPartPrediction:
        """
        Detecção heurística baseada em análise visual.
        
        Esta é uma fallback quando o modelo CNN não está disponível.
        Usa características como:
        - Proporção da imagem (aspect ratio)
        - Distribuição de tons de pele
        - Presença de características anatômicas
        """
        h, w = image.shape[:2]
        aspect_ratio = w / h
        
        # Análise de cor
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        
        # Detecta tons de pele
        lower_skin = np.array([0, 20, 70])
        upper_skin = np.array([20, 255, 255])
        skin_mask = cv2.inRange(hsv, lower_skin, upper_skin)
        skin_ratio = np.sum(skin_mask > 0) / (h * w)
        
        # Análise de forma/contornos
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, 50, 150)
        edge_density = np.sum(edges > 0) / (h * w)
        
        # Heurísticas simples baseadas em características
        probabilities = {name: 0.05 for name in self.class_names}
        
        # Imagens mais largas que altas → possível tronco
        if aspect_ratio > 1.3:
            probabilities["abdomen"] = 0.20
            probabilities["back"] = 0.15
            probabilities["chest"] = 0.15
        
        # Imagens mais altas que largas → possível perna/braço
        elif aspect_ratio < 0.8:
            probabilities["lower_leg"] = 0.25
            probabilities["forearm"] = 0.20
            probabilities["upper_leg"] = 0.15
        
        # Alta densidade de bordas → possível mão/pé (dedos)
        if edge_density > 0.1:
            probabilities["hand"] = 0.25
            probabilities["foot"] = 0.25
        
        # Baixa quantidade de pele visível → possível heel/sacro
        if skin_ratio < 0.4:
            probabilities["sacrum"] = 0.20
            probabilities["heel"] = 0.20
        
        # Normaliza probabilidades
        total = sum(probabilities.values())
        probabilities = {k: v / total for k, v in probabilities.items()}
        
        # Encontra mais provável
        best_class = max(probabilities, key=probabilities.get)
        confidence = probabilities[best_class]
        
        region = BodyRegion(best_class)
        region_info = REGION_INFO.get(region, REGION_INFO[BodyRegion.UNKNOWN])
        
        return BodyPartPrediction(
            region=region,
            confidence=confidence * 0.5,  # Penaliza por ser heurística
            all_probabilities=probabilities,
            region_info=region_info,
            is_pressure_point=region_info.get("pressure_point", False),
            etiology_priors=REGION_ETIOLOGY_PRIORS.get(region),
            is_reliable=False,
            reliability_note="Predição heurística (sem modelo treinado).",
        )
    
    def _preprocess(self, image: np.ndarray) -> np.ndarray:
        """Pré-processa imagem para inferência."""
        # Resize
        resized = cv2.resize(image, self.INPUT_SIZE)
        
        # BGR -> RGB
        rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
        
        # Normaliza para [0, 1]
        normalized = rgb.astype(np.float32) / 255.0
        
        # Normalização ImageNet
        mean = np.array([0.485, 0.456, 0.406])
        std = np.array([0.229, 0.224, 0.225])
        normalized = (normalized - mean) / std
        
        # Adiciona dimensão do batch e transpõe para NCHW
        tensor = np.transpose(normalized, (2, 0, 1))
        tensor = np.expand_dims(tensor, axis=0).astype(np.float32)
        
        return tensor
    
    def _unknown_prediction(
        self,
        confidence: float = 0.0,
        all_probabilities: Optional[Dict[str, float]] = None,
        note: str = ""
    ) -> BodyPartPrediction:
        """Retorna predição desconhecida."""
        return BodyPartPrediction(
            region=BodyRegion.UNKNOWN,
            confidence=confidence,
            all_probabilities=all_probabilities or {name: 0.0 for name in self.class_names},
            region_info=REGION_INFO[BodyRegion.UNKNOWN],
            is_pressure_point=False,
            etiology_priors=None,
            is_reliable=False,
            reliability_note=note or "Confiança insuficiente para rotular região anatômica.",
        )
    
    def adjust_etiology_probabilities(
        self,
        etiology_probs: Dict[str, float],
        body_part: BodyPartPrediction,
        weight: float = 0.3
    ) -> Dict[str, float]:
        """
        Ajusta probabilidades de etiologia com base na região anatômica.
        
        Usa ponderação Bayesiana para combinar probabilidades do classificador
        de etiologia com os priors da localização anatômica.
        
        Args:
            etiology_probs: Probabilidades do classificador de etiologia
            body_part: Resultado da detecção de parte do corpo
            weight: Peso dos priors anatômicos (0-1)
            
        Returns:
            Dict com probabilidades ajustadas
        """
        if body_part.etiology_priors is None or body_part.confidence < 0.4:
            return etiology_probs
        
        priors = body_part.etiology_priors
        adjusted = {}
        
        for etiology, prob in etiology_probs.items():
            prior = priors.get(etiology, 0.1)
            
            # Combinação ponderada
            adjusted[etiology] = (1 - weight) * prob + weight * prior
        
        # Normaliza
        total = sum(adjusted.values())
        if total > 0:
            adjusted = {k: v / total for k, v in adjusted.items()}
        
        return adjusted


def create_body_part_detector(
    model_path: Optional[str] = None
) -> BodyPartDetector:
    """
    Factory function para criar detector.
    
    Args:
        model_path: Caminho para modelo (opcional)
        
    Returns:
        BodyPartDetector configurado
    """
    # Procura modelo padrão
    default_paths = [
        "models/body_part_detector/body_part_detector.onnx",
        "models/body_part_detector/body_part_detector.pt",
        "models/body_part_detector/body_part_detector_full.pt",
        "models/body_part_detector.onnx",
        "models/body_part_detector.pt",
        "models/body_part_mobilenet.onnx",
    ]
    
    if model_path is None:
        for path in default_paths:
            if Path(path).exists():
                model_path = path
                break
    
    detector = BodyPartDetector(
        model_path=model_path,
        confidence_threshold=0.40,
        use_heuristics=True
    )
    if detector._mp_detector is not None:
        logger.info("Body part detector: MediaPipe (primário) + CNN (secundário)")
    elif detector._is_loaded:
        logger.info("Body part detector: CNN apenas (MediaPipe indisponível)")
    else:
        logger.info("Body part detector: heurístico apenas (sem modelo/MediaPipe)")
    return detector
