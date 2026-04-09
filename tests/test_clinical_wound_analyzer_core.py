import numpy as np

from src.processing.clinical_wound_analyzer_core import ClinicalReport, ClinicalWoundAnalyzer


def test_headless_core_imports_and_analyzes_without_pyqt(red_wound_frame):
    analyzer = ClinicalWoundAnalyzer()

    report = analyzer.analyze(red_wound_frame)

    assert isinstance(report, ClinicalReport)
    assert isinstance(report.is_valid_wound, bool)
    assert isinstance(report.primary_tissue, str)
    assert 0 <= report.health_score <= 100
    assert report.processing_time_ms >= 0
    if not report.is_valid_wound:
        assert report.rejection_reason


def test_headless_core_rejects_empty_frame():
    analyzer = ClinicalWoundAnalyzer()

    report = analyzer.analyze(np.zeros((0, 0, 3), dtype=np.uint8))

    assert isinstance(report, ClinicalReport)
    assert report.is_valid_wound is False
    assert report.rejection_reason
