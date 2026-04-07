import io
import time

import pytest
from PIL import Image

from src.dashboard.clinical_dashboard import ClinicalDashboard
from src.data.database import Database, PatientRecord


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("CLINICAL_API_REQUIRE_AUTH", "0")
    db = Database(str(tmp_path / "test.db"))
    db.save_patient(PatientRecord(id="p001", name="Paciente Teste"))
    app = ClinicalDashboard(database=db).create_app()
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def _png_bytes(color: tuple[int, int, int] = (180, 20, 20)) -> bytes:
    buffer = io.BytesIO()
    image = Image.new("RGB", (32, 32), color=color)
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def test_health_contract(client):
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload["status"] == "ok"
    assert "metrics" in payload


def test_evaluation_image_analyze_job_contract(client):
    create_resp = client.post(
        "/api/v1/evaluations",
        json={
            "patient_id": "p001",
            "evaluation_date": "2026-03-19",
            "wound_type": "venous_ulcer",
            "wound_location": "perna direita",
            "clinical_description": "teste",
            "wound_area_cm2": 10.0,
            "depth_mm": 3.0,
            "pain_score": 5,
            "tissue_composition": {"granulation": 50, "slough": 40, "necrosis": 10},
        },
    )
    assert create_resp.status_code == 201
    evaluation = create_resp.get_json()
    evaluation_id = evaluation["id"]

    upload_resp = client.post(
        f"/api/v1/evaluations/{evaluation_id}/images",
        data={"imageRole": "frontal", "image": (io.BytesIO(_png_bytes()), "wound.png")},
        content_type="multipart/form-data",
    )
    assert upload_resp.status_code == 201

    analyze_resp = client.post(f"/api/v1/evaluations/{evaluation_id}/analyze", json={})
    assert analyze_resp.status_code == 202
    job_id = analyze_resp.get_json()["jobId"]

    for _ in range(15):
        status_resp = client.get(f"/api/v1/analysis-jobs/{job_id}")
        assert status_resp.status_code == 200
        payload = status_resp.get_json()
        if payload["job"]["status"] == "completed":
            assert payload["result"] is not None
            break
        time.sleep(0.2)
    else:
        pytest.fail("Job de IA não concluiu dentro do tempo esperado.")


def test_comparison_deltas_contract(client):
    base = client.post(
        "/api/v1/evaluations",
        json={
            "patient_id": "p001",
            "evaluation_date": "2026-03-01",
            "wound_area_cm2": 12.0,
            "depth_mm": 4.0,
            "pain_score": 7,
            "push_score": 12,
            "bwat_score": 35,
            "tissue_composition": {"granulation": 40, "slough": 45, "necrosis": 15},
        },
    ).get_json()

    follow = client.post(
        "/api/v1/evaluations",
        json={
            "patient_id": "p001",
            "case_id": base["case_id"],
            "evaluation_date": "2026-03-10",
            "wound_area_cm2": 9.0,
            "depth_mm": 3.0,
            "pain_score": 4,
            "push_score": 8,
            "bwat_score": 28,
            "tissue_composition": {"granulation": 60, "slough": 30, "necrosis": 10},
        },
    ).get_json()

    resp = client.get(f"/api/v1/comparisons?left={base['id']}&right={follow['id']}")
    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload["deltas"]["area_cm2"] == -3.0
    assert payload["deltas"]["depth_mm"] == -1.0
    assert payload["deltas"]["pain_score"] == -3.0
    assert payload["deltas"]["tissue"]["granulation"] == 20.0

