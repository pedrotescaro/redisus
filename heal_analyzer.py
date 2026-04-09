# -*- coding: utf-8 -*-
"""
HEAL+ / REDISUS — Analisador Clínico de Feridas v3.0 (Desktop PyQt6)
=====================================================================

Aplicação especialista em Estomaterapia com Visão Computacional + IA.

Taxonomia clínica rigorosa:
  1. Necrose de Coagulação (Escara)  — preto/marrom, endurecido, seco ou úmido
  2. Esfacelo (Fibrina)              — amarelo/branco, viscoso ou fibroso
  3. Tecido de Granulação             — vermelho brilhante, úmido, granulado
  4. Epitelização                     — rosa claro/translúcido, avança das bordas

Classificação Etiológica (ResNet50 Two-Stage):
  Estágio 1: Normal vs. Ferida (classificação binária)
  Estágio 2: Tipo de Ferida (Diabética, Pressão, Venosa)
  Explicabilidade: Grad-CAM sobre layer4 do ResNet50

Pipeline v3:
  Imagem → Validação → Detecção → ROI Contorno → Zonas (Periferia/Core)
        → Segmentação Multi-Espaço (HSV+LAB) restrita à ROI
        → Gradiente de Borda (Scharr) → Epitelização Periférica
        → Análise de Textura → Classificação DL (EfficientNet + TTA)
        → ResNet50 Two-Stage (Normal/Ferida + Tipo) com TTA 4-flip
        → Grad-CAM (explicabilidade)
        → Análise de Bordas → Laudo Clínico

Melhorias v3 vs v2:
  - Máscara ROI por contorno (não mais bounding box retangular)
  - Zonas espaciais: periferia vs. core vs. anel externo
  - Detecção de epitelização por gradiente na borda (Scharr)
  - Classificação espacial de background (variância + crominância + conectividade)
    separa fundo de câmera de tecido necrótico por contexto espacial
  - Necrose priorizada por luminância: pixels V < 50 dentro do perímetro
    anatômico segmentado são tratados como necrose de alta confiança
  - Esfacelo restrito ao core; epitelização à periferia
  - Distance transform para peso espacial

Melhorias v2 vs v1:
  - Segmentação multi-espaço de cor (HSV 60% + LAB 40%)
  - Refinamento por textura (variância local, LBP)
  - CLAHE para normalização de iluminação
  - Integração com modelo DL (EfficientNetB3, TTA 4x flips)
  - Intervalos HSV/LAB clínicos recalibrados
  - Classes consolidadas (24 → 10 categorias significativas)

Uso:
    python heal_analyzer.py
"""
import sys
import os
import io
import time
import logging
from pathlib import Path
from typing import Dict, Optional, Tuple, List
from dataclasses import dataclass, field

# Força o console do Windows a aceitar UTF-8
try:
    if sys.stdout and sys.stdout.encoding != 'utf-8':
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    if sys.stderr and sys.stderr.encoding != 'utf-8':
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
except Exception:
    pass

# Import torch BEFORE cv2 to avoid DLL conflicts on Windows
try:
    import torch
    from torchvision import transforms as _tv_transforms
    _TORCH_AVAILABLE = True
except ImportError:
    _TORCH_AVAILABLE = False

import cv2
import numpy as np

# PIL para renderizar texto com UTF-8/acentos (cv2.putText não suporta)
try:
    from PIL import Image, ImageDraw, ImageFont
    _PIL_AVAILABLE = True
except ImportError:
    _PIL_AVAILABLE = False

# Path setup
sys.path.insert(0, str(Path(__file__).resolve().parent))

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QFileDialog, QScrollArea, QFrame,
    QProgressBar, QSplitter, QGroupBox, QTextEdit,
    QTabWidget, QComboBox,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QImage, QPixmap, QFont, QColor, QPalette

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
from src.processing.roi_segmentation import ROISegmenter
from src.monitoring.wound_progression import (
    WoundProgressionResult,
    analyze_wound_photo_progression,
)

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
    "venous_arterial_ulcers": {0: 0.6, 1: 0.4},
}


# ============================================================
# TAXONOMIA CLINICA - Estomaterapia
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
class ModelPrediction:
    class_name: str
    display_name: str
    confidence: float
    top3: List[Dict[str, float]] = field(default_factory=list)
    probabilities: Dict[str, float] = field(default_factory=dict)
    redisus_probs: Dict[int, float] = field(default_factory=dict)
    redisus_supported_mass: float = 0.0

@dataclass
class AIPredictions:
    dl: Optional[ModelPrediction] = None
    resnet: Optional[Dict] = None
    ensemble: Optional[Dict] = None

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

    # Classificação ResNet50 Grad-CAM (se disponível)
    grad_cam_overlay: Optional[np.ndarray] = None

    # Escalas clínicas (PUSH, BWAT)
    push_score: Optional[Dict] = None
    bwat_score: Optional[Dict] = None

    # Imagens processadas e análises adicionais
    lighting_analysis: Optional[Dict] = None
    image_corrections: Optional[Dict] = None
    body_part: Optional[Dict] = None
    wound_zones: Optional[Dict] = None

    # Agrupamento de predições de IA
    ai_predictions: Optional[AIPredictions] = None

    # Imagens processadas
    original: Optional[np.ndarray] = None
    detection_overlay: Optional[np.ndarray] = None
    segmentation_map: Optional[np.ndarray] = None
    tissue_overlay: Optional[np.ndarray] = None
    tissue_analysis_trace: Optional[Dict] = None

    @property
    def dl_prediction(self):
        return self.ai_predictions.dl.__dict__ if self.ai_predictions and self.ai_predictions.dl else None

    @property
    def resnet_prediction(self):
        return self.ai_predictions.resnet if self.ai_predictions else None

    @property
    def ensemble_classification(self):
        return self.ai_predictions.ensemble.get("classification") if self.ai_predictions and self.ai_predictions.ensemble else None

    @property
    def ensemble_agreement(self):
        return self.ai_predictions.ensemble.get("agreement") if self.ai_predictions and self.ai_predictions.ensemble else None

    @property
    def ensemble_infection(self):
        return self.ai_predictions.ensemble.get("infection") if self.ai_predictions and self.ai_predictions.ensemble else None

    @property
    def ensemble_severity(self):
        return self.ai_predictions.ensemble.get("severity") if self.ai_predictions and self.ai_predictions.ensemble else None

    @property
    def ensemble_models_loaded(self):
        return self.ai_predictions.ensemble.get("models_loaded") if self.ai_predictions and self.ai_predictions.ensemble else None


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
# INTERVALOS CLINICOS REFINADOS v2 - Multi-espaco de cor
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
        self.roi_segmenter = ROISegmenter()
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

    def _safe_load(self, name: str, loader):
        try:
            result = loader()
            if result:
                logger.info(f"[HEAL+] {name} carregado com sucesso")
            return result, True
        except Exception as e:
            logger.exception(f"[HEAL+] Falha ao carregar {name}: {e}")
            return None, False

    def _load_resnet_classifier(self):
        """Carrega o classificador ResNet50 de dois estágios."""
        if not HAS_RESNET_CLASSIFIER:
            logger.info("[HEAL+] Módulo ResNet50 não disponível")
            return
        try:
            self._resnet_classifier = create_two_stage_classifier()
            self._resnet_available = self._resnet_classifier.available
            if self._resnet_available:
                status = self._resnet_classifier.get_status()
                logger.info(f"[HEAL+] ResNet50 Two-Stage: S1={status['stage1_available']}, S2={status['stage2_available']} ({status['device']})")
            else:
                logger.info("[HEAL+] ResNet50: Modelos não encontrados (classificação por heurística)")
        except Exception as e:
            logger.exception(f"[HEAL+] Erro ao carregar ResNet50: {e}")
            self._resnet_available = False

    def _load_dl_model(self):
        """Tenta carregar modelo DL treinado (PyTorch) para classificação."""
        # PyTorch model paths (traced/TorchScript preferred - self-contained)
        model_paths = [
            Path(__file__).parent / "models" / "wound_classifier_v2" / "wound_classifier_v2_traced.pt",
            Path(__file__).parent / "models" / "wound_classifier_v2" / "wound_classifier_v2_full.pt",
            Path(__file__).parent / "models" / "wound_classifier_v2" / "wound_classifier_v2.pt",
        ]
        meta_paths = [
            Path(__file__).parent / "models" / "wound_classifier_v2" / "model_metadata_v2.json",
            Path(__file__).parent / "models" / "wound_classifier" / "model_metadata.json",
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
                    logger.info(f"[HEAL+] Modelo DL PyTorch carregado: {mp.name}")
                    break
                except Exception as e:
                    logger.exception(f"[HEAL+] Erro DL ({mp.name}): {e}")

        for mp in meta_paths:
            if mp.exists():
                try:
                    import json
                    with open(mp, encoding='utf-8') as f:
                        self._dl_metadata = json.load(f)
                    logger.info(f"[HEAL+] Metadados: {mp.name}")
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
            self._ensemble_available = True
            loaded = sum(1 for v in status.values() if v)
            logger.info(f"[HEAL+] Ensemble multi-modelo: {loaded}/3 modelos ({status})")
        except Exception as e:
            logger.info(f"[HEAL+] Ensemble indisponível: {e}")
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
            logger.info(f"[HEAL+] Ensemble prediction error: {e}")
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

    def _predict_dl(self, image: np.ndarray) -> Optional[ModelPrediction]:
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

            probabilities = {class_names[i]: float(avg_pred[i]) for i in range(len(class_names)) if i < len(avg_pred)}
            redisus_probs, supported_mass = self._map_classifier_probs_to_redisus(probabilities)
            return ModelPrediction(
                class_name=class_name,
                display_name=display_name,
                confidence=confidence,
                top3=top3,
                probabilities=probabilities,
                redisus_probs=redisus_probs or {},
                redisus_supported_mass=float(supported_mass),
            )
        except Exception as e:
            logger.exception(f"[HEAL+] Erro predicao DL: {e}")
            return None

    # -------------------------------------------------------
    def _prepare_input(self, image: np.ndarray, report: ClinicalReport) -> np.ndarray:
        h, w = image.shape[:2]
        if max(h, w) > 1024:
            scale = 1024 / max(h, w)
            image = cv2.resize(image, (int(w * scale), int(h * scale)))

        if self.image_enhancer is not None:
            try:
                lighting = self.image_enhancer.analyze_lighting(image)
                report.lighting_analysis = lighting.to_dict()
                if lighting.corrections_needed:
                    image, corrections = self.image_enhancer.auto_correct(image, lighting)
                    report.image_corrections = corrections
            except Exception as e:
                logger.exception(f"[HEAL+] Erro análise de iluminação: {e}")

        if self.body_detector is not None:
            try:
                body_part = self.body_detector.detect(image)
                report.body_part = body_part.to_dict()
            except Exception as e:
                logger.exception(f"[HEAL+] Erro detecção parte do corpo: {e}")

        return image

    def _detect_wound_region(self, image: np.ndarray):
        detections = self.detector.detect(image)

        wound_mask = self.roi_segmenter.create_wound_roi_mask(image, detections)
        wound_mask = self.roi_segmenter.exclude_surgical_background(image, wound_mask)

        background_mask = self.roi_segmenter.create_background_mask_spatial(image, wound_mask)
        wound_mask_clean = cv2.bitwise_and(wound_mask, cv2.bitwise_not(background_mask))

        if np.sum(wound_mask > 0) > 0:
            cleaned_ratio = np.sum(wound_mask_clean > 0) / np.sum(wound_mask > 0)
            if cleaned_ratio > 0.05:
                wound_mask = wound_mask_clean

        return detections, wound_mask

    def _fill_ai_predictions(self, report: ClinicalReport, image: np.ndarray, detections: list, wound_mask: np.ndarray):
        ai_preds = AIPredictions()
        
        dl_result = self._predict_dl(image)
        if dl_result:
            ai_preds.dl = dl_result

        resnet_result = self._predict_resnet(image)
        if resnet_result:
            ai_preds.resnet = resnet_result
            if isinstance(resnet_result, dict) and resnet_result.get('grad_cam_overlay') is not None:
                report.grad_cam_overlay = resnet_result.pop('grad_cam_overlay')

        dl_probs = None
        if dl_result and hasattr(dl_result, 'probabilities'):
            if getattr(dl_result, "redisus_supported_mass", 0.0) >= 0.40:
                dl_probs = getattr(dl_result, "redisus_probs", None)
            
        ensemble_result = self._predict_ensemble(
            image, detections, dl_probs=dl_probs, wound_mask=wound_mask,
        )
        if ensemble_result:
            ai_preds.ensemble = ensemble_result
            
        report.ai_predictions = ai_preds

    def analyze(self, image: np.ndarray) -> ClinicalReport:
        """Pipeline completo de análise clínica."""
        t0 = time.perf_counter()
        report = ClinicalReport(is_valid_wound=True)
        report.original = image.copy()

        try:
            image = self._prepare_input(image, report)

            if not self._validate_wound_image(image):
                report.is_valid_wound = False
                report.rejection_reason = (
                    "Input Inválido — A imagem fornecida não apresenta características "
                    "compatíveis com ferida cutânea humana."
                )
                return report

            detections, wound_mask = self._detect_wound_region(image)
            report.wound_area_px = int(np.sum(wound_mask > 0))

            peripheral_zone, core_zone, outer_ring = self.roi_segmenter.create_zone_masks(wound_mask)
            report.wound_zones = {
                "peripheral_area_px": int(np.sum(peripheral_zone > 0)),
                "core_area_px": int(np.sum(core_zone > 0)),
                "outer_ring_area_px": int(np.sum(outer_ring > 0)),
                "border_width_adaptive": True,
            }

            det_overlay = image.copy()
            for det in detections:
                x1, y1, x2, y2 = det.bbox
                cv2.rectangle(det_overlay, (x1, y1), (x2, y2), (0, 255, 0), 2)
                cv2.putText(det_overlay,
                            f"Ferida {det.confidence:.0%}",
                            (x1, y1 - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 0), 1)
            report.detection_overlay = det_overlay

            tissue_pcts, seg_map, tissue_overlay = self._segment_clinical_v3(
                image, wound_mask, peripheral_zone, core_zone, outer_ring
            )
            report.segmentation_map = seg_map
            report.tissue_overlay = tissue_overlay
            report.tissue_analysis_trace = dict(self._last_tissue_analysis_trace or {})

            for key in ["necrosis", "slough", "granulation", "epithelialization"]:
                pct = tissue_pcts.get(key, 0.0)
                info = CLINICAL_TISSUES[key]
                report.tissues.append(TissueClassification(
                    name=info["name"], name_en=info["name_en"], percentage=pct,
                    color_bgr=info["color_bgr"], color_hex=info["color_hex"],
                    description=info["description"], clinical_action=info["clinical_action"],
                ))

            dominant = max(report.tissues, key=lambda t: t.percentage)
            report.primary_tissue = dominant.name
            report.primary_justification = self._build_justification(dominant, tissue_pcts)

            report.border_analysis = self._analyze_borders(image, wound_mask)
            report.health_score = self._compute_health_score(tissue_pcts)

            if HAS_CLINICAL_SCALES:
                try:
                    border_dict = None
                    if report.border_analysis:
                        border_dict = {
                            "maceration": report.border_analysis.maceration,
                            "inflammation": report.border_analysis.inflammation,
                            "regular_borders": report.border_analysis.regular_borders,
                        }
                    
                    push = ScaleCalculator.calculate_push_from_analysis(
                        tissue_percentages=tissue_pcts, wound_area_px=report.wound_area_px
                    )
                    report.push_score = push.to_dict()
                    
                    bwat = ScaleCalculator.calculate_bwat_from_analysis(
                        tissue_percentages=tissue_pcts, wound_area_px=report.wound_area_px,
                        border_analysis=border_dict
                    )
                    report.bwat_score = bwat.to_dict()
                except Exception as e:
                    logger.exception(f"[HEAL+] Erro ao calcular escalas clínicas: {e}")

            self._fill_ai_predictions(report, image, detections, wound_mask)

            return report

        except Exception as e:
            logger.exception(f"[HEAL+] Erro no pipeline principal: {e}")
            report.is_valid_wound = False
            report.rejection_reason = "Erro interno durante a análise."
            return report

        finally:
            report.processing_time_ms = (time.perf_counter() - t0) * 1000

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
            logger.exception(f"[HEAL+] Erro ResNet50: {e}")
            return None

    # -------------------------------------------------------

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



        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)

        for det in detections:
            x1, y1, x2, y2 = det.bbox
            # Margem de segurança (5% do bbox)
            margin_x = int((x2 - x1) * 0.05)
            margin_y = int((y2 - y1) * 0.05)
            rx1 = max(0, x1 - margin_x)
            ry1 = max(0, y1 - margin_y)
            rx2 = min(w, x2 + margin_x)
            ry2 = min(h, y2 + margin_y)

            roi_hsv = hsv[ry1:ry2, rx1:rx2]

            # Máscara de cores compatíveis com ferida (não-pele-sã, não-fundo)
            wound_colors = np.zeros(roi_hsv.shape[:2], dtype=np.uint8)

            # Vermelho/rosa (granulação, sangue, inflamação)
            wound_colors = cv2.bitwise_or(wound_colors, cv2.inRange(
                roi_hsv, np.array([0, 40, 40]), np.array([15, 255, 255])))
            wound_colors = cv2.bitwise_or(wound_colors, cv2.inRange(
                roi_hsv, np.array([155, 40, 40]), np.array([180, 255, 255])))
            # Amarelo (esfacelo/fibrina)
            wound_colors = cv2.bitwise_or(wound_colors, cv2.inRange(
                roi_hsv, np.array([12, 30, 100]), np.array([45, 255, 255])))
            # Escuro (necrose)
            wound_colors = cv2.bitwise_or(wound_colors, cv2.inRange(
                roi_hsv, np.array([0, 0, 0]), np.array([180, 255, 70])))
            # Rosa (epitelização)
            wound_colors = cv2.bitwise_or(wound_colors, cv2.inRange(
                roi_hsv, np.array([0, 8, 160]), np.array([20, 80, 255])))
            wound_colors = cv2.bitwise_or(wound_colors, cv2.inRange(
                roi_hsv, np.array([150, 8, 160]), np.array([180, 80, 255])))

            # Exclui fundo hospitalar
            bg_mask = np.zeros(roi_hsv.shape[:2], dtype=np.uint8)
            # Azul
            bg_mask = cv2.bitwise_or(bg_mask, cv2.inRange(
                roi_hsv, np.array([90, 30, 20]), np.array([130, 255, 255])))
            # Verde
            bg_mask = cv2.bitwise_or(bg_mask, cv2.inRange(
                roi_hsv, np.array([35, 30, 30]), np.array([85, 255, 255])))

            # Combina: cor de ferida AND NOT fundo
            roi_mask = cv2.bitwise_and(wound_colors, cv2.bitwise_not(bg_mask))

            # Limpeza morfológica
            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
            roi_mask = cv2.morphologyEx(roi_mask, cv2.MORPH_CLOSE, kernel, iterations=2)
            roi_mask = cv2.morphologyEx(roi_mask, cv2.MORPH_OPEN, kernel, iterations=1)

            # Preenche buracos: extrai e preenche contornos externos
            roi_filled = np.zeros_like(roi_mask)
            contours, _ = cv2.findContours(
                roi_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
            )
            if contours:
                # Pega contornos maiores (descarta artefatos < 2% do bbox)
                min_contour_area = (rx2 - rx1) * (ry2 - ry1) * 0.02
                for cnt in contours:
                    if cv2.contourArea(cnt) >= min_contour_area:
                        cv2.drawContours(roi_filled, [cnt], -1, 255, cv2.FILLED)

            # Se segmentação capturou muito pouco, fallback para bbox
            roi_area = np.sum(roi_filled > 0)
            bbox_area = (rx2 - rx1) * (ry2 - ry1)
            if roi_area < bbox_area * 0.10:
                wound_mask[y1:y2, x1:x2] = 255
            else:
                wound_mask[ry1:ry2, rx1:rx2] = cv2.bitwise_or(
                    wound_mask[ry1:ry2, rx1:rx2], roi_filled
                )

        return wound_mask




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
    # SEGMENTACAO TECIDUAL
    # -------------------------------------------------------

    def _segment_clinical(
        self, image: np.ndarray, wound_mask: np.ndarray
    ) -> Tuple[Dict[str, float], np.ndarray, np.ndarray]:
        """Segmenta a ferida segundo taxonomia clínica (v1/v2 — legado)."""
        peripheral, core, outer = self.roi_segmenter.create_zone_masks(wound_mask)
        return self._segment_clinical_v3(image, wound_mask, peripheral, core, outer)

    def _segment_clinical_v2(
        self, image: np.ndarray, wound_mask: np.ndarray
    ) -> Tuple[Dict[str, float], np.ndarray, np.ndarray]:
        """Compat v2: delega para v3 com zonas auto-calculadas."""
        peripheral, core, outer = self.roi_segmenter.create_zone_masks(wound_mask)
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
            hsv_raw, np.array([35, 30, 30]), np.array([85, 255, 255])))
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
        light_l_thr = max(118.0, self._safe_percentile(roi_values(light), 42, 125.0))
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
        slough_bool = (
            base_roi
            & inner_zone
            & (~dark_candidate)
            & (yellowish | off_white)
            & (light >= light_l_thr)
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
        7. CRIACAO DE MASCARA DE PELE SAUDAVEL para excluir da necrose
        8. Restrição espacial por zonas
        9. Detecção de epitelização por gradiente de borda (Scharr)
        10. Verificação de textura para necrose (necrose real tem textura diferente de pele)
        11. Exclusão de fundo cirúrgico
        12. Resolução de sobreposições com prioridade clínica
        """
        # ── 0. Estimação do tom de pele do paciente ───────────────
        skin_L, skin_a, skin_b, fitzpatrick = self._estimate_skin_tone(image, wound_mask)
        is_dark_skin = fitzpatrick in ("V", "VI")
        is_medium_skin = fitzpatrick in ("IV", "V")
        logger.debug(
            f"Tom de pele estimado: Fitzpatrick {fitzpatrick} "
            f"(L={skin_L:.0f}, a*={skin_a:.0f}, b*={skin_b:.0f})"
        )

        # ── 1. Pré-processamento: denoise + CLAHE ─────────────────────
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

        # ── 2. Segmentação HSV — restrita estritamente à wound_mask ───
        hsv_masks = {}
        for tissue_key, ranges in CLINICAL_HSV_RANGES.items():
            mask = np.zeros((h, w), dtype=np.uint8)
            for lower, upper in ranges:
                mask = cv2.bitwise_or(mask, cv2.inRange(hsv, lower, upper))
            # OBRIGATÓRIO: restringe à ROI — ignora todo pixel fora do perímetro
            mask = cv2.bitwise_and(mask, wound_mask)
            mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel_s)
            mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel_m)
            hsv_masks[tissue_key] = mask

        # ── 3. Segmentação LAB — restrita à wound_mask ────────────────
        lab_masks = {}
        for tissue_key, ranges in CLINICAL_LAB_RANGES.items():
            mask = np.zeros((h, w), dtype=np.uint8)
            for lower, upper in ranges:
                mask = cv2.bitwise_or(mask, cv2.inRange(lab, lower, upper))
            mask = cv2.bitwise_and(mask, wound_mask)
            mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel_s)
            mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel_m)
            lab_masks[tissue_key] = mask

        # ── 4. Fusão ponderada HSV (60%) + LAB (40%) ─────────────────
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

        # ── 5. Criação de máscara de pele saudável (skin exclusion) ────
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

        # ── 5b. Restrição espacial por zonas ─────────────────────────
        # Necrose: viés espacial moderado. Em peles escuras, requer
        # confirmacao por textura, mas NAO restringimos excessivamente.
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
        # que NAO sao pele saudavel do paciente (anti-bias)
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
        # Mescla: máscara de cor original (restrita à periferia) + gradiente
        epi_color_periph = cv2.bitwise_and(masks["epithelialization"], peripheral_zone)

        # Epitelização só é válida se estiver na zona periférica interna
        masks["epithelialization"] = cv2.bitwise_and(
            cv2.bitwise_or(epi_color_periph, epi_gradient),
            peripheral_zone
        )

        # ── 6. Refinamento por textura ───────────────────────────────
        gray = cv2.cvtColor(denoised_norm, cv2.COLOR_BGR2GRAY)
        local_var = cv2.GaussianBlur(
            (gray.astype(np.float32) ** 2), (15, 15), 0
        ) - cv2.GaussianBlur(gray.astype(np.float32), (15, 15), 0) ** 2
        local_var = np.clip(local_var, 0, None)

        low_texture = (local_var < 200).astype(np.uint8)
        high_texture = (local_var > 500).astype(np.uint8)

        # ── 7. Exclusão de fundo cirúrgico ───────────────────────────
        hsv_raw = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        _drape = np.zeros((h, w), dtype=np.uint8)
        _drape = cv2.bitwise_or(_drape, cv2.inRange(
            hsv_raw, np.array([90, 30, 20]), np.array([130, 255, 255])))
        _drape = cv2.bitwise_or(_drape, cv2.inRange(
            hsv_raw, np.array([35, 30, 30]), np.array([85, 255, 255])))
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

        # ── 8. Reforço por textura + luminância (com proteção anti-bias) ─
        # Combina luminância + textura para reforçar necrose, mas EXCLUI
        # pixels que correspondem ao tom de pele do paciente.

        # 8a. Pixels escuros dentro da ROI que NAO sao pele saudavel
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

        # ── 9. Resolução de sobreposições — prioridade clínica ───────
        priority = ["necrosis", "slough", "granulation", "epithelialization"]
        used = np.zeros((h, w), dtype=np.uint8)
        for key in priority:
            masks[key] = cv2.bitwise_and(masks[key], cv2.bitwise_not(used))
            used = cv2.bitwise_or(used, masks[key])

        # ── 10. Métricas e visualização ──────────────────────────────
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

        # Mapa de segmentação colorido
        seg_map = np.full((h, w, 3), 80, dtype=np.uint8)
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
        cv2.addWeighted(seg_map, 0.45, overlay, 0.55, 0, overlay)

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
        """Score de saúde baseado na composição tecidual."""
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

class AnalysisThread(QThread):
    # IMPORTANT: Do NOT name this 'finished' — it shadows QThread.finished
    # and breaks Qt's internal thread cleanup, causing crashes.
    result_ready = pyqtSignal(object)
    progress = pyqtSignal(str)

    def __init__(self, image_path: str, parent=None):
        super().__init__(parent)  # Parent garante cleanup adequado
        self.image_path = image_path
        # NAO conecte finished.connect(deleteLater) - causa crash
        # Lifecycle é gerenciado manualmente

    def run(self):
        self.progress.emit("Carregando imagem...")
        image = cv2.imread(self.image_path)
        if image is None:
            report = ClinicalReport(is_valid_wound=False,
                                    rejection_reason="Não foi possível carregar a imagem.")
            self.result_ready.emit(report)
            return

        self.progress.emit("Analisando ferida...")
        analyzer = ClinicalWoundAnalyzer()
        report = analyzer.analyze(image)
        self.result_ready.emit(report)


class ProgressionAnalysisThread(QThread):
    """Thread para comparar duas ou mais fotos sem travar a UI."""

    result_ready = pyqtSignal(object)
    progress = pyqtSignal(str)

    def __init__(self, image_paths: List[str], days_between_photos: float, parent=None):
        super().__init__(parent)
        self.image_paths = list(image_paths)
        self.days_between_photos = days_between_photos

    def run(self):
        try:
            result = analyze_wound_photo_progression(
                self.image_paths,
                analyzer_factory=ClinicalWoundAnalyzer,
                days_between_photos=self.days_between_photos,
                progress_callback=self.progress.emit,
            )
            self.result_ready.emit(result)
        except Exception as exc:
            logger.exception("[HEAL+] Erro na analise de evolucao por fotos: %s", exc)
            self.result_ready.emit({"error": str(exc)})


# ============================================================
# APLICACAO DESKTOP PyQt6
# ============================================================

def np_to_qpixmap(img: np.ndarray, max_w: int = 500) -> QPixmap:
    """Converte imagem OpenCV (BGR) para QPixmap."""
    rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    h, w, ch = rgb.shape
    if w > max_w:
        scale = max_w / w
        rgb = cv2.resize(rgb, (max_w, int(h * scale)))
        h, w = rgb.shape[:2]
    bytes_per_line = ch * w
    qimg = QImage(rgb.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
    return QPixmap.fromImage(qimg.copy())


class HealAnalyzerApp(QMainWindow):
    """Janela principal do analisador de feridas HEAL+."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("HEAL+ — Analisador Clínico de Feridas")
        self.setMinimumSize(1200, 800)
        self._current_report: Optional[ClinicalReport] = None
        self._thread: Optional[AnalysisThread] = None
        self._progression_thread: Optional[ProgressionAnalysisThread] = None
        self._progression_paths: List[str] = []


        self._setup_ui()

    # -------------------------------------------------------
    # UI
    # -------------------------------------------------------
    def _setup_ui(self):
        palette = QPalette()
        palette.setColor(QPalette.ColorRole.Window, QColor("#0f172a"))
        palette.setColor(QPalette.ColorRole.WindowText, QColor("#e2e8f0"))
        palette.setColor(QPalette.ColorRole.Base, QColor("#1e293b"))
        palette.setColor(QPalette.ColorRole.Text, QColor("#e2e8f0"))
        palette.setColor(QPalette.ColorRole.Button, QColor("#334155"))
        palette.setColor(QPalette.ColorRole.ButtonText, QColor("#e2e8f0"))
        palette.setColor(QPalette.ColorRole.Highlight, QColor("#38bdf8"))
        self.setPalette(palette)

        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(16, 12, 16, 12)
        main_layout.setSpacing(10)

        # === HEADER ===
        header_layout = QHBoxLayout()
        
        title_layout = QVBoxLayout()
        header = QLabel("HEAL+  —  Analisador Clínico de Feridas")
        header.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        header.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        header.setStyleSheet("color: #e2e8f0; padding: 0px; margin: 0px;")
        title_layout.addWidget(header)

        subtitle = QLabel("Estomaterapia + Visão Computacional  ·  ResNet50 Two-Stage + Grad-CAM  ·  Classificação Tecidual e Etiológica")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        subtitle.setFont(QFont("Segoe UI", 10))
        subtitle.setStyleSheet("color: #94a3b8; padding: 0px; margin: 0px;")
        title_layout.addWidget(subtitle)
        
        header_layout.addLayout(title_layout)
        header_layout.addStretch()
        main_layout.addLayout(header_layout)

        # Linha separadora
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        line.setFixedHeight(1)
        line.setStyleSheet("background: #334155; border: none;")
        main_layout.addWidget(line)

        # === TOOLBAR ===
        toolbar = QHBoxLayout()
        self.lbl_status = QLabel("Selecione uma aba para começar")
        self.lbl_status.setFont(QFont("Segoe UI", 10))
        self.lbl_status.setStyleSheet("color: #94a3b8; padding-left: 10px;")
        toolbar.addWidget(self.lbl_status, stretch=1)

        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setFixedWidth(180)
        self.progress.setVisible(False)
        self.progress.setStyleSheet("""
            QProgressBar { background: #1e293b; border: 1px solid #334155;
                border-radius: 6px; height: 14px; }
            QProgressBar::chunk { background: #38bdf8; border-radius: 5px; }
        """)
        toolbar.addWidget(self.progress)
        main_layout.addLayout(toolbar)

        # === TABS ===
        self.tab_widget = QTabWidget()
        self.tab_widget.setFont(QFont("Segoe UI", 11))
        self.tab_widget.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #334155;
                border-radius: 8px;
                background: #1e293b;
            }
            QTabBar::tab {
                background: #1e293b;
                color: #94a3b8;
                padding: 10px 24px;
                margin-right: 4px;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
                font-weight: bold;
            }
            QTabBar::tab:selected {
                background: #0ea5e9;
                color: white;
            }
            QTabBar::tab:hover:!selected {
                background: #334155;
                color: #e2e8f0;
            }
        """)

        # === TAB 1: ARQUIVO DE IMAGEM ===
        self.tab_image = QWidget()
        self._setup_image_tab()
        self.tab_widget.addTab(self.tab_image, "Arquivo de Imagem")

        # === TAB 2: EVOLUCAO POR FOTOS ===
        self.tab_progression = QWidget()
        self._setup_progression_tab()
        self.tab_widget.addTab(self.tab_progression, "Evolucao por Fotos")

        self.tab_widget.currentChanged.connect(self._on_tab_changed)
        main_layout.addWidget(self.tab_widget, stretch=1)

        footer = QLabel("HEAL/REDISUS  —  Plataforma Nacional de Saúde Digital  ·  Cluster REDISUS  —  RNP/RUTE")
        footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        footer.setFont(QFont("Segoe UI", 8))
        footer.setStyleSheet("color: #475569; padding: 6px;")
        main_layout.addWidget(footer)

    # -------------------------------------------------------
    def _make_image_panel(self, title: str) -> QLabel:
        frame = QLabel(title)
        frame.setAlignment(Qt.AlignmentFlag.AlignCenter)
        frame.setMinimumSize(240, 180)
        frame.setFont(QFont("Segoe UI", 9))
        frame.setStyleSheet("""
            QLabel {
                background: #1e293b;
                border: 1px solid #334155;
                border-radius: 10px;
                color: #64748b;
                padding: 4px;
            }
        """)
        frame.setScaledContents(False)
        return frame

    # -------------------------------------------------------
    def _setup_image_tab(self):
        """Configura aba de análise de imagem estática."""
        layout = QVBoxLayout(self.tab_image)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # Toolbar da aba
        toolbar = QHBoxLayout()
        self.btn_open = QPushButton("Abrir Imagem de Ferida")
        self.btn_open.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        self.btn_open.setMinimumHeight(40)
        self.btn_open.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_open.setStyleSheet("""
            QPushButton {
                background: #0ea5e9;
                color: white; border: none; border-radius: 6px;
                padding: 0 24px; font-size: 13px;
            }
            QPushButton:hover { background: #38bdf8; }
            QPushButton:pressed { background: #0284c7; }
        """)
        self.btn_open.clicked.connect(self._on_open_image)
        toolbar.addWidget(self.btn_open)
        toolbar.addStretch()
        layout.addLayout(toolbar)

        # Splitter principal
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(2)

        # LEFT: Imagens
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(8)

        self.lbl_img_original = self._make_image_panel("Imagem Original")
        self.lbl_img_detection = self._make_image_panel("Detecção de Feridas")
        self.lbl_img_segmentation = self._make_image_panel("Mapa de Segmentação")
        self.lbl_img_overlay = self._make_image_panel("Overlay Tecidual")
        self.lbl_img_gradcam = self._make_image_panel("Grad-CAM (Explicabilidade)")

        img_grid = QHBoxLayout()
        col1 = QVBoxLayout()
        col1.addWidget(self.lbl_img_original)
        col1.addWidget(self.lbl_img_segmentation)
        col1.addWidget(self.lbl_img_gradcam)
        col2 = QVBoxLayout()
        col2.addWidget(self.lbl_img_detection)
        col2.addWidget(self.lbl_img_overlay)
        img_grid.addLayout(col1)
        img_grid.addLayout(col2)
        left_layout.addLayout(img_grid)

        splitter.addWidget(left)

        # RIGHT: Laudo
        right_scroll = QScrollArea()
        right_scroll.setWidgetResizable(True)
        right_scroll.setStyleSheet("""
            QScrollArea {
                border: none;
                background: #0f172a;
            }
            QScrollBar:vertical {
                background: #0f172a;
                width: 8px;
                margin: 4px 2px;
            }
            QScrollBar::handle:vertical {
                background: #475569;
                border-radius: 4px;
                min-height: 30px;
            }
            QScrollBar::handle:vertical:hover {
                background: #64748b;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)
        self.right_panel = QWidget()
        self.right_panel.setStyleSheet("background: #0f172a;")
        self.right_layout = QVBoxLayout(self.right_panel)
        self.right_layout.setContentsMargins(10, 8, 10, 10)
        self.right_layout.setSpacing(10)
        self.right_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # Placeholder
        self.lbl_placeholder = QLabel(
            "Abra uma imagem de ferida para iniciar a análise clínica.\n\n"
            "Formatos suportados: JPG, PNG, BMP, TIFF\n\n"
            "O sistema irá classificar o tecido predominante em:\n"
            "  • Necrose de Coagulação (Escara)\n"
            "  • Esfacelo (Fibrina)\n"
            "  • Tecido de Granulação\n"
            "  • Epitelização"
        )
        self.lbl_placeholder.setFont(QFont("Segoe UI", 11))
        self.lbl_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_placeholder.setStyleSheet("""
            color: #64748b;
            padding: 40px;
            background: #0f172a;
        """)
        self.lbl_placeholder.setWordWrap(True)
        self.right_layout.addWidget(self.lbl_placeholder)

        right_scroll.setWidget(self.right_panel)
        splitter.addWidget(right_scroll)

        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        layout.addWidget(splitter, stretch=1)

    # -------------------------------------------------------
    def _setup_progression_tab(self):
        """Configura aba de comparacao longitudinal por fotos."""
        layout = QVBoxLayout(self.tab_progression)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        toolbar = QHBoxLayout()

        self.btn_progression_select = QPushButton("Selecionar 2+ Fotos")
        self.btn_progression_select.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        self.btn_progression_select.setMinimumHeight(40)
        self.btn_progression_select.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_progression_select.setStyleSheet("""
            QPushButton {
                background: #0ea5e9;
                color: white; border: none; border-radius: 6px;
                padding: 0 22px; font-size: 13px;
            }
            QPushButton:hover { background: #38bdf8; }
            QPushButton:pressed { background: #0284c7; }
        """)
        self.btn_progression_select.clicked.connect(self._on_select_progression_images)
        toolbar.addWidget(self.btn_progression_select)

        self.btn_progression_run = QPushButton("Comparar Evolucao")
        self.btn_progression_run.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        self.btn_progression_run.setMinimumHeight(40)
        self.btn_progression_run.setEnabled(False)
        self.btn_progression_run.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_progression_run.setStyleSheet("""
            QPushButton {
                background: #16a34a;
                color: white; border: none; border-radius: 6px;
                padding: 0 22px; font-size: 13px;
            }
            QPushButton:hover:enabled { background: #22c55e; }
            QPushButton:pressed:enabled { background: #15803d; }
            QPushButton:disabled { background: #334155; color: #64748b; }
        """)
        self.btn_progression_run.clicked.connect(self._on_run_progression_analysis)
        toolbar.addWidget(self.btn_progression_run)

        toolbar.addSpacing(12)
        toolbar.addWidget(self._styled_label("Intervalo medio:", "#94a3b8", 10))
        self.combo_progression_interval = QComboBox()
        self.combo_progression_interval.addItems(["7 dias", "3 dias", "14 dias", "30 dias"])
        self.combo_progression_interval.setMinimumWidth(110)
        self.combo_progression_interval.setStyleSheet("""
            QComboBox {
                background: #334155; color: #e2e8f0; border: 1px solid #475569;
                border-radius: 6px; padding: 6px 12px;
            }
            QComboBox::drop-down { border: none; }
            QComboBox QAbstractItemView { background: #1e293b; color: #e2e8f0; }
        """)
        toolbar.addWidget(self.combo_progression_interval)

        self.lbl_progression_status = QLabel("Selecione fotos cronologicas da mesma ferida")
        self.lbl_progression_status.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        self.lbl_progression_status.setStyleSheet("color: #64748b;")
        toolbar.addWidget(self.lbl_progression_status)
        toolbar.addStretch()
        layout.addLayout(toolbar)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(2)

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(8)

        self.txt_progression_files = QTextEdit()
        self.txt_progression_files.setReadOnly(True)
        self.txt_progression_files.setMinimumHeight(120)
        self.txt_progression_files.setText(
            "Nenhuma foto selecionada.\n\n"
            "Use fotos da mesma ferida em ordem cronologica para comparar area, tecidos e score."
        )
        self.txt_progression_files.setStyleSheet("""
            QTextEdit {
                background: #0f172a;
                color: #94a3b8;
                border: 1px solid #334155;
                border-radius: 8px;
                padding: 10px;
            }
        """)
        left_layout.addWidget(self.txt_progression_files)

        comparison_grid = QHBoxLayout()
        self.lbl_progression_first = self._make_image_panel("Primeira Foto")
        self.lbl_progression_last = self._make_image_panel("Foto Mais Recente")
        comparison_grid.addWidget(self.lbl_progression_first)
        comparison_grid.addWidget(self.lbl_progression_last)
        left_layout.addLayout(comparison_grid, stretch=1)

        note = QLabel(
            "Estimativa aproximada: depende de mesma distancia, angulo, luz e escala. "
            "Use como apoio para triagem/evolucao, nao como alta automatica."
        )
        note.setWordWrap(True)
        note.setFont(QFont("Segoe UI", 9))
        note.setStyleSheet("color: #64748b; padding: 6px;")
        left_layout.addWidget(note)

        splitter.addWidget(left)

        right_scroll = QScrollArea()
        right_scroll.setWidgetResizable(True)
        right_scroll.setStyleSheet("""
            QScrollArea { border: none; background: #0f172a; }
            QScrollBar:vertical { background: #0f172a; width: 8px; margin: 4px 2px; }
            QScrollBar::handle:vertical { background: #475569; border-radius: 4px; min-height: 30px; }
            QScrollBar::handle:vertical:hover { background: #64748b; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
        """)
        self.progression_right_panel = QWidget()
        self.progression_right_panel.setStyleSheet("background: #0f172a;")
        self.progression_right_layout = QVBoxLayout(self.progression_right_panel)
        self.progression_right_layout.setContentsMargins(10, 8, 10, 10)
        self.progression_right_layout.setSpacing(10)
        self.progression_right_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.progression_placeholder = QLabel(
            "Compare duas ou mais fotos para ver:\n\n"
            "  - mudanca de area em pixels\n"
            "  - evolucao de granulacao, epitelizacao, esfacelo e necrose\n"
            "  - score de saude da ferida\n"
            "  - estimativa de fechamento se houver reducao consistente\n\n"
            "A ordem das fotos selecionadas sera usada como linha do tempo."
        )
        self.progression_placeholder.setFont(QFont("Segoe UI", 11))
        self.progression_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.progression_placeholder.setStyleSheet("""
            color: #64748b;
            padding: 40px;
            background: #0f172a;
        """)
        self.progression_placeholder.setWordWrap(True)
        self.progression_right_layout.addWidget(self.progression_placeholder)

        right_scroll.setWidget(self.progression_right_panel)
        splitter.addWidget(right_scroll)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        layout.addWidget(splitter, stretch=1)

    # -------------------------------------------------------
    def _on_tab_changed(self, index: int):
        """Callback quando troca de aba."""
        if index == 0:
            self.lbl_status.setText("Modo: Arquivo de Imagem")
        else:
            self.lbl_status.setText("Modo: Evolucao por Fotos")

    # -------------------------------------------------------
    # PROGRESSION METHODS
    # -------------------------------------------------------
    def _progression_interval_days(self) -> float:
        text = self.combo_progression_interval.currentText().split()[0]
        try:
            return float(text)
        except ValueError:
            return 7.0

    def _on_select_progression_images(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Selecionar Fotos da Evolucao da Ferida",
            str(Path(__file__).parent / "dataset"),
            "Imagens (*.jpg *.jpeg *.png *.bmp *.tif *.tiff);;Todos (*)",
        )
        if not paths:
            return

        self._progression_paths = list(paths)
        lines = [
            f"{index}. {Path(path).name}"
            for index, path in enumerate(self._progression_paths, start=1)
        ]
        self.txt_progression_files.setText("\n".join(lines))
        self.btn_progression_run.setEnabled(len(self._progression_paths) >= 2)
        self.lbl_progression_status.setText(f"{len(self._progression_paths)} foto(s) selecionada(s)")
        self.lbl_progression_status.setStyleSheet("color: #38bdf8;")
        self.lbl_status.setText("Fotos carregadas para comparacao longitudinal")
        self.lbl_status.setStyleSheet("color: #38bdf8;")
        self._display_progression_preview()

    def _display_progression_preview(self):
        if not self._progression_paths:
            return
        first = cv2.imread(self._progression_paths[0])
        last = cv2.imread(self._progression_paths[-1])
        if first is not None:
            self.lbl_progression_first.setPixmap(np_to_qpixmap(first, 520))
        if last is not None:
            self.lbl_progression_last.setPixmap(np_to_qpixmap(last, 520))

    def _on_run_progression_analysis(self):
        if len(self._progression_paths) < 2:
            self.lbl_progression_status.setText("Selecione pelo menos duas fotos")
            self.lbl_progression_status.setStyleSheet("color: #fbbf24;")
            return
        if self._progression_thread is not None and self._progression_thread.isRunning():
            return

        self._set_progression_busy(True)
        self._progression_thread = ProgressionAnalysisThread(
            self._progression_paths,
            self._progression_interval_days(),
            parent=self,
        )
        self._progression_thread.progress.connect(self._on_progress, Qt.ConnectionType.QueuedConnection)
        self._progression_thread.result_ready.connect(self._on_progression_done, Qt.ConnectionType.QueuedConnection)
        self._progression_thread.start()

    def _set_progression_busy(self, busy: bool):
        self.progress.setVisible(busy)
        self.btn_progression_select.setEnabled(not busy)
        self.btn_progression_run.setEnabled((not busy) and len(self._progression_paths) >= 2)
        self.combo_progression_interval.setEnabled(not busy)
        if busy:
            self.lbl_progression_status.setText("Analisando evolucao...")
            self.lbl_progression_status.setStyleSheet("color: #fbbf24;")

    def _on_progression_done(self, payload):
        self._set_progression_busy(False)
        self._progression_thread = None

        if isinstance(payload, dict) and payload.get("error"):
            self.lbl_status.setText(f"Erro na evolucao: {payload['error']}")
            self.lbl_status.setStyleSheet("color: #ef4444;")
            self.lbl_progression_status.setText("Erro")
            self.lbl_progression_status.setStyleSheet("color: #ef4444;")
            return

        result: WoundProgressionResult = payload
        self.lbl_status.setText(
            f"Evolucao concluida | {result.valid_photo_count} foto(s) validas | {result.closure_estimate.trajectory}"
        )
        status_color = "#22c55e" if result.closure_estimate.trajectory == "improving" else (
            "#ef4444" if result.closure_estimate.trajectory == "worsening" else "#fbbf24"
        )
        self.lbl_status.setStyleSheet(f"color: {status_color};")
        self.lbl_progression_status.setText(result.closure_estimate.trajectory)
        self.lbl_progression_status.setStyleSheet(f"color: {status_color};")
        self._show_progression_results(result)

    def _show_progression_results(self, result: WoundProgressionResult):
        self._clear_progression_panel()

        estimate = result.closure_estimate
        trajectory_names = {
            "improving": "Melhora",
            "worsening": "Piora",
            "stable": "Estavel/sem reducao robusta",
            "insufficient_data": "Dados insuficientes",
        }
        trajectory_color = "#22c55e" if estimate.trajectory == "improving" else (
            "#ef4444" if estimate.trajectory == "worsening" else "#fbbf24"
        )

        box_main = self._make_group("EVOLUCAO GERAL")
        lbl_trajectory = QLabel(trajectory_names.get(estimate.trajectory, estimate.trajectory))
        lbl_trajectory.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        lbl_trajectory.setStyleSheet(f"color: {trajectory_color}; padding: 2px 0;")
        box_main.layout().addWidget(lbl_trajectory)
        lbl_summary = QLabel(result.summary)
        lbl_summary.setWordWrap(True)
        lbl_summary.setFont(QFont("Segoe UI", 10))
        lbl_summary.setStyleSheet("color: #cbd5e1;")
        box_main.layout().addWidget(lbl_summary)
        self.progression_right_layout.addWidget(box_main)

        box_metrics = self._make_group("METRICAS DE COMPARACAO")
        metric_items = [
            ("Fotos validas", f"{result.valid_photo_count}"),
            ("Fotos rejeitadas", f"{result.invalid_photo_count}"),
            ("Mudanca de area", self._format_optional_pct(result.area_change_pct)),
            ("Delta score", self._format_signed(result.health_score_delta)),
            ("Tecido de reparo", self._format_optional_pct(result.healthy_tissue_delta_pct, suffix=' pp')),
            ("Tecido desvitalizado", self._format_optional_pct(result.devitalized_tissue_delta_pct, suffix=' pp')),
        ]
        for label, value in metric_items:
            row = QWidget()
            rl = QHBoxLayout(row)
            rl.setContentsMargins(0, 1, 0, 1)
            rl.addWidget(self._styled_label(label, "#94a3b8", 10))
            rl.addStretch()
            rl.addWidget(self._styled_label(value, "#e2e8f0", 10, bold=True))
            box_metrics.layout().addWidget(row)
        self.progression_right_layout.addWidget(box_metrics)

        box_estimate = self._make_group("ESTIMATIVA DE FECHAMENTO")
        if estimate.estimated_days_to_closure_min is not None:
            days_text = f"{estimate.estimated_days_to_closure_min}-{estimate.estimated_days_to_closure_max} dias"
            if estimate.estimated_weeks_to_closure is not None:
                days_text += f" (~{estimate.estimated_weeks_to_closure:.1f} semanas)"
            lbl_days = QLabel(days_text)
            lbl_days.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
            lbl_days.setStyleSheet("color: #38bdf8;")
            box_estimate.layout().addWidget(lbl_days)
        else:
            lbl_days = QLabel("Sem estimativa segura de fechamento")
            lbl_days.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
            lbl_days.setStyleSheet("color: #fbbf24;")
            box_estimate.layout().addWidget(lbl_days)
        lbl_conf = QLabel(f"Confianca: {estimate.confidence}. {estimate.rationale}")
        lbl_conf.setWordWrap(True)
        lbl_conf.setFont(QFont("Segoe UI", 9))
        lbl_conf.setStyleSheet("color: #94a3b8;")
        box_estimate.layout().addWidget(lbl_conf)
        for alert in estimate.alerts:
            lbl_alert = QLabel(f"Alerta: {alert}")
            lbl_alert.setWordWrap(True)
            lbl_alert.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
            lbl_alert.setStyleSheet("color: #f97316;")
            box_estimate.layout().addWidget(lbl_alert)
        self.progression_right_layout.addWidget(box_estimate)

        if result.tissue_deltas:
            box_tissues = self._make_group("EVOLUCAO DOS TECIDOS")
            for delta in result.tissue_deltas:
                if abs(delta.delta_pct) < 0.5:
                    continue
                color = "#22c55e" if delta.delta_pct > 0 and any(k in delta.tissue_name.lower() for k in ("granula", "epitel")) else (
                    "#ef4444" if delta.delta_pct > 0 else "#38bdf8"
                )
                row = QWidget()
                rl = QHBoxLayout(row)
                rl.setContentsMargins(0, 1, 0, 1)
                rl.addWidget(self._styled_label(delta.tissue_name[:34], "#e2e8f0", 9))
                rl.addStretch()
                rl.addWidget(self._styled_label(
                    f"{delta.first_pct:.1f}% -> {delta.last_pct:.1f}% ({delta.delta_pct:+.1f} pp)",
                    color,
                    9,
                    bold=True,
                ))
                box_tissues.layout().addWidget(row)
            self.progression_right_layout.addWidget(box_tissues)

        box_timeline = self._make_group("LINHA DO TEMPO")
        for snapshot in result.snapshots:
            color = "#22c55e" if snapshot.is_valid_wound else "#ef4444"
            text = (
                f"{snapshot.sequence_index}. {snapshot.filename}: "
                f"{snapshot.primary_tissue or 'Imagem rejeitada'} | "
                f"area {snapshot.wound_area_px:,} px | score {snapshot.health_score:.0f}/100"
            )
            lbl = QLabel(text)
            lbl.setWordWrap(True)
            lbl.setFont(QFont("Segoe UI", 9))
            lbl.setStyleSheet(f"color: {color};")
            box_timeline.layout().addWidget(lbl)
            if snapshot.rejection_reason:
                reason = QLabel(snapshot.rejection_reason)
                reason.setWordWrap(True)
                reason.setFont(QFont("Segoe UI", 8))
                reason.setStyleSheet("color: #f97316; padding-left: 8px;")
                box_timeline.layout().addWidget(reason)
        self.progression_right_layout.addWidget(box_timeline)

        box_recs = self._make_group("PROXIMAS ACOES")
        for recommendation in result.recommendations:
            lbl = QLabel(f"- {recommendation}")
            lbl.setWordWrap(True)
            lbl.setFont(QFont("Segoe UI", 9))
            lbl.setStyleSheet("color: #cbd5e1;")
            box_recs.layout().addWidget(lbl)
        self.progression_right_layout.addWidget(box_recs)
        self.progression_right_layout.addStretch()

    def _clear_progression_panel(self):
        while self.progression_right_layout.count():
            w = self.progression_right_layout.takeAt(0).widget()
            if w:
                w.deleteLater()

    def _format_optional_pct(self, value: Optional[float], suffix: str = "%") -> str:
        if value is None:
            return "N/A"
        return f"{value:+.1f}{suffix}"

    def _format_signed(self, value: Optional[float]) -> str:
        if value is None:
            return "N/A"
        return f"{value:+.1f}"

    # -------------------------------------------------------
    # -------------------------------------------------------
    def _on_open_image(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Selecionar Imagem de Ferida",
            str(Path(__file__).parent / "dataset"),
            "Imagens (*.jpg *.jpeg *.png *.bmp *.tif *.tiff);;Todos (*)",
        )
        if not path:
            return

        self.lbl_status.setText(f"Analisando: {Path(path).name}")
        self.lbl_status.setStyleSheet("color: #fbbf24;")
        self.progress.setVisible(True)
        self.btn_open.setEnabled(False)

        self._thread = AnalysisThread(path, parent=self)
        self._thread.progress.connect(self._on_progress, Qt.ConnectionType.QueuedConnection)
        self._thread.result_ready.connect(self._on_analysis_done, Qt.ConnectionType.QueuedConnection)
        self._thread.start()

    def _on_progress(self, msg: str):
        self.lbl_status.setText(msg)

    def _on_analysis_done(self, report: ClinicalReport):
        self.progress.setVisible(False)
        self.btn_open.setEnabled(True)
        self._current_report = report

        if not report.is_valid_wound:
            self.lbl_status.setText("Análise concluída — Input Inválido")
            self.lbl_status.setStyleSheet("color: #ef4444;")
            self._show_invalid(report)
            return

        # Monta status final com ResNet50 se disponível
        resnet_tag = ""
        if report.ai_predictions and report.ai_predictions.resnet:
            rn = report.ai_predictions.resnet
            final_pt = rn.get("final_class_pt", "")
            final_conf = rn.get("final_confidence", 0)
            if final_pt:
                resnet_tag = f"  |  Etiologia: {final_pt} ({final_conf:.0%})"

        self.lbl_status.setText(
            f"Análise concluída  |  {report.processing_time_ms:.0f}ms  |  "
            f"Tecido: {report.primary_tissue}{resnet_tag}"
        )
        self.lbl_status.setStyleSheet("color: #22c55e;")
        self._show_results(report)

    # -------------------------------------------------------
    def _show_invalid(self, report: ClinicalReport):
        if report.original is not None:
            self.lbl_img_original.setPixmap(np_to_qpixmap(report.original, 400))
        self._clear_right_panel()
        lbl = QLabel(report.rejection_reason)
        lbl.setFont(QFont("Segoe UI", 13))
        lbl.setWordWrap(True)
        lbl.setStyleSheet("color: #ef4444; padding: 30px;")
        self.right_layout.addWidget(lbl)

    # -------------------------------------------------------
    def _show_results(self, r: ClinicalReport):
        # Imagens
        if r.original is not None:
            self.lbl_img_original.setPixmap(np_to_qpixmap(r.original, 400))
        if r.detection_overlay is not None:
            self.lbl_img_detection.setPixmap(np_to_qpixmap(r.detection_overlay, 400))
        if r.segmentation_map is not None:
            self.lbl_img_segmentation.setPixmap(np_to_qpixmap(r.segmentation_map, 400))
        if r.tissue_overlay is not None:
            self.lbl_img_overlay.setPixmap(np_to_qpixmap(r.tissue_overlay, 400))
        if r.grad_cam_overlay is not None:
            self.lbl_img_gradcam.setPixmap(np_to_qpixmap(r.grad_cam_overlay, 400))
        else:
            self.lbl_img_gradcam.setText("Grad-CAM (modelo não carregado)")

        self._clear_right_panel()

        # --- CLASSIFICACAO PRINCIPAL ---
        box_main = self._make_group("CLASSIFICACAO PRINCIPAL")
        
        # Layout horizontal para texto
        main_hl = QHBoxLayout()
        
        # Texto da classificação
        text_vl = QVBoxLayout()
        # Cor dinâmica baseada no tecido
        tissue_colors = {
            "Tecido de Granulação": "#22c55e",
            "Epitelização": "#a78bfa",
            "Esfacelo (Fibrina)": "#fbbf24",
            "Necrose de Coagulação (Escara)": "#ef4444",
        }
        primary_color = tissue_colors.get(r.primary_tissue, "#38bdf8")

        lbl_primary = QLabel(r.primary_tissue)
        lbl_primary.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        lbl_primary.setStyleSheet(f"color: {primary_color}; padding: 0px;")
        text_vl.addWidget(lbl_primary)

        lbl_just = QLabel(r.primary_justification)
        lbl_just.setWordWrap(True)
        lbl_just.setFont(QFont("Segoe UI", 10))
        lbl_just.setStyleSheet("color: #cbd5e1; padding: 2px 0 6px; line-height: 1.4;")
        text_vl.addWidget(lbl_just)
        
        main_hl.addLayout(text_vl)
        box_main.layout().addLayout(main_hl)
        self.right_layout.addWidget(box_main)

        # --- COMPOSICAO TECIDUAL ---
        box_tissue = self._make_group("COMPOSICAO TECIDUAL")
        for t in sorted(r.tissues, key=lambda x: -x.percentage):
            row = QWidget()
            rl = QHBoxLayout(row)
            rl.setContentsMargins(0, 2, 0, 2)

            # Cor
            swatch = QLabel()
            swatch.setFixedSize(14, 14)
            swatch.setStyleSheet(f"background: {t.color_hex}; border-radius: 3px; border: 1px solid #475569;")
            rl.addWidget(swatch)

            # Nome + %
            rl.addWidget(self._styled_label(t.name, "#e2e8f0", 10))
            rl.addStretch()
            rl.addWidget(self._styled_label(f"{t.percentage:.1f}%", "#38bdf8", 10, bold=True))

            box_tissue.layout().addWidget(row)

            # Barra
            bar_bg = QFrame()
            bar_bg.setFixedHeight(8)
            bar_bg.setStyleSheet("background: #0f172a; border-radius: 4px;")
            bar_inner = QFrame(bar_bg)
            bar_inner.setFixedHeight(8)
            pct_clamped = min(t.percentage, 100)
            bar_inner.setFixedWidth(max(int(pct_clamped * 2.5), 1))
            bar_inner.setStyleSheet(f"background: {t.color_hex}; border-radius: 4px;")
            box_tissue.layout().addWidget(bar_bg)

        # Score
        score_row = QWidget()
        score_color = "#22c55e" if r.health_score >= 60 else ("#fbbf24" if r.health_score >= 30 else "#ef4444")
        score_row.setStyleSheet("""
            QWidget {
                background: #0f172a;
                border: 1px solid #334155;
                border-radius: 6px;
                margin-top: 6px;
            }
        """)
        sl = QHBoxLayout(score_row)
        sl.setContentsMargins(12, 8, 12, 8)
        sl.addWidget(self._styled_label("Score de Saúde:", "#94a3b8", 11))
        sl.addWidget(self._styled_label(f"{r.health_score:.0f}/100", score_color, 14, bold=True))
        sl.addStretch()
        box_tissue.layout().addWidget(score_row)

        self.right_layout.addWidget(box_tissue)

        trace = r.tissue_analysis_trace or {}
        criteria = [str(item).strip() for item in trace.get("criteria") or [] if str(item).strip()]
        coverage = trace.get("coverage_pct")
        unclassified = trace.get("unclassified_pct")
        if criteria or coverage is not None:
            box_trace = self._make_group("SINAIS CONSIDERADOS")

            if coverage is not None:
                summary = f"Cobertura classificada: {float(coverage):.1f}%"
                if unclassified is not None:
                    summary += f" | Indeterminado: {float(unclassified):.1f}%"
                lbl_summary = QLabel(summary)
                lbl_summary.setWordWrap(True)
                lbl_summary.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
                lbl_summary.setStyleSheet("color: #38bdf8; padding: 2px 0 6px;")
                box_trace.layout().addWidget(lbl_summary)

            lbl_hint = QLabel(
                "Os limiares de cor e textura sao adaptados ao ROI da propria ferida."
            )
            lbl_hint.setWordWrap(True)
            lbl_hint.setFont(QFont("Segoe UI", 9))
            lbl_hint.setStyleSheet("color: #94a3b8; padding-bottom: 4px;")
            box_trace.layout().addWidget(lbl_hint)

            for item in criteria:
                lbl_item = QLabel(f"- {item}")
                lbl_item.setWordWrap(True)
                lbl_item.setFont(QFont("Segoe UI", 9))
                lbl_item.setStyleSheet("color: #cbd5e1; padding: 1px 0;")
                box_trace.layout().addWidget(lbl_item)

            self.right_layout.addWidget(box_trace)

        # --- CLASSIFICACAO IA (Deep Learning) ---
        if r.dl_prediction:
            box_dl = self._make_group("CLASSIFICACAO IA (Deep Learning)")
            dl = r.dl_prediction

            # Classe principal
            lbl_cls = QLabel(dl.get("display_name", "N/A"))
            lbl_cls.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
            conf = dl.get("confidence", 0)
            conf_color = "#22c55e" if conf >= 0.7 else ("#fbbf24" if conf >= 0.4 else "#ef4444")
            lbl_cls.setStyleSheet(f"color: {conf_color}; padding: 4px 0;")
            box_dl.layout().addWidget(lbl_cls)

            # Confiança
            conf_row = QWidget()
            cl = QHBoxLayout(conf_row)
            cl.setContentsMargins(0, 2, 0, 2)
            cl.addWidget(self._styled_label("Confiança:", "#94a3b8", 10))
            cl.addWidget(self._styled_label(f"{conf:.1%}", conf_color, 11, bold=True))
            cl.addStretch()
            box_dl.layout().addWidget(conf_row)

            # Top-3 predictions
            top3 = dl.get("top3", [])
            if len(top3) > 1:
                box_dl.layout().addWidget(self._styled_label("Diagnósticos diferenciais:", "#64748b", 9))
                for pred in top3[1:]:
                    p_conf = pred.get("confidence", 0)
                    p_name = pred.get("display", pred.get("class", ""))
                    row = QWidget()
                    rl = QHBoxLayout(row)
                    rl.setContentsMargins(8, 0, 0, 0)
                    rl.addWidget(self._styled_label(f"• {p_name}", "#94a3b8", 9))
                    rl.addStretch()
                    rl.addWidget(self._styled_label(f"{p_conf:.1%}", "#64748b", 9))
                    box_dl.layout().addWidget(row)

            # Nota sobre modelo
            if conf < 0.5:
                note = QLabel("Confiança baixa — recomenda-se avaliação por especialista")
                note.setWordWrap(True)
                note.setFont(QFont("Segoe UI", 9))
                note.setStyleSheet("color: #fbbf24; padding-top: 4px;")
                box_dl.layout().addWidget(note)

            self.right_layout.addWidget(box_dl)

        # --- CLASSIFICACAO RESNET50 (Dois Estagios) ---
        if r.resnet_prediction:
            rn = r.resnet_prediction
            box_rn = self._make_group("CLASSIFICACAO ETIOLOGICA (ResNet50)")

            # Estágio 1 — Normal vs Ferida
            s1 = rn.get("stage1", {})
            if s1:
                s1_conf = s1.get("confidence", 0)
                s1_wound = s1.get("is_wound", True)
                s1_text = "Ferida Detectada" if s1_wound else "Pele Normal"
                s1_color = "#ef4444" if s1_wound else "#22c55e"

                s1_row = QWidget()
                s1l = QHBoxLayout(s1_row)
                s1l.setContentsMargins(0, 2, 0, 2)
                s1l.addWidget(self._styled_label("Triagem:", "#94a3b8", 10))
                s1l.addWidget(self._styled_label(s1_text, s1_color, 11, bold=True))
                s1l.addWidget(self._styled_label(f"({s1_conf:.0%})", "#64748b", 9))
                s1l.addStretch()
                box_rn.layout().addWidget(s1_row)

            # Estágio 2 — Tipo de Ferida
            s2 = rn.get("stage2", {})
            if s2:
                wound_type_pt = s2.get("wound_type_pt", "")
                s2_conf = s2.get("confidence", 0)
                s2_color = "#22c55e" if s2_conf >= 0.7 else ("#fbbf24" if s2_conf >= 0.45 else "#ef4444")

                lbl_type = QLabel(wound_type_pt)
                lbl_type.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
                lbl_type.setStyleSheet(f"color: {s2_color}; padding: 4px 0;")
                box_rn.layout().addWidget(lbl_type)

                # Confiança
                conf_row = QWidget()
                crl = QHBoxLayout(conf_row)
                crl.setContentsMargins(0, 2, 0, 2)
                crl.addWidget(self._styled_label("Confiança:", "#94a3b8", 10))
                crl.addWidget(self._styled_label(f"{s2_conf:.1%}", s2_color, 11, bold=True))
                crl.addStretch()
                box_rn.layout().addWidget(conf_row)

                # Diagnósticos diferenciais
                top_preds = s2.get("top_predictions", [])
                if len(top_preds) > 1:
                    box_rn.layout().addWidget(self._styled_label("Diagnósticos diferenciais:", "#64748b", 9))
                    for pred in top_preds[1:]:
                        p_conf = pred.get("confidence", 0)
                        p_name = pred.get("class_pt", pred.get("class", ""))
                        row = QWidget()
                        rl = QHBoxLayout(row)
                        rl.setContentsMargins(8, 0, 0, 0)
                        rl.addWidget(self._styled_label(f"• {p_name}", "#94a3b8", 9))
                        rl.addStretch()
                        rl.addWidget(self._styled_label(f"{p_conf:.1%}", "#64748b", 9))
                        box_rn.layout().addWidget(row)

            # Ação clínica específica da etiologia
            clinical_action = rn.get("clinical_action", "")
            if clinical_action:
                lbl_action = QLabel(clinical_action)
                lbl_action.setWordWrap(True)
                lbl_action.setFont(QFont("Segoe UI", 9))
                lbl_action.setStyleSheet("color: #cbd5e1; padding-top: 6px;")
                box_rn.layout().addWidget(lbl_action)

            # Nota de confiança baixa
            final_conf = rn.get("final_confidence", 0)
            if final_conf < 0.5:
                note = QLabel("Confiança baixa — recomenda-se avaliação por especialista em estomaterapia")
                note.setWordWrap(True)
                note.setFont(QFont("Segoe UI", 9))
                note.setStyleSheet("color: #fbbf24; padding-top: 4px;")
                box_rn.layout().addWidget(note)

            self.right_layout.addWidget(box_rn)

        # --- GRAD-CAM (Explicabilidade) ---
        if r.grad_cam_overlay is not None:
            box_gcam = self._make_group("GRAD-CAM (Explicabilidade IA)")
            lbl_gcam_desc = QLabel(
                "Mapa de calor indicando as regiões da imagem que mais "
                "influenciaram a decisão do modelo de classificação."
            )
            lbl_gcam_desc.setWordWrap(True)
            lbl_gcam_desc.setFont(QFont("Segoe UI", 9))
            lbl_gcam_desc.setStyleSheet("color: #94a3b8;")
            box_gcam.layout().addWidget(lbl_gcam_desc)

            lbl_gcam_img = QLabel()
            lbl_gcam_img.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl_gcam_img.setPixmap(np_to_qpixmap(r.grad_cam_overlay, 320))
            lbl_gcam_img.setStyleSheet("border: 1px solid #334155; border-radius: 4px; padding: 4px;")
            box_gcam.layout().addWidget(lbl_gcam_img)
            self.right_layout.addWidget(box_gcam)

        # --- ENSEMBLE MULTI-MODELO (IA Pré-Treinada) ---
        if r.ensemble_classification:
            box_ens = self._make_group("ENSEMBLE MULTI-MODELO (IA Pré-Treinada)")
            ec = r.ensemble_classification

            # Classe principal
            ens_name = ec.get("class_name", "N/A")
            ens_conf = ec.get("confidence", 0)
            ens_color = "#22c55e" if ens_conf >= 0.7 else ("#fbbf24" if ens_conf >= 0.4 else "#ef4444")

            lbl_ens = QLabel(ens_name)
            lbl_ens.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
            lbl_ens.setStyleSheet(f"color: {ens_color}; padding: 4px 0;")
            box_ens.layout().addWidget(lbl_ens)

            # Confiança + agreement
            conf_row = QWidget()
            cr = QHBoxLayout(conf_row)
            cr.setContentsMargins(0, 2, 0, 2)
            cr.addWidget(self._styled_label("Confiança ensemble:", "#94a3b8", 10))
            cr.addWidget(self._styled_label(f"{ens_conf:.1%}", ens_color, 11, bold=True))
            cr.addStretch()
            box_ens.layout().addWidget(conf_row)

            # Agreement
            if r.ensemble_agreement:
                agr = r.ensemble_agreement
                agr_score = agr.get("agreement_score", 0)
                agr_icon = "Concordam" if agr.get("models_agree") else "Divergem"
                agr_color = "#22c55e" if agr.get("models_agree") else "#fbbf24"

                agr_row = QWidget()
                al = QHBoxLayout(agr_row)
                al.setContentsMargins(0, 2, 0, 2)
                al.addWidget(self._styled_label(f"Modelos: {agr_icon} ({agr_score:.0%})", agr_color, 10))
                al.addStretch()
                box_ens.layout().addWidget(agr_row)

                # Predições individuais
                indiv = agr.get("individual_predictions", {})
                if indiv:
                    box_ens.layout().addWidget(self._styled_label("Predições por modelo:", "#64748b", 9))
                    for model_name, pred_cls in indiv.items():
                        row = QWidget()
                        rl = QHBoxLayout(row)
                        rl.setContentsMargins(8, 0, 0, 0)
                        rl.addWidget(self._styled_label(f"• {model_name}:", "#94a3b8", 9))
                        rl.addWidget(self._styled_label(pred_cls, "#e2e8f0", 9, bold=True))
                        rl.addStretch()
                        box_ens.layout().addWidget(row)

            # Modelos carregados
            if r.ensemble_models_loaded:
                loaded_str = ", ".join(
                    f"{k}={'OK' if v else 'OFF'}" for k, v in r.ensemble_models_loaded.items()
                )
                box_ens.layout().addWidget(self._styled_label(f"Modelos: {loaded_str}", "#475569", 8))

            # Probabilidades
            all_probs = ec.get("all_probabilities", {})
            if all_probs:
                box_ens.layout().addWidget(self._styled_label("Probabilidades:", "#64748b", 9))
                etiology_names = {
                    0: "Úlcera Venosa", 1: "Úlcera Arterial", 2: "Pé Diabético",
                    3: "Lesão por Pressão", 4: "Ferida Cirúrgica"
                }
                sorted_probs = sorted(all_probs.items(), key=lambda x: x[1], reverse=True)
                for cid_str, prob in sorted_probs:
                    cid = int(cid_str) if isinstance(cid_str, str) else cid_str
                    name = etiology_names.get(cid, f"Classe {cid}")
                    p_color = "#22c55e" if prob >= 0.3 else "#94a3b8"
                    row = QWidget()
                    rl = QHBoxLayout(row)
                    rl.setContentsMargins(8, 0, 0, 0)
                    rl.addWidget(self._styled_label(f"• {name}", "#94a3b8", 9))
                    rl.addStretch()
                    rl.addWidget(self._styled_label(f"{prob:.1%}", p_color, 9))
                    box_ens.layout().addWidget(row)

            self.right_layout.addWidget(box_ens)

        # --- ANALISE DE INFECCAO E GRAVIDADE (BiomedCLIP) ---
        if r.ensemble_infection or r.ensemble_severity is not None:
            box_inf = self._make_group("ANALISE DE INFECCAO E GRAVIDADE")

            # Severidade
            if r.ensemble_severity is not None:
                sev = r.ensemble_severity
                if sev < 0.25:
                    sev_text, sev_color = "Leve", "#22c55e"
                elif sev < 0.50:
                    sev_text, sev_color = "Moderada", "#fbbf24"
                elif sev < 0.75:
                    sev_text, sev_color = "Grave", "#f97316"
                else:
                    sev_text, sev_color = "Crítica", "#ef4444"

                sev_row = QWidget()
                sl = QHBoxLayout(sev_row)
                sl.setContentsMargins(0, 2, 0, 2)
                sl.addWidget(self._styled_label("Gravidade:", "#94a3b8", 10))
                sl.addWidget(self._styled_label(f"{sev_text} ({sev:.0%})", sev_color, 11, bold=True))
                sl.addStretch()
                box_inf.layout().addWidget(sev_row)

            # Infecção
            if r.ensemble_infection:
                inf_scores = r.ensemble_infection
                infected = inf_scores.get("Infectada", 0) + inf_scores.get("Celulite", 0)
                clean = inf_scores.get("Limpa", 0)
                risk = infected / (infected + clean + 1e-8)

                if risk >= 0.6:
                    risk_text, risk_color = "ALTO", "#ef4444"
                elif risk >= 0.35:
                    risk_text, risk_color = "MODERADO", "#fbbf24"
                else:
                    risk_text, risk_color = "BAIXO", "#22c55e"

                inf_row = QWidget()
                il = QHBoxLayout(inf_row)
                il.setContentsMargins(0, 2, 0, 2)
                il.addWidget(self._styled_label("Risco de infecção:", "#94a3b8", 10))
                il.addWidget(self._styled_label(f"{risk_text} ({risk:.0%})", risk_color, 11, bold=True))
                il.addStretch()
                box_inf.layout().addWidget(inf_row)

                if risk >= 0.6:
                    alert = QLabel("ALERTA: Sinais de infecção detectados — encaminhar para avaliação")
                    alert.setWordWrap(True)
                    alert.setFont(QFont("Segoe UI", 9))
                    alert.setStyleSheet("color: #ef4444; padding-top: 4px;")
                    box_inf.layout().addWidget(alert)

                # Scores individuais
                box_inf.layout().addWidget(self._styled_label("Detalhes:", "#475569", 8))
                for lbl, sc in inf_scores.items():
                    row = QWidget()
                    rl = QHBoxLayout(row)
                    rl.setContentsMargins(8, 0, 0, 0)
                    rl.addWidget(self._styled_label(f"• {lbl}", "#94a3b8", 8))
                    rl.addStretch()
                    rl.addWidget(self._styled_label(f"{sc:.0%}", "#64748b", 8))
                    box_inf.layout().addWidget(row)

            self.right_layout.addWidget(box_inf)

        # --- ANÁLISE DE BORDAS ---
        if r.border_analysis:
            box_border = self._make_group("ANALISE DE BORDAS E PERILESAO")
            ba = r.border_analysis

            flags = []
            if ba.maceration:
                flags.append(("Maceração perilesional", "#fbbf24"))
            if ba.inflammation:
                flags.append(("Inflamação perilesional", "#ef4444"))
            if not ba.regular_borders:
                flags.append(("Bordas irregulares", "#f97316"))
            if not flags:
                flags.append(("Sem alterações perilesionais", "#22c55e"))

            for text, color in flags:
                box_border.layout().addWidget(self._styled_label(text, color, 10))

            lbl_desc = QLabel(ba.description)
            lbl_desc.setWordWrap(True)
            lbl_desc.setFont(QFont("Segoe UI", 9))
            lbl_desc.setStyleSheet("color: #94a3b8; padding-top: 4px;")
            box_border.layout().addWidget(lbl_desc)
            self.right_layout.addWidget(box_border)

        # --- ACOES CLINICAS ---
        box_actions = self._make_group("RECOMENDACOES CLINICAS")
        dominant = max(r.tissues, key=lambda x: x.percentage)
        lbl_act = QLabel(dominant.clinical_action)
        lbl_act.setWordWrap(True)
        lbl_act.setFont(QFont("Segoe UI", 10))
        lbl_act.setStyleSheet("color: #cbd5e1; padding: 4px 0;")
        box_actions.layout().addWidget(lbl_act)

        for t in r.tissues:
            if t.percentage > 10 and t.name != dominant.name:
                lbl_sec = QLabel(f"{t.name}: {t.clinical_action}")
                lbl_sec.setWordWrap(True)
                lbl_sec.setFont(QFont("Segoe UI", 9))
                lbl_sec.setStyleSheet("color: #94a3b8; padding: 2px 0 2px 8px;")
                box_actions.layout().addWidget(lbl_sec)

        self.right_layout.addWidget(box_actions)

        # --- ESCALAS CLÍNICAS (PUSH/BWAT) ---
        if r.push_score or r.bwat_score:
            box_scales = self._make_group("ESCALAS CLÍNICAS")
            
            # PUSH Score
            if r.push_score:
                push = r.push_score
                push_total = push.get("total_score", 0)
                push_color = "#22c55e" if push_total <= 5 else ("#fbbf24" if push_total <= 10 else "#ef4444")
                
                push_row = QWidget()
                pl = QHBoxLayout(push_row)
                pl.setContentsMargins(0, 2, 0, 2)
                pl.addWidget(self._styled_label("PUSH Score:", "#94a3b8", 10))
                pl.addWidget(self._styled_label(f"{push_total}/17", push_color, 11, bold=True))
                pl.addStretch()
                box_scales.layout().addWidget(push_row)
                
                # Detalhes PUSH
                push_details = f"Área: {push.get('area_score', 0)} | Exsudato: {push.get('exudate_score', 0)} | Tecido: {push.get('tissue_score', 0)}"
                lbl_push_det = QLabel(push_details)
                lbl_push_det.setFont(QFont("Segoe UI", 8))
                lbl_push_det.setStyleSheet("color: #64748b;")
                box_scales.layout().addWidget(lbl_push_det)
                
                # Interpretação PUSH
                lbl_push_int = QLabel(push.get("interpretation", ""))
                lbl_push_int.setWordWrap(True)
                lbl_push_int.setFont(QFont("Segoe UI", 9))
                lbl_push_int.setStyleSheet(f"color: {push_color}; padding: 2px 0;")
                box_scales.layout().addWidget(lbl_push_int)
            
            # BWAT Score
            if r.bwat_score:
                bwat = r.bwat_score
                bwat_total = bwat.get("total_score", 0)
                severity = bwat.get("severity", "")
                
                # Cor baseada na severidade
                severity_colors = {
                    "LEVE": "#22c55e",
                    "MODERADA": "#fbbf24",
                    "GRAVE": "#f97316",
                    "CRÍTICA": "#ef4444",
                }
                bwat_color = severity_colors.get(severity, "#94a3b8")
                
                bwat_row = QWidget()
                bl = QHBoxLayout(bwat_row)
                bl.setContentsMargins(0, 6, 0, 2)
                bl.addWidget(self._styled_label("BWAT Score:", "#94a3b8", 10))
                bl.addWidget(self._styled_label(f"{bwat_total}/65", bwat_color, 11, bold=True))
                bl.addWidget(self._styled_label(f"({severity})", bwat_color, 9))
                bl.addStretch()
                box_scales.layout().addWidget(bwat_row)
                
                # Itens auto-preenchidos vs pendentes
                auto_count = len(bwat.get("auto_filled", {}))
                manual_count = len(bwat.get("manual_filled", {}))
                pending = 13 - auto_count - manual_count
                
                fill_text = f"Auto: {auto_count} | Manual: {manual_count}"
                if pending > 0:
                    fill_text += f" | Pendente: {pending}"
                lbl_fill = QLabel(fill_text)
                lbl_fill.setFont(QFont("Segoe UI", 8))
                lbl_fill.setStyleSheet("color: #64748b;")
                box_scales.layout().addWidget(lbl_fill)
            
            self.right_layout.addWidget(box_scales)

        # --- ANÁLISE DE IMAGEM (Iluminação e Parte do Corpo) ---
        if r.lighting_analysis or r.body_part:
            box_img_analysis = self._make_group("ANÁLISE DE IMAGEM")
            
            # Análise de iluminação
            if r.lighting_analysis:
                lighting = r.lighting_analysis
                condition = lighting.get("condition", "unknown")
                quality = lighting.get("quality_score", 0)
                
                # Cor baseada na qualidade
                qual_color = "#22c55e" if quality >= 0.7 else ("#fbbf24" if quality >= 0.4 else "#ef4444")
                
                # Linha de qualidade
                qual_row = QWidget()
                ql = QHBoxLayout(qual_row)
                ql.setContentsMargins(0, 2, 0, 2)
                ql.addWidget(self._styled_label("Qualidade:", "#94a3b8", 9))
                ql.addWidget(self._styled_label(f"{quality:.0%}", qual_color, 10, bold=True))
                ql.addStretch()
                box_img_analysis.layout().addWidget(qual_row)
                
                # Condição de iluminação
                condition_names = {
                    "optimal": "Ideal",
                    "underexposed": "Subexposta",
                    "overexposed": "Superexposta",
                    "uneven": "Irregular",
                    "warm": "Luz quente",
                    "cool": "Luz fria",
                    "flash": "Flash detectado",
                }
                cond_text = condition_names.get(condition, condition)
                
                cond_row = QWidget()
                cl = QHBoxLayout(cond_row)
                cl.setContentsMargins(0, 1, 0, 1)
                cl.addWidget(self._styled_label("Iluminação:", "#94a3b8", 9))
                cl.addWidget(self._styled_label(cond_text, "#e2e8f0", 9))
                cl.addStretch()
                box_img_analysis.layout().addWidget(cond_row)
                
                # Temperatura de cor
                temp_k = lighting.get("color_temperature_k", 5500)
                temp_row = QWidget()
                tl = QHBoxLayout(temp_row)
                tl.setContentsMargins(0, 1, 0, 1)
                tl.addWidget(self._styled_label("Temp. cor:", "#94a3b8", 9))
                tl.addWidget(self._styled_label(f"{temp_k}K", "#e2e8f0", 9))
                tl.addStretch()
                box_img_analysis.layout().addWidget(temp_row)
                
                # Correções aplicadas
                if r.image_corrections:
                    corrections_text = ", ".join(r.image_corrections.keys())
                    corr_row = QWidget()
                    crl = QHBoxLayout(corr_row)
                    crl.setContentsMargins(0, 1, 0, 1)
                    crl.addWidget(self._styled_label("Correções:", "#94a3b8", 9))
                    crl.addWidget(self._styled_label(corrections_text[:30], "#22c55e", 9))
                    crl.addStretch()
                    box_img_analysis.layout().addWidget(corr_row)
            
            # Detecção de parte do corpo
            if r.body_part:
                body = r.body_part
                region_name = body.get("name_pt", "Desconhecido")
                confidence = body.get("confidence", 0)
                is_pressure = body.get("is_pressure_point", False)
                is_reliable = body.get("is_reliable", True)
                reliability_note = body.get("reliability_note", "")
                
                # Separador visual
                sep = QWidget()
                sep.setFixedHeight(6)
                box_img_analysis.layout().addWidget(sep)
                
                # Região anatômica
                body_row = QWidget()
                bl = QHBoxLayout(body_row)
                bl.setContentsMargins(0, 2, 0, 2)
                bl.addWidget(self._styled_label("Região:", "#94a3b8", 9))
                body_color = "#38bdf8" if is_reliable else "#fbbf24"
                bl.addWidget(self._styled_label(region_name, body_color, 10, bold=True))
                bl.addWidget(self._styled_label(f"({confidence:.0%})", "#64748b", 8))
                bl.addStretch()
                box_img_analysis.layout().addWidget(body_row)

                if not is_reliable and reliability_note:
                    warn_row = QWidget()
                    wl = QHBoxLayout(warn_row)
                    wl.setContentsMargins(0, 1, 0, 1)
                    wl.addWidget(self._styled_label("Atenção", "#f97316", 9, bold=True))
                    wl.addWidget(self._styled_label(reliability_note[:48], "#f97316", 8))
                    wl.addStretch()
                    box_img_analysis.layout().addWidget(warn_row)
                
                # Ponto de pressão
                if is_pressure:
                    press_row = QWidget()
                    pl = QHBoxLayout(press_row)
                    pl.setContentsMargins(0, 1, 0, 1)
                    pl.addWidget(self._styled_label("Ponto de pressão", "#f97316", 9))
                    pl.addStretch()
                    box_img_analysis.layout().addWidget(press_row)
                
                # Feridas comuns na região
                common = body.get("common_wounds", [])
                if common:
                    common_text = ", ".join(common[:3])
                    common_row = QWidget()
                    cwl = QHBoxLayout(common_row)
                    cwl.setContentsMargins(0, 1, 0, 1)
                    cwl.addWidget(self._styled_label("Típico:", "#94a3b8", 8))
                    cwl.addWidget(self._styled_label(common_text[:35], "#64748b", 8))
                    cwl.addStretch()
                    box_img_analysis.layout().addWidget(common_row)
            
            self.right_layout.addWidget(box_img_analysis)

        # --- METADADOS ---
        box_meta = self._make_group("METADADOS")
        dl_status = "Ativo (TTA)" if r.dl_prediction else "Não disponível"
        resnet_status = "ResNet50 Two-Stage (TTA + Grad-CAM)" if r.resnet_prediction else "Não disponível"
        pipeline_desc = "Detecção → Segm. HSV+LAB → Textura → ResNet50 → Grad-CAM"
        meta_items = [
            ("Área da ferida", f"{r.wound_area_px:,} px"),
            ("Tempo de processamento", f"{r.processing_time_ms:.0f} ms"),
            ("Pipeline", pipeline_desc),
            ("Segmentação", "Multi-espaço (HSV 60% + LAB 40%) + Textura"),
            ("Classificação DL", dl_status),
            ("Etiologia ResNet50", resnet_status),
            ("Explicabilidade", "Grad-CAM (layer4 ResNet50)"),
            ("Versão", "HEAL+ v3.0 — ResNet50 Two-Stage + Grad-CAM"),
        ]
        for k, v in meta_items:
            row = QWidget()
            rl = QHBoxLayout(row)
            rl.setContentsMargins(0, 1, 0, 1)
            rl.addWidget(self._styled_label(k, "#64748b", 9))
            rl.addStretch()
            rl.addWidget(self._styled_label(v, "#94a3b8", 9))
            box_meta.layout().addWidget(row)

        self.right_layout.addWidget(box_meta)

        # --- ANALISE DE ILUMINACAO ---
        if r.lighting_analysis:
            box_light = self._make_group("ILUMINACAO")
            la = r.lighting_analysis
            
            # Condição de iluminação
            condition = la.get("condition", "unknown")
            cond_colors = {
                "optimal": "#22c55e",
                "underexposed": "#ef4444",
                "overexposed": "#fbbf24",
                "uneven": "#f97316",
                "warm": "#fbbf24",
                "cool": "#3b82f6",
                "flash": "#f97316",
            }
            cond_color = cond_colors.get(condition, "#94a3b8")
            cond_names = {
                "optimal": "Adequada",
                "underexposed": "Subexposta",
                "overexposed": "Superexposta",
                "uneven": "Irregular",
                "warm": "Luz Quente",
                "cool": "Luz Fria",
                "flash": "Flash Detectado",
            }
            cond_name = cond_names.get(condition, condition)
            
            cond_row = QWidget()
            cl = QHBoxLayout(cond_row)
            cl.setContentsMargins(0, 2, 0, 2)
            cl.addWidget(self._styled_label("Condição:", "#94a3b8", 9))
            cl.addWidget(self._styled_label(cond_name, cond_color, 10, bold=True))
            cl.addStretch()
            box_light.layout().addWidget(cond_row)
            
            # Score de qualidade
            quality = la.get("quality_score", 0)
            q_color = "#22c55e" if quality >= 0.7 else ("#fbbf24" if quality >= 0.4 else "#ef4444")
            q_row = QWidget()
            ql = QHBoxLayout(q_row)
            ql.setContentsMargins(0, 1, 0, 1)
            ql.addWidget(self._styled_label("Qualidade:", "#94a3b8", 9))
            ql.addWidget(self._styled_label(f"{quality:.0%}", q_color, 10, bold=True))
            ql.addStretch()
            box_light.layout().addWidget(q_row)
            
            # Correções aplicadas
            if r.image_corrections:
                corr_text = ", ".join(r.image_corrections.keys())
                lbl_corr = QLabel(f"Correções: {corr_text}")
                lbl_corr.setFont(QFont("Segoe UI", 8))
                lbl_corr.setStyleSheet("color: #64748b;")
                box_light.layout().addWidget(lbl_corr)
            
            self.right_layout.addWidget(box_light)

        # --- PARTE DO CORPO ---
        if r.body_part:
            box_body = self._make_group("REGIAO ANATOMICA")
            bp = r.body_part
            
            region_name = bp.get("name_pt", "Não identificado")
            confidence = bp.get("confidence", 0)
            is_pressure = bp.get("is_pressure_point", False)
            is_reliable = bp.get("is_reliable", True)
            reliability_note = bp.get("reliability_note", "")
            
            # Nome da região
            bp_color = "#38bdf8" if is_reliable else "#fbbf24"
            bp_row = QWidget()
            bl = QHBoxLayout(bp_row)
            bl.setContentsMargins(0, 2, 0, 2)
            bl.addWidget(self._styled_label(region_name, bp_color, 11, bold=True))
            if confidence > 0:
                bl.addWidget(self._styled_label(f"({confidence:.0%})", "#64748b", 9))
            bl.addStretch()
            box_body.layout().addWidget(bp_row)

            if not is_reliable and reliability_note:
                lbl_rel = QLabel(reliability_note)
                lbl_rel.setWordWrap(True)
                lbl_rel.setFont(QFont("Segoe UI", 8))
                lbl_rel.setStyleSheet("color: #f97316;")
                box_body.layout().addWidget(lbl_rel)
            
            # Ponto de pressão
            if is_pressure:
                lbl_press = QLabel("Ponto de pressão - risco de LPP")
                lbl_press.setFont(QFont("Segoe UI", 9))
                lbl_press.setStyleSheet("color: #f97316;")
                box_body.layout().addWidget(lbl_press)
            
            # Feridas comuns nesta região
            common = bp.get("common_wounds", [])
            if common:
                common_text = ", ".join(w.replace("_", " ").title() for w in common[:3])
                lbl_common = QLabel(f"Etiologias comuns: {common_text}")
                lbl_common.setFont(QFont("Segoe UI", 8))
                lbl_common.setStyleSheet("color: #64748b;")
                lbl_common.setWordWrap(True)
                box_body.layout().addWidget(lbl_common)
            
            self.right_layout.addWidget(box_body)

        self.right_layout.addStretch()

    # -------------------------------------------------------
    # HELPERS
    # -------------------------------------------------------
    def _make_group(self, title: str) -> QGroupBox:
        box = QGroupBox(title)
        box.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        box.setStyleSheet("""
            QGroupBox {
                background: #1e293b;
                border: 1px solid #334155;
                border-radius: 8px;
                margin-top: 12px;
                padding: 16px 12px 10px;
                color: #94a3b8;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 1px 6px;
                color: #94a3b8;
                text-transform: uppercase;
                letter-spacing: 1px;
            }
        """)
        layout = QVBoxLayout()
        layout.setSpacing(6)
        box.setLayout(layout)
        return box

    def _styled_label(self, text: str, color: str, size: int, bold: bool = False) -> QLabel:
        lbl = QLabel(text)
        weight = QFont.Weight.Bold if bold else QFont.Weight.Normal
        lbl.setFont(QFont("Segoe UI", size, weight))
        lbl.setStyleSheet(f"color: {color};")
        return lbl

    def _clear_right_panel(self):
        while self.right_layout.count():
            w = self.right_layout.takeAt(0).widget()
            if w:
                w.deleteLater()

    def closeEvent(self, event):
        """Encerramento seguro: para todas as threads antes de fechar."""
        logger.info("[HEAL+] Finalizando componentes com segurança...")

        # Para thread de evolucao por fotos (se existir)
        if self._progression_thread is not None:
            try:
                self._progression_thread.result_ready.disconnect()
                self._progression_thread.progress.disconnect()
            except (TypeError, RuntimeError):
                pass
            if self._progression_thread.isRunning():
                if not self._progression_thread.wait(5000):
                    self._progression_thread.terminate()
                    self._progression_thread.wait(1000)
            self._progression_thread = None

        # Para thread de análise de imagem estática (se existir)
        if self._thread is not None:
            try:
                self._thread.result_ready.disconnect()
                self._thread.progress.disconnect()
            except (TypeError, RuntimeError):
                pass
            if self._thread.isRunning():
                if not self._thread.wait(5000):
                    self._thread.terminate()
                    self._thread.wait(1000)
            self._thread = None

        # Processa eventos pendentes (deleteLater, etc.) várias vezes
        # para garantir que objetos sejam destruídos corretamente
        for _ in range(3):
            QApplication.processEvents()

        logger.info("[HEAL+] Encerramento concluído.")
        event.accept()


# ============================================================
# MAIN
# ============================================================

def main():
    # Garante UTF-8 no Qt
    import locale
    try:
        locale.setlocale(locale.LC_ALL, '')
    except locale.Error:
        pass
    
    # Força UTF-8 em variável de ambiente para Qt
    os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
    os.environ.setdefault('QT_QPA_PLATFORM_PLUGIN_PATH', '')
    
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    window = HealAnalyzerApp()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
