from types import SimpleNamespace

from packages.clinical_domain.workflow import DEFAULT_MODEL_VERSION, build_headless_analyzer_result


def _tissue(
    *,
    name: str,
    name_en: str,
    percentage: float,
    clinical_action: str = "",
    color_hex: str = "#000000",
    description: str = "",
):
    return SimpleNamespace(
        name=name,
        name_en=name_en,
        percentage=percentage,
        color_hex=color_hex,
        description=description,
        clinical_action=clinical_action,
    )


def test_build_headless_analyzer_result_merges_official_and_legacy_contracts():
    report = SimpleNamespace(
        is_valid_wound=True,
        rejection_reason="",
        primary_tissue="Granulation Tissue",
        primary_justification="Predominio de tecido de granulacao.",
        wound_area_px=1024,
        health_score=82.5,
        processing_time_ms=12.4,
        tissues=[
            _tissue(
                name="Tecido de granulação",
                name_en="Granulation Tissue",
                percentage=72.0,
                clinical_action="Manter ambiente umido e monitorar epitelizacao.",
                color_hex="#d95f5f",
                description="Tecido viavel.",
            ),
            _tissue(name="Slough (fibrin)", name_en="Slough (fibrin)", percentage=18.0),
            _tissue(name="Coagulation necrosis (eschar)", name_en="Coagulation necrosis (eschar)", percentage=10.0),
        ],
        border_analysis=SimpleNamespace(
            maceration=False,
            inflammation=True,
            regular_borders=True,
            description="Bordas preservadas com hiperemia leve.",
        ),
        resnet_prediction={
            "mapped_etiology": "pressure_injury",
            "final_confidence": 0.91,
            "needs_expert_review": False,
            "confidence_level": "high",
            "confidence_entropy": 0.11,
            "confidence_margin": 0.44,
        },
        dl_prediction={"class_name": "pressure_injury", "confidence": 0.87},
        ensemble_classification={"class_name": "pressure_injury", "confidence": 0.89},
        body_part={"label": "heel"},
        push_score={"total": 8},
        lighting_analysis={"quality": "good"},
    )

    payload = build_headless_analyzer_result(
        report,
        analysis_id="analysis-123",
        patient_id="patient-456",
        image_filename="wound.png",
        image_content_type="image/png",
        generated_at="2026-04-09T00:00:00+00:00",
    )

    assert payload["contract_version"] == "2026-04-07"
    assert payload["analysis_id"] == "analysis-123"
    assert payload["case_id"] == "analysis-123"
    assert payload["patient_id"] == "patient-456"
    assert payload["model_version"] == "heal-analyzer-headless-resnet"
    assert payload["inference"]["etiology"] == "PRESSURE_INJURY"
    assert payload["inference"]["tissue_percentages"] == {
        "granulation": 72.0,
        "slough": 18.0,
        "necrosis": 10.0,
    }
    assert payload["interpretation"]["summary"] == "Predominio de tecido de granulacao."
    assert payload["metadata"]["analysis_id"] == "analysis-123"
    assert payload["metadata"]["image_filename"] == "wound.png"
    assert payload["primary_tissue"] == "Granulation Tissue"
    assert payload["border_analysis"]["inflammation"] is True
    assert payload["processing_time_ms"] == 12.4


def test_build_headless_analyzer_result_handles_ptbr_labels_and_fallback():
    report = SimpleNamespace(
        is_valid_wound=False,
        rejection_reason="Imagem sem ferida visivel para analise clinica.",
        primary_tissue="",
        primary_justification="",
        wound_area_px=0,
        health_score=0.0,
        processing_time_ms=5.0,
        tissues=[
            _tissue(
                name="Necrose de coagulação (escara)",
                name_en="",
                percentage=30.0,
                clinical_action="Considerar desbridamento conforme avaliacao clinica.",
            ),
            _tissue(name="Tecido de granulação", name_en="", percentage=70.0),
        ],
        border_analysis=None,
        resnet_prediction={},
        dl_prediction={},
        ensemble_classification={},
        body_part=None,
        push_score=None,
        lighting_analysis=None,
    )

    payload = build_headless_analyzer_result(
        report,
        analysis_id="analysis-fallback",
        patient_id="",
        image_filename="invalid.png",
        image_content_type="image/png",
        generated_at="2026-04-09T00:00:00+00:00",
    )

    assert payload["model_version"] == DEFAULT_MODEL_VERSION
    assert payload["inference"]["fallback_used"] is True
    assert payload["inference"]["needs_expert_review"] is True
    assert payload["inference"]["tissue_percentages"]["necrosis"] == 30.0
    assert payload["inference"]["tissue_percentages"]["granulation"] == 70.0
    assert payload["interpretation"]["summary"] == "Imagem sem ferida visivel para analise clinica."
    assert payload["interpretation"]["requires_expert_review"] is True
    assert payload["rejection_reason"] == "Imagem sem ferida visivel para analise clinica."
