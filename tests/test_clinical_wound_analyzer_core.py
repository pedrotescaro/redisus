import numpy as np
import cv2

from src.processing.clinical_wound_analyzer_core import ClinicalReport, ClinicalWoundAnalyzer


def test_headless_core_imports_and_analyzes_without_pyqt(red_wound_frame):
    analyzer = ClinicalWoundAnalyzer()

    report = analyzer.analyze(red_wound_frame)

    assert isinstance(report, ClinicalReport)
    assert isinstance(report.is_valid_wound, bool)
    assert isinstance(report.primary_tissue, str)
    assert 0 <= report.health_score <= 100
    assert report.processing_time_ms >= 0
    assert isinstance(report.tissue_analysis_trace, (dict, type(None)))
    if not report.is_valid_wound:
        assert report.rejection_reason


def test_headless_core_rejects_empty_frame():
    analyzer = ClinicalWoundAnalyzer()

    report = analyzer.analyze(np.zeros((0, 0, 3), dtype=np.uint8))

    assert isinstance(report, ClinicalReport)
    assert report.is_valid_wound is False
    assert report.rejection_reason


def test_segment_clinical_v3_detects_mixed_dark_yellow_red_tissues():
    analyzer = ClinicalWoundAnalyzer()

    image = np.full((320, 320, 3), (180, 200, 220), dtype=np.uint8)
    wound_mask = np.zeros((320, 320), dtype=np.uint8)
    cv2.circle(wound_mask, (160, 160), 100, 255, -1)

    cv2.circle(image, (160, 160), 100, (40, 60, 180), -1)
    cv2.ellipse(image, (190, 145), (45, 28), 10, 0, 360, (120, 200, 210), -1)
    cv2.ellipse(image, (135, 175), (38, 30), -20, 0, 360, (25, 55, 65), -1)

    peripheral_zone, core_zone, outer_ring = analyzer._create_zone_masks(wound_mask)
    tissue_pcts, _, _ = analyzer._segment_clinical_v3(
        image,
        wound_mask,
        peripheral_zone,
        core_zone,
        outer_ring,
    )

    assert tissue_pcts["granulation"] > 35.0
    assert tissue_pcts["slough"] > 5.0
    assert tissue_pcts["necrosis"] > 5.0
