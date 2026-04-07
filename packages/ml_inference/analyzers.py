"""Canonical wrappers for inference modules."""

from packages.shared.runtime import ensure_project_root_on_path

ensure_project_root_on_path()

from src.diagnosis.etiology_classifier import EtiologyClassifier  # noqa: E402
from src.diagnosis.tissue_segmenter import UNetSegmenter  # noqa: E402
from src.diagnosis.wound_analyzer import WoundAnalyzer  # noqa: E402
from src.processing.tissue_analyzer import TissueAnalyzerCV  # noqa: E402
from src.processing.wound_classifier_cv import WoundClassifierCV  # noqa: E402

__all__ = [
    "EtiologyClassifier",
    "TissueAnalyzerCV",
    "UNetSegmenter",
    "WoundAnalyzer",
    "WoundClassifierCV",
]
