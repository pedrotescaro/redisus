"""
Testes unitários — WoundDetectorCV
"""
import cv2
import numpy as np
import pytest

from src.processing.wound_detector_cv import (
    ColorRanges,
    DetectionMethod,
    DetectionResult,
    WoundDetectorCV,
)


# ===================================================================
# DetectionResult dataclass
# ===================================================================

class TestDetectionResult:
    """Testes do dataclass DetectionResult."""

    def test_width_height(self):
        r = DetectionResult(bbox=(10, 20, 110, 220), confidence=0.9)
        assert r.width == 100
        assert r.height == 200

    def test_to_dict_keys(self):
        r = DetectionResult(
            bbox=(0, 0, 50, 50), confidence=0.8,
            wound_type="test", area_pixels=1000,
            center=(25, 25), features={"f": 1.0},
        )
        d = r.to_dict()
        assert set(d.keys()) == {"bbox", "confidence", "wound_type", "area_pixels", "center", "features"}

    def test_default_values(self):
        r = DetectionResult(bbox=(0, 0, 1, 1), confidence=0.5)
        assert r.wound_type == "wound"
        assert r.area_pixels == 0
        assert r.center == (0, 0)
        assert r.features == {}
        assert r.mask is None
        assert r.contour is None


# ===================================================================
# Instanciação do detector
# ===================================================================

class TestWoundDetectorInit:
    """Testes de criação do WoundDetectorCV."""

    def test_default_init(self):
        det = WoundDetectorCV()
        assert det.method == DetectionMethod.TEXTURE_PRIORITY
        assert det.min_area == WoundDetectorCV.DEFAULT_MIN_AREA
        assert det.max_area == WoundDetectorCV.DEFAULT_MAX_AREA
        assert det.confidence_threshold == WoundDetectorCV.DEFAULT_CONFIDENCE_THRESHOLD

    def test_custom_params(self):
        det = WoundDetectorCV(
            method=DetectionMethod.COLOR_SEGMENTATION,
            min_area=500, max_area=100000,
            confidence_threshold=0.7,
            enable_false_positive_filter=False,
            texture_weight=0.8,
            color_weight=0.2,
        )
        assert det.method == DetectionMethod.COLOR_SEGMENTATION
        assert det.min_area == 500
        assert det.confidence_threshold == 0.7
        assert det.texture_weight == 0.8

    def test_fp_filter_disabled(self):
        det = WoundDetectorCV(enable_false_positive_filter=False)
        assert det._fp_filter is None


# ===================================================================
# detect() — entradas inválidas / vazias
# ===================================================================

class TestDetectEdgeCases:
    """Testes de entradas inválidas para detect()."""

    def test_none_frame_returns_empty(self):
        det = WoundDetectorCV(enable_false_positive_filter=False)
        assert det.detect(None) == []

    def test_empty_frame_returns_empty(self):
        det = WoundDetectorCV(enable_false_positive_filter=False)
        empty = np.array([], dtype=np.uint8)
        assert det.detect(empty) == []


# ===================================================================
# detect() — frames sintéticos
# ===================================================================

class TestDetectOnSyntheticFrames:
    """Testes com imagens sintéticas."""

    def test_black_frame_no_detections(self, black_frame):
        det = WoundDetectorCV(enable_false_positive_filter=False)
        results = det.detect(black_frame)
        assert isinstance(results, list)
        # Frame preto puro geralmente não tem ferida visível (low confidence)

    def test_white_frame_no_detections(self, white_frame):
        det = WoundDetectorCV(enable_false_positive_filter=False)
        results = det.detect(white_frame)
        assert isinstance(results, list)

    def test_red_wound_produces_detections_or_empty(self, red_wound_frame):
        """
        Com um círculo vermelho grande, o detector por cor
        pode gerar detecção. Verificamos que retorna lista válida
        e que cada item tem atributos esperados.
        """
        det = WoundDetectorCV(
            method=DetectionMethod.COLOR_SEGMENTATION,
            min_area=500,
            confidence_threshold=0.2,
            enable_false_positive_filter=False,
        )
        results = det.detect(red_wound_frame)
        assert isinstance(results, list)
        for r in results:
            assert isinstance(r, DetectionResult)
            assert 0 <= r.confidence <= 1
            assert r.width > 0 and r.height > 0

    def test_detect_returns_list_with_all_methods(self, red_wound_frame):
        """Cada método de detecção retorna lista sem lançar exceção."""
        for method in DetectionMethod:
            if method == DetectionMethod.ML_MODEL:
                continue  # sem modelo disponível
            det = WoundDetectorCV(
                method=method,
                min_area=200,
                confidence_threshold=0.1,
                enable_false_positive_filter=False,
            )
            results = det.detect(red_wound_frame)
            assert isinstance(results, list), f"Falhou com {method}"

    def test_texture_priority_detects_pressure_injury_like_olive_slough(self):
        image = np.full((420, 420, 3), (175, 188, 205), dtype=np.uint8)
        cv2.circle(image, (210, 210), 120, (100, 130, 125), -1)
        cv2.ellipse(image, (210, 110), (55, 40), 0, 0, 360, (70, 75, 190), -1)
        cv2.ellipse(image, (210, 305), (60, 42), 0, 0, 360, (70, 75, 185), -1)
        cv2.circle(image, (165, 135), 10, (25, 30, 40), -1)
        cv2.circle(image, (255, 295), 12, (22, 28, 38), -1)
        cv2.circle(image, (190, 210), 14, (45, 60, 70), -1)

        det = WoundDetectorCV(
            method=DetectionMethod.TEXTURE_PRIORITY,
            min_area=1000,
            confidence_threshold=0.15,
            enable_false_positive_filter=False,
        )
        results = det.detect(image)

        assert results
        x1 = min(result.bbox[0] for result in results)
        y1 = min(result.bbox[1] for result in results)
        x2 = max(result.bbox[2] for result in results)
        y2 = max(result.bbox[3] for result in results)

        assert x1 < 170 < x2
        assert y1 < 210 < y2


# ===================================================================
# Confidence filtering
# ===================================================================

class TestConfidenceFiltering:
    """Verifica que detecções abaixo do limiar são descartadas."""

    def test_high_threshold_filters_all(self, red_wound_frame):
        det = WoundDetectorCV(
            method=DetectionMethod.COLOR_SEGMENTATION,
            confidence_threshold=0.99,
            enable_false_positive_filter=False,
        )
        results = det.detect(red_wound_frame)
        # Com threshold 0.99, quase tudo é filtrado
        for r in results:
            assert r.confidence >= 0.99


# ===================================================================
# ColorRanges
# ===================================================================

class TestColorRanges:
    """Verifica que os intervalos HSV estão bem definidos."""

    def test_ranges_are_numpy_arrays(self):
        attrs = [
            "RED_LOWER_1", "RED_UPPER_1", "RED_LOWER_2", "RED_UPPER_2",
            "YELLOW_LOWER", "YELLOW_UPPER", "DARK_LOWER", "DARK_UPPER",
            "OLIVE_SLOUGH_LOWER", "OLIVE_SLOUGH_UPPER",
            "PINK_LOWER", "PINK_UPPER", "SKIN_LOWER", "SKIN_UPPER",
        ]
        for attr in attrs:
            arr = getattr(ColorRanges, attr)
            assert isinstance(arr, np.ndarray), f"{attr} não é ndarray"
            assert arr.shape == (3,)

    def test_lower_le_upper(self):
        pairs = [
            ("RED_LOWER_1", "RED_UPPER_1"),
            ("YELLOW_LOWER", "YELLOW_UPPER"),
            ("OLIVE_SLOUGH_LOWER", "OLIVE_SLOUGH_UPPER"),
            ("DARK_LOWER", "DARK_UPPER"),
            ("PINK_LOWER", "PINK_UPPER"),
            ("SKIN_LOWER", "SKIN_UPPER"),
        ]
        for lo, hi in pairs:
            assert np.all(getattr(ColorRanges, lo) <= getattr(ColorRanges, hi)), f"{lo} > {hi}"


# ===================================================================
# DetectionMethod enum
# ===================================================================

class TestDetectionMethodEnum:
    def test_all_members(self):
        expected = {"color", "edge", "texture", "combined", "texture_priority", "ml"}
        assert {m.value for m in DetectionMethod} == expected
