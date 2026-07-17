# -*- coding: utf-8 -*-
"""Headless clinical wound analyzer shared by API and desktop runtime.

This module is a transitional extraction from heal_analyzer.py. It keeps the
analysis engine importable without PyQt6 so backend code can run headless.
"""

from __future__ import annotations

import logging
import os
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
from src.processing.wound_detector_cv import WoundDetectorCV, DetectionMethod
from src.processing.tissue_analyzer import TissueAnalyzerCV, TissueType, TISSUE_COLORS
from src.processing.wound_classifier_cv import WoundClassifierCV

try:
    from src.processing.wound_segmentation_dl import WoundSegmentationPredictor
    HAS_WOUND_SEGMENTATION_DL = True
except ImportError:
    HAS_WOUND_SEGMENTATION_DL = False

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
    from src.processing.image_enhancer import (
        ImageEnhancer, LightingAnalysis, LightingCondition,
        ContrastAnalysis, create_medical_enhancer
    )
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
    wound_segmentation: Optional[Dict] = None

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

        self._wound_segmenter = None
        self._wound_segmenter_status: Dict[str, Any] = {
            "available": False,
            "source": "classical_cv_or_manual_roi",
            "reason": "not_enabled",
        }
        self._load_wound_segmenter()

        # Classificador ResNet50 de dois estágios (do notebook)
        self._resnet_classifier = None
        self._resnet_available = False
        self._load_resnet_classifier()

        # Ensemble Multi-Modelo (camada adicional de IA pré-treinada)
        self._ensemble = None
        self._ensemble_available = False
        self._last_tissue_analysis_trace = None
        self._load_ensemble()

    def _load_wound_segmenter(self) -> None:
        """Carrega o modelo de pesquisa somente com habilitacao explicita."""

        if not HAS_WOUND_SEGMENTATION_DL:
            self._wound_segmenter_status["reason"] = "module_unavailable"
            return
        enabled = os.getenv("HEAL_ENABLE_EXPERIMENTAL_WOUND_SEGMENTER", "").strip().lower()
        if enabled not in {"1", "true", "yes", "on"}:
            return
        checkpoint = Path(
            os.getenv(
                "HEAL_WOUND_SEGMENTATION_CHECKPOINT",
                str(LEGACY_ROOT / "models" / "wound_segmentation" / "best_small_unet.pt"),
            )
        )
        allow_research = os.getenv("HEAL_ALLOW_NONCOMMERCIAL_RESEARCH_MODEL", "").strip().lower() in {
            "1", "true", "yes", "on"
        }
        try:
            self._wound_segmenter = WoundSegmentationPredictor(
                checkpoint,
                allow_non_commercial_research=allow_research,
            )
            self._wound_segmenter_status = {
                "available": True,
                "source": "deep_learning",
                "checkpoint": str(checkpoint),
                "model_version": self._wound_segmenter.model_version,
                "clinical_status": self._wound_segmenter.clinical_status,
                "license_scope": self._wound_segmenter.license_scope,
            }
        except Exception as exc:
            self._wound_segmenter = None
            self._wound_segmenter_status = {
                "available": False,
                "source": "classical_cv_or_manual_roi",
                "reason": type(exc).__name__,
                "detail": str(exc),
                "checkpoint": str(checkpoint),
            }

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

        report.wound_segmentation = dict(self._wound_segmenter_status)
        report.wound_segmentation["initial_mask_source"] = (
            "manual_roi" if manual_roi_applied else "classical_cv"
        )
        report.wound_segmentation["applied_to_analysis"] = False
        if self._wound_segmenter is not None:
            try:
                prediction = self._wound_segmenter.predict(
                    image,
                    roi_mask=wound_mask if manual_roi_applied else None,
                )
                report.wound_segmentation.update(prediction.metadata())
                if prediction.accepted:
                    wound_mask = prediction.mask
                    report.wound_segmentation["applied_to_analysis"] = True
                    report.wound_segmentation["final_mask_source"] = "deep_learning"
                    if not manual_roi_applied:
                        detections = self._detections_from_mask(wound_mask)
                else:
                    report.wound_segmentation["final_mask_source"] = (
                        "manual_roi" if manual_roi_applied else "classical_cv"
                    )
                    report.wound_segmentation["fallback_reason"] = prediction.reason
            except Exception as exc:
                report.wound_segmentation.update({
                    "accepted": False,
                    "final_mask_source": "manual_roi" if manual_roi_applied else "classical_cv",
                    "fallback_reason": "runtime_error",
                    "runtime_error": str(exc),
                })
        else:
            report.wound_segmentation["final_mask_source"] = (
                "manual_roi" if manual_roi_applied else "classical_cv"
            )

        # 3.2/3.3 A ROI manual é autoritativa: não subtrai pixels internos por
        # cor, pois esfacelo cinza/oliva e necrose podem parecer fundo. A limpeza
        # automática permanece apenas quando a própria pipeline detectou a ROI.
        if not manual_roi_applied:
            wound_mask = self._exclude_surgical_background(image, wound_mask)
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
            image,
            wound_mask,
            peripheral_zone,
            core_zone,
            outer_ring,
            manual_roi_applied=manual_roi_applied,
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

        Pipeline:
        1. Inicializa com bounding boxes das detecções
        2. Segmenta por cor dentro de cada bbox (exclui pele sã, fundo)
        3. Extrai contorno externo (perímetro da lesão)
        4. Preenche contorno para criar máscara binária precisa

        Resultado: máscara onde 255 = leito da ferida, 0 = fora.
        """
        h, w = image.shape[:2]
        wound_mask = np.zeros((h, w), dtype=np.uint8)

        if not detections:
            # Close-up: assume imagem inteira, mas tenta segmentar
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

            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
            roi_mask = cv2.morphologyEx(roi_mask, cv2.MORPH_CLOSE, kernel, iterations=2)
            roi_mask = cv2.morphologyEx(roi_mask, cv2.MORPH_OPEN, kernel, iterations=1)

            roi_filled = np.zeros_like(roi_mask)
            contours, _ = cv2.findContours(
                roi_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
            )
            if contours:
                min_contour_area = (rx2 - rx1) * (ry2 - ry1) * 0.02
                for cnt in contours:
                    if cv2.contourArea(cnt) >= min_contour_area:
                        cv2.drawContours(roi_filled, [cnt], -1, 255, cv2.FILLED)

            return roi_filled

        for det in detections:
            x1, y1, x2, y2 = det.bbox
            # Margem de segurança (5% do bbox)
            margin_x = int((x2 - x1) * 0.05)
            margin_y = int((y2 - y1) * 0.05)
            rx1 = max(0, x1 - margin_x)
            ry1 = max(0, y1 - margin_y)
            rx2 = min(w, x2 + margin_x)
            ry2 = min(h, y2 + margin_y)

            roi_filled = build_roi_mask(rx1, ry1, rx2, ry2)

            # Se segmentação capturou muito pouco, fallback para bbox
            roi_area = np.sum(roi_filled > 0)
            bbox_area = (rx2 - rx1) * (ry2 - ry1)
            if roi_area < bbox_area * 0.10:
                wound_mask[y1:y2, x1:x2] = 255
            else:
                wound_mask[ry1:ry2, rx1:rx2] = cv2.bitwise_or(
                    wound_mask[ry1:ry2, rx1:rx2], roi_filled
                )

        if len(detections) >= 2:
            x1 = max(0, min(det.bbox[0] for det in detections))
            y1 = max(0, min(det.bbox[1] for det in detections))
            x2 = min(w, max(det.bbox[2] for det in detections))
            y2 = min(h, max(det.bbox[3] for det in detections))
            merged_filled = build_roi_mask(x1, y1, x2, y2)
            merged_area = int(np.sum(merged_filled > 0))
            current_roi_area = int(np.sum(wound_mask > 0))
            merged_bbox_area = max((x2 - x1) * (y2 - y1), 1)
            if (
                merged_area > max(int(current_roi_area * 1.15), 1200)
                and merged_area < int(merged_bbox_area * 0.92)
            ):
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
        manual_roi_applied: bool = False,
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
        # Dentro de uma ROI manual confirmada, cinza/oliva pode ser tecido da
        # ferida. Não o remove como lençol/fundo; apenas a ROI automática usa
        # essa exclusão cromática.
        _not_drape = (
            np.full((h, w), 255, dtype=np.uint8)
            if manual_roi_applied
            else cv2.bitwise_not(_drape)
        )

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

        # Mapa de segmentação colorido. Fora da ROI fica preto; pixels internos
        # sem evidência suficiente recebem azul-ardósia para tornar a incerteza
        # visível, em vez de parecer que a região não foi processada.
        seg_map = np.zeros((h, w, 3), dtype=np.uint8)
        seg_map[wound_mask > 0] = (145, 92, 48)
        colors = {
            "necrosis": (30, 30, 60),
            "slough": (80, 220, 220),
            "granulation": (60, 60, 220),
            "epithelialization": (200, 180, 255),
        }
        for key, mask in masks.items():
            seg_map[mask > 0] = colors[key]

        # Desenha contorno da wound_mask (perímetro da ROI) no overlay
        overlay = image.copy()
        blended_roi = cv2.addWeighted(seg_map, 0.45, image, 0.55, 0)
        overlay[wound_mask > 0] = blended_roi[wound_mask > 0]

        # Contorno do perímetro da ferida (verde, 2px)
        contours_roi, _ = cv2.findContours(
            wound_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )
        cv2.drawContours(overlay, contours_roi, -1, (0, 255, 0), 2)

        # Contorno da zona periférica (azul claro, 1px) para referência
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
