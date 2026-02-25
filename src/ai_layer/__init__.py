"""
REDISUS - Camada Adicional de IA Pré-Treinada
Módulos de modelos externos treinados com imagens médicas/feridas.

Modelos integrados:
  - DermaIntel ViT  (PayamFard123/dermaintel-wound-classifier)
  - MedSAM          (bowang-lab/MedSAM)
  - BiomedCLIP      (microsoft/BiomedCLIP-PubMedBERT_256-vit_base_patch16_224)
  - Ensemble        (orquestração multi-modelo com votação ponderada)
"""

from .dermaintel_classifier import DermaIntelClassifier, DermaIntelPrediction
from .medsam_segmenter import MedSAMSegmenter, MedSAMSegmentationResult
from .biomedclip_analyzer import BiomedCLIPAnalyzer, BiomedCLIPResult
from .ensemble_orchestrator import EnsembleOrchestrator, EnsembleResult

__all__ = [
    "DermaIntelClassifier", "DermaIntelPrediction",
    "MedSAMSegmenter", "MedSAMSegmentationResult",
    "BiomedCLIPAnalyzer", "BiomedCLIPResult",
    "EnsembleOrchestrator", "EnsembleResult",
]
