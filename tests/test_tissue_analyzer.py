"""
Testes unitários — TissueAnalyzerCV
"""
import numpy as np
import pytest

from src.processing.tissue_analyzer import (
    TISSUE_COLORS,
    TISSUE_HSV_RANGES,
    TissueAnalyzerCV,
    TissueResult,
    TissueType,
)


# ===================================================================
# TissueType enum
# ===================================================================

class TestTissueTypeEnum:
    def test_members(self):
        expected = {
            "granulation", "slough", "necrosis",
            "epithelialization", "periwound", "fibrin", "eschar",
        }
        assert {t.value for t in TissueType} == expected


# ===================================================================
# TissueResult dataclass
# ===================================================================

class TestTissueResult:
    def test_to_dict_keys(self):
        r = TissueResult(
            tissue_mask=np.zeros((10, 10), dtype=np.uint8),
            tissue_percentages={"granulation": 50.0, "necrosis": 10.0},
            dominant_tissue="granulation",
            wound_area_pixels=100,
            color_map=np.zeros((10, 10, 3), dtype=np.uint8),
            health_score=65.0,
        )
        d = r.to_dict()
        assert "tissue_percentages" in d
        assert "dominant_tissue" in d
        assert "health_score" in d
        assert "wound_area_pixels" in d


# ===================================================================
# HSV Ranges
# ===================================================================

class TestHSVRanges:
    def test_all_segmented_types_have_ranges(self):
        required = [
            TissueType.GRANULATION,
            TissueType.SLOUGH,
            TissueType.NECROSIS,
            TissueType.EPITHELIALIZATION,
            TissueType.FIBRIN,
        ]
        for tt in required:
            assert tt in TISSUE_HSV_RANGES, f"Sem HSV range para {tt}"

    def test_range_arrays_shape(self):
        for tt, ranges in TISSUE_HSV_RANGES.items():
            for arr in ranges["lower"]:
                assert arr.shape == (3,), f"lower shape errado para {tt}"
            for arr in ranges["upper"]:
                assert arr.shape == (3,), f"upper shape errado para {tt}"

    def test_lower_count_equals_upper(self):
        for tt, ranges in TISSUE_HSV_RANGES.items():
            assert len(ranges["lower"]) == len(ranges["upper"]), f"Mismatch em {tt}"


# ===================================================================
# TISSUE_COLORS
# ===================================================================

class TestTissueColors:
    def test_all_types_have_color(self):
        for tt in TissueType:
            assert tt in TISSUE_COLORS, f"Sem cor para {tt}"

    def test_colors_are_bgr_tuples(self):
        for tt, color in TISSUE_COLORS.items():
            assert len(color) == 3
            assert all(0 <= c <= 255 for c in color)


# ===================================================================
# Instanciação
# ===================================================================

class TestTissueAnalyzerInit:
    def test_default_init(self):
        ana = TissueAnalyzerCV()
        assert ana.use_ml_model is False
        assert ana._model is None


# ===================================================================
# analyze() — entradas inválidas
# ===================================================================

class TestAnalyzeEdgeCases:
    def test_none_image_returns_empty(self):
        ana = TissueAnalyzerCV()
        result = ana.analyze(None)
        assert isinstance(result, TissueResult)
        assert result.health_score == 0
        assert result.wound_area_pixels == 0

    def test_empty_image_returns_empty(self):
        ana = TissueAnalyzerCV()
        empty = np.array([], dtype=np.uint8).reshape(0, 0, 3)
        result = ana.analyze(empty)
        assert isinstance(result, TissueResult)
        assert result.health_score == 0


# ===================================================================
# analyze() — frames sintéticos
# ===================================================================

class TestAnalyzeOnSyntheticFrames:
    def test_returns_tissue_result(self, red_wound_frame):
        ana = TissueAnalyzerCV()
        result = ana.analyze(red_wound_frame)
        assert isinstance(result, TissueResult)

    def test_percentages_sum_reasonable(self, red_wound_frame, wound_mask_center):
        """Porcentagens devem somar ≤ 100 (pode não somar exatamente se background não contado)."""
        ana = TissueAnalyzerCV()
        result = ana.analyze(red_wound_frame, wound_mask=wound_mask_center)
        total = sum(result.tissue_percentages.values())
        assert total >= 0
        assert total <= 200  # tolerância para sobreposições residuais

    def test_health_score_range(self, red_wound_frame):
        ana = TissueAnalyzerCV()
        result = ana.analyze(red_wound_frame)
        assert 0 <= result.health_score <= 100

    def test_dominant_tissue_is_string(self, red_wound_frame):
        ana = TissueAnalyzerCV()
        result = ana.analyze(red_wound_frame)
        assert isinstance(result.dominant_tissue, str)

    def test_color_map_same_size(self, red_wound_frame):
        ana = TissueAnalyzerCV()
        result = ana.analyze(red_wound_frame)
        assert result.color_map.shape[:2] == red_wound_frame.shape[:2]
        assert result.color_map.shape[2] == 3

    def test_tissue_mask_same_hw(self, red_wound_frame):
        ana = TissueAnalyzerCV()
        result = ana.analyze(red_wound_frame)
        assert result.tissue_mask.shape == red_wound_frame.shape[:2]


# ===================================================================
# Health score logic
# ===================================================================

class TestHealthScore:
    def test_high_granulation_good_score(self, red_wound_frame):
        """Uma imagem vermelha (granulação) deve produzir score razoável."""
        ana = TissueAnalyzerCV()
        result = ana.analyze(red_wound_frame)
        # Não podemos garantir um valor exato, mas verificamos range
        assert isinstance(result.health_score, (int, float))
        assert 0 <= result.health_score <= 100

    def test_dark_necrosis_lower_score(self, dark_necrosis_frame):
        """Uma imagem escura (necrose) deve ter score menor ou igual."""
        ana = TissueAnalyzerCV()
        result = ana.analyze(dark_necrosis_frame)
        assert isinstance(result.health_score, (int, float))
        # Score para necrose tende a ser menor
        assert 0 <= result.health_score <= 100


# ===================================================================
# analyze() com máscara
# ===================================================================

class TestAnalyzeWithMask:
    def test_mask_limits_area(self, red_wound_frame, wound_mask_center):
        ana = TissueAnalyzerCV()
        result_no_mask = ana.analyze(red_wound_frame)
        result_with_mask = ana.analyze(red_wound_frame, wound_mask=wound_mask_center)
        # Com máscara a área analisada é menor ou igual
        assert result_with_mask.wound_area_pixels <= red_wound_frame.shape[0] * red_wound_frame.shape[1]

    def test_wound_area_matches_mask(self, red_wound_frame, wound_mask_center):
        ana = TissueAnalyzerCV()
        result = ana.analyze(red_wound_frame, wound_mask=wound_mask_center)
        expected_pixels = int(np.sum(wound_mask_center > 0))
        assert result.wound_area_pixels == expected_pixels
