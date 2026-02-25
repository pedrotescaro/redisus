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
    QProgressBar, QSplitter, QGroupBox, QTextEdit, QSizePolicy,
    QGraphicsDropShadowEffect, QTabWidget, QComboBox, QSlider,
)
from PyQt6.QtCore import Qt, QSize, QThread, pyqtSignal, QTimer, QMutex
from PyQt6.QtGui import QImage, QPixmap, QFont, QColor, QPalette, QIcon

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

    # Imagens processadas
    original: Optional[np.ndarray] = None
    detection_overlay: Optional[np.ndarray] = None
    segmentation_map: Optional[np.ndarray] = None
    tissue_overlay: Optional[np.ndarray] = None


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
        """Pipeline completo de análise clínica."""
        t0 = time.perf_counter()
        report = ClinicalReport(is_valid_wound=True)
        report.original = image.copy()

        # 1. Validação — é uma ferida?
        if not self._validate_wound_image(image):
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

        # 3. Detecção de regiões de ferida
        detections = self.detector.detect(image)

        # 3.1 Cria máscara ROI precisa por contorno (não mais bbox retangular)
        wound_mask = self._create_wound_roi_mask(image, detections)

        # 3.2 Remove fundo cirúrgico (lençol azul/verde/cinza) da máscara
        wound_mask = self._exclude_surgical_background(image, wound_mask)

        # 3.3 Classificação espacial de background — separa fundo de câmera
        # de tecido necrótico usando variância local, crominância e conectividade
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

        # Desenha detecções
        det_overlay = image.copy()
        for det in detections:
            x1, y1, x2, y2 = det.bbox
            cv2.rectangle(det_overlay, (x1, y1), (x2, y2), (0, 255, 0), 2)
            cv2.putText(det_overlay,
                        f"Ferida {det.confidence:.0%}",
                        (x1, y1 - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 0), 1)
        report.detection_overlay = det_overlay
        report.wound_area_px = int(np.sum(wound_mask > 0))

        # 4. Segmentação tecidual clínica v3 (HSV + LAB + zonas + gradiente)
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

        # 10. Deep Learning — classificação etiológica (se disponível)
        dl_result = self._predict_dl(image)
        if dl_result:
            report.dl_prediction = dl_result

        # 11. ResNet50 Two-Stage — classificação Normal/Ferida + Tipo
        resnet_result = self._predict_resnet(image)
        if resnet_result:
            report.resnet_prediction = resnet_result
            # Se Grad-CAM foi gerado, inclui no report
            if isinstance(resnet_result, dict) and resnet_result.get('grad_cam_overlay') is not None:
                report.grad_cam_overlay = resnet_result.pop('grad_cam_overlay')

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
            cv2.inRange(hsv, np.array([35, 30, 30]), np.array([85, 255, 255]))
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
    # MÉTODOS DE ROI E ZONAS ESPACIAIS (v3)
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
    # CLASSIFICAÇÃO ESPACIAL DE BACKGROUND
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
    # SEGMENTAÇÃO TECIDUAL
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
        7. CRIAÇÃO DE MÁSCARA DE PELE SAUDÁVEL para excluir da necrose
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
        # confirmação por textura, mas NÃO restringimos excessivamente.
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
        # que NÃO são pele saudável do paciente (anti-bias)
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
        epi_roi_zone = cv2.bitwise_or(peripheral_zone, outer_ring)
        epi_color_periph = cv2.bitwise_and(masks["epithelialization"], epi_roi_zone)
        
        # Epitelização só é válida se estiver na zona periférica
        masks["epithelialization"] = cv2.bitwise_and(
            cv2.bitwise_or(epi_color_periph, epi_gradient),
            epi_roi_zone
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
        for _tk in masks:
            masks[_tk] = cv2.bitwise_and(masks[_tk], _not_drape)

        # ── 8. Reforço por textura + luminância (com proteção anti-bias) ─
        # Combina luminância + textura para reforçar necrose, mas EXCLUI
        # pixels que correspondem ao tom de pele do paciente.

        # 8a. Pixels escuros dentro da ROI que NÃO são pele saudável
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
    def _compute_health_score(self, pcts: Dict[str, float]) -> float:
        """Score de saúde baseado na composição tecidual.

        Critérios clínicos:
        - Granulação e epitelização são tecidos saudáveis (positivo)
        - Necrose é o pior indicador (penalidade forte)
        - Esfacelo indica desvitalização moderada
        - Tecido não classificado na ferida não conta como saudável
        """
        gran = pcts.get("granulation", 0)
        epit = pcts.get("epithelialization", 0)
        slough = pcts.get("slough", 0)
        necro = pcts.get("necrosis", 0)

        # Proporção de tecido saudável vs total classificado
        total_classified = gran + epit + slough + necro
        if total_classified < 5:
            return 50.0  # Sem dados suficientes

        # Tecido não classificado (dentro da ferida) é neutro/negativo
        unclassified = max(0, 100 - total_classified)

        # Score: peso positivo para saudável, negativo para inviável
        healthy = gran * 0.6 + epit * 1.0
        unhealthy = necro * 2.0 + slough * 0.8 + unclassified * 0.3

        score = max(0.0, min(100.0, healthy - unhealthy))
        return score


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
        # NÃO conecte finished.connect(deleteLater) - causa crash
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


# ============================================================
# THREAD DE WEBCAM (captura em tempo real)
# ============================================================

class FaceExclusionFilter:
    """
    Filtro de exclusão de rostos usando Haar Cascade do OpenCV.

    Impede que o detector de feridas marque rostos humanos como ferida.
    Também rejeita regiões com pele uniformemente saudável (sem textura de lesão).
    """

    def __init__(self):
        # Haar cascade para detecção de rostos (incluso no OpenCV)
        cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        self._face_cascade = cv2.CascadeClassifier(cascade_path)
        profile_path = cv2.data.haarcascades + "haarcascade_profileface.xml"
        self._profile_cascade = cv2.CascadeClassifier(profile_path)
        self._face_rects: List[Tuple[int, int, int, int]] = []
        self._face_update_interval = 5  # Atualiza faces a cada N frames
        self._frame_counter = 0

    def update_faces(self, gray_frame: np.ndarray):
        """Detecta rostos no frame (chamado periodicamente)."""
        self._frame_counter += 1
        if self._frame_counter % self._face_update_interval != 0:
            return

        # Reduz resolução para velocidade
        h, w = gray_frame.shape[:2]
        scale = min(320 / max(h, w), 1.0)
        small = cv2.resize(gray_frame, (int(w * scale), int(h * scale)))

        faces = self._face_cascade.detectMultiScale(
            small, scaleFactor=1.15, minNeighbors=4, minSize=(40, 40)
        )
        profiles = self._profile_cascade.detectMultiScale(
            small, scaleFactor=1.15, minNeighbors=4, minSize=(40, 40)
        )

        all_faces = []
        for (fx, fy, fw, fh) in list(faces) + list(profiles):
            # Escala de volta + margem de 30%
            margin = 0.3
            fx1 = int((fx - fw * margin) / scale)
            fy1 = int((fy - fh * margin) / scale)
            fx2 = int((fx + fw + fw * margin) / scale)
            fy2 = int((fy + fh + fh * margin) / scale)
            all_faces.append((max(0, fx1), max(0, fy1), min(w, fx2), min(h, fy2)))

        self._face_rects = all_faces

    def overlaps_face(self, bbox: Tuple[int, int, int, int]) -> bool:
        """Verifica se uma bounding box intersecta algum rosto."""
        x1, y1, x2, y2 = bbox
        for fx1, fy1, fx2, fy2 in self._face_rects:
            # IoU parcial: se >30% de overlap, é rosto
            ix1 = max(x1, fx1)
            iy1 = max(y1, fy1)
            ix2 = min(x2, fx2)
            iy2 = min(y2, fy2)
            inter = max(0, ix2 - ix1) * max(0, iy2 - iy1)
            det_area = max((x2 - x1) * (y2 - y1), 1)
            if inter / det_area > 0.25:
                return True
        return False

    def get_face_rects(self) -> List[Tuple[int, int, int, int]]:
        return self._face_rects

    @staticmethod
    def is_uniform_skin(roi_bgr: np.ndarray) -> bool:
        """
        Verifica se a ROI é pele uniforme saudável (sem textura de lesão).
        Pele saudável tem: baixa variância de cor, tom uniforme.
        AGRESSIVO: prefere rejeitar do que aceitar falsos positivos.
        """
        if roi_bgr is None or roi_bgr.size < 100:
            return True

        hsv = cv2.cvtColor(roi_bgr, cv2.COLOR_BGR2HSV)
        h, s, v = hsv[:, :, 0], hsv[:, :, 1], hsv[:, :, 2]

        # Pele uniforme: saturação e valor com pouca variação
        s_std = np.std(s)
        v_std = np.std(v)
        h_std = np.std(h)

        # Variância de textura (Laplaciano)
        gray = cv2.cvtColor(roi_bgr, cv2.COLOR_BGR2GRAY)
        lap_var = cv2.Laplacian(gray, cv2.CV_64F).var()

        # AGRESSIVO: Pele saudável uniforme (thresholds aumentados)
        if s_std < 25 and v_std < 30 and lap_var < 400:
            return True

        # Cor muito uniforme (pouca variação de hue)
        if h_std < 15 and s_std < 30 and lap_var < 500:
            return True

        # Tom de pele fortemente dominante, pouca textura
        skin_lower = np.array([0, 15, 60])  # Ampliado para capturar mais tons de pele
        skin_upper = np.array([30, 170, 255])
        skin_mask = cv2.inRange(hsv, skin_lower, skin_upper)
        skin_ratio = np.sum(skin_mask > 0) / max(skin_mask.size, 1)

        # Se >70% é pele e textura baixa, provavelmente é pele saudável
        if skin_ratio > 0.70 and lap_var < 500:
            return True

        # Gradiente da imagem - feridas têm bordas mais marcadas
        sobelx = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
        sobely = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
        gradient_mag = np.sqrt(sobelx**2 + sobely**2).mean()

        # Pele saudável tem gradiente baixo (superfície lisa)
        if gradient_mag < 15 and skin_ratio > 0.5:
            return True

        return False


class WebcamThread(QThread):
    """
    Thread para captura de vídeo + detecção rápida em cada frame.

    Estratégia anti-falso-positivo:
    1. Detector com TEXTURE_PRIORITY (peso 50% textura, 25% cor)
    2. Confiança mínima 0.45
    3. Área mínima 1200px
    4. Filtro de falsos positivos DESLIGADO (fast-path)
    5. Exclusão automática de rostos (Haar Cascade)
    6. Rejeição de pele uniforme saudável
    7. Detecção a cada 2 frames para responsividade
    """
    frame_ready = pyqtSignal(np.ndarray, np.ndarray)  # (annotated_frame, raw_frame)
    error = pyqtSignal(str)

    def __init__(self, camera_id: int = 0, parent=None):
        super().__init__(parent)  # Parent garante cleanup adequado
        self.camera_id = camera_id
        self._running = False
        self._mutex = QMutex()
        # NÃO conecte finished.connect(deleteLater) - causa crash
        # Lifecycle é gerenciado manualmente

    def run(self):
        cap = cv2.VideoCapture(self.camera_id)
        if not cap.isOpened():
            self.error.emit(f"Não foi possível abrir a câmera {self.camera_id}")
            return

        # Configurações da câmera
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

        # Detector RÁPIDO para overlay (sem FP filter pesado;
        # WebcamThread já tem filtros próprios: rosto, pele, aspect ratio)
        # Detector RÁPIDO para overlay - mais conservador para evitar falsos positivos
        detector = WoundDetectorCV(
            method=DetectionMethod.TEXTURE_PRIORITY,
            min_area=2000,              # Aumentado: áreas pequenas são mais propensas a FP
            confidence_threshold=0.55,   # Aumentado: exige mais certeza
            enable_false_positive_filter=False,  # Desligado no fast-path
            texture_weight=0.6,          # Aumentado: textura é mais confiável
            color_weight=0.2,            # Reduzido: cor de pele causa FP
        )

        # Filtro de rostos
        face_filter = FaceExclusionFilter()

        fps_timer = time.perf_counter()
        fps_count = 0
        fps_display = 0.0
        n_faces = 0

        # Controle de throtlling: detecta a cada N frames
        frame_counter = 0
        detect_every_n = 2          # Roda detecção a cada 2 frames
        cached_detections = []       # Reutiliza detecções entre frames
        cached_n_det = 0
        cached_annotations = []      # (x1,y1,x2,y2,label,conf)

        self._running = True
        while self._running:
            ret, frame = cap.read()
            if not ret:
                time.sleep(0.01)
                continue

            h, w = frame.shape[:2]
            frame_counter += 1

            # Atualiza detecção de rostos (já tem throttle interno de 5 frames)
            gray_full = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            face_filter.update_faces(gray_full)
            n_faces = len(face_filter.get_face_rects())

            # Só roda detecção a cada N frames; reusa resultado nos intermediários
            if frame_counter % detect_every_n == 0:
                # Redimensiona para processamento rápido
                proc_frame = frame
                if max(h, w) > 768:
                    scale = 768 / max(h, w)
                    proc_frame = cv2.resize(frame, (int(w * scale), int(h * scale)))

                cached_annotations = []
                cached_n_det = 0
                try:
                    detections = detector.detect(proc_frame)
                    scale_x = w / proc_frame.shape[1]
                    scale_y = h / proc_frame.shape[0]

                    for det in detections:
                        x1, y1, x2, y2 = det.bbox
                        x1 = int(x1 * scale_x)
                        y1 = int(y1 * scale_y)
                        x2 = int(x2 * scale_x)
                        y2 = int(y2 * scale_y)
                        conf = det.confidence

                        # FILTRO 1: Rejeita se sobrepõe rosto
                        if face_filter.overlaps_face((x1, y1, x2, y2)):
                            continue

                        # FILTRO 2: Rejeita pele uniforme saudável
                        roi = frame[max(0, y1):min(h, y2), max(0, x1):min(w, x2)]
                        if FaceExclusionFilter.is_uniform_skin(roi):
                            continue

                        # FILTRO 3: Aspect ratio
                        det_w = x2 - x1
                        det_h = y2 - y1
                        aspect = max(det_w, det_h) / max(min(det_w, det_h), 1)
                        if aspect > 5.0:
                            continue

                        wound_type = det.wound_type or "wound"
                        type_labels = {
                            "granulating_wound": "Granulação",
                            "necrotic_wound": "Necrose",
                            "infected_wound": "Infectada",
                            "pressure_injury": "Pressão",
                            "surgical_wound": "Cirúrgica",
                            "wound": "Ferida",
                        }
                        label_txt = type_labels.get(wound_type, "Ferida")
                        cached_annotations.append((x1, y1, x2, y2, f"{label_txt} {conf:.0%}", conf))
                        cached_n_det += 1

                except Exception:
                    cached_annotations = []
                    cached_n_det = 0

            # Desenha anotações (cached) sobre o frame atual
            annotated = frame.copy()
            for (x1, y1, x2, y2, label, conf) in cached_annotations:
                cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 255, 0), 2)
                # Usa PIL para texto com acentos
                annotated = cv2_put_text_utf8(
                    annotated, label, (x1 + 3, max(y1 - 20, 5)),
                    font_size=16, color=(0, 0, 0), bg_color=(0, 255, 0)
                )

            # Desenha rostos excluídos (azul tracejado)
            for (fx1, fy1, fx2, fy2) in face_filter.get_face_rects():
                cv2.rectangle(annotated, (fx1, fy1), (fx2, fy2), (255, 150, 50), 1)
                annotated = cv2_put_text_utf8(
                    annotated, "Rosto (ignorado)", (fx1, max(fy1 - 18, 5)),
                    font_size=12, color=(255, 150, 50)
                )

            # FPS
            fps_count += 1
            elapsed = time.perf_counter() - fps_timer
            if elapsed >= 1.0:
                fps_display = fps_count / elapsed
                fps_count = 0
                fps_timer = time.perf_counter()

            # HUD overlay
            n_det = cached_n_det
            hud_h = 90 if n_faces > 0 else 72
            cv2.rectangle(annotated, (8, 8), (290, hud_h), (0, 0, 0), -1)
            cv2.rectangle(annotated, (8, 8), (290, hud_h), (0, 255, 0), 1)
            annotated = cv2_put_text_utf8(
                annotated, f"HEAL+ LIVE  |  {fps_display:.0f} FPS",
                (14, 12), font_size=16, color=(0, 255, 0)
            )

            det_color = (0, 255, 0) if n_det > 0 else (100, 100, 100)
            status_txt = f"Feridas: {n_det}" if n_det > 0 else "Nenhuma ferida"
            annotated = cv2_put_text_utf8(
                annotated, status_txt,
                (14, 38), font_size=14, color=det_color
            )

            if n_faces > 0:
                annotated = cv2_put_text_utf8(
                    annotated, f"Rostos ignorados: {n_faces}",
                    (14, 62), font_size=12, color=(255, 150, 50)
                )

            # Indicador de "escaneando"
            scan_x = int((time.perf_counter() * 150) % w)
            cv2.line(annotated, (scan_x, 0), (scan_x, h), (0, 255, 0), 1)

            self.frame_ready.emit(annotated, frame)

        cap.release()

    def stop(self):
        """Para a thread de forma segura. Retorna True se parou com sucesso."""
        self._mutex.lock()
        self._running = False
        self._mutex.unlock()
        # Espera até 5 segundos para a thread terminar
        if not self.wait(5000):
            # Se não terminou, tenta terminar forçadamente
            self.terminate()
            self.wait(1000)
            return False
        return True


class RealtimeAnalysisThread(QThread):
    """Thread para análise clínica completa de um frame (roda em background)."""
    # IMPORTANT: Do NOT name this 'finished' — it shadows QThread.finished
    result_ready = pyqtSignal(object)

    def __init__(self, frame: np.ndarray, analyzer: ClinicalWoundAnalyzer, parent=None):
        super().__init__(parent)  # Parent garante cleanup adequado
        self.frame = frame.copy()
        self.analyzer = analyzer
        self._cancelled = False
        # NÃO conecte finished.connect(deleteLater) - causa crash
        # Lifecycle é gerenciado manualmente

    def run(self):
        try:
            if self._cancelled:
                return
            report = self.analyzer.analyze(self.frame)
            if not self._cancelled:
                self.result_ready.emit(report)
        except Exception as e:
            print(f"[HEAL+] Erro na análise em tempo real: {e}")

    def cancel(self):
        """Marca a thread como cancelada (não emitirá resultado)."""
        self._cancelled = True


# ============================================================
# APLICAÇÃO DESKTOP PyQt6
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

        # Webcam
        self._webcam_thread: Optional[WebcamThread] = None
        self._realtime_thread: Optional[RealtimeAnalysisThread] = None
        self._last_frame: Optional[np.ndarray] = None
        self._webcam_active = False
        self._analysis_interval_ms = 1000  # Análise completa a cada 1s
        self._last_analysis_time = 0.0
        self._rt_analyzer: Optional[ClinicalWoundAnalyzer] = None  # Instância reutilizável

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

        # === TAB 2: TEMPO REAL (WEBCAM) ===
        self.tab_webcam = QWidget()
        self._setup_webcam_tab()
        self.tab_widget.addTab(self.tab_webcam, "Tempo Real (Webcam)")

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
    def _setup_webcam_tab(self):
        """Configura aba de análise em tempo real (webcam)."""
        layout = QVBoxLayout(self.tab_webcam)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # Toolbar da aba
        toolbar = QHBoxLayout()

        # Botão iniciar/parar webcam
        self.btn_webcam = QPushButton("Iniciar Detecção em Tempo Real")
        self.btn_webcam.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        self.btn_webcam.setMinimumHeight(40)
        self.btn_webcam.setMinimumWidth(260)
        self.btn_webcam.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_webcam.setStyleSheet("""
            QPushButton {
                background: #16a34a;
                color: white; border: none; border-radius: 6px;
                padding: 0 24px; font-size: 13px;
            }
            QPushButton:hover { background: #22c55e; }
            QPushButton:pressed { background: #15803d; }
        """)
        self.btn_webcam.clicked.connect(self._toggle_webcam)
        toolbar.addWidget(self.btn_webcam)

        # Seletor de câmera
        toolbar.addSpacing(10)
        toolbar.addWidget(self._styled_label("Câmera:", "#94a3b8", 10))
        self.combo_camera = QComboBox()
        self.combo_camera.addItems(["0 (Padrão)", "1", "2", "3"])
        self.combo_camera.setMinimumWidth(100)
        self.combo_camera.setStyleSheet("""
            QComboBox {
                background: #334155; color: #e2e8f0; border: 1px solid #475569;
                border-radius: 6px; padding: 6px 12px;
            }
            QComboBox::drop-down { border: none; }
            QComboBox QAbstractItemView { background: #1e293b; color: #e2e8f0; }
        """)
        toolbar.addWidget(self.combo_camera)

        # Indicador de status
        toolbar.addSpacing(20)
        self.lbl_rt_status = QLabel("Parado")
        self.lbl_rt_status.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        self.lbl_rt_status.setStyleSheet("color: #64748b;")
        toolbar.addWidget(self.lbl_rt_status)

        toolbar.addStretch()
        layout.addLayout(toolbar)

        # Splitter principal
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(2)

        # LEFT: Feed da webcam
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(8)

        self.lbl_webcam_feed = QLabel("Clique em \"Iniciar Detecção\" para análise em tempo real")
        self.lbl_webcam_feed.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_webcam_feed.setMinimumSize(640, 480)
        self.lbl_webcam_feed.setFont(QFont("Segoe UI", 13))
        self.lbl_webcam_feed.setStyleSheet("""
            QLabel {
                background: #0f172a;
                border: 1px solid #334155;
                border-radius: 8px;
                color: #64748b;
            }
        """)
        left_layout.addWidget(self.lbl_webcam_feed, stretch=3)

        # Imagens de análise em tempo real
        rt_grid = QHBoxLayout()
        self.lbl_rt_segmentation = self._make_image_panel("Segmentação Tecidual")
        self.lbl_rt_overlay = self._make_image_panel("Overlay Clínico")
        rt_grid.addWidget(self.lbl_rt_segmentation)
        rt_grid.addWidget(self.lbl_rt_overlay)
        left_layout.addLayout(rt_grid, stretch=1)

        splitter.addWidget(left)

        # RIGHT: Laudo em tempo real
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
        self.rt_right_panel = QWidget()
        self.rt_right_panel.setStyleSheet("background: #0f172a;")
        self.rt_right_layout = QVBoxLayout(self.rt_right_panel)
        self.rt_right_layout.setContentsMargins(10, 8, 10, 10)
        self.rt_right_layout.setSpacing(10)
        self.rt_right_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # Placeholder
        self.rt_placeholder = QLabel(
            "Detecção e classificação de feridas em tempo real.\n\n"
            "Ao iniciar:\n"
            "  • Detecção de feridas a cada frame (bounding boxes)\n"
            "  • Classificação tecidual automática contínua\n"
            "  • Laudo clínico atualizado em tempo real\n\n"
            "Basta apontar a câmera para a ferida."
        )
        self.rt_placeholder.setFont(QFont("Segoe UI", 11))
        self.rt_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.rt_placeholder.setStyleSheet("""
            color: #64748b;
            padding: 40px;
            background: #0f172a;
        """)
        self.rt_placeholder.setWordWrap(True)
        self.rt_right_layout.addWidget(self.rt_placeholder)

        right_scroll.setWidget(self.rt_right_panel)
        splitter.addWidget(right_scroll)

        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        layout.addWidget(splitter, stretch=1)

    # -------------------------------------------------------
    def _on_tab_changed(self, index: int):
        """Callback quando troca de aba."""
        if index == 0:
            # Aba de imagem - para webcam se estiver ativa
            if self._webcam_active:
                self._stop_webcam()
            self.lbl_status.setText("Modo: Arquivo de Imagem")
        else:
            # Aba de tempo real
            self.lbl_status.setText("Modo: Tempo Real (Webcam)")

    # -------------------------------------------------------
    # WEBCAM METHODS
    # -------------------------------------------------------
    def _toggle_webcam(self):
        """Liga/desliga a webcam."""
        if self._webcam_active:
            self._stop_webcam()
        else:
            self._start_webcam()

    def _start_webcam(self):
        """Inicia detecção em tempo real."""
        camera_id = self.combo_camera.currentIndex()

        # Cria analyzer reutilizável (uma vez)
        if self._rt_analyzer is None:
            self.lbl_status.setText("Carregando motor de análise...")
            self.lbl_status.setStyleSheet("color: #fbbf24;")
            QApplication.processEvents()
            self._rt_analyzer = ClinicalWoundAnalyzer()

        self._webcam_thread = WebcamThread(camera_id, parent=self)
        # QueuedConnection garante que signals são processados na main thread
        self._webcam_thread.frame_ready.connect(self._on_frame_ready, Qt.ConnectionType.QueuedConnection)
        self._webcam_thread.error.connect(self._on_webcam_error, Qt.ConnectionType.QueuedConnection)
        self._webcam_thread.start()

        self._webcam_active = True
        self.btn_webcam.setText("Parar Detecção")
        self.btn_webcam.setStyleSheet("""
            QPushButton {
                background: #dc2626;
                color: white; border: none; border-radius: 6px;
                padding: 0 24px; font-size: 13px;
            }
            QPushButton:hover { background: #ef4444; }
            QPushButton:pressed { background: #b91c1c; }
        """)
        self.combo_camera.setEnabled(False)
        self.lbl_rt_status.setText("Escaneando")
        self.lbl_rt_status.setStyleSheet("color: #22c55e;")
        self.lbl_status.setText("Detecção em tempo real ativa — aponte a câmera para a ferida")
        self.lbl_status.setStyleSheet("color: #22c55e;")

    def _stop_webcam(self):
        """Para detecção em tempo real com shutdown seguro."""
        self._webcam_active = False

        # 1. DESCONECTA SIGNALS PRIMEIRO (impede novos callbacks durante cleanup)
        if self._webcam_thread is not None:
            try:
                self._webcam_thread.frame_ready.disconnect(self._on_frame_ready)
                self._webcam_thread.error.disconnect(self._on_webcam_error)
            except (TypeError, RuntimeError):
                pass  # Já desconectados ou objeto inválido

        # 2. Para a thread da webcam
        if self._webcam_thread is not None:
            self._webcam_thread.stop()  # seta _running=False + wait
            # NÃO define como None imediatamente; deleteLater cuidará disso
            wt = self._webcam_thread
            self._webcam_thread = None
            # Processa eventos pendentes para permitir deleteLater
            QApplication.processEvents()

        # 3. Para a thread de análise clínica (se estiver rodando)
        if self._realtime_thread is not None:
            try:
                self._realtime_thread.result_ready.disconnect(self._on_realtime_analysis_done)
            except (TypeError, RuntimeError):
                pass
            self._realtime_thread.cancel()
            if self._realtime_thread.isRunning():
                if not self._realtime_thread.wait(5000):
                    self._realtime_thread.terminate()
                    self._realtime_thread.wait(1000)
            self._realtime_thread = None
        self.btn_webcam.setText("Iniciar Detecção em Tempo Real")
        self.btn_webcam.setStyleSheet("""
            QPushButton {
                background: #16a34a;
                color: white; border: none; border-radius: 6px;
                padding: 0 24px; font-size: 13px;
            }
            QPushButton:hover { background: #22c55e; }
            QPushButton:pressed { background: #15803d; }
        """)
        self.combo_camera.setEnabled(True)
        self.lbl_webcam_feed.setText("Clique em \"Iniciar Detecção\" para análise em tempo real")
        self.lbl_webcam_feed.setPixmap(QPixmap())
        self.lbl_rt_status.setText("Parado")
        self.lbl_rt_status.setStyleSheet("color: #64748b;")
        self.lbl_status.setText("Detecção parada")
        self.lbl_status.setStyleSheet("color: #94a3b8;")

    def _on_frame_ready(self, annotated_frame: np.ndarray, raw_frame: np.ndarray):
        """Callback quando um frame com detecção está pronto."""
        # Guard: ignora se webcam já foi parada (signal pode ter chegado após stop)
        if not self._webcam_active or self._webcam_thread is None:
            return

        self._last_frame = raw_frame

        # Exibe frame anotado (já tem bounding boxes do detector)
        pixmap = np_to_qpixmap(annotated_frame, max_w=900)
        self.lbl_webcam_feed.setPixmap(pixmap)

        # Dispara análise clínica completa automaticamente a cada intervalo
        # Verifica que não há thread de análise ativa E que analyzer foi inicializado
        if self._webcam_active and self._realtime_thread is None and self._rt_analyzer is not None:
            current_time = time.time() * 1000
            if current_time - self._last_analysis_time > self._analysis_interval_ms:
                self._last_analysis_time = current_time
                thread = RealtimeAnalysisThread(raw_frame, self._rt_analyzer, parent=self)
                thread.result_ready.connect(self._on_realtime_analysis_done, Qt.ConnectionType.QueuedConnection)
                self._realtime_thread = thread  # referência forte antes de start()
                thread.start()

    def _on_webcam_error(self, error: str):
        """Callback de erro da webcam."""
        self.lbl_status.setText(f"Erro: {error}")
        self.lbl_status.setStyleSheet("color: #ef4444;")
        self.lbl_rt_status.setText("Erro")
        self.lbl_rt_status.setStyleSheet("color: #ef4444;")
        self._stop_webcam()

    def _on_realtime_analysis_done(self, report: ClinicalReport):
        """Callback quando análise clínica completa termina."""
        # Guard: ignora se webcam foi parada durante a análise
        if not self._webcam_active:
            self._realtime_thread = None
            return

        # Permite que a próxima análise seja agendada.
        # deleteLater (connected no __init__) cuida da limpeza segura do QThread.
        self._realtime_thread = None

        if not report.is_valid_wound:
            # Não mostra erro, apenas continua escaneando
            self.lbl_rt_status.setText("Escaneando (sem ferida)")
            self.lbl_rt_status.setStyleSheet("color: #f59e0b;")
            return

        # Monta status realtime com ResNet50
        rt_resnet_tag = ""
        if report.resnet_prediction:
            rn = report.resnet_prediction
            final_pt = rn.get("final_class_pt", "")
            if final_pt:
                rt_resnet_tag = f"  |  {final_pt}"

        self.lbl_rt_status.setText("Ferida detectada")
        self.lbl_rt_status.setStyleSheet("color: #22c55e;")
        self.lbl_status.setText(
            f"Ferida: {report.primary_tissue}  |  Score: {report.health_score:.0f}/100{rt_resnet_tag}  |  {report.processing_time_ms:.0f}ms"
        )
        self.lbl_status.setStyleSheet("color: #22c55e;")

        # Atualiza imagens de análise
        if report.segmentation_map is not None:
            self.lbl_rt_segmentation.setPixmap(np_to_qpixmap(report.segmentation_map, 350))
        if report.tissue_overlay is not None:
            self.lbl_rt_overlay.setPixmap(np_to_qpixmap(report.tissue_overlay, 350))

        # Atualiza laudo
        self._show_realtime_results(report)

    def _show_realtime_results(self, r: ClinicalReport):
        """Exibe resultados da análise em tempo real."""
        self._clear_rt_right_panel()

        # Classificação principal
        box_main = self._make_group("CLASSIFICAÇÃO")
        lbl_primary = QLabel(r.primary_tissue)
        lbl_primary.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        lbl_primary.setStyleSheet("color: #38bdf8; padding: 2px 0;")
        box_main.layout().addWidget(lbl_primary)

        # Score
        score_color = "#22c55e" if r.health_score >= 60 else ("#fbbf24" if r.health_score >= 30 else "#ef4444")
        score_row = QWidget()
        sl = QHBoxLayout(score_row)
        sl.setContentsMargins(0, 2, 0, 0)
        sl.addWidget(self._styled_label("Score:", "#94a3b8", 10))
        sl.addWidget(self._styled_label(f"{r.health_score:.0f}/100", score_color, 12, bold=True))
        sl.addStretch()
        box_main.layout().addWidget(score_row)

        self.rt_right_layout.addWidget(box_main)

        # Composição tecidual
        box_tissue = self._make_group("TECIDOS")
        for t in sorted(r.tissues, key=lambda x: -x.percentage):
            if t.percentage > 1:
                row = QWidget()
                rl = QHBoxLayout(row)
                rl.setContentsMargins(0, 1, 0, 1)
                swatch = QLabel()
                swatch.setFixedSize(10, 10)
                swatch.setStyleSheet(f"background: {t.color_hex}; border-radius: 2px;")
                rl.addWidget(swatch)
                # Trunca de forma segura para UTF-8 (sem cortar no meio de caractere)
                tissue_name = t.name if len(t.name) <= 25 else t.name[:22] + "..."
                rl.addWidget(self._styled_label(tissue_name, "#e2e8f0", 9))
                rl.addStretch()
                rl.addWidget(self._styled_label(f"{t.percentage:.0f}%", "#38bdf8", 9, bold=True))
                box_tissue.layout().addWidget(row)
        self.rt_right_layout.addWidget(box_tissue)

        # DL prediction
        if r.dl_prediction:
            box_dl = self._make_group("IA")
            dl = r.dl_prediction
            conf = dl.get("confidence", 0)
            conf_color = "#22c55e" if conf >= 0.7 else ("#fbbf24" if conf >= 0.4 else "#ef4444")
            lbl_cls = QLabel(f"{dl.get('display_name', 'N/A')} ({conf:.0%})")
            lbl_cls.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
            lbl_cls.setStyleSheet(f"color: {conf_color};")
            box_dl.layout().addWidget(lbl_cls)
            self.rt_right_layout.addWidget(box_dl)

        # ResNet50 Two-Stage prediction (tempo real)
        if r.resnet_prediction:
            rn = r.resnet_prediction
            box_rn = self._make_group("ETIOLOGIA (ResNet50)")

            s1 = rn.get("stage1", {})
            if s1:
                s1_wound = s1.get("is_wound", True)
                s1_conf = s1.get("confidence", 0)
                s1_text = "Ferida" if s1_wound else "Normal"
                s1_color = "#ef4444" if s1_wound else "#22c55e"
                s1_row = QWidget()
                s1l = QHBoxLayout(s1_row)
                s1l.setContentsMargins(0, 1, 0, 1)
                s1l.addWidget(self._styled_label("Triagem:", "#94a3b8", 9))
                s1l.addWidget(self._styled_label(f"{s1_text} ({s1_conf:.0%})", s1_color, 9, bold=True))
                s1l.addStretch()
                box_rn.layout().addWidget(s1_row)

            s2 = rn.get("stage2", {})
            if s2:
                s2_pt = s2.get("wound_type_pt", "")
                s2_conf = s2.get("confidence", 0)
                s2_color = "#22c55e" if s2_conf >= 0.7 else ("#fbbf24" if s2_conf >= 0.45 else "#ef4444")
                lbl_type = QLabel(f"{s2_pt} ({s2_conf:.0%})")
                lbl_type.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
                lbl_type.setStyleSheet(f"color: {s2_color};")
                box_rn.layout().addWidget(lbl_type)

            self.rt_right_layout.addWidget(box_rn)

        # Ação clínica
        box_action = self._make_group("AÇÃO CLÍNICA")
        dominant = max(r.tissues, key=lambda x: x.percentage)
        lbl_act = QLabel(dominant.clinical_action[:150] + "..." if len(dominant.clinical_action) > 150 else dominant.clinical_action)
        lbl_act.setWordWrap(True)
        lbl_act.setFont(QFont("Segoe UI", 9))
        lbl_act.setStyleSheet("color: #cbd5e1;")
        box_action.layout().addWidget(lbl_act)
        self.rt_right_layout.addWidget(box_action)

        # Escalas Clínicas (PUSH e BWAT) - versão compacta para tempo real
        if HAS_CLINICAL_SCALES and (r.push_score is not None or r.bwat_score is not None):
            box_scales = self._make_group("ESCALAS")
            
            # PUSH Score compacto
            if r.push_score is not None:
                push_total = r.push_score.get("total_score", 0)
                push_row = QWidget()
                pl = QHBoxLayout(push_row)
                pl.setContentsMargins(0, 1, 0, 1)
                pl.addWidget(self._styled_label("PUSH:", "#94a3b8", 9))
                push_color = "#22c55e" if push_total <= 5 else ("#fbbf24" if push_total <= 10 else "#ef4444")
                pl.addWidget(self._styled_label(f"{push_total}/17", push_color, 10, bold=True))
                pl.addStretch()
                box_scales.layout().addWidget(push_row)
            
            # BWAT Score compacto
            if r.bwat_score is not None:
                bwat_total = r.bwat_score.get("total_score", 0)
                severity = r.bwat_score.get("severity", "")
                bwat_row = QWidget()
                bl = QHBoxLayout(bwat_row)
                bl.setContentsMargins(0, 1, 0, 1)
                bl.addWidget(self._styled_label("BWAT:", "#94a3b8", 9))
                bwat_color = "#22c55e" if bwat_total <= 20 else ("#fbbf24" if bwat_total <= 35 else "#ef4444")
                bl.addWidget(self._styled_label(f"{bwat_total}/65 ({severity})", bwat_color, 10, bold=True))
                bl.addStretch()
                box_scales.layout().addWidget(bwat_row)
            
            self.rt_right_layout.addWidget(box_scales)

        self.rt_right_layout.addStretch()

    def _clear_rt_right_panel(self):
        """Limpa painel direito da aba tempo real."""
        while self.rt_right_layout.count():
            w = self.rt_right_layout.takeAt(0).widget()
            if w:
                w.deleteLater()

    # -------------------------------------------------------
    # ACTIONS
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
        if report.resnet_prediction:
            rn = report.resnet_prediction
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

        # --- CLASSIFICAÇÃO PRINCIPAL ---
        box_main = self._make_group("CLASSIFICAÇÃO PRINCIPAL")
        
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

        # --- COMPOSIÇÃO TECIDUAL ---
        box_tissue = self._make_group("COMPOSIÇÃO TECIDUAL")
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

        # --- CLASSIFICAÇÃO IA (Deep Learning) ---
        if r.dl_prediction:
            box_dl = self._make_group("CLASSIFICAÇÃO IA (Deep Learning)")
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

        # --- CLASSIFICAÇÃO RESNET50 (Dois Estágios) ---
        if r.resnet_prediction:
            rn = r.resnet_prediction
            box_rn = self._make_group("CLASSIFICAÇÃO ETIOLÓGICA (ResNet50)")

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

        # --- ANÁLISE DE BORDAS ---
        if r.border_analysis:
            box_border = self._make_group("ANÁLISE DE BORDAS E PERILESÃO")
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

        # --- AÇÕES CLÍNICAS ---
        box_actions = self._make_group("RECOMENDAÇÕES CLÍNICAS")
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

        # --- ANÁLISE DE ILUMINAÇÃO ---
        if r.lighting_analysis:
            box_light = self._make_group("ILUMINAÇÃO")
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
            box_body = self._make_group("REGIÃO ANATÔMICA")
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
        print("[HEAL+] Finalizando componentes com segurança...")

        # Para webcam + análise em tempo real (sempre, mesmo se _webcam_active é False)
        self._stop_webcam()

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

        print("[HEAL+] Encerramento concluído.")
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
