# -*- coding: utf-8 -*-
"""Headless clinical wound analyzer shared by API and desktop runtime.

This module is a transitional extraction from heal_analyzer.py. It keeps the
analysis engine importable without PyQt6 so backend code can run headless.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

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
        pos: PosiÃ§Ã£o (x, y) do canto superior esquerdo
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
# MÃ³dulos do projeto
# ============================================================
from src.processing.wound_detector_cv import WoundDetectorCV, DetectionMethod
from src.processing.tissue_analyzer import TissueAnalyzerCV, TissueType, TISSUE_COLORS
from src.processing.wound_classifier_cv import WoundClassifierCV

logger = logging.getLogger(__name__)

# Escalas clÃ­nicas validadas
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

# MÃ³dulos avanÃ§ados de processamento de imagem
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

# Classificador ResNet50 de dois estÃ¡gios (do notebook de treinamento)
try:
    from src.diagnosis.resnet_wound_classifier import (
        TwoStageWoundClassifier, TwoStageResult, GradCAM,
        create_two_stage_classifier, WOUND_TYPE_PT,
        WOUND_CLINICAL_ACTIONS, WOUND_TO_ETIOLOGY,
    )
    HAS_RESNET_CLASSIFIER = True
except ImportError:
    HAS_RESNET_CLASSIFIER = False


# ============================================================
# TAXONOMIA CLÃNICA â€” Estomaterapia
# ============================================================

@dataclass
class TissueClassification:
    """ClassificaÃ§Ã£o tecidual clÃ­nica."""
    name: str
    name_en: str
    percentage: float
    color_bgr: Tuple[int, int, int]
    color_hex: str
    description: str
    clinical_action: str


@dataclass
class BorderAnalysis:
    """AnÃ¡lise das bordas da ferida."""
    maceration: bool
    inflammation: bool
    regular_borders: bool
    description: str


@dataclass
class ClinicalReport:
    """Laudo clÃ­nico completo."""
    is_valid_wound: bool
    rejection_reason: str = ""

    # ClassificaÃ§Ã£o principal
    primary_tissue: str = ""
    primary_justification: str = ""

    # Tecidos identificados
    tissues: List[TissueClassification] = field(default_factory=list)

    # Bordas
    border_analysis: Optional[BorderAnalysis] = None

    # MÃ©tricas
    wound_area_px: int = 0
    health_score: float = 0.0
    processing_time_ms: float = 0.0

    # Deep Learning prediction (quando disponÃ­vel)
    dl_prediction: Optional[Dict] = None

    # ClassificaÃ§Ã£o ResNet50 dois estÃ¡gios (Normal/Ferida + Tipo)
    resnet_prediction: Optional[Dict] = None
    grad_cam_overlay: Optional[np.ndarray] = None

    # Escalas clÃ­nicas (PUSH, BWAT) - calculadas automaticamente
    push_score: Optional[Dict] = None
    bwat_score: Optional[Dict] = None

    # AnÃ¡lise de iluminaÃ§Ã£o (quando disponÃ­vel)
    lighting_analysis: Optional[Dict] = None
    image_corrections: Optional[Dict] = None
    
    # DetecÃ§Ã£o de parte do corpo (quando disponÃ­vel)
    body_part: Optional[Dict] = None

    # Zonas espaciais da ferida (periferia, core, anel externo)
    wound_zones: Optional[Dict] = None

    # Ensemble Multi-Modelo (camada adicional de IA prÃ©-treinada)
    ensemble_classification: Optional[Dict] = None
    ensemble_agreement: Optional[Dict] = None
    ensemble_infection: Optional[Dict] = None
    ensemble_severity: Optional[float] = None
    ensemble_models_loaded: Optional[Dict] = None

    # Imagens processadas
    original: Optional[np.ndarray] = None
    detection_overlay: Optional[np.ndarray] = None
    segmentation_map: Optional[np.ndarray] = None
    tissue_overlay: Optional[np.ndarray] = None


# DefiniÃ§Ã£o clÃ­nica dos tecidos
CLINICAL_TISSUES = {
    "necrosis": {
        "name": "Necrose de CoagulaÃ§Ã£o (Escara)",
        "name_en": "Coagulation Necrosis (Eschar)",
        "color_bgr": (30, 30, 60),
        "color_hex": "#3C1E1E",
        "description": (
            "Tecido preto ou marrom-escuro, endurecido, seco ou Ãºmido (couro), "
            "que indica morte celular por falta de suprimento sanguÃ­neo. "
            "Pode estar aderido ou solto no leito da ferida."
        ),
        "clinical_action": (
            "Necessita de desbridamento (autolÃ­tico, enzimÃ¡tico, instrumental ou cirÃºrgico) "
            "para remoÃ§Ã£o do tecido desvitalizado e promoÃ§Ã£o da cicatrizaÃ§Ã£o."
        ),
    },
    "slough": {
        "name": "Esfacelo (Fibrina)",
        "name_en": "Slough (Fibrin)",
        "color_bgr": (80, 220, 220),
        "color_hex": "#DCC850",
        "description": (
            "Tecido amarelado, esbranquiÃ§ado ou acinzentado, de consistÃªncia viscosa "
            "ou fibrosa, que adere ao leito da ferida. Composto por fibrina, "
            "leucÃ³citos, bactÃ©rias e restos celulares."
        ),
        "clinical_action": (
            "Avaliar necessidade de desbridamento autolÃ­tico (hidrogel) ou enzimÃ¡tico. "
            "Manter o leito Ãºmido para facilitar a remoÃ§Ã£o fisiolÃ³gica."
        ),
    },
    "granulation": {
        "name": "Tecido de GranulaÃ§Ã£o",
        "name_en": "Granulation Tissue",
        "color_bgr": (60, 60, 220),
        "color_hex": "#DC3C3C",
        "description": (
            "Tecido vermelho vivo/brilhante, Ãºmido, com aspecto granulado ('em amora'). "
            "Rico em neovasos e fibroblastos, indicando processo de cicatrizaÃ§Ã£o ativo "
            "na fase proliferativa."
        ),
        "clinical_action": (
            "Proteger o tecido neoformado. Utilizar coberturas que mantenham meio Ãºmido "
            "(espuma, alginato, hidrofibra). Evitar trauma na troca de curativos."
        ),
    },
    "epithelialization": {
        "name": "EpitelizaÃ§Ã£o",
        "name_en": "Epithelialization",
        "color_bgr": (200, 180, 255),
        "color_hex": "#FFB4C8",
        "description": (
            "Tecido rosa claro ou translÃºcido que avanÃ§a das bordas para o centro "
            "da ferida, selando a superfÃ­cie. Indica fase final da cicatrizaÃ§Ã£o "
            "com migraÃ§Ã£o de queratinÃ³citos."
        ),
        "clinical_action": (
            "Proteger o epitÃ©lio neoformado com coberturas nÃ£o aderentes. "
            "Evitar qualquer trauma. Monitorar fechamento completo."
        ),
    },
}

# ============================================================
# INTERVALOS CLÃNICOS REFINADOS v2 â€” Multi-espaÃ§o de cor
# ============================================================
# HSV: matiz-saturaÃ§Ã£o-valor (boa discriminaÃ§Ã£o de cores puras)
# LAB: luminosidade-a*-b* (boa separaÃ§Ã£o perceptual, eixo a*=vermelho/verde)
# YCrCb: luminÃ¢ncia-crominÃ¢ncia (boa para detecÃ§Ã£o de pele/tecido)

CLINICAL_HSV_RANGES = {
    "necrosis": [
        # 1. Preto/muito escuro â€” V â‰¤ 40, exceto azul/verde cirÃºrgico
        (np.array([0, 0, 0]), np.array([80, 255, 40])),
        (np.array([140, 0, 0]), np.array([180, 255, 40])),
        # 2. Marrom escuro necrÃ³tico â€” tom marrom (H 5-25), V 15-60
        #    S â‰¥ 25 para separar de cinza acromÃ¡tico
        (np.array([5, 25, 15]), np.array([25, 200, 60])),
        # 3. Escara seca acromÃ¡tica â€” S < 30, V < 50
        (np.array([0, 5, 5]), np.array([180, 30, 50])),
        # 4. Marrom acinzentado (necrose Ãºmida) â€” H 8-30, S moderada
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
        # Vermelho vivo intenso â€” S â‰¥ 130 (requer alta saturaÃ§Ã£o)
        (np.array([0, 130, 90]), np.array([10, 255, 255])),
        (np.array([165, 130, 90]), np.array([180, 255, 255])),
        # Vermelho moderado â€” S â‰¥ 100 (mais restrito para nÃ£o pegar pele/epi)
        (np.array([0, 100, 110]), np.array([8, 220, 255])),
        (np.array([170, 100, 110]), np.array([180, 220, 255])),
        # Vermelho escuro (granulaÃ§Ã£o madura) â€” S â‰¥ 110
        (np.array([0, 110, 60]), np.array([10, 255, 150])),
        (np.array([162, 110, 60]), np.array([180, 255, 150])),
    ],
    "epithelialization": [
        # Rosa claro â€” S baixa (15-50), V alta (â‰¥ 190)
        (np.array([0, 15, 190]), np.array([10, 50, 255])),
        (np.array([165, 15, 190]), np.array([180, 50, 255])),
        # Rosa pÃ¡lido quase branco â€” S muito baixa
        (np.array([0, 8, 210]), np.array([8, 35, 255])),
        (np.array([168, 8, 210]), np.array([180, 35, 255])),
    ],
}

# Intervalos no espaÃ§o LAB para refinamento
# L: luminosidade (0=preto, 255=branco)
# A: verde(-) â†’ vermelho(+)
# B: azul(-) â†’ amarelo(+)
CLINICAL_LAB_RANGES = {
    "necrosis": [
        # Muito escuro com crominÃ¢ncia neutra (escara/necrose)
        # L < 45 â€” pele escura saudÃ¡vel geralmente L > 50
        (np.array([0, 100, 100]), np.array([45, 150, 150])),
        # Marrom necrÃ³tico (L baixo-mÃ©dio, a+/b+ moderados)
        (np.array([10, 128, 120]), np.array([55, 165, 165])),
        # Necrose Ãºmida/esverdeada (L baixo, b desviado)
        (np.array([5, 120, 105]), np.array([40, 145, 135])),
    ],
    "slough": [
        # Amarelo claro (L alto, b muito positivo)
        (np.array([150, 110, 150]), np.array([240, 140, 200])),
        # Bege/branco-amarelado
        (np.array([170, 118, 135]), np.array([250, 135, 165])),
    ],
    "granulation": [
        # Vermelho (a muito positivo, L mÃ©dio)
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
# MOTOR DE ANÃLISE CLÃNICA
# ============================================================

class ClinicalWoundAnalyzer:
    """
    Motor de anÃ¡lise clÃ­nica de feridas v2.

    Atua como especialista em Estomaterapia â€” classifica texturas
    segundo a taxonomia de tecidos viÃ¡veis e inviÃ¡veis, analisa
    bordas/perilesÃ£o e gera laudo tÃ©cnico.

    v2: Multi-espaÃ§o de cor (HSV + LAB), textura LBP, modelo DL
    integrado (quando disponÃ­vel), calibraÃ§Ã£o de confianÃ§a.
    """

    MIN_WOUND_AREA_RATIO = 0.005   # MÃ­nimo 0.5% da imagem
    MAX_SKIN_RATIO = 0.97          # Se > 97% for pele â†’ invÃ¡lido

    # Escala de Fitzpatrick aproximada por luminosidade LAB
    # Usada para adaptar limiares de necrose ao tom de pele do paciente
    FITZPATRICK_L_THRESHOLDS = {
        # L mÃ©dio do periwound -> Fitzpatrick aproximado
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

        # Classificador ResNet50 de dois estÃ¡gios (do notebook)
        self._resnet_classifier = None
        self._resnet_available = False
        self._load_resnet_classifier()

        # Ensemble Multi-Modelo (camada adicional de IA prÃ©-treinada)
        self._ensemble = None
        self._ensemble_available = False
        self._load_ensemble()

    def _load_resnet_classifier(self):
        """Carrega o classificador ResNet50 de dois estÃ¡gios."""
        if not HAS_RESNET_CLASSIFIER:
            print("[HEAL+] MÃ³dulo ResNet50 nÃ£o disponÃ­vel")
            return
        try:
            self._resnet_classifier = create_two_stage_classifier()
            self._resnet_available = self._resnet_classifier.available
            if self._resnet_available:
                status = self._resnet_classifier.get_status()
                print(f"[HEAL+] ResNet50 Two-Stage: S1={status['stage1_available']}, S2={status['stage2_available']} ({status['device']})")
            else:
                print("[HEAL+] ResNet50: Modelos nÃ£o encontrados (classificaÃ§Ã£o por heurÃ­stica)")
        except Exception as e:
            print(f"[HEAL+] Erro ao carregar ResNet50: {e}")
            self._resnet_available = False

    def _load_dl_model(self):
        """Tenta carregar modelo DL treinado (PyTorch) para classificaÃ§Ã£o."""
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
                        # state_dict â€” needs metadata to reconstruct model
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
            self._ensemble_available = True
            loaded = sum(1 for v in status.values() if v)
            print(f"[HEAL+] Ensemble multi-modelo: {loaded}/3 modelos ({status})")
        except Exception as e:
            print(f"[HEAL+] Ensemble indisponÃ­vel: {e}")
            self._ensemble_available = False

    def _predict_ensemble(
        self,
        image: np.ndarray,
        detections=None,
        dl_probs: Optional[Dict[int, float]] = None,
        wound_mask: Optional[np.ndarray] = None,
    ) -> Optional[Dict]:
        """PrediÃ§Ã£o via ensemble multi-modelo (quando disponÃ­vel).

        Args:
            image: imagem BGR
            detections: lista de detecÃ§Ãµes (com bbox)
            dl_probs: probabilidades do modelo DL base (5 classes REDISUS)
            wound_mask: mÃ¡scara de segmentaÃ§Ã£o do pipeline base
        """
        if not self._ensemble_available or self._ensemble is None:
            return None
        try:
            # Determina bbox a partir das detecÃ§Ãµes
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

    def _predict_dl(self, image: np.ndarray) -> Optional[Dict]:
        """PrediÃ§Ã£o com modelo DL PyTorch (se disponÃ­vel)."""
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

            # TTA â€” Test Time Augmentation (4 flips)
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

                # MÃ©dia TTA
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

            return {
                "class_name": class_name,
                "display_name": display_name,
                "confidence": confidence,
                "top3": top3,
                "all_probs": {class_names[i]: float(avg_pred[i]) for i in range(len(class_names)) if i < len(avg_pred)},
            }
        except Exception as e:
            print(f"[HEAL+] Erro predicao DL: {e}")
            return None

    # -------------------------------------------------------
    def analyze(self, image: np.ndarray) -> ClinicalReport:
        """Pipeline completo de anÃ¡lise clÃ­nica."""
        t0 = time.perf_counter()
        report = ClinicalReport(is_valid_wound=True)
        if image is None or not isinstance(image, np.ndarray) or image.size == 0 or image.ndim != 3:
            report.is_valid_wound = False
            report.rejection_reason = "Input InvÃ¡lido â€” imagem vazia ou malformada."
            report.processing_time_ms = (time.perf_counter() - t0) * 1000
            return report
        report.original = image.copy()

        # 1. ValidaÃ§Ã£o â€” Ã© uma ferida?
        if not self._validate_wound_image(image):
            report.is_valid_wound = False
            report.rejection_reason = (
                "Input InvÃ¡lido â€” A imagem fornecida nÃ£o apresenta caracterÃ­sticas "
                "compatÃ­veis com ferida cutÃ¢nea humana."
            )
            report.processing_time_ms = (time.perf_counter() - t0) * 1000
            return report

        # 2. Redimensiona se necessÃ¡rio
        h, w = image.shape[:2]
        if max(h, w) > 1024:
            scale = 1024 / max(h, w)
            image = cv2.resize(image, (int(w * scale), int(h * scale)))

        # 2.1 AnÃ¡lise de iluminaÃ§Ã£o e correÃ§Ã£o automÃ¡tica
        if self.image_enhancer is not None:
            try:
                lighting = self.image_enhancer.analyze_lighting(image)
                report.lighting_analysis = lighting.to_dict()
                
                # Aplica correÃ§Ãµes se necessÃ¡rio
                if lighting.corrections_needed:
                    image, corrections = self.image_enhancer.auto_correct(image, lighting)
                    report.image_corrections = corrections
            except Exception as e:
                print(f"[HEAL+] Erro anÃ¡lise de iluminaÃ§Ã£o: {e}")
        
        # 2.2 DetecÃ§Ã£o de parte do corpo
        if self.body_detector is not None:
            try:
                body_part = self.body_detector.detect(image)
                report.body_part = body_part.to_dict()
            except Exception as e:
                print(f"[HEAL+] Erro detecÃ§Ã£o parte do corpo: {e}")

        # 3. DetecÃ§Ã£o de regiÃµes de ferida
        detections = self.detector.detect(image)

        # 3.1 Cria mÃ¡scara ROI precisa por contorno (nÃ£o mais bbox retangular)
        wound_mask = self._create_wound_roi_mask(image, detections)

        # 3.2 Remove fundo cirÃºrgico (lenÃ§ol azul/verde/cinza) da mÃ¡scara
        wound_mask = self._exclude_surgical_background(image, wound_mask)

        # 3.3 ClassificaÃ§Ã£o espacial de background â€” separa fundo de cÃ¢mera
        # de tecido necrÃ³tico usando variÃ¢ncia local, crominÃ¢ncia e conectividade
        background_mask = self._create_background_mask_spatial(image, wound_mask)
        wound_mask_clean = cv2.bitwise_and(wound_mask, cv2.bitwise_not(background_mask))
        # Se a limpeza removeu quase tudo, ignora (provavelmente nÃ£o tem fundo)
        if np.sum(wound_mask_clean > 0) > 0.05 * np.sum(wound_mask > 0):
            wound_mask = wound_mask_clean

        # 3.4 SeparaÃ§Ã£o em zonas espaciais (periferia, core, anel externo)
        peripheral_zone, core_zone, outer_ring = self._create_zone_masks(wound_mask)
        report.wound_zones = {
            "peripheral_area_px": int(np.sum(peripheral_zone > 0)),
            "core_area_px": int(np.sum(core_zone > 0)),
            "outer_ring_area_px": int(np.sum(outer_ring > 0)),
            "border_width_adaptive": True,
        }

        # Desenha detecÃ§Ãµes
        det_overlay = image.copy()
        for det in detections:
            x1, y1, x2, y2 = det.bbox
            cv2.rectangle(det_overlay, (x1, y1), (x2, y2), (0, 255, 0), 2)
            cv2.putText(det_overlay,
                        f"Ferida {det.confidence:.0%}",
                        (x1, y1 - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 0), 1)
        report.detection_overlay = det_overlay
        report.wound_area_px = int(np.sum(wound_mask > 0))

        # 4. SegmentaÃ§Ã£o tecidual clÃ­nica v3 (HSV + LAB + zonas + gradiente)
        tissue_pcts, seg_map, tissue_overlay = self._segment_clinical_v3(
            image, wound_mask, peripheral_zone, core_zone, outer_ring
        )
        report.segmentation_map = seg_map
        report.tissue_overlay = tissue_overlay

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

        # 6. ClassificaÃ§Ã£o principal
        dominant = max(report.tissues, key=lambda t: t.percentage)
        report.primary_tissue = dominant.name
        report.primary_justification = self._build_justification(dominant, tissue_pcts)

        # 7. AnÃ¡lise de bordas
        report.border_analysis = self._analyze_borders(image, wound_mask)

        # 8. Score de saÃºde
        report.health_score = self._compute_health_score(tissue_pcts)

        # 9. Escalas clÃ­nicas (PUSH e BWAT)
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
                
                # BWAT Score (itens auto-preenchÃ­veis)
                bwat = ScaleCalculator.calculate_bwat_from_analysis(
                    tissue_percentages=tissue_pcts,
                    wound_area_px=report.wound_area_px,
                    border_analysis=border_dict,
                )
                report.bwat_score = bwat.to_dict()
            except Exception as e:
                print(f"[HEAL+] Erro ao calcular escalas clÃ­nicas: {e}")

        # 10. Deep Learning â€” classificaÃ§Ã£o etiolÃ³gica (se disponÃ­vel)
        dl_result = self._predict_dl(image)
        if dl_result:
            report.dl_prediction = dl_result

        # 11. ResNet50 Two-Stage â€” classificaÃ§Ã£o Normal/Ferida + Tipo
        resnet_result = self._predict_resnet(image)
        if resnet_result:
            report.resnet_prediction = resnet_result
            # Se Grad-CAM foi gerado, inclui no report
            if isinstance(resnet_result, dict) and resnet_result.get('grad_cam_overlay') is not None:
                report.grad_cam_overlay = resnet_result.pop('grad_cam_overlay')

        # 12. Ensemble Multi-Modelo â€” camada adicional de IA prÃ©-treinada
        #     Passa probabilidades DL e mÃ¡scara de segmentaÃ§Ã£o para fusÃ£o cruzada
        dl_probs = None
        if dl_result and "probabilities" in dl_result:
            dl_probs = dl_result["probabilities"]
        ensemble_result = self._predict_ensemble(
            image, detections, dl_probs=dl_probs, wound_mask=wound_mask,
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
        """ClassificaÃ§Ã£o ResNet50 de dois estÃ¡gios com Grad-CAM."""
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

            # AÃ§Ã£o clÃ­nica recomendada
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
        Detecta e exclui fundo cirÃºrgico (lenÃ§ol azul, verde, cinza de maca)
        da mÃ¡scara de ferida para evitar que o segmentador confunda sombras do
        campo cirÃºrgico com necrose ou esfacelo.

        Detecta:
        - Azul hospitalar:  H 90-130, S > 30, V qualquer
        - Verde cirÃºrgico:  H 35-85,  S > 30, V > 30
        - Cinza de maca:    S < 25,   V 40-170 (acromÃ¡tico)
        - Branco de gaze:   S < 20,   V > 200
        """
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)

        drape_mask = np.zeros(image.shape[:2], dtype=np.uint8)

        # Azul hospitalar (lenÃ§ol, campo cirÃºrgico)
        drape_mask = cv2.bitwise_or(
            drape_mask,
            cv2.inRange(hsv, np.array([90, 30, 20]), np.array([130, 255, 255]))
        )
        # Verde cirÃºrgico
        drape_mask = cv2.bitwise_or(
            drape_mask,
            cv2.inRange(hsv, np.array([35, 30, 30]), np.array([85, 255, 255]))
        )
        # Cinza acromÃ¡tico (maca, superfÃ­cie metÃ¡lica)
        drape_mask = cv2.bitwise_or(
            drape_mask,
            cv2.inRange(hsv, np.array([0, 0, 40]), np.array([180, 25, 170]))
        )

        # SÃ³ exclui se a regiÃ£o de drape cobre uma fraÃ§Ã£o significativa
        # (evita excluir pixels legÃ­timos em imagens sem campo cirÃºrgico)
        drape_ratio = np.sum(drape_mask > 0) / max(drape_mask.size, 1)
        if drape_ratio < 0.05:
            # Quase nada detectado â€” provavelmente nÃ£o tem campo cirÃºrgico
            return wound_mask

        # Dilata levemente para pegar bordas de transiÃ§Ã£o
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
        drape_mask = cv2.dilate(drape_mask, kernel, iterations=1)

        # Remove do wound_mask
        cleaned = cv2.bitwise_and(wound_mask, cv2.bitwise_not(drape_mask))

        # Garante que ainda resta Ã¡rea Ãºtil (nÃ£o remove tudo)
        if np.sum(cleaned > 0) < 0.02 * wound_mask.size:
            # Se removeu quase tudo, ignora a exclusÃ£o
            return wound_mask

        return cleaned

    # -------------------------------------------------------
    def _validate_wound_image(self, image: np.ndarray) -> bool:
        """Verifica se a imagem provavelmente contÃ©m uma ferida."""
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)

        # Verifica se Ã© completamente monoton (tela preta, branca, etc.)
        std_val = np.std(hsv[:, :, 2])
        if std_val < 8:
            return False

        # Verifica se tem variaÃ§Ã£o de matiz suficiente
        std_hue = np.std(hsv[:, :, 0])
        if std_hue < 3 and np.std(hsv[:, :, 1]) < 10:
            return False

        # Verifica se Ã© uma foto (nÃ£o um diagrama/texto)
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, 50, 150)
        edge_ratio = np.sum(edges > 0) / edges.size
        # Textos/diagramas tÃªm muitas bordas finas
        if edge_ratio > 0.35:
            return False

        # Busca por cores compatÃ­veis com ferida/pele
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
        Cria mÃ¡scara ROI precisa do leito da ferida usando contorno real
        em vez de bounding boxes retangulares.

        Pipeline:
        1. Inicializa com bounding boxes das detecÃ§Ãµes
        2. Segmenta por cor dentro de cada bbox (exclui pele sÃ£, fundo)
        3. Extrai contorno externo (perÃ­metro da lesÃ£o)
        4. Preenche contorno para criar mÃ¡scara binÃ¡ria precisa

        Resultado: mÃ¡scara onde 255 = leito da ferida, 0 = fora.
        """
        h, w = image.shape[:2]
        wound_mask = np.zeros((h, w), dtype=np.uint8)

        if not detections:
            # Close-up: assume imagem inteira, mas tenta segmentar
            wound_mask[:] = 255
            return wound_mask

        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)

        for det in detections:
            x1, y1, x2, y2 = det.bbox
            # Margem de seguranÃ§a (5% do bbox)
            margin_x = int((x2 - x1) * 0.05)
            margin_y = int((y2 - y1) * 0.05)
            rx1 = max(0, x1 - margin_x)
            ry1 = max(0, y1 - margin_y)
            rx2 = min(w, x2 + margin_x)
            ry2 = min(h, y2 + margin_y)

            roi_hsv = hsv[ry1:ry2, rx1:rx2]

            # MÃ¡scara de cores compatÃ­veis com ferida (nÃ£o-pele-sÃ£, nÃ£o-fundo)
            wound_colors = np.zeros(roi_hsv.shape[:2], dtype=np.uint8)

            # Vermelho/rosa (granulaÃ§Ã£o, sangue, inflamaÃ§Ã£o)
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
            # Rosa (epitelizaÃ§Ã£o)
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

            # Limpeza morfolÃ³gica
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

            # Se segmentaÃ§Ã£o capturou muito pouco, fallback para bbox
            roi_area = np.sum(roi_filled > 0)
            bbox_area = (rx2 - rx1) * (ry2 - ry1)
            if roi_area < bbox_area * 0.10:
                wound_mask[y1:y2, x1:x2] = 255
            else:
                wound_mask[ry1:ry2, rx1:rx2] = cv2.bitwise_or(
                    wound_mask[ry1:ry2, rx1:rx2], roi_filled
                )

        return wound_mask

    @staticmethod
    def _create_zone_masks(
        wound_mask: np.ndarray,
        border_width_px: int = 15
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Separa a mÃ¡scara da ferida em zonas espaciais:

        - peripheral_zone: anel de borda interna (transiÃ§Ã£o ferida â†’ pele sÃ£)
        - core_zone: centro/miolo do leito da ferida
        - outer_ring: anel externo (para detectar epitelizaÃ§Ã£o avanÃ§ando)

        A largura do buffer Ã© adaptativa: usa min(border_width_px,
        ~15% do raio equivalente) para nÃ£o engolir feridas pequenas.

        Args:
            wound_mask: MÃ¡scara binÃ¡ria da ferida (255 = ferida)
            border_width_px: Largura base do anel de borda em pixels

        Returns:
            (peripheral_zone, core_zone, outer_ring) â€” todas uint8, 0/255
        """
        h, w = wound_mask.shape[:2]

        # Raio equivalente para adaptar largura do buffer
        wound_area = np.sum(wound_mask > 0)
        equiv_radius = np.sqrt(wound_area / np.pi) if wound_area > 0 else 0

        # Buffer adaptativo: mÃ¡x 15% do raio, mÃ­n 3px, mÃ¡x border_width_px
        adaptive_width = int(np.clip(equiv_radius * 0.15, 3, border_width_px))

        # ErosÃ£o para criar zona central (core)
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

        # outer_ring = dilataÃ§Ã£o - wound_mask (anel externo)
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

        Racional clÃ­nico:
          Fundo de cÃ¢mera fotogrÃ¡fica e necrose de coagulaÃ§Ã£o (escara) sÃ£o
          ambos muito escuros (V â‰ˆ 0). PorÃ©m, diferem em:
            1. VariÃ¢ncia local â€” fundo Ã© uniformemente preto (var â‰ˆ 0),
               enquanto tecido necrÃ³tico tem micro-textura (var > 0).
            2. CrominÃ¢ncia â€” fundo puro Ã© acromÃ¡tico (a*â‰ˆ128, b*â‰ˆ128),
               enquanto necrose geralmente tem tint marrom/vermelho.
            3. Conectividade â€” fundo tende a formar regiÃµes grandes e
               contÃ­guas que tocam as bordas da imagem; necrose forma
               ilhas menores dentro do perÃ­metro anatÃ´mico.
            4. PosiÃ§Ã£o relativa â€” fundo de cÃ¢mera frequentemente toca
               as bordas da imagem; necrose estÃ¡ centrada no leito.

        Pipeline:
          1) Identifica pixels muito escuros (V < 20) dentro do wound_mask
          2) Calcula variÃ¢ncia local (5Ã—5) â€” background: var < threshold
          3) Calcula desvio cromÃ¡tico (chroma) â€” background: chroma â‰ˆ 0
          4) Conectividade: regiÃµes escuras > 30% do wound_mask E tocando
             borda da imagem â†’ provÃ¡vel background leaking
          5) Score combinado â†’ mÃ¡scara de background

        Args:
            image: Imagem BGR original
            wound_mask: MÃ¡scara binÃ¡ria da ferida (255 = ferida)

        Returns:
            background_mask: MÃ¡scara onde 255 = pixel de background, 0 = tecido
        """
        h, w = image.shape[:2]
        background_mask = np.zeros((h, w), dtype=np.uint8)

        # 1. Pixels muito escuros dentro do wound_mask
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        very_dark = (gray < 20).astype(np.uint8) * 255
        dark_in_roi = cv2.bitwise_and(very_dark, wound_mask)

        # Se quase nÃ£o tem pixels escuros no ROI, retorna vazio
        dark_count = np.sum(dark_in_roi > 0)
        roi_count = max(np.sum(wound_mask > 0), 1)
        if dark_count < roi_count * 0.02:
            return background_mask  # < 2% escuro â†’ nÃ£o tem background significativo

        # 2. VariÃ¢ncia local (5Ã—5) â€” background tem variÃ¢ncia â‰ˆ 0
        gray_f = gray.astype(np.float32)
        local_mean = cv2.blur(gray_f, (5, 5))
        local_sqmean = cv2.blur(gray_f ** 2, (5, 5))
        local_var = local_sqmean - local_mean ** 2
        local_var = np.clip(local_var, 0, None)

        # Background: variÃ¢ncia muito baixa (superfÃ­cie uniforme)
        low_var = (local_var < 8.0).astype(np.uint8) * 255

        # 3. CrominÃ¢ncia â€” background Ã© acromÃ¡tico puro
        lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
        a_ch = lab[:, :, 1].astype(np.float32)
        b_ch = lab[:, :, 2].astype(np.float32)
        chroma_deviation = np.sqrt((a_ch - 128.0) ** 2 + (b_ch - 128.0) ** 2)

        # AcromÃ¡tico = desvio cromÃ¡tico < 5 (praticamente neutro)
        achromatic = (chroma_deviation < 5.0).astype(np.uint8) * 255

        # 4. Candidato a background: escuro + variÃ¢ncia baixa + acromÃ¡tico
        bg_candidate = cv2.bitwise_and(dark_in_roi, low_var)
        bg_candidate = cv2.bitwise_and(bg_candidate, achromatic)

        # 5. AnÃ¡lise de conectividade â€” regiÃµes grandes e/ou tocando borda
        # sÃ£o mais provÃ¡veis de ser background
        contours, _ = cv2.findContours(
            bg_candidate, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )

        border_margin = 3  # pixels da borda da imagem
        for cnt in contours:
            area = cv2.contourArea(cnt)

            # CritÃ©rio 1: regiÃ£o muito grande (> 15% do wound_mask) â†’ background
            if area > roi_count * 0.15:
                cv2.drawContours(background_mask, [cnt], -1, 255, cv2.FILLED)
                continue

            # CritÃ©rio 2: toca borda da imagem â†’ provÃ¡vel background de cÃ¢mera
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

            # CritÃ©rio 3: regiÃ£o pequena mas extremamente uniforme
            # (variÃ¢ncia mÃ©dia dentro da regiÃ£o < 2) â†’ background
            cnt_mask = np.zeros((h, w), dtype=np.uint8)
            cv2.drawContours(cnt_mask, [cnt], -1, 255, cv2.FILLED)
            region_var = local_var[cnt_mask > 0]
            if len(region_var) > 10 and np.mean(region_var) < 2.0:
                cv2.drawContours(background_mask, [cnt], -1, 255, cv2.FILLED)

        # 6. Dilata levemente para fechar bordas de transiÃ§Ã£o
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
        Detecta tecido epitelial usando anÃ¡lise de gradiente na zona de borda.

        A epitelizaÃ§Ã£o ocorre especificamente na transiÃ§Ã£o ferida â†’ pele sÃ£:
        - Cor rosa claro / translÃºcido
        - Gradiente suave (superfÃ­cie lisa, sem textura granulada)
        - Proximidade com pele Ã­ntegra (zona perifÃ©rica)
        - Baixo contraste local (tecido uniforme)

        Combina:
        1. DetecÃ§Ã£o por cor HSV/LAB restrita Ã  zona perifÃ©rica
        2. AnÃ¡lise de gradiente (Scharr) â€” epitelizaÃ§Ã£o tem gradiente baixo
        3. Proximidade com borda (weighted distance transform)

        Returns:
            epithelial_mask: mÃ¡scara binÃ¡ria dos pixels epiteliais (0/255)
        """
        h, w = image.shape[:2]

        # Zona de interesse: periferia interna + anel externo
        epi_roi = cv2.bitwise_or(peripheral_zone, outer_ring)

        # 1. DetecÃ§Ã£o por cor na zona perifÃ©rica (HSV + LAB)
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
        # Restringe estritamente Ã  zona perifÃ©rica + anel externo
        color_mask = cv2.bitwise_and(color_mask, epi_roi)

        # 2. AnÃ¡lise de gradiente â€” Scharr (mais preciso que Sobel)
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        gray_smooth = cv2.GaussianBlur(gray, (5, 5), 0)

        grad_x = cv2.Scharr(gray_smooth, cv2.CV_64F, 1, 0)
        grad_y = cv2.Scharr(gray_smooth, cv2.CV_64F, 0, 1)
        gradient_mag = np.sqrt(grad_x ** 2 + grad_y ** 2)

        # Normaliza gradiente para 0-255
        grad_norm = cv2.normalize(
            gradient_mag, None, 0, 255, cv2.NORM_MINMAX
        ).astype(np.uint8)

        # EpitelizaÃ§Ã£o = gradiente BAIXO (superfÃ­cie lisa/translÃºcida)
        # Threshold adaptativo: 40Âº percentil na zona de interesse
        peri_grads = grad_norm[epi_roi > 0]
        if len(peri_grads) > 50:
            grad_threshold = np.percentile(peri_grads, 40)
        else:
            grad_threshold = 30

        low_gradient = (grad_norm < grad_threshold).astype(np.uint8) * 255
        low_gradient = cv2.bitwise_and(low_gradient, epi_roi)

        # 3. Distance transform â€” peso por proximidade da borda
        dist = cv2.distanceTransform(wound_mask, cv2.DIST_L2, 5)
        max_dist = np.max(dist) if np.max(dist) > 0 else 1.0

        # Peso maior para pixels prÃ³ximos Ã  borda (inverso da distÃ¢ncia)
        border_weight = 1.0 - (dist / max_dist)
        border_weight_u8 = (border_weight * 255).astype(np.uint8)

        # Peso alto na borda (>= 80% de peso â†’ V > 200) â€” mais restrito
        border_strong = (border_weight_u8 > 200).astype(np.uint8) * 255

        # 4. CombinaÃ§Ã£o ponderada:
        #    Cor rosa: 50% (mais peso para cor) | Gradiente baixo: 25% | Borda: 25%
        epi_score = np.zeros((h, w), dtype=np.float32)
        epi_score += (color_mask.astype(np.float32) / 255.0) * 0.50
        epi_score += (low_gradient.astype(np.float32) / 255.0) * 0.25
        epi_score += (border_strong.astype(np.float32) / 255.0) * 0.25

        # Threshold alto: cor Ã© obrigatÃ³ria + pelo menos 1 outro critÃ©rio (> 0.70)
        epithelial_mask = np.where(epi_score > 0.70, 255, 0).astype(np.uint8)

        # Restringe estritamente Ã  zona perifÃ©rica + outer ring
        epithelial_mask = cv2.bitwise_and(epithelial_mask, epi_roi)

        # Limpeza morfolÃ³gica â€” open maior para remover ruÃ­do
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
        """Segmenta a ferida segundo taxonomia clÃ­nica (v1/v2 â€” legado)."""
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
        Estima o tom de pele do paciente amostrand pixel da regiÃ£o perilesional.

        Amostra pixels no anel de 15-40px ao redor da wound_mask que nÃ£o sejam
        fundo cirÃºrgico (azul/verde/cinza) nem partes da ferida.

        Returns:
            (L_mean, a_mean, b_mean, fitzpatrick_approx)
            L_mean: luminosidade mÃ©dia LAB do periwound
            a_mean: canal a* mÃ©dio
            b_mean: canal b* mÃ©dio
            fitzpatrick_approx: "I-II", "III", "IV", "V", "VI"
        """
        h, w = image.shape[:2]

        # Cria anel perilesional: dilata 40px - dilata 15px
        kernel_inner = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (31, 31))
        kernel_outer = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (81, 81))
        inner_ring = cv2.dilate(wound_mask, kernel_inner)
        outer_ring = cv2.dilate(wound_mask, kernel_outer)
        periwound = cv2.bitwise_and(outer_ring, cv2.bitwise_not(inner_ring))

        # Exclui fundo cirÃºrgico do periwound
        hsv_raw = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        drape = np.zeros((h, w), dtype=np.uint8)
        # Azul hospitalar
        drape = cv2.bitwise_or(drape, cv2.inRange(
            hsv_raw, np.array([90, 30, 20]), np.array([130, 255, 255])))
        # Verde cirÃºrgico
        drape = cv2.bitwise_or(drape, cv2.inRange(
            hsv_raw, np.array([35, 30, 30]), np.array([85, 255, 255])))
        # Cinza acromÃ¡tico (maca/fundo)
        drape = cv2.bitwise_or(drape, cv2.inRange(
            hsv_raw, np.array([0, 0, 0]), np.array([180, 20, 100])))

        skin_sample = cv2.bitwise_and(periwound, cv2.bitwise_not(drape))

        # Amostra em LAB
        lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
        skin_pixels = lab[skin_sample > 0]

        if len(skin_pixels) < 50:
            # Fallback: sem dados suficientes, assume pele mÃ©dia
            return 140.0, 128.0, 128.0, "III"

        L_mean = float(np.median(skin_pixels[:, 0]))
        a_mean = float(np.median(skin_pixels[:, 1]))
        b_mean = float(np.median(skin_pixels[:, 2]))

        # ClassificaÃ§Ã£o Fitzpatrick aproximada
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

    def _segment_clinical_v3(
        self,
        image: np.ndarray,
        wound_mask: np.ndarray,
        peripheral_zone: np.ndarray,
        core_zone: np.ndarray,
        outer_ring: np.ndarray,
    ) -> Tuple[Dict[str, float], np.ndarray, np.ndarray]:
        """
        SegmentaÃ§Ã£o clÃ­nica v3 â€” multi-espaÃ§o de cor + zonas espaciais + gradiente.

        Pipeline:
        1. EstimaÃ§Ã£o do tom de pele (Fitzpatrick) via periwound
        2. Denoise bilateral (preserva bordas)
        3. CLAHE adaptativo (L + canal a*)
        4. ConversÃ£o HSV + LAB
        5. SegmentaÃ§Ã£o por cor restrita estritamente Ã  wound_mask (ROI)
        6. FusÃ£o ponderada HSV (60%) + LAB (40%)
        7. CRIAÃ‡ÃƒO DE MÃSCARA DE PELE SAUDÃVEL para excluir da necrose
        8. RestriÃ§Ã£o espacial por zonas
        9. DetecÃ§Ã£o de epitelizaÃ§Ã£o por gradiente de borda (Scharr)
        10. VerificaÃ§Ã£o de textura para necrose (necrose real tem textura diferente de pele)
        11. ExclusÃ£o de fundo cirÃºrgico
        12. ResoluÃ§Ã£o de sobreposiÃ§Ãµes com prioridade clÃ­nica
        """
        # â”€â”€ 0. EstimaÃ§Ã£o do tom de pele do paciente â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        skin_L, skin_a, skin_b, fitzpatrick = self._estimate_skin_tone(image, wound_mask)
        is_dark_skin = fitzpatrick in ("V", "VI")
        is_medium_skin = fitzpatrick in ("IV", "V")
        logger.debug(
            f"Tom de pele estimado: Fitzpatrick {fitzpatrick} "
            f"(L={skin_L:.0f}, a*={skin_a:.0f}, b*={skin_b:.0f})"
        )

        # â”€â”€ 1. PrÃ©-processamento: denoise + CLAHE â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
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

        # â”€â”€ 2. SegmentaÃ§Ã£o HSV â€” restrita estritamente Ã  wound_mask â”€â”€â”€
        hsv_masks = {}
        for tissue_key, ranges in CLINICAL_HSV_RANGES.items():
            mask = np.zeros((h, w), dtype=np.uint8)
            for lower, upper in ranges:
                mask = cv2.bitwise_or(mask, cv2.inRange(hsv, lower, upper))
            # OBRIGATÃ“RIO: restringe Ã  ROI â€” ignora todo pixel fora do perÃ­metro
            mask = cv2.bitwise_and(mask, wound_mask)
            mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel_s)
            mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel_m)
            hsv_masks[tissue_key] = mask

        # â”€â”€ 3. SegmentaÃ§Ã£o LAB â€” restrita Ã  wound_mask â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        lab_masks = {}
        for tissue_key, ranges in CLINICAL_LAB_RANGES.items():
            mask = np.zeros((h, w), dtype=np.uint8)
            for lower, upper in ranges:
                mask = cv2.bitwise_or(mask, cv2.inRange(lab, lower, upper))
            mask = cv2.bitwise_and(mask, wound_mask)
            mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel_s)
            mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel_m)
            lab_masks[tissue_key] = mask

        # â”€â”€ 4. FusÃ£o ponderada HSV (60%) + LAB (40%) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
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
            # RestriÃ§Ã£o final Ã  ROI (nenhum pixel fora do perÃ­metro)
            mask = cv2.bitwise_and(mask, wound_mask)
            masks[tissue_key] = mask

        # â”€â”€ 5. CriaÃ§Ã£o de mÃ¡scara de pele saudÃ¡vel (skin exclusion) â”€â”€â”€â”€
        # Gera uma mÃ¡scara PRECISA de pixels que se parecem com pele saudÃ¡vel
        # do paciente (tolerÃ¢ncias ESTREITAS para nÃ£o excluir necrose real).
        lab_for_skin = cv2.cvtColor(denoised_norm, cv2.COLOR_BGR2LAB)

        # TolerÃ¢ncias ESTREITAS: sÃ³ exclui pixels MUITO prÃ³ximos da pele
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

        # VerificaÃ§Ã£o de textura: pele saudÃ¡vel Ã© UNIFORME (variÃ¢ncia 50-400)
        # Necrose tem textura irregular OU muito lisa (escara)
        gray_tex = cv2.cvtColor(denoised_norm, cv2.COLOR_BGR2GRAY)
        local_variance = cv2.GaussianBlur(
            (gray_tex.astype(np.float32) ** 2), (11, 11), 0
        ) - cv2.GaussianBlur(gray_tex.astype(np.float32), (11, 11), 0) ** 2
        local_variance = np.clip(local_variance, 0, None)

        # Somente textura tÃ­pica de pele saudÃ¡vel (moderadamente uniforme)
        smooth_skin = ((local_variance > 50) & (local_variance < 400)).astype(np.uint8) * 255
        skin_exclude_mask = cv2.bitwise_and(skin_exclude_mask, smooth_skin)

        # Limpeza morfolÃ³gica
        kernel_skin = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        skin_exclude_mask = cv2.morphologyEx(skin_exclude_mask, cv2.MORPH_CLOSE, kernel_skin)
        skin_exclude_mask = cv2.morphologyEx(skin_exclude_mask, cv2.MORPH_OPEN, kernel_skin)

        # Remove pixels de pele saudÃ¡vel da mÃ¡scara de necrose
        masks["necrosis"] = cv2.bitwise_and(
            masks["necrosis"], cv2.bitwise_not(skin_exclude_mask)
        )

        logger.debug(
            f"Skin exclusion: {np.sum(skin_exclude_mask > 0)} px excluÃ­dos da necrose "
            f"(Fitzpatrick {fitzpatrick})"
        )

        # â”€â”€ 5b. RestriÃ§Ã£o espacial por zonas â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        # Necrose: viÃ©s espacial moderado. Em peles escuras, requer
        # confirmaÃ§Ã£o por textura, mas NÃƒO restringimos excessivamente.
        necro_spatial = np.zeros((h, w), dtype=np.float32)
        necro_spatial[core_zone > 0] = 1.0
        if is_dark_skin:
            # Pele escura: periferia com peso moderado (nÃ£o bloquear)
            necro_spatial[peripheral_zone > 0] = 0.45
        elif is_medium_skin:
            necro_spatial[peripheral_zone > 0] = 0.5
        else:
            necro_spatial[peripheral_zone > 0] = 0.6

        # Boost por luminÃ¢ncia CONDICIONAL: somente pixels escuros
        # que NÃƒO sÃ£o pele saudÃ¡vel do paciente (anti-bias)
        gray_roi = cv2.cvtColor(
            cv2.bitwise_and(denoised_norm, denoised_norm, mask=wound_mask),
            cv2.COLOR_BGR2GRAY
        )
        low_lum = (gray_roi < 45).astype(np.float32)
        not_skin_f = (cv2.bitwise_not(skin_exclude_mask) / 255.0).astype(np.float32)
        # Pixels escuros + nÃ£o-pele dentro da ROI recebem boost espacial
        lum_boost = low_lum * not_skin_f * (wound_mask.astype(np.float32) / 255.0)
        necro_spatial = np.maximum(necro_spatial, lum_boost * 0.8)

        m_necro = masks["necrosis"].astype(np.float32)
        m_necro_biased = m_necro * necro_spatial
        # Threshold moderado (mesmo para pele escura â€” a skin exclusion jÃ¡ protege)
        necro_threshold = 100 if is_dark_skin else (90 if is_medium_skin else 80)
        masks["necrosis"] = np.where(m_necro_biased > necro_threshold, 255, 0).astype(np.uint8)
        masks["necrosis"] = cv2.bitwise_and(masks["necrosis"], wound_mask)

        # --- Esfacelo: viÃ©s moderado para core + periferia interna ---
        core_bias_slough = np.zeros((h, w), dtype=np.float32)
        core_bias_slough[core_zone > 0] = 1.0
        core_bias_slough[peripheral_zone > 0] = 0.5  # esfacelo pode estar na periferia

        m_slough = masks["slough"].astype(np.float32)
        m_slough_biased = m_slough * core_bias_slough
        masks["slough"] = np.where(m_slough_biased > 100, 255, 0).astype(np.uint8)
        masks["slough"] = cv2.bitwise_and(masks["slough"], wound_mask)

        # GranulaÃ§Ã£o: presente no leito inteiro (core + periferia)
        # Sem viÃ©s espacial adicional â€” jÃ¡ restrita Ã  wound_mask

        # EpitelizaÃ§Ã£o: EXCLUSIVAMENTE perifÃ©rica.
        # Substitui a mÃ¡scara de cor pura pelo detector de gradiente
        # que combina cor + suavidade + proximidade Ã  borda.
        epi_gradient = self._detect_epithelialization_gradient(
            denoised_norm, wound_mask, peripheral_zone, outer_ring
        )
        # Mescla: mÃ¡scara de cor original (restrita Ã  periferia) + gradiente
        epi_roi_zone = cv2.bitwise_or(peripheral_zone, outer_ring)
        epi_color_periph = cv2.bitwise_and(masks["epithelialization"], epi_roi_zone)
        
        # EpitelizaÃ§Ã£o sÃ³ Ã© vÃ¡lida se estiver na zona perifÃ©rica
        masks["epithelialization"] = cv2.bitwise_and(
            cv2.bitwise_or(epi_color_periph, epi_gradient),
            epi_roi_zone
        )

        # â”€â”€ 6. Refinamento por textura â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        gray = cv2.cvtColor(denoised_norm, cv2.COLOR_BGR2GRAY)
        local_var = cv2.GaussianBlur(
            (gray.astype(np.float32) ** 2), (15, 15), 0
        ) - cv2.GaussianBlur(gray.astype(np.float32), (15, 15), 0) ** 2
        local_var = np.clip(local_var, 0, None)

        low_texture = (local_var < 200).astype(np.uint8)
        high_texture = (local_var > 500).astype(np.uint8)

        # â”€â”€ 7. ExclusÃ£o de fundo cirÃºrgico â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        hsv_raw = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        _drape = np.zeros((h, w), dtype=np.uint8)
        _drape = cv2.bitwise_or(_drape, cv2.inRange(
            hsv_raw, np.array([90, 30, 20]), np.array([130, 255, 255])))
        _drape = cv2.bitwise_or(_drape, cv2.inRange(
            hsv_raw, np.array([35, 30, 30]), np.array([85, 255, 255])))
        _drape = cv2.bitwise_or(_drape, cv2.inRange(
            hsv_raw, np.array([0, 0, 40]), np.array([180, 22, 170])))
        _not_drape = cv2.bitwise_not(_drape)
        for _tk in masks:
            masks[_tk] = cv2.bitwise_and(masks[_tk], _not_drape)

        # â”€â”€ 8. ReforÃ§o por textura + luminÃ¢ncia (com proteÃ§Ã£o anti-bias) â”€
        # Combina luminÃ¢ncia + textura para reforÃ§ar necrose, mas EXCLUI
        # pixels que correspondem ao tom de pele do paciente.

        # 8a. Pixels escuros dentro da ROI que NÃƒO sÃ£o pele saudÃ¡vel
        dark_px = (gray < 55).astype(np.uint8) * 255
        dark_px = cv2.bitwise_and(dark_px, _not_drape)
        dark_px = cv2.bitwise_and(dark_px, cv2.bitwise_not(skin_exclude_mask))

        # ProteÃ§Ã£o background residual
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

        # 8b. Necrose por luminÃ¢ncia: V < 45, dentro do ROI, nÃ£o-pele, nÃ£o-bg
        very_dark_roi = (gray < 45).astype(np.uint8) * 255
        very_dark_roi = cv2.bitwise_and(very_dark_roi, wound_mask)
        very_dark_roi = cv2.bitwise_and(very_dark_roi, _not_drape)
        very_dark_roi = cv2.bitwise_and(very_dark_roi, cv2.bitwise_not(skin_exclude_mask))
        very_dark_roi = cv2.bitwise_and(very_dark_roi, cv2.bitwise_not(possible_bg_residual))
        masks["necrosis"] = cv2.bitwise_or(masks["necrosis"], very_dark_roi)

        # 8c. Necrose por textura: baixa textura + escuro + nÃ£o-pele
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
        # ViÃ©s para core + periferia (necrose pode cobrir toda a ferida)
        necro_texture_zone = cv2.bitwise_or(core_zone, peripheral_zone)
        necro_texture_boost = cv2.bitwise_and(necro_texture_boost, necro_texture_zone)
        masks["necrosis"] = cv2.bitwise_or(masks["necrosis"], necro_texture_boost)

        # GranulaÃ§Ã£o: textura alta + vermelho dominante (mais restrito)
        red_channel = denoised_norm[:, :, 2]  # BGR â†’ canal R
        green_channel = denoised_norm[:, :, 1]
        red_dominant = (
            (red_channel.astype(np.int16) - green_channel.astype(np.int16)) > 40
        ).astype(np.uint8) * 255
        # GranulaÃ§Ã£o requer ALTA textura + vermelho forte
        gran_boost = cv2.bitwise_and(
            cv2.bitwise_and(red_dominant, wound_mask),
            (high_texture * 255).astype(np.uint8)
        )
        # NÃ£o adicionar granulaÃ§Ã£o onde jÃ¡ tem necrose
        gran_boost = cv2.bitwise_and(gran_boost, cv2.bitwise_not(masks["necrosis"]))
        masks["granulation"] = cv2.bitwise_or(masks["granulation"], gran_boost)

        # â”€â”€ 9. ResoluÃ§Ã£o de sobreposiÃ§Ãµes â€” prioridade clÃ­nica â”€â”€â”€â”€â”€â”€â”€
        priority = ["necrosis", "slough", "granulation", "epithelialization"]
        used = np.zeros((h, w), dtype=np.uint8)
        for key in priority:
            masks[key] = cv2.bitwise_and(masks[key], cv2.bitwise_not(used))
            used = cv2.bitwise_or(used, masks[key])

        # â”€â”€ 10. MÃ©tricas e visualizaÃ§Ã£o â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        total = max(np.sum(wound_mask > 0), 1)
        pcts = {}
        for key in priority:
            pcts[key] = float(np.sum(masks[key] > 0) / total * 100)

        # Mapa de segmentaÃ§Ã£o colorido
        seg_map = np.full((h, w, 3), 80, dtype=np.uint8)
        colors = {
            "necrosis": (30, 30, 60),
            "slough": (80, 220, 220),
            "granulation": (60, 60, 220),
            "epithelialization": (200, 180, 255),
        }
        for key, mask in masks.items():
            seg_map[mask > 0] = colors[key]

        # Desenha contorno da wound_mask (perÃ­metro da ROI) no overlay
        overlay = image.copy()
        cv2.addWeighted(seg_map, 0.45, overlay, 0.55, 0, overlay)

        # Contorno do perÃ­metro da ferida (verde, 2px)
        contours_roi, _ = cv2.findContours(
            wound_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )
        cv2.drawContours(overlay, contours_roi, -1, (0, 255, 0), 2)

        # Contorno da zona perifÃ©rica (azul claro, 1px) para referÃªncia
        contours_peri, _ = cv2.findContours(
            core_zone, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )
        cv2.drawContours(overlay, contours_peri, -1, (255, 200, 100), 1)

        return pcts, seg_map, overlay

    # -------------------------------------------------------
    def _analyze_borders(
        self, image: np.ndarray, wound_mask: np.ndarray
    ) -> BorderAnalysis:
        """Analisa bordas e perilesÃ£o."""
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)

        # ExpansÃ£o da mÃ¡scara para pegar borda perilesional
        kernel_big = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (25, 25))
        expanded = cv2.dilate(wound_mask, kernel_big)
        peri_mask = cv2.bitwise_and(expanded, cv2.bitwise_not(wound_mask))

        peri_region = hsv[peri_mask > 0]

        # MaceraÃ§Ã£o: pele esbranquiÃ§ada/amolecida ao redor (S baixo, V alto)
        maceration = False
        if len(peri_region) > 100:
            mean_s = np.mean(peri_region[:, 1])
            mean_v = np.mean(peri_region[:, 2])
            if mean_s < 40 and mean_v > 180:
                maceration = True

        # InflamaÃ§Ã£o: vermelhidÃ£o/calor ao redor (H baixo, S moderada+, V moderado+)
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
            desc_parts.append("MaceraÃ§Ã£o perilesional presente (pele esbranquiÃ§ada)")
        if inflammation:
            desc_parts.append("Sinais de inflamaÃ§Ã£o perilesional (eritema)")
        if not regular:
            desc_parts.append("Bordas irregulares/anfractuosas")
        if not desc_parts:
            desc_parts.append("Bordas sem alteraÃ§Ãµes significativas")

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
        """ConstrÃ³i justificativa clÃ­nica baseada no tecido predominante."""
        parts = [f"ClassificaÃ§Ã£o principal: {dominant.name} ({dominant.percentage:.1f}%)."]

        key_map = {
            "Necrose de CoagulaÃ§Ã£o (Escara)": "necrosis",
            "Esfacelo (Fibrina)": "slough",
            "Tecido de GranulaÃ§Ã£o": "granulation",
            "EpitelizaÃ§Ã£o": "epithelialization",
        }
        key = key_map.get(dominant.name, "")

        if key == "necrosis":
            parts.append(
                "PresenÃ§a predominante de tecido escurecido (preto/marrom) aderido ao leito, "
                "consistente com necrose de coagulaÃ§Ã£o. A coloraÃ§Ã£o escura e a textura "
                "endurecida sÃ£o caracterÃ­sticas de morte celular por isquemia."
            )
        elif key == "slough":
            parts.append(
                "PresenÃ§a predominante de tecido amarelado/esbranquiÃ§ado aderido ao leito, "
                "caracterÃ­stico de esfacelo (fibrina). A consistÃªncia viscosa e a coloraÃ§Ã£o "
                "indicam acÃºmulo de fibrina, leucÃ³citos e restos celulares."
            )
        elif key == "granulation":
            parts.append(
                "PresenÃ§a predominante de tecido vermelho vivo/brilhante com aspecto granulado, "
                "indicando processo de cicatrizaÃ§Ã£o ativo (fase proliferativa). "
                "O leito apresenta neovascularizaÃ§Ã£o compatÃ­vel com tecido de granulaÃ§Ã£o saudÃ¡vel."
            )
        elif key == "epithelialization":
            parts.append(
                "PresenÃ§a predominante de tecido rosa claro/translÃºcido avanÃ§ando das bordas, "
                "indicando epitelizaÃ§Ã£o em curso (fase de maturaÃ§Ã£o). A migraÃ§Ã£o de "
                "queratinÃ³citos sugere evoluÃ§Ã£o favorÃ¡vel da cicatrizaÃ§Ã£o."
            )

        # Menciona tecidos secundÃ¡rios relevantes
        secondaries = []
        for k, v in sorted(pcts.items(), key=lambda x: -x[1]):
            if k != key and v > 5:
                name = CLINICAL_TISSUES[k]["name"]
                secondaries.append(f"{name} ({v:.1f}%)")
        if secondaries:
            parts.append(f"Tecidos secundÃ¡rios: {', '.join(secondaries)}.")

        return " ".join(parts)

    # -------------------------------------------------------
    def _compute_health_score(self, pcts: Dict[str, float]) -> float:
        """Score de saÃºde baseado na composiÃ§Ã£o tecidual.

        CritÃ©rios clÃ­nicos:
        - GranulaÃ§Ã£o e epitelizaÃ§Ã£o sÃ£o tecidos saudÃ¡veis (positivo)
        - Necrose Ã© o pior indicador (penalidade forte)
        - Esfacelo indica desvitalizaÃ§Ã£o moderada
        - Tecido nÃ£o classificado na ferida nÃ£o conta como saudÃ¡vel
        """
        gran = pcts.get("granulation", 0)
        epit = pcts.get("epithelialization", 0)
        slough = pcts.get("slough", 0)
        necro = pcts.get("necrosis", 0)

        # ProporÃ§Ã£o de tecido saudÃ¡vel vs total classificado
        total_classified = gran + epit + slough + necro
        if total_classified < 5:
            return 50.0  # Sem dados suficientes

        # Tecido nÃ£o classificado (dentro da ferida) Ã© neutro/negativo
        unclassified = max(0, 100 - total_classified)

        # Score: peso positivo para saudÃ¡vel, negativo para inviÃ¡vel
        healthy = gran * 0.6 + epit * 1.0
        unhealthy = necro * 2.0 + slough * 0.8 + unclassified * 0.3

        score = max(0.0, min(100.0, healthy - unhealthy))
        return score


# ============================================================
# THREAD DE ANÃLISE (nÃ£o trava a UI)
# ============================================================

