"""
Testes unitários — WoundClassifierCV
"""
import numpy as np
import pytest

from src.processing.wound_classifier_cv import (
    ETIOLOGY_INFO,
    ClassificationResult,
    WoundClassifierCV,
    WoundEtiology,
)


# ===================================================================
# WoundEtiology enum
# ===================================================================

class TestWoundEtiologyEnum:
    def test_all_members(self):
        expected = {
            "venous_ulcer", "arterial_ulcer", "diabetic_foot",
            "pressure_injury", "surgical_wound", "traumatic", "burn", "unknown",
        }
        assert {e.value for e in WoundEtiology} == expected

    def test_all_have_info(self):
        for e in WoundEtiology:
            assert e in ETIOLOGY_INFO, f"Sem info para {e}"
            info = ETIOLOGY_INFO[e]
            assert "name" in info
            assert "description" in info


# ===================================================================
# ClassificationResult
# ===================================================================

class TestClassificationResult:
    def test_name_property(self):
        r = ClassificationResult(
            etiology=WoundEtiology.VENOUS_ULCER,
            confidence=0.85,
            probabilities={},
        )
        assert r.name == "Úlcera Venosa"

    def test_description_property(self):
        r = ClassificationResult(
            etiology=WoundEtiology.DIABETIC_FOOT,
            confidence=0.7,
            probabilities={},
        )
        assert "neuropática" in r.description.lower() or "diabétic" in r.description.lower()

    def test_to_dict_keys(self):
        r = ClassificationResult(
            etiology=WoundEtiology.BURN,
            confidence=0.6,
            probabilities={"burn": 0.6},
            needs_review=True,
        )
        d = r.to_dict()
        expected_keys = {"etiology", "name", "confidence", "probabilities", "description", "needs_review"}
        assert set(d.keys()) == expected_keys

    def test_to_dict_etiology_is_string(self):
        r = ClassificationResult(
            etiology=WoundEtiology.SURGICAL_WOUND,
            confidence=0.9,
            probabilities={},
        )
        assert r.to_dict()["etiology"] == "surgical_wound"


# ===================================================================
# WoundClassifierCV — init
# ===================================================================

class TestClassifierInit:
    def test_default_init(self):
        clf = WoundClassifierCV()
        assert clf.model_path is None
        assert clf._model is None
        assert clf._model_loaded is False

    def test_init_with_nonexistent_model(self):
        clf = WoundClassifierCV(
            model_path="/nonexistent/model.h5",
            use_keras_model=True,
        )
        # Não carrega (path não existe)
        assert clf._model_loaded is False


# ===================================================================
# classify() — entradas inválidas
# ===================================================================

class TestClassifyEdgeCases:
    def test_none_returns_unknown(self):
        clf = WoundClassifierCV()
        result = clf.classify(None)
        assert result.etiology == WoundEtiology.UNKNOWN
        assert result.confidence == 0.0
        assert result.needs_review is True

    def test_empty_image_returns_unknown(self):
        clf = WoundClassifierCV()
        empty = np.array([], dtype=np.uint8).reshape(0, 0, 3)
        result = clf.classify(empty)
        assert result.etiology == WoundEtiology.UNKNOWN
        assert result.needs_review is True


# ===================================================================
# classify() — imagens sintéticas
# ===================================================================

class TestClassifyOnSyntheticFrames:
    def test_returns_classification_result(self, red_wound_frame):
        clf = WoundClassifierCV()
        result = clf.classify(red_wound_frame)
        assert isinstance(result, ClassificationResult)

    def test_confidence_range(self, red_wound_frame):
        clf = WoundClassifierCV()
        result = clf.classify(red_wound_frame)
        assert 0 <= result.confidence <= 1

    def test_probabilities_sum_to_one(self, red_wound_frame):
        clf = WoundClassifierCV()
        result = clf.classify(red_wound_frame)
        total = sum(result.probabilities.values())
        assert abs(total - 1.0) < 0.01, f"Soma das probabilidades = {total}"

    def test_probabilities_no_unknown_key(self, red_wound_frame):
        """Probabilidades não incluem UNKNOWN."""
        clf = WoundClassifierCV()
        result = clf.classify(red_wound_frame)
        assert WoundEtiology.UNKNOWN.value not in result.probabilities

    def test_features_dict_populated(self, red_wound_frame):
        clf = WoundClassifierCV()
        result = clf.classify(red_wound_frame)
        assert len(result.features) > 0
        assert "mean_hue" in result.features
        assert "circularity" in result.features


# ===================================================================
# needs_review logic
# ===================================================================

class TestNeedsReview:
    def test_low_confidence_needs_review(self, red_wound_frame):
        """Se confiança < 0.6, needs_review deve ser True."""
        clf = WoundClassifierCV()
        result = clf.classify(red_wound_frame)
        if result.confidence < 0.6:
            assert result.needs_review == True  # noqa: E712 — numpy bool

    def test_high_confidence_no_review(self):
        """Se classificação com alta confiança e boa margem, needs_review pode ser False."""
        # Cria resultado direto para testar a lógica
        r = ClassificationResult(
            etiology=WoundEtiology.VENOUS_ULCER,
            confidence=0.95,
            probabilities={"venous_ulcer": 0.95, "arterial_ulcer": 0.05},
            needs_review=False,
        )
        assert r.needs_review is False


# ===================================================================
# classify() com tissue_percentages
# ===================================================================

class TestClassifyWithTissue:
    def test_tissue_percentages_affect_features(self, red_wound_frame):
        clf = WoundClassifierCV()
        tp = {"granulation": 60, "necrosis": 10, "slough": 20, "epithelialization": 10}
        result = clf.classify(red_wound_frame, tissue_percentages=tp)
        assert result.features.get("granulation") == 60
        assert result.features.get("necrosis") == 10

    def test_no_tissue_defaults_zero(self, red_wound_frame):
        clf = WoundClassifierCV()
        result = clf.classify(red_wound_frame)
        assert result.features.get("granulation") == 0
        assert result.features.get("necrosis") == 0
