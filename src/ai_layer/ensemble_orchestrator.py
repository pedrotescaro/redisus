"""
REDISUS - Ensemble Orchestrator (Multi-Model Fusion)
=====================================================

Orquestração de múltiplos modelos de IA com fusão de resultados:
  - Classificação: Weighted Soft Voting (EfficientNet + DermaIntel + BiomedCLIP)
  - Segmentação: Mask Fusion (U-Net tissue + MedSAM boundary)
  - Métricas extras: infecção e severidade (BiomedCLIP)

Pesos padrão:
  EfficientNet (local):  0.35
  DermaIntel ViT:        0.40
  BiomedCLIP zero-shot:  0.25

Agreement scoring:
  - Boost 1.15× se todos concordam na mesma classe
  - Penalty 0.85× se há discordância
"""
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np
from loguru import logger

from .dermaintel_classifier import DermaIntelClassifier, DermaIntelResult
from .medsam_segmenter import MedSAMSegmenter, MedSAMSegmentationResult
from .biomedclip_analyzer import BiomedCLIPAnalyzer, BiomedCLIPResult


# Nomes REDISUS para as 5 classes
REDISUS_NAMES = {
    0: "Úlcera Venosa",
    1: "Úlcera Arterial",
    2: "Pé Diabético",
    3: "Lesão por Pressão",
    4: "Ferida Cirúrgica",
}


@dataclass
class ModelAgreement:
    """Métricas de concordância entre modelos."""
    models_agree: bool
    agreement_score: float    # 0 (todos discordam) a 1 (todos concordam)
    individual_predictions: Dict[str, str]  # model_name → class_name
    confidence_boost: float   # multiplicador aplicado


@dataclass
class EnsembleClassificationResult:
    """Resultado da classificação por ensemble."""
    class_id: int
    class_name: str
    confidence: float
    all_probabilities: Dict[int, float]   # class_id → prob
    agreement: ModelAgreement
    individual_results: Dict[str, Any]    # model_name → result
    # Confiança e revisão (baseado no notebook wounds_classifier_embeddings.ipynb)
    needs_expert_review: bool = False
    confidence_entropy: float = 0.0       # Entropia normalizada da distribuição fundida
    confidence_margin: float = 0.0        # Margem entre top-2 classes


@dataclass
class EnsembleSegmentationResult:
    """Resultado da segmentação por ensemble."""
    fused_mask: np.ndarray          # U-Net tissue classes dentro do MedSAM boundary
    medsam_boundary: np.ndarray     # Máscara binária MedSAM
    wound_area_pixels: int
    circularity: float
    individual_results: Dict[str, Any]


@dataclass
class EnsembleResult:
    """Resultado completo do ensemble."""
    classification: EnsembleClassificationResult
    segmentation: Optional[EnsembleSegmentationResult]
    infection_risk: float           # 0 a 1
    severity_index: float           # 0 a 1
    infection_scores: Dict[str, float]
    severity_scores: List[float]
    total_inference_time_ms: float
    models_loaded: Dict[str, bool]


class EnsembleOrchestrator:
    """
    Orquestrador multi-modelo que combina:
      - DermaIntel ViT (classificação)
      - MedSAM (segmentação)
      - BiomedCLIP (zero-shot: classificação + infecção + severidade)
    com os modelos base do REDISUS (EfficientNet + U-Net).
    """

    # Pesos para classificação (Weighted Soft Voting)
    DEFAULT_WEIGHTS = {
        "efficientnet": 0.35,
        "dermaintel": 0.40,
        "biomedclip": 0.25,
    }

    # Pesos para fusão de segmentação
    SEG_WEIGHT_UNET = 0.40
    SEG_WEIGHT_MEDSAM = 0.60

    def __init__(
        self,
        dermaintel: Optional[DermaIntelClassifier] = None,
        medsam: Optional[MedSAMSegmenter] = None,
        biomedclip: Optional[BiomedCLIPAnalyzer] = None,
        classification_weights: Optional[Dict[str, float]] = None,
    ):
        self.dermaintel = dermaintel or DermaIntelClassifier()
        self.medsam = medsam or MedSAMSegmenter()
        self.biomedclip = biomedclip or BiomedCLIPAnalyzer()

        self.weights = classification_weights or self.DEFAULT_WEIGHTS.copy()
        self._loaded = False

    # ------------------------------------------------------------------
    def load_all_models(self) -> Dict[str, bool]:
        """Carrega todos os modelos. Retorna status de cada um."""
        status: Dict[str, bool] = {}

        def _safe_load(name, model):
            try:
                return name, model.load_model()
            except Exception as e:
                logger.error(f"Ensemble: erro ao carregar {name}: {e}")
                return name, False

        # Carregamento sequencial evita deadlocks/circular imports do
        # torchvision em ambientes Windows/Python 3.14.
        for name, model in (
            ("dermaintel", self.dermaintel),
            ("medsam", self.medsam),
            ("biomedclip", self.biomedclip),
        ):
            loaded_name, ok = _safe_load(name, model)
            status[loaded_name] = ok

        self._loaded = True
        loaded_count = sum(1 for v in status.values() if v)
        logger.info(f"Ensemble: {loaded_count}/3 modelos carregados: {status}")
        return status

    # ------------------------------------------------------------------
    def predict(
        self,
        image: np.ndarray,
        bbox: Optional[Tuple[int, int, int, int]] = None,
        efficientnet_probs: Optional[Dict[int, float]] = None,
        unet_mask: Optional[np.ndarray] = None,
    ) -> EnsembleResult:
        """
        Executa ensemble completo.

        Args:
            image: BGR (H, W, 3)
            bbox: bounding box da ferida (x1, y1, x2, y2)
            efficientnet_probs: probabilidades do modelo base REDISUS (5 classes)
            unet_mask: máscara de segmentação do U-Net base (H, W)
        """
        start = time.perf_counter()

        # Executa modelos em paralelo
        dermaintel_result: Optional[DermaIntelResult] = None
        medsam_result: Optional[MedSAMSegmentationResult] = None
        biomedclip_result: Optional[BiomedCLIPResult] = None

        def _safe_dermaintel():
            try:
                return self.dermaintel.classify(image)
            except Exception as e:
                logger.error(f"Ensemble/dermaintel: {e}")
                return None

        def _safe_medsam():
            try:
                return self.medsam.segment(image, bbox)
            except Exception as e:
                logger.error(f"Ensemble/medsam: {e}")
                return None

        def _safe_biomedclip():
            try:
                return self.biomedclip.analyze(image)
            except Exception as e:
                logger.error(f"Ensemble/biomedclip: {e}")
                return None

        with ThreadPoolExecutor(max_workers=5) as executor:
            f_di = executor.submit(_safe_dermaintel)
            f_ms = executor.submit(_safe_medsam)
            f_bc = executor.submit(_safe_biomedclip)

            dermaintel_result = f_di.result()
            medsam_result = f_ms.result()
            biomedclip_result = f_bc.result()

        # ---- Classificação por Weighted Soft Voting ----
        classification = self._fuse_classification(
            efficientnet_probs, dermaintel_result, biomedclip_result
        )

        # ---- Segmentação por Mask Fusion ----
        segmentation = self._fuse_segmentation(unet_mask, medsam_result)

        # ---- Infecção e Severidade (BiomedCLIP) ----
        if biomedclip_result:
            infection_risk = biomedclip_result.infection_risk
            severity_index = biomedclip_result.severity_index
            infection_scores = biomedclip_result.infection_scores
            severity_scores = biomedclip_result.severity_scores
        else:
            infection_risk = 0.0
            severity_index = 0.0
            infection_scores = {}
            severity_scores = []

        elapsed_ms = (time.perf_counter() - start) * 1000

        return EnsembleResult(
            classification=classification,
            segmentation=segmentation,
            infection_risk=infection_risk,
            severity_index=severity_index,
            infection_scores=infection_scores,
            severity_scores=severity_scores,
            total_inference_time_ms=elapsed_ms,
            models_loaded={
                "dermaintel": self.dermaintel.is_loaded,
                "medsam": self.medsam.is_loaded,
                "biomedclip": self.biomedclip.is_loaded,
            },
        )

    # ==================================================================
    #  CLASSIFICATION FUSION
    # ==================================================================
    def _fuse_classification(
        self,
        efficientnet_probs: Optional[Dict[int, float]],
        dermaintel_result: Optional[DermaIntelResult],
        biomedclip_result: Optional[BiomedCLIPResult],
    ) -> EnsembleClassificationResult:
        """Fusão por Confidence-Weighted Soft Voting de até 3 modelos.
        
        Melhorado com pesos adaptativos baseados na confiança individual
        de cada modelo (técnica inspirada no notebook embeddings).
        """

        fused = np.zeros(5, dtype=np.float64)
        total_weight = 0.0
        individual: Dict[str, Any] = {}

        # EfficientNet (modelo base REDISUS)
        if efficientnet_probs:
            w = self.weights.get("efficientnet", 0.35)
            # Confidence-weighted: modelos mais confiantes têm mais peso
            eff_conf = max(efficientnet_probs.values()) if efficientnet_probs else 0.5
            adaptive_w = w * (0.5 + 0.5 * eff_conf)  # [w*0.5, w*1.0]
            for cid, p in efficientnet_probs.items():
                fused[cid] += p * adaptive_w
            total_weight += adaptive_w
            eff_best = max(efficientnet_probs, key=efficientnet_probs.get)
            individual["efficientnet"] = REDISUS_NAMES.get(eff_best, "?")

        # DermaIntel
        if dermaintel_result:
            w = self.weights.get("dermaintel", 0.40)
            redisus_probs = dermaintel_result.get_redisus_probabilities()
            di_conf = max(redisus_probs.values()) if redisus_probs else 0.5
            adaptive_w = w * (0.5 + 0.5 * di_conf)
            for cid, p in redisus_probs.items():
                fused[cid] += p * adaptive_w
            total_weight += adaptive_w
            di_best = max(redisus_probs, key=redisus_probs.get)
            individual["dermaintel"] = REDISUS_NAMES.get(di_best, "?")

        # BiomedCLIP
        if biomedclip_result:
            w = self.weights.get("biomedclip", 0.25)
            bc_conf = max(biomedclip_result.etiology_probs.values()) if biomedclip_result.etiology_probs else 0.5
            adaptive_w = w * (0.5 + 0.5 * bc_conf)
            for cid, p in biomedclip_result.etiology_probs.items():
                if 0 <= cid < 5:
                    fused[cid] += p * adaptive_w
            total_weight += adaptive_w
            bc_best = max(biomedclip_result.etiology_probs, key=biomedclip_result.etiology_probs.get)
            individual["biomedclip"] = REDISUS_NAMES.get(bc_best, "?")

        # Normaliza
        if total_weight > 0:
            fused = fused / total_weight
        else:
            fused = np.ones(5) / 5

        # Agreement
        agreement = self._compute_agreement(individual, fused)

        # Aplica boost/penalty
        best_id = int(np.argmax(fused))
        final_confidence = float(fused[best_id]) * agreement.confidence_boost
        final_confidence = min(final_confidence, 0.99)

        all_probs = {i: float(fused[i]) for i in range(5)}

        # Métricas de confiança (do notebook embeddings)
        eps = 1e-10
        fused_clipped = np.clip(fused, eps, 1.0)
        entropy = -np.sum(fused_clipped * np.log(fused_clipped))
        max_entropy = np.log(5)  # 5 classes
        norm_entropy = entropy / max_entropy if max_entropy > 0 else 0.0

        sorted_fused = np.sort(fused)[::-1]
        margin = float(sorted_fused[0] - sorted_fused[1]) if len(sorted_fused) >= 2 else 1.0

        # Revisão especialista: confiança baixa, baixo agreement, ou alta entropia
        needs_review = (
            final_confidence < 0.80
            or not agreement.models_agree
            or norm_entropy > 0.70
        )

        return EnsembleClassificationResult(
            class_id=best_id,
            class_name=REDISUS_NAMES.get(best_id, "Desconhecido"),
            confidence=final_confidence,
            all_probabilities=all_probs,
            agreement=agreement,
            individual_results=individual,
            needs_expert_review=needs_review,
            confidence_entropy=float(norm_entropy),
            confidence_margin=margin,
        )

    # ------------------------------------------------------------------
    def _compute_agreement(
        self,
        individual: Dict[str, str],
        fused: np.ndarray,
    ) -> ModelAgreement:
        predictions = list(individual.values())
        if len(predictions) < 2:
            return ModelAgreement(True, 1.0, individual, 1.0)

        unique = set(predictions)
        all_agree = len(unique) == 1

        # Pairwise agreement fraction
        pairs_total = len(predictions) * (len(predictions) - 1) / 2
        pairs_agree = sum(
            1 for i in range(len(predictions))
            for j in range(i + 1, len(predictions))
            if predictions[i] == predictions[j]
        )
        agreement_score = pairs_agree / pairs_total if pairs_total > 0 else 1.0

        # Entropia da distribuição fundida (métrica adicional de incerteza)
        eps = 1e-10
        fused_clipped = np.clip(fused, eps, 1.0)
        fused_entropy = -np.sum(fused_clipped * np.log(fused_clipped))
        max_entropy = np.log(len(fused))
        norm_entropy = fused_entropy / max_entropy if max_entropy > 0 else 0.0

        # Boost/Penalty adaptativo com entropia
        if all_agree and norm_entropy < 0.5:
            boost = 1.15  # Alta concordância + baixa entropia
        elif all_agree:
            boost = 1.08  # Concordância mas alta entropia
        elif agreement_score >= 0.5:
            boost = 1.0
        elif norm_entropy > 0.7:
            boost = 0.80  # Baixa concordância + alta entropia = muito incerto
        else:
            boost = 0.85

        return ModelAgreement(
            models_agree=all_agree,
            agreement_score=agreement_score,
            individual_predictions=individual,
            confidence_boost=boost,
        )

    # ==================================================================
    #  SEGMENTATION FUSION
    # ==================================================================
    def _fuse_segmentation(
        self,
        unet_mask: Optional[np.ndarray],
        medsam_result: Optional[MedSAMSegmentationResult],
    ) -> Optional[EnsembleSegmentationResult]:
        """Fusão de segmentação: MedSAM boundary + U-Net tissue classes."""
        if unet_mask is None and medsam_result is None:
            return None

        individual: Dict[str, Any] = {}

        if medsam_result is not None:
            medsam_mask = medsam_result.mask
            individual["medsam"] = {
                "area": medsam_result.wound_area_pixels,
                "circularity": medsam_result.circularity,
            }
        else:
            medsam_mask = None

        if unet_mask is not None:
            individual["unet"] = {"classes": int(unet_mask.max()) + 1}

        # Fusão: usa MedSAM como boundary, U-Net como tissue classifier
        if unet_mask is not None and medsam_mask is not None:
            # Redimensiona se necessário
            if medsam_mask.shape != unet_mask.shape:
                medsam_mask = cv2.resize(
                    medsam_mask,
                    (unet_mask.shape[1], unet_mask.shape[0]),
                    interpolation=cv2.INTER_NEAREST,
                )

            # Aplica boundary MedSAM sobre tissue classes U-Net
            fused = unet_mask.copy()
            fused[medsam_mask == 0] = 0  # Background onde MedSAM diz que não há ferida

            boundary_mask = medsam_mask
        elif medsam_mask is not None:
            fused = medsam_mask.copy()
            boundary_mask = medsam_mask
        else:
            fused = unet_mask.copy()
            boundary_mask = (unet_mask > 0).astype(np.uint8)

        area = int(np.sum(fused > 0))
        contours, _ = cv2.findContours(
            (fused > 0).astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )
        perimeter = sum(cv2.arcLength(c, True) for c in contours) if contours else 0.0
        circularity = (4 * np.pi * area / (perimeter ** 2)) if perimeter > 0 else 0.0

        return EnsembleSegmentationResult(
            fused_mask=fused,
            medsam_boundary=boundary_mask,
            wound_area_pixels=area,
            circularity=min(circularity, 1.0),
            individual_results=individual,
        )

    # ==================================================================
    @property
    def is_loaded(self) -> bool:
        return self._loaded
