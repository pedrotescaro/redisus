import io
import time

import pytest
from PIL import Image

from src.dashboard.clinical_dashboard import ClinicalDashboard
from src.data.database import Database, PatientRecord


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("CLINICAL_API_REQUIRE_AUTH", "0")
    db = Database(str(tmp_path / "test-fhir-export.db"))
    db.save_patient(
        PatientRecord(
            id="p001",
            name="Paciente FHIR",
            birth_date="1954-08-14",
            metadata={
                "gender": "female",
                "cpf": "12345678901",
                "cns": "700000000000001",
                "phone": "+55-11-99999-0001",
                "address": {
                    "line": "Rua FHIR, 100",
                    "city": "Sao Paulo",
                    "state": "SP",
                    "postalCode": "01000-000",
                    "country": "BR",
                },
            },
        )
    )
    app = ClinicalDashboard(database=db).create_app()
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def _png_bytes(color=(180, 20, 20)) -> bytes:
    buffer = io.BytesIO()
    image = Image.new("RGB", (32, 32), color=color)
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _wait_for_job_completion(client, job_id: str) -> dict:
    for _ in range(20):
        response = client.get(f"/api/v1/analysis-jobs/{job_id}")
        assert response.status_code == 200
        payload = response.get_json()
        if payload["job"]["status"] == "completed":
            return payload
        time.sleep(0.2)
    pytest.fail("Job de IA nao concluiu dentro do tempo esperado.")


def _create_case_with_completed_ai(client) -> dict:
    create_response = client.post(
        "/api/v1/evaluations",
        json={
            "patient_id": "p001",
            "evaluation_date": "2026-04-19",
            "wound_type": "venous_ulcer",
            "wound_location": "perna esquerda",
            "clinical_description": "ferida cronica com exsudato moderado",
            "wound_area_cm2": 12.0,
            "depth_mm": 3.0,
            "pain_score": 5,
            "tissue_composition": {"granulation": 52, "slough": 33, "necrosis": 15},
        },
    )
    assert create_response.status_code == 201
    evaluation = create_response.get_json()

    upload_response = client.post(
        f"/api/v1/evaluations/{evaluation['id']}/images",
        data={"imageRole": "clinical", "image": (io.BytesIO(_png_bytes()), "wound.png")},
        content_type="multipart/form-data",
    )
    assert upload_response.status_code == 201

    analyze_response = client.post(f"/api/v1/evaluations/{evaluation['id']}/analyze", json={})
    assert analyze_response.status_code == 202
    job_payload = _wait_for_job_completion(client, analyze_response.get_json()["jobId"])
    return {
        "evaluation": evaluation,
        "job": job_payload["job"],
        "result": job_payload["result"],
    }


def test_case_fhir_export_returns_transaction_bundle(client):
    created = _create_case_with_completed_ai(client)
    evaluation = created["evaluation"]

    response = client.get(f"/api/v1/lesions/{evaluation['case_id']}/fhir?bundleType=transaction")
    assert response.status_code == 200
    payload = response.get_json()

    assert payload["case_id"] == evaluation["case_id"]
    assert payload["patient_id"] == "p001"
    assert payload["evaluation_id"] == evaluation["id"]
    assert payload["bundle_type"] == "transaction"
    assert payload["resource_count"] == 7
    assert payload["bundle"]["resourceType"] == "Bundle"
    assert payload["bundle"]["type"] == "transaction"

    resource_types = [entry["resource"]["resourceType"] for entry in payload["bundle"]["entry"]]
    assert resource_types == ["Patient", "Practitioner", "Condition", "Encounter", "Observation", "DiagnosticReport", "CarePlan"]

    resources = {entry["resource"]["resourceType"]: entry["resource"] for entry in payload["bundle"]["entry"]}
    assert resources["Practitioner"]["name"][0]["text"] == "local-dev"
    assert resources["Encounter"]["participant"][0]["individual"]["reference"] == (
        f"Practitioner/{resources['Practitioner']['id']}"
    )
    assert resources["Encounter"]["diagnosis"][0]["condition"]["reference"] == (
        f"Condition/{resources['Condition']['id']}"
    )
    assert resources["Observation"]["encounter"]["reference"] == f"Encounter/{resources['Encounter']['id']}"
    assert resources["CarePlan"]["author"]["reference"] == f"Practitioner/{resources['Practitioner']['id']}"

    report_entry = next(entry for entry in payload["bundle"]["entry"] if entry["resource"]["resourceType"] == "DiagnosticReport")
    assert report_entry["resource"]["presentedForm"]


def test_case_fhir_export_rejects_evaluation_from_other_case(client):
    first_case = _create_case_with_completed_ai(client)
    second_create = client.post(
        "/api/v1/evaluations",
        json={
            "patient_id": "p001",
            "evaluation_date": "2026-04-20",
            "wound_type": "pressure_injury",
            "wound_location": "sacro",
            "clinical_description": "segunda lesao para teste",
            "wound_area_cm2": 8.0,
            "depth_mm": 1.5,
            "pain_score": 4,
            "tissue_composition": {"granulation": 40, "slough": 45, "necrosis": 15},
        },
    )
    assert second_create.status_code == 201
    second_evaluation = second_create.get_json()

    response = client.get(
        f"/api/v1/lesions/{first_case['evaluation']['case_id']}/fhir?evaluationId={second_evaluation['id']}"
    )
    assert response.status_code == 404
    assert response.get_json()["error"] == "fhir_export_evaluation_not_found_for_case"
