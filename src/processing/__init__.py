"""
REDISUS - Camada de Processamento
Módulos de processamento de imagem e detecção
"""
from .wound_detector_cv import WoundDetectorCV, DetectionResult
from .image_processor import ImageProcessor, PreprocessingPipeline
from .tissue_analyzer import TissueAnalyzerCV, TissueResult
from .wound_classifier_cv import WoundClassifierCV, ClassificationResult

__all__ = [
    'WoundDetectorCV',
    'DetectionResult',
    'ImageProcessor',
    'PreprocessingPipeline',
    'TissueAnalyzerCV',
    'TissueResult',
    'WoundClassifierCV',
    'ClassificationResult'
]
