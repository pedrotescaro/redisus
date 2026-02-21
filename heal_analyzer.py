"""
HEAL+ / REDISUS — Analisador Clínico de Feridas v2.0 (Desktop PyQt6)
=====================================================================

Aplicação especialista em Estomaterapia com Visão Computacional + IA.

Taxonomia clínica rigorosa:
  1. Necrose de Coagulação (Escara)  — preto/marrom, endurecido, seco ou úmido
  2. Esfacelo (Fibrina)              — amarelo/branco, viscoso ou fibroso
  3. Tecido de Granulação             — vermelho brilhante, úmido, granulado
  4. Epitelização                     — rosa claro/translúcido, avança das bordas

Pipeline v2:
  Imagem → Validação → Detecção → Segmentação Multi-Espaço (HSV+LAB)
        → Análise de Textura → Classificação DL (EfficientNet + TTA)
        → Análise de Bordas → Laudo Clínico

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
import time
from pathlib import Path
from typing import Dict, Optional, Tuple, List
from dataclasses import dataclass, field

# Import torch BEFORE cv2 to avoid DLL conflicts on Windows
try:
    import torch
    from torchvision import transforms as _tv_transforms
    _TORCH_AVAILABLE = True
except ImportError:
    _TORCH_AVAILABLE = False

import cv2
import numpy as np

# Path setup
sys.path.insert(0, str(Path(__file__).resolve().parent))

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QFileDialog, QScrollArea, QFrame,
    QProgressBar, QSplitter, QGroupBox, QTextEdit, QSizePolicy,
    QGraphicsDropShadowEffect,
)
from PyQt6.QtCore import Qt, QSize, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QImage, QPixmap, QFont, QColor, QPalette, QIcon

# ============================================================
# Módulos do projeto
# ============================================================
from src.processing.wound_detector_cv import WoundDetectorCV, DetectionMethod
from src.processing.tissue_analyzer import TissueAnalyzerCV, TissueType, TISSUE_COLORS
from src.processing.wound_classifier_cv import WoundClassifierCV

try:
    from src.diagnosis.tissue_segmenter import UNetSegmenter
    from src.diagnosis.etiology_classifier import EtiologyClassifier
    from src.diagnosis.wound_analyzer import WoundAnalyzer
    HAS_DL_MODULES = True
except ImportError:
    HAS_DL_MODULES = False


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
        # Preto absoluto
        (np.array([0, 0, 0]), np.array([180, 255, 40])),
        # Marrom muito escuro
        (np.array([5, 30, 15]), np.array([25, 200, 70])),
        # Escuro com saturação baixa (necrose seca)
        (np.array([0, 0, 40]), np.array([180, 40, 65])),
        # Marrom escuro acinzentado
        (np.array([8, 15, 25]), np.array([22, 150, 75])),
    ],
    "slough": [
        # Amarelo fibrina puro
        (np.array([15, 50, 140]), np.array([38, 255, 255])),
        # Branco amarelado (fibrina clara)
        (np.array([0, 0, 185]), np.array([30, 55, 255])),
        # Cinza-amarelado
        (np.array([15, 20, 120]), np.array([40, 100, 200])),
        # Amarelo-esverdeado (fibrina contaminada)
        (np.array([30, 30, 130]), np.array([50, 180, 230])),
        # Bege / amarelo pálido
        (np.array([12, 25, 160]), np.array([28, 90, 240])),
    ],
    "granulation": [
        # Vermelho vivo intenso (H wrap around 0/180)
        (np.array([0, 100, 80]), np.array([10, 255, 255])),
        (np.array([160, 100, 80]), np.array([180, 255, 255])),
        # Vermelho rosado moderado
        (np.array([0, 60, 100]), np.array([8, 200, 255])),
        (np.array([165, 60, 100]), np.array([180, 200, 255])),
        # Vermelho escuro (granulação madura)
        (np.array([0, 80, 60]), np.array([12, 255, 150])),
        (np.array([158, 80, 60]), np.array([180, 255, 150])),
    ],
    "epithelialization": [
        # Rosa claro
        (np.array([0, 15, 170]), np.array([15, 70, 255])),
        (np.array([155, 15, 170]), np.array([175, 70, 255])),
        # Rosa pálido quase branco
        (np.array([0, 8, 195]), np.array([12, 45, 255])),
        (np.array([160, 8, 195]), np.array([180, 45, 255])),
        # Salmão claro
        (np.array([2, 25, 185]), np.array([18, 80, 255])),
    ],
}

# Intervalos no espaço LAB para refinamento
# L: luminosidade (0=preto, 255=branco)
# A: verde(-) → vermelho(+)
# B: azul(-) → amarelo(+)
CLINICAL_LAB_RANGES = {
    "necrosis": [
        # Muito escuro, qualquer crominância
        (np.array([0, 100, 100]), np.array([50, 145, 145])),
        # Marrom escuro (L baixo, a+, b+)
        (np.array([15, 128, 120]), np.array([65, 160, 160])),
    ],
    "slough": [
        # Amarelo claro (L alto, b muito positivo)
        (np.array([150, 110, 145]), np.array([240, 140, 200])),
        # Bege/branco-amarelado
        (np.array([170, 118, 130]), np.array([250, 138, 165])),
    ],
    "granulation": [
        # Vermelho (a muito positivo, L médio)
        (np.array([40, 145, 115]), np.array([180, 220, 165])),
        # Vermelho escuro
        (np.array([25, 140, 110]), np.array([100, 200, 150])),
    ],
    "epithelialization": [
        # Rosa (L alto, a levemente positivo, b neutro)
        (np.array([170, 132, 120]), np.array([240, 155, 142])),
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

    def __init__(self):
        self.detector = WoundDetectorCV(
            method=DetectionMethod.COMBINED,
            min_area=300,
            confidence_threshold=0.20,
            enable_false_positive_filter=False,
        )
        self.tissue_analyzer = TissueAnalyzerCV()
        self.classifier = WoundClassifierCV()

        # Deep Learning model (carregado sob demanda)
        self._dl_model = None
        self._dl_metadata = None
        self._dl_available = False
        self._load_dl_model()

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
                    with open(mp) as f:
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

        # 3. Detecção de regiões de ferida
        detections = self.detector.detect(image)

        # Cria máscara da região de interesse
        wound_mask = np.zeros(image.shape[:2], dtype=np.uint8)
        if detections:
            for det in detections:
                x1, y1, x2, y2 = det.bbox
                wound_mask[y1:y2, x1:x2] = 255
        else:
            # Assume imagem inteira é área de ferida (close-up)
            wound_mask[:] = 255

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

        # 4. Segmentação tecidual clínica (HSV + LAB multi-espaço)
        tissue_pcts, seg_map, tissue_overlay = self._segment_clinical_v2(image, wound_mask)
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

        # 9. Deep Learning — classificação etiológica (se disponível)
        dl_result = self._predict_dl(image)
        if dl_result:
            report.dl_prediction = dl_result

        report.processing_time_ms = (time.perf_counter() - t0) * 1000
        return report

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
    def _segment_clinical(
        self, image: np.ndarray, wound_mask: np.ndarray
    ) -> Tuple[Dict[str, float], np.ndarray, np.ndarray]:
        """Segmenta a ferida segundo taxonomia clínica (v1 — legado)."""
        return self._segment_clinical_v2(image, wound_mask)

    def _segment_clinical_v2(
        self, image: np.ndarray, wound_mask: np.ndarray
    ) -> Tuple[Dict[str, float], np.ndarray, np.ndarray]:
        """
        Segmentação clínica v2 — multi-espaço de cor + textura.

        Pipeline:
        1. Denoise bilateral (preserva bordas melhor que NLMeans)
        2. Conversão HSV + LAB
        3. Segmentação em cada espaço de cor
        4. Fusão com voto ponderado (HSV 60% + LAB 40%)
        5. Refinamento morfológico adaptativo
        6. Análise de textura para ambiguidades
        """
        # 1. Denoise: bilateral preserva bordas melhor
        denoised = cv2.bilateralFilter(image, d=9, sigmaColor=50, sigmaSpace=50)
        # Aplica leve CLAHE para normalizar iluminação
        lab_clahe = cv2.cvtColor(denoised, cv2.COLOR_BGR2LAB)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        lab_clahe[:, :, 0] = clahe.apply(lab_clahe[:, :, 0])
        denoised_norm = cv2.cvtColor(lab_clahe, cv2.COLOR_LAB2BGR)

        hsv = cv2.cvtColor(denoised_norm, cv2.COLOR_BGR2HSV)
        lab = cv2.cvtColor(denoised_norm, cv2.COLOR_BGR2LAB)

        h, w = image.shape[:2]
        kernel_s = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        kernel_m = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        kernel_l = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9))

        # 2. Segmentação HSV
        hsv_masks = {}
        for tissue_key, ranges in CLINICAL_HSV_RANGES.items():
            mask = np.zeros((h, w), dtype=np.uint8)
            for lower, upper in ranges:
                mask = cv2.bitwise_or(mask, cv2.inRange(hsv, lower, upper))
            mask = cv2.bitwise_and(mask, wound_mask)
            mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel_s)
            mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel_m)
            hsv_masks[tissue_key] = mask

        # 3. Segmentação LAB (refinamento)
        lab_masks = {}
        for tissue_key, ranges in CLINICAL_LAB_RANGES.items():
            mask = np.zeros((h, w), dtype=np.uint8)
            for lower, upper in ranges:
                mask = cv2.bitwise_or(mask, cv2.inRange(lab, lower, upper))
            mask = cv2.bitwise_and(mask, wound_mask)
            mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel_s)
            mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel_m)
            lab_masks[tissue_key] = mask

        # 4. Fusão ponderada HSV (60%) + LAB (40%)
        masks = {}
        for tissue_key in CLINICAL_HSV_RANGES.keys():
            hsv_m = hsv_masks.get(tissue_key, np.zeros((h, w), dtype=np.uint8))
            lab_m = lab_masks.get(tissue_key, np.zeros((h, w), dtype=np.uint8))

            # Score combinado por pixel
            combined = (hsv_m.astype(np.float32) * 0.6 +
                        lab_m.astype(np.float32) * 0.4)
            # Threshold: se pelo menos um detector forte OU ambos fracos concordam
            mask = np.where(combined > 80, 255, 0).astype(np.uint8)

            # Refinamento morfológico
            mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel_s)
            mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel_l)
            mask = cv2.bitwise_and(mask, wound_mask)
            masks[tissue_key] = mask

        # 5. Refinamento por textura — usa variância local para resolver ambiguidades
        gray = cv2.cvtColor(denoised_norm, cv2.COLOR_BGR2GRAY)
        local_var = cv2.GaussianBlur(
            (gray.astype(np.float32) ** 2), (15, 15), 0
        ) - cv2.GaussianBlur(gray.astype(np.float32), (15, 15), 0) ** 2
        local_var = np.clip(local_var, 0, None)

        # Necrose tende a ter textura baixa (homogênea)
        # Granulação tende a ter textura alta (grânulos)
        low_texture = (local_var < 200).astype(np.uint8)
        high_texture = (local_var > 500).astype(np.uint8)

        # Reforça necrose em áreas de baixa textura + escuro
        dark_px = (gray < 60).astype(np.uint8) * 255
        masks["necrosis"] = cv2.bitwise_or(
            masks["necrosis"],
            cv2.bitwise_and(cv2.bitwise_and(dark_px, wound_mask),
                            (low_texture * 255).astype(np.uint8))
        )

        # Reforça granulação em áreas de alta textura + vermelho
        red_channel = denoised_norm[:, :, 2]  # BGR → canal R
        red_dominant = ((red_channel.astype(np.int16) - denoised_norm[:, :, 1].astype(np.int16)) > 30).astype(np.uint8) * 255
        masks["granulation"] = cv2.bitwise_or(
            masks["granulation"],
            cv2.bitwise_and(cv2.bitwise_and(red_dominant, wound_mask),
                            (high_texture * 255).astype(np.uint8))
        )

        # 6. Resolução de sobreposições — prioridade clínica
        priority = ["necrosis", "slough", "granulation", "epithelialization"]
        used = np.zeros((h, w), dtype=np.uint8)
        for key in priority:
            masks[key] = cv2.bitwise_and(masks[key], cv2.bitwise_not(used))
            used = cv2.bitwise_or(used, masks[key])

        # Porcentagens
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

        # Overlay na imagem original
        overlay = image.copy()
        cv2.addWeighted(seg_map, 0.45, overlay, 0.55, 0, overlay)

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
        """Score de saúde: granulação/epitelização → bom; necrose → ruim."""
        gran = pcts.get("granulation", 0)
        epit = pcts.get("epithelialization", 0)
        slough = pcts.get("slough", 0)
        necro = pcts.get("necrosis", 0)

        score = 50 + (gran * 0.8 + epit * 1.5) - (necro * 1.5 + slough * 0.5)
        return max(0.0, min(100.0, score))


# ============================================================
# THREAD DE ANÁLISE (não trava a UI)
# ============================================================

class AnalysisThread(QThread):
    finished = pyqtSignal(object)
    progress = pyqtSignal(str)

    def __init__(self, image_path: str):
        super().__init__()
        self.image_path = image_path

    def run(self):
        self.progress.emit("Carregando imagem...")
        image = cv2.imread(self.image_path)
        if image is None:
            report = ClinicalReport(is_valid_wound=False,
                                    rejection_reason="Não foi possível carregar a imagem.")
            self.finished.emit(report)
            return

        self.progress.emit("Analisando ferida...")
        analyzer = ClinicalWoundAnalyzer()
        report = analyzer.analyze(image)
        self.finished.emit(report)


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
        header = QLabel("HEAL+ — Analisador Clínico de Feridas")
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        header.setStyleSheet("color: #38bdf8; padding: 6px;")
        main_layout.addWidget(header)

        subtitle = QLabel("Especialista em Estomaterapia e Visão Computacional  ·  Classificação Tecidual Rigorosa")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setFont(QFont("Segoe UI", 10))
        subtitle.setStyleSheet("color: #94a3b8; padding-bottom: 4px;")
        main_layout.addWidget(subtitle)

        # === TOOLBAR ===
        toolbar = QHBoxLayout()
        self.btn_open = QPushButton("📂  Abrir Imagem de Ferida")
        self.btn_open.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        self.btn_open.setMinimumHeight(44)
        self.btn_open.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_open.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #0ea5e9, stop:1 #6366f1);
                color: white; border: none; border-radius: 8px;
                padding: 0 24px; font-size: 13px;
            }
            QPushButton:hover { background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                stop:0 #38bdf8, stop:1 #818cf8); }
            QPushButton:pressed { background: #0284c7; }
        """)
        self.btn_open.clicked.connect(self._on_open_image)
        toolbar.addWidget(self.btn_open)

        self.lbl_status = QLabel("Nenhuma imagem carregada")
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

        # === CONTENT ===
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

        img_grid = QHBoxLayout()
        col1 = QVBoxLayout()
        col1.addWidget(self.lbl_img_original)
        col1.addWidget(self.lbl_img_segmentation)
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
            QScrollArea { border: none; background: transparent; }
            QScrollBar:vertical { background: #1e293b; width: 8px; }
            QScrollBar::handle:vertical { background: #475569; border-radius: 4px; }
        """)
        self.right_panel = QWidget()
        self.right_layout = QVBoxLayout(self.right_panel)
        self.right_layout.setContentsMargins(8, 0, 8, 8)
        self.right_layout.setSpacing(8)
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
        self.lbl_placeholder.setStyleSheet("color: #64748b; padding: 40px;")
        self.lbl_placeholder.setWordWrap(True)
        self.right_layout.addWidget(self.lbl_placeholder)

        right_scroll.setWidget(self.right_panel)
        splitter.addWidget(right_scroll)

        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        main_layout.addWidget(splitter, stretch=1)

        # Footer
        footer = QLabel("HEAL/REDISUS — Plataforma Nacional de Saúde Digital  ·  Cluster REDISUS — RNP/RUTE")
        footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        footer.setFont(QFont("Segoe UI", 8))
        footer.setStyleSheet("color: #475569; padding: 4px;")
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

        self._thread = AnalysisThread(path)
        self._thread.progress.connect(self._on_progress)
        self._thread.finished.connect(self._on_analysis_done)
        self._thread.start()

    def _on_progress(self, msg: str):
        self.lbl_status.setText(msg)

    def _on_analysis_done(self, report: ClinicalReport):
        self.progress.setVisible(False)
        self.btn_open.setEnabled(True)
        self._current_report = report

        if not report.is_valid_wound:
            self.lbl_status.setText("⚠ Análise concluída — Input Inválido")
            self.lbl_status.setStyleSheet("color: #ef4444;")
            self._show_invalid(report)
            return

        self.lbl_status.setText(
            f"✓ Análise concluída  ·  {report.processing_time_ms:.0f}ms  ·  "
            f"Classificação: {report.primary_tissue}"
        )
        self.lbl_status.setStyleSheet("color: #22c55e;")
        self._show_results(report)

    # -------------------------------------------------------
    def _show_invalid(self, report: ClinicalReport):
        if report.original is not None:
            self.lbl_img_original.setPixmap(np_to_qpixmap(report.original, 400))
        self._clear_right_panel()
        lbl = QLabel(f"⚠ {report.rejection_reason}")
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

        self._clear_right_panel()

        # --- CLASSIFICAÇÃO PRINCIPAL ---
        box_main = self._make_group("🔬 CLASSIFICAÇÃO PRINCIPAL")
        lbl_primary = QLabel(r.primary_tissue)
        lbl_primary.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        lbl_primary.setStyleSheet("color: #38bdf8; padding: 4px 0;")
        box_main.layout().addWidget(lbl_primary)

        lbl_just = QLabel(r.primary_justification)
        lbl_just.setWordWrap(True)
        lbl_just.setFont(QFont("Segoe UI", 10))
        lbl_just.setStyleSheet("color: #cbd5e1; padding: 2px 0 6px;")
        box_main.layout().addWidget(lbl_just)
        self.right_layout.addWidget(box_main)

        # --- COMPOSIÇÃO TECIDUAL ---
        box_tissue = self._make_group("📊 COMPOSIÇÃO TECIDUAL")
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
            bar_bg.setFixedHeight(6)
            bar_bg.setStyleSheet("background: #1e293b; border-radius: 3px;")
            bar_inner = QFrame(bar_bg)
            bar_inner.setFixedHeight(6)
            pct_clamped = min(t.percentage, 100)
            bar_inner.setFixedWidth(max(int(pct_clamped * 2.5), 1))
            bar_inner.setStyleSheet(f"background: {t.color_hex}; border-radius: 3px;")
            box_tissue.layout().addWidget(bar_bg)

        # Score
        score_row = QWidget()
        sl = QHBoxLayout(score_row)
        sl.setContentsMargins(0, 8, 0, 0)
        sl.addWidget(self._styled_label("Score de Saúde:", "#94a3b8", 10))
        score_color = "#22c55e" if r.health_score >= 60 else ("#fbbf24" if r.health_score >= 30 else "#ef4444")
        sl.addWidget(self._styled_label(f"{r.health_score:.0f}/100", score_color, 12, bold=True))
        sl.addStretch()
        box_tissue.layout().addWidget(score_row)

        self.right_layout.addWidget(box_tissue)

        # --- CLASSIFICAÇÃO IA (Deep Learning) ---
        if r.dl_prediction:
            box_dl = self._make_group("🧠 CLASSIFICAÇÃO IA (Deep Learning)")
            dl = r.dl_prediction

            # Classe principal
            lbl_cls = QLabel(dl.get("display_name", "N/A"))
            lbl_cls.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
            conf = dl.get("confidence", 0)
            conf_color = "#22c55e" if conf >= 0.7 else ("#fbbf24" if conf >= 0.4 else "#ef4444")
            lbl_cls.setStyleSheet(f"color: {conf_color}; padding: 2px 0;")
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
                note = QLabel("⚠ Confiança baixa — recomenda-se avaliação por especialista")
                note.setWordWrap(True)
                note.setFont(QFont("Segoe UI", 9))
                note.setStyleSheet("color: #fbbf24; padding-top: 4px;")
                box_dl.layout().addWidget(note)

            self.right_layout.addWidget(box_dl)

        # --- ANÁLISE DE BORDAS ---
        if r.border_analysis:
            box_border = self._make_group("🔎 ANÁLISE DE BORDAS E PERILESÃO")
            ba = r.border_analysis

            flags = []
            if ba.maceration:
                flags.append(("⚠ Maceração perilesional", "#fbbf24"))
            if ba.inflammation:
                flags.append(("⚠ Inflamação perilesional", "#ef4444"))
            if not ba.regular_borders:
                flags.append(("Bordas irregulares", "#f97316"))
            if not flags:
                flags.append(("✓ Sem alterações perilesionais", "#22c55e"))

            for text, color in flags:
                box_border.layout().addWidget(self._styled_label(text, color, 10))

            lbl_desc = QLabel(ba.description)
            lbl_desc.setWordWrap(True)
            lbl_desc.setFont(QFont("Segoe UI", 9))
            lbl_desc.setStyleSheet("color: #94a3b8; padding-top: 4px;")
            box_border.layout().addWidget(lbl_desc)
            self.right_layout.addWidget(box_border)

        # --- AÇÕES CLÍNICAS ---
        box_actions = self._make_group("💊 RECOMENDAÇÕES CLÍNICAS")
        dominant = max(r.tissues, key=lambda x: x.percentage)
        lbl_act = QLabel(dominant.clinical_action)
        lbl_act.setWordWrap(True)
        lbl_act.setFont(QFont("Segoe UI", 10))
        lbl_act.setStyleSheet("color: #cbd5e1;")
        box_actions.layout().addWidget(lbl_act)

        for t in r.tissues:
            if t.percentage > 10 and t.name != dominant.name:
                lbl_sec = QLabel(f"• {t.name}: {t.clinical_action}")
                lbl_sec.setWordWrap(True)
                lbl_sec.setFont(QFont("Segoe UI", 9))
                lbl_sec.setStyleSheet("color: #94a3b8; padding-top: 2px;")
                box_actions.layout().addWidget(lbl_sec)

        self.right_layout.addWidget(box_actions)

        # --- METADADOS ---
        box_meta = self._make_group("ℹ METADADOS")
        dl_status = "✓ Ativo (TTA)" if r.dl_prediction else "Não disponível"
        pipeline_desc = "Detecção (OpenCV) → Segm. HSV+LAB → Textura → DL"
        meta_items = [
            ("Área da ferida", f"{r.wound_area_px:,} px"),
            ("Tempo de processamento", f"{r.processing_time_ms:.0f} ms"),
            ("Pipeline", pipeline_desc),
            ("Segmentação", "Multi-espaço (HSV 60% + LAB 40%) + Textura"),
            ("Modelo DL", dl_status),
            ("Versão", "HEAL+ v2.0 — Análise Clínica Avançada"),
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
        self.right_layout.addStretch()

    # -------------------------------------------------------
    # HELPERS
    # -------------------------------------------------------
    def _make_group(self, title: str) -> QGroupBox:
        box = QGroupBox(title)
        box.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        box.setStyleSheet("""
            QGroupBox {
                background: rgba(30, 41, 59, 0.7);
                border: 1px solid #334155;
                border-radius: 10px;
                margin-top: 12px;
                padding: 14px 10px 10px;
                color: #38bdf8;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 6px;
                color: #38bdf8;
            }
        """)
        layout = QVBoxLayout()
        layout.setSpacing(4)
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


# ============================================================
# MAIN
# ============================================================

def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    window = HealAnalyzerApp()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
