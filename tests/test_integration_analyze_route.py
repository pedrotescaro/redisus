import io
import json
from types import SimpleNamespace

import numpy as np
from PIL import Image


def _png_bytes(color: tuple[int, int, int] = (180, 20, 20)) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (64, 64), color=color).save(buffer, format="PNG")
    return buffer.getvalue()


def test_integration_analyze_route_uses_headless_analyzer(tmp_path, monkeypatch):
    monkeypatch.setenv("CLINICAL_API_REQUIRE_AUTH", "0")
    monkeypatch.setenv("REDISUS_DB_PATH", str(tmp_path / "integration-analyze.db"))

    from apps.api.app import create_app

    app = create_app()
    app.config["TESTING"] = True

    with app.test_client() as client:
        response = client.post(
            "/api/v1/analyze",
            data={"image": (io.BytesIO(_png_bytes()), "wound.png")},
            content_type="multipart/form-data",
        )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["analysis_id"]
    assert "is_valid_wound" in payload
    assert "primary_tissue" in payload
    assert "processing_time_ms" in payload
    assert payload["contract_version"] == "2026-04-07"
    assert payload["model_version"]
    assert isinstance(payload["inference"], dict)
    assert isinstance(payload["interpretation"], dict)
    assert isinstance(payload["metadata"], dict)


def test_integration_analyze_route_returns_visual_payloads(tmp_path, monkeypatch):
    monkeypatch.setenv("CLINICAL_API_REQUIRE_AUTH", "0")
    monkeypatch.setenv("REDISUS_DB_PATH", str(tmp_path / "integration-analyze-visuals.db"))

    from apps.api.app import create_app
    from apps.api.routes import integration as integration_routes

    class DummyAnalyzer:
        def analyze(self, _image, **_kwargs):
            red_block = np.full((24, 24, 3), (0, 0, 255), dtype=np.uint8)
            green_block = np.full((24, 24, 3), (0, 255, 0), dtype=np.uint8)
            blue_block = np.full((24, 24, 3), (255, 0, 0), dtype=np.uint8)
            return SimpleNamespace(
                is_valid_wound=True,
                rejection_reason="",
                primary_tissue="Granulation Tissue",
                primary_justification="Predominio de tecido de granulacao.",
                wound_area_px=576,
                health_score=82.0,
                processing_time_ms=10.2,
                tissues=[
                    SimpleNamespace(
                        name="Tecido de granulacao",
                        name_en="Granulation Tissue",
                        percentage=70.0,
                        color_hex="#D96666",
                        description="Tecido viavel.",
                        clinical_action="Monitorar evolucao.",
                    )
                ],
                border_analysis=None,
                resnet_prediction={
                    "mapped_etiology": "pressure_injury",
                    "final_confidence": 0.88,
                    "needs_expert_review": False,
                    "confidence_level": "high",
                    "confidence_entropy": 0.12,
                    "confidence_margin": 0.33,
                },
                dl_prediction={},
                ensemble_classification={},
                body_part=None,
                push_score=None,
                lighting_analysis=None,
                roi=None,
                detection_overlay=red_block,
                segmentation_map=green_block,
                tissue_overlay=blue_block,
                grad_cam_overlay=red_block,
            )

    monkeypatch.setattr(integration_routes, "_get_wound_analyzer", lambda: DummyAnalyzer())

    app = create_app()
    app.config["TESTING"] = True

    with app.test_client() as client:
        response = client.post(
            "/api/v1/analyze",
            data={"image": (io.BytesIO(_png_bytes()), "wound.png")},
            content_type="multipart/form-data",
        )

    assert response.status_code == 200
    payload = response.get_json()
    assert isinstance(payload["visuals"], dict)
    assert payload["visuals"]["segmentation"]["data_url"].startswith("data:image/png;base64,")
    assert payload["visuals"]["combined"]["data_url"].startswith("data:image/jpeg;base64,")
    assert payload["visuals"]["attention"]["data_url"].startswith("data:image/jpeg;base64,")


def test_integration_analyze_route_normalizes_numpy_scalars(tmp_path, monkeypatch):
    monkeypatch.setenv("CLINICAL_API_REQUIRE_AUTH", "0")
    monkeypatch.setenv("REDISUS_DB_PATH", str(tmp_path / "integration-analyze-numpy.db"))

    from apps.api.app import create_app
    from apps.api.routes import integration as integration_routes

    class DummyAnalyzer:
        def analyze(self, _image, **_kwargs):
            block = np.full((16, 16, 3), (120, 20, 220), dtype=np.uint8)
            return SimpleNamespace(
                is_valid_wound=np.bool_(True),
                rejection_reason="",
                primary_tissue="Esfacelo (Fibrina)",
                primary_justification="Padrao compativel com tecido desvitalizado.",
                wound_area_px=np.int64(256),
                health_score=np.float32(61.5),
                processing_time_ms=np.float32(14.7),
                tissues=[
                    SimpleNamespace(
                        name="Esfacelo (Fibrina)",
                        name_en="Slough (Fibrin)",
                        percentage=np.float32(68.4),
                        color_hex="#DCC850",
                        description="Tecido desvitalizado.",
                        clinical_action="Avaliar desbridamento.",
                    )
                ],
                border_analysis=SimpleNamespace(
                    maceration=np.bool_(False),
                    inflammation=np.bool_(True),
                    regular_borders=np.bool_(False),
                    description="Bordas inflamadas.",
                ),
                resnet_prediction={
                    "mapped_etiology": "pressure_injury",
                    "final_confidence": np.float32(0.84),
                    "needs_expert_review": np.bool_(True),
                    "confidence_level": "moderate",
                    "confidence_entropy": np.float32(0.21),
                    "confidence_margin": np.float32(0.18),
                },
                dl_prediction={},
                ensemble_classification={},
                body_part={"region": "sacral", "supported": np.bool_(True)},
                push_score={"score": np.int64(11), "healing": np.bool_(False)},
                lighting_analysis={"adequate": np.bool_(True), "exposure": np.float32(0.73)},
                roi=None,
                detection_overlay=block,
                segmentation_map=block,
                tissue_overlay=block,
                grad_cam_overlay=block,
            )

    monkeypatch.setattr(integration_routes, "_get_wound_analyzer", lambda: DummyAnalyzer())

    app = create_app()
    app.config["TESTING"] = True

    with app.test_client() as client:
        response = client.post(
            "/api/v1/analyze",
            data={"image": (io.BytesIO(_png_bytes()), "wound.png")},
            content_type="multipart/form-data",
        )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["is_valid_wound"] is True
    assert payload["border_analysis"]["inflammation"] is True
    assert payload["body_part"]["supported"] is True
    assert payload["push_score"]["score"] == 11
    assert payload["lighting_analysis"]["adequate"] is True
    assert payload["inference"]["needs_expert_review"] is True


def test_integration_analyze_route_repairs_mojibake_strings(tmp_path, monkeypatch):
    monkeypatch.setenv("CLINICAL_API_REQUIRE_AUTH", "0")
    monkeypatch.setenv("REDISUS_DB_PATH", str(tmp_path / "integration-analyze-text.db"))

    from apps.api.app import create_app
    from apps.api.routes import integration as integration_routes

    class DummyAnalyzer:
        def analyze(self, _image, **_kwargs):
            block = np.full((16, 16, 3), (90, 40, 180), dtype=np.uint8)
            return SimpleNamespace(
                is_valid_wound=True,
                rejection_reason="",
                primary_tissue="Tecido de Granula\u00c3\u00a7\u00c3\u00a3o",
                primary_justification=(
                    "Predom\u00c3\u00adnio de tecido vermelho vivo, compat\u00c3\u00advel "
                    "com cicatriza\u00c3\u00a7\u00c3\u00a3o ativa."
                ),
                wound_area_px=256,
                health_score=74.0,
                processing_time_ms=11.8,
                tissues=[
                    SimpleNamespace(
                        name="Tecido de Granula\u00c3\u00a7\u00c3\u00a3o",
                        name_en="Granulation Tissue",
                        percentage=58.5,
                        color_hex="#D96666",
                        description="Tecido com neovasculariza\u00c3\u00a7\u00c3\u00a3o ativa.",
                        clinical_action="Manter cobertura \u00c3\u00bamida e proteger a les\u00c3\u00a3o.",
                    )
                ],
                border_analysis=None,
                resnet_prediction={
                    "mapped_etiology": "pressure_injury",
                    "final_confidence": 0.9,
                    "needs_expert_review": False,
                    "confidence_level": "high",
                    "confidence_entropy": 0.12,
                    "confidence_margin": 0.31,
                },
                dl_prediction={},
                ensemble_classification={},
                body_part=None,
                push_score=None,
                lighting_analysis=None,
                roi=None,
                detection_overlay=block,
                segmentation_map=block,
                tissue_overlay=block,
                grad_cam_overlay=block,
            )

    monkeypatch.setattr(integration_routes, "_get_wound_analyzer", lambda: DummyAnalyzer())

    app = create_app()
    app.config["TESTING"] = True

    with app.test_client() as client:
        response = client.post(
            "/api/v1/analyze",
            data={"image": (io.BytesIO(_png_bytes()), "wound.png")},
            content_type="multipart/form-data",
        )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["primary_tissue"] == "Tecido de GranulaÃ§Ã£o"
    assert "cicatrizaÃ§Ã£o ativa" in payload["primary_justification"]
    assert payload["tissues"][0]["description"] == "Tecido com neovascularizaÃ§Ã£o ativa."
    assert payload["interpretation"]["recommendations"][0] == "Manter cobertura Ãºmida e proteger a lesÃ£o."


def test_integration_analyze_route_passes_manual_roi_and_returns_roi_payload(tmp_path, monkeypatch):
    monkeypatch.setenv("CLINICAL_API_REQUIRE_AUTH", "0")
    monkeypatch.setenv("REDISUS_DB_PATH", str(tmp_path / "integration-analyze-roi.db"))

    from apps.api.app import create_app
    from apps.api.routes import integration as integration_routes

    class DummyAnalyzer:
        def __init__(self):
            self.received_mask = None
            self.received_roi = None

        def analyze(self, _image, **kwargs):
            self.received_mask = kwargs.get("manual_roi_mask")
            self.received_roi = kwargs.get("roi_metadata")
            block = np.full((16, 16, 3), (50, 120, 200), dtype=np.uint8)
            return SimpleNamespace(
                is_valid_wound=True,
                rejection_reason="",
                primary_tissue="Tecido de Granulação",
                primary_justification="ROI manual aplicada antes da segmentação.",
                wound_area_px=144,
                health_score=79.0,
                processing_time_ms=12.0,
                tissues=[
                    SimpleNamespace(
                        name="Tecido de Granulação",
                        name_en="Granulation Tissue",
                        percentage=82.0,
                        color_hex="#D96666",
                        description="Leito viável.",
                        clinical_action="Manter cobertura protetora.",
                    )
                ],
                border_analysis=None,
                resnet_prediction={
                    "mapped_etiology": "pressure_injury",
                    "final_confidence": 0.91,
                    "needs_expert_review": False,
                    "confidence_level": "high",
                    "confidence_entropy": 0.09,
                    "confidence_margin": 0.42,
                },
                dl_prediction={},
                ensemble_classification={},
                body_part=None,
                push_score=None,
                lighting_analysis=None,
                roi={
                    "source": "manual",
                    "tool": "polygon",
                    "confirmed": True,
                    "points": [
                        {"x": 0.2, "y": 0.2},
                        {"x": 0.8, "y": 0.2},
                        {"x": 0.8, "y": 0.8},
                        {"x": 0.2, "y": 0.8},
                    ],
                    "area_ratio": 0.36,
                },
                detection_overlay=block,
                segmentation_map=block,
                tissue_overlay=block,
                grad_cam_overlay=block,
            )

    analyzer = DummyAnalyzer()
    monkeypatch.setattr(integration_routes, "_get_wound_analyzer", lambda: analyzer)

    app = create_app()
    app.config["TESTING"] = True

    roi_payload = {
        "version": "2026-04-17",
        "tool": "polygon",
        "confirmed": True,
        "source": "manual",
        "image_width": 64,
        "image_height": 64,
        "area_ratio": 0.36,
        "area_px": 144,
        "analysis_width": 64,
        "analysis_height": 64,
        "bounding_box": {"x": 0.2, "y": 0.2, "width": 0.6, "height": 0.6},
        "points": [
            {"x": 0.2, "y": 0.2},
            {"x": 0.8, "y": 0.2},
            {"x": 0.8, "y": 0.8},
            {"x": 0.2, "y": 0.8},
        ],
    }

    with app.test_client() as client:
        response = client.post(
            "/api/v1/analyze",
            data={
                "image": (io.BytesIO(_png_bytes()), "wound.png"),
                "roi_payload": json.dumps(roi_payload),
            },
            content_type="multipart/form-data",
        )

    assert response.status_code == 200
    assert analyzer.received_mask is not None
    assert analyzer.received_mask.shape == (64, 64)
    assert int(np.sum(analyzer.received_mask > 0)) > 0
    assert analyzer.received_roi["tool"] == "polygon"
    assert analyzer.received_roi["source"] == "manual"

    payload = response.get_json()
    assert payload["roi"]["source"] == "manual"
    assert payload["roi"]["tool"] == "polygon"
    assert payload["visuals"]["detection"]["label"] == "ROI manual confirmada"


def test_integration_analyze_route_accepts_multiple_manual_rois(tmp_path, monkeypatch):
    monkeypatch.setenv("CLINICAL_API_REQUIRE_AUTH", "0")
    monkeypatch.setenv("REDISUS_DB_PATH", str(tmp_path / "integration-analyze-multi-roi.db"))

    from apps.api.app import create_app
    from apps.api.routes import integration as integration_routes

    class DummyAnalyzer:
        def __init__(self):
            self.received_mask = None
            self.received_masks = None
            self.received_roi = None
            self.received_roi_list = None

        def analyze(self, _image, **kwargs):
            self.received_mask = kwargs.get("manual_roi_mask")
            self.received_masks = kwargs.get("manual_roi_masks")
            self.received_roi = kwargs.get("roi_metadata")
            self.received_roi_list = kwargs.get("roi_metadata_list")
            block = np.full((16, 16, 3), (70, 160, 90), dtype=np.uint8)
            return SimpleNamespace(
                is_valid_wound=True,
                rejection_reason="",
                primary_tissue="Tecido de GranulaÃ§Ã£o",
                primary_justification="ROIs manuais aplicadas antes da segmentaÃ§Ã£o.",
                wound_area_px=288,
                health_score=77.0,
                processing_time_ms=13.5,
                tissues=[
                    SimpleNamespace(
                        name="Tecido de GranulaÃ§Ã£o",
                        name_en="Granulation Tissue",
                        percentage=74.0,
                        color_hex="#D96666",
                        description="Leito viÃ¡vel.",
                        clinical_action="Manter cobertura protetora.",
                    )
                ],
                border_analysis=None,
                resnet_prediction={
                    "mapped_etiology": "pressure_injury",
                    "final_confidence": 0.87,
                    "needs_expert_review": False,
                    "confidence_level": "high",
                    "confidence_entropy": 0.11,
                    "confidence_margin": 0.31,
                },
                dl_prediction={},
                ensemble_classification={},
                body_part=None,
                push_score=None,
                lighting_analysis=None,
                roi={
                    "source": "manual",
                    "selection_count": 2,
                    "area_ratio": 0.18,
                },
                rois=[
                    {
                        "source": "manual",
                        "tool": "polygon",
                        "confirmed": True,
                        "points": [
                            {"x": 0.15, "y": 0.18},
                            {"x": 0.38, "y": 0.18},
                            {"x": 0.38, "y": 0.45},
                            {"x": 0.15, "y": 0.45},
                        ],
                        "area_ratio": 0.062,
                        "image_width": 64,
                        "image_height": 64,
                    },
                    {
                        "source": "manual",
                        "tool": "polygon",
                        "confirmed": True,
                        "points": [
                            {"x": 0.55, "y": 0.42},
                            {"x": 0.8, "y": 0.42},
                            {"x": 0.8, "y": 0.76},
                            {"x": 0.55, "y": 0.76},
                        ],
                        "area_ratio": 0.085,
                        "image_width": 64,
                        "image_height": 64,
                    },
                ],
                detection_overlay=block,
                segmentation_map=block,
                tissue_overlay=block,
                grad_cam_overlay=block,
            )

    analyzer = DummyAnalyzer()
    monkeypatch.setattr(integration_routes, "_get_wound_analyzer", lambda: analyzer)

    app = create_app()
    app.config["TESTING"] = True

    roi_payload = [
        {
            "version": "2026-04-17",
            "tool": "polygon",
            "confirmed": True,
            "image_width": 64,
            "image_height": 64,
            "area_ratio": 0.062,
            "bounding_box": {"x": 0.15, "y": 0.18, "width": 0.23, "height": 0.27},
            "points": [
                {"x": 0.15, "y": 0.18},
                {"x": 0.38, "y": 0.18},
                {"x": 0.38, "y": 0.45},
                {"x": 0.15, "y": 0.45},
            ],
        },
        {
            "version": "2026-04-17",
            "tool": "polygon",
            "confirmed": True,
            "image_width": 64,
            "image_height": 64,
            "area_ratio": 0.085,
            "bounding_box": {"x": 0.55, "y": 0.42, "width": 0.25, "height": 0.34},
            "points": [
                {"x": 0.55, "y": 0.42},
                {"x": 0.8, "y": 0.42},
                {"x": 0.8, "y": 0.76},
                {"x": 0.55, "y": 0.76},
            ],
        },
    ]

    with app.test_client() as client:
        response = client.post(
            "/api/v1/analyze",
            data={
                "image": (io.BytesIO(_png_bytes()), "wound.png"),
                "roi_payload": json.dumps(roi_payload),
            },
            content_type="multipart/form-data",
        )

    assert response.status_code == 200
    assert analyzer.received_mask is not None
    assert analyzer.received_masks is not None
    assert len(analyzer.received_masks) == 2
    assert analyzer.received_roi["selection_count"] == 2
    assert len(analyzer.received_roi_list) == 2

    payload = response.get_json()
    assert payload["roi"]["selection_count"] == 2
    assert len(payload["rois"]) == 2
    assert payload["visuals"]["detection"]["label"] == "2 ROIs manuais confirmadas"
