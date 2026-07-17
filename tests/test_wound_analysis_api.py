import io
import json
from types import SimpleNamespace

import numpy as np
import pytest
from PIL import Image

from packages.clinical_domain import PatientRecord


def _png_bytes(color: tuple[int, int, int] = (180, 35, 35)) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (48, 48), color=color).save(buffer, format="PNG")
    return buffer.getvalue()


class _DummyAnalyzer:
    def analyze(self, _image, **_kwargs):
        red = np.full((24, 24, 3), (0, 0, 220), dtype=np.uint8)
        green = np.full((24, 24, 3), (0, 180, 0), dtype=np.uint8)
        return SimpleNamespace(
            is_valid_wound=True,
            rejection_reason="",
            primary_tissue="Granulation Tissue",
            primary_justification="Predomínio de tecido de granulação.",
            wound_area_px=576,
            health_score=80.0,
            processing_time_ms=12.0,
            tissues=[
                SimpleNamespace(
                    name="Tecido de granulação",
                    name_en="Granulation Tissue",
                    percentage=100.0,
                    color_hex="#D96666",
                    description="Tecido viável.",
                    clinical_action="Revisar clinicamente.",
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
            wound_zones=None,
            wound_segmentation=None,
            tissue_analysis_trace=None,
            roi=None,
            rois=None,
            detection_overlay=red,
            segmentation_map=green,
            tissue_overlay=red,
            grad_cam_overlay=red,
        )


@pytest.fixture
def canonical_client(tmp_path, monkeypatch):
    monkeypatch.setenv("CLINICAL_API_REQUIRE_AUTH", "0")
    monkeypatch.setenv("REDISUS_DB_PATH", str(tmp_path / "wound-analysis.db"))

    from apps.api.app import create_app
    from apps.api.routes import integration as integration_routes

    monkeypatch.setattr(integration_routes, "_get_wound_analyzer", lambda: _DummyAnalyzer())
    app = create_app()
    app.config["TESTING"] = True
    app.extensions["redisus_db"].save_patient(PatientRecord(id="patient-1", name="Paciente Teste"))
    with app.test_client() as client:
        yield client, app.extensions["redisus_db"]


def test_canonical_wound_analysis_create_get_and_idempotent_replay(canonical_client):
    client, _database = canonical_client
    headers = {"Idempotency-Key": "heal-test-create-0001"}

    created = client.post(
        "/api/v1/wound-analyses",
        data={"image": (io.BytesIO(_png_bytes()), "wound.png")},
        headers=headers,
        content_type="multipart/form-data",
    )

    assert created.status_code == 201
    payload = created.get_json()
    assert payload["resource_type"] == "wound_analysis"
    assert payload["api_version"] == "1.0.0"
    assert payload["status"] == "completed"
    assert payload["persistence"] == {"stored": True, "backend": "sqlite"}
    assert payload["safety"]["clinician_review_required"] is True
    assert payload["execution"]["mode"] == "model_assisted"
    assert created.headers["Location"].endswith(payload["analysis_id"])

    fetched = client.get(created.headers["Location"])
    assert fetched.status_code == 200
    assert fetched.get_json()["analysis_id"] == payload["analysis_id"]

    replay = client.post(
        "/api/v1/wound-analyses",
        data={"image": (io.BytesIO(_png_bytes()), "wound.png")},
        headers=headers,
        content_type="multipart/form-data",
    )
    assert replay.status_code == 200
    assert replay.headers["X-Idempotent-Replay"] == "true"
    assert replay.get_json()["analysis_id"] == payload["analysis_id"]


def test_canonical_wound_analysis_rejects_idempotency_key_reuse(canonical_client):
    client, _database = canonical_client
    headers = {"Idempotency-Key": "heal-test-conflict-0001"}
    first = client.post(
        "/api/v1/wound-analyses",
        data={"image": (io.BytesIO(_png_bytes()), "wound.png")},
        headers=headers,
        content_type="multipart/form-data",
    )
    assert first.status_code == 201

    conflict = client.post(
        "/api/v1/wound-analyses",
        data={"image": (io.BytesIO(_png_bytes((20, 20, 180))), "other.png")},
        headers=headers,
        content_type="multipart/form-data",
    )
    assert conflict.status_code == 409
    assert conflict.content_type == "application/problem+json"
    assert conflict.get_json()["code"] == "idempotency_conflict"
    assert conflict.get_json()["request_id"]


def test_canonical_wound_analysis_links_optional_evaluation(canonical_client):
    client, database = canonical_client
    evaluation = database.create_wound_evaluation(
        {
            "patient_id": "patient-1",
            "evaluation_date": "2026-07-16",
            "tissue_composition": {},
            "timers_payload": {},
        }
    )
    assert evaluation is not None

    response = client.post(
        "/api/v1/wound-analyses",
        data={
            "evaluation_id": evaluation["id"],
            "image": (io.BytesIO(_png_bytes()), "wound.png"),
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 201
    subject = response.get_json()["subject"]
    assert subject == {"patient_id": "patient-1", "evaluation_id": evaluation["id"]}
    assert response.get_json()["evaluation_id"] == evaluation["id"]


def test_canonical_wound_analysis_validates_roi_image_dimensions(canonical_client):
    client, _database = canonical_client
    roi = {
        "version": "1",
        "tool": "polygon",
        "confirmed": True,
        "image_width": 512,
        "image_height": 512,
        "points": [{"x": 0.1, "y": 0.1}, {"x": 0.8, "y": 0.1}, {"x": 0.5, "y": 0.8}],
    }

    response = client.post(
        "/api/v1/wound-analyses",
        data={
            "roi_payload": json.dumps(roi),
            "image": (io.BytesIO(_png_bytes()), "wound.png"),
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 422
    assert response.content_type == "application/problem+json"
    assert "do not match" in response.get_json()["detail"]


def test_wound_analysis_capabilities_disclose_runtime_and_limits(canonical_client):
    client, _database = canonical_client
    response = client.get("/api/v1/wound-analyses/capabilities")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["runtime"]["status"] == "ready"
    assert payload["runtime"]["generative_fallback_allowed"] is False
    assert payload["clinical_use"]["clinician_review_required"] is True
    assert payload["outputs"]["idempotency_key_supported"] is True


def test_canonical_wound_analysis_fails_closed_without_clinical_engine(canonical_client, monkeypatch):
    client, _database = canonical_client
    from apps.api.routes import integration as integration_routes

    monkeypatch.setattr(integration_routes, "_get_wound_analyzer", lambda: None)
    response = client.post(
        "/api/v1/wound-analyses",
        data={"image": (io.BytesIO(_png_bytes()), "wound.png")},
        content_type="multipart/form-data",
    )

    assert response.status_code == 503
    assert response.content_type == "application/problem+json"
    payload = response.get_json()
    assert payload["code"] == "analyzer_unavailable"
    assert "canonical clinical analyzer" not in payload["detail"]
