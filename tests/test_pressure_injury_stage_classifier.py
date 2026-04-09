import numpy as np

from src.diagnosis.clinical_ml import merge_pressure_injury_stage_assessment
from src.diagnosis.pressure_injury_stage_classifier import PressureInjuryStageClassifier


def _solid_bgr(color: tuple[int, int, int]) -> np.ndarray:
    return np.full((128, 128, 3), color, dtype=np.uint8)


def test_pressure_injury_stage_classifier_explains_dark_advanced_pattern():
    classifier = PressureInjuryStageClassifier(weights_path="missing-lp-weights.pth", metadata_path="missing-lp-metadata.json")
    prediction = classifier.predict(
        _solid_bgr((20, 20, 20)),
        evaluation_context={"wound_area_cm2": 24.0, "pain_score": 8.0},
    )

    assert prediction.stage_code == "stage_4"
    assert prediction.source in {"heuristic", "model+heuristic"}
    assert prediction.considerations
    assert prediction.visual_signals.dark_ratio > 0.5
    assert prediction.recommended_actions


def test_merge_pressure_injury_stage_assessment_enriches_raw_output():
    classifier = PressureInjuryStageClassifier(weights_path="missing-lp-weights.pth", metadata_path="missing-lp-metadata.json")
    prediction = classifier.predict(
        _solid_bgr((0, 220, 255)),
        evaluation_context={"wound_area_cm2": 12.0, "pain_score": 5.0},
    )
    merged = merge_pressure_injury_stage_assessment(
        {
            "etiology": "pressure_injury",
            "confidence": 0.74,
            "diagnosis_summary": "Lesao por pressao detectada.",
            "recommendations": ["Validar manualmente o achado."],
            "metadata": {"source": "test"},
        },
        prediction,
    )

    assert merged["etiology"] == "pressure_injury"
    assert merged["confidence"] >= 0.37
    assert "Avaliacao especializada de LP sugere" in merged["diagnosis_summary"]
    assert "pressure_injury_stage_assessment" in merged["metadata"]
    assert merged["recommendations"]


def test_stage34_pairwise_calibration_can_shift_ambiguous_pair():
    classifier = PressureInjuryStageClassifier(weights_path="missing-lp-weights.pth", metadata_path="missing-lp-metadata.json")
    classifier._stage34_calibration = {
        "weights": [0.0 for _ in classifier.stage34_feature_names()],
        "bias": -5.0,
        "feature_mean": [0.0 for _ in classifier.stage34_feature_names()],
        "feature_scale": [1.0 for _ in classifier.stage34_feature_names()],
    }
    signals = classifier._extract_visual_signals(_solid_bgr((20, 180, 220)))
    calibrated, applied = classifier._apply_stage34_calibration(
        {"stage_1": 0.05, "stage_2": 0.05, "stage_3": 0.25, "stage_4": 0.65},
        signals,
    )

    assert applied is True
    assert calibrated["stage_3"] > calibrated["stage_4"]
