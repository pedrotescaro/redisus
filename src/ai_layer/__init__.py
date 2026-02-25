"""
REDISUS - Camada Adicional de IA Pré-Treinada
Módulos de modelos externos treinados com imagens médicas/feridas.

Modelos integrados:
  - DermaIntel ViT  (PayamFard123/dermaintel-wound-classifier)
  - MedSAM          (bowang-lab/MedSAM)
  - BiomedCLIP      (microsoft/BiomedCLIP-PubMedBERT_256-vit_base_patch16_224)
  - Ensemble        (orquestração multi-modelo com votação ponderada)
  - Confidence      (calibração e filtragem de confiança)
"""

from .dermaintel_classifier import DermaIntelClassifier, DermaIntelPrediction
from .medsam_segmenter import MedSAMSegmenter, MedSAMSegmentationResult
from .biomedclip_analyzer import BiomedCLIPAnalyzer, BiomedCLIPResult
from .ensemble_orchestrator import EnsembleOrchestrator, EnsembleResult
from .confidence_calibration import (
    ConfidenceCalibrator, CalibrationResult, FilteredPrediction,
    filter_by_confidence, compute_entropy, compute_margin, compute_ece,
)

__all__ = [
    "DermaIntelClassifier", "DermaIntelPrediction",
    "MedSAMSegmenter", "MedSAMSegmentationResult",
    "BiomedCLIPAnalyzer", "BiomedCLIPResult",
    "EnsembleOrchestrator", "EnsembleResult",
    "ConfidenceCalibrator", "CalibrationResult", "FilteredPrediction",
    "filter_by_confidence", "compute_entropy", "compute_margin", "compute_ece",
]
