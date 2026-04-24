import io
import time

import pytest
from PIL import Image

from src.dashboard.clinical_dashboard import ClinicalDashboard
from src.data.database import Database, PatientRecord

pytestmark = [pytest.mark.contract, pytest.mark.fhir]


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
    assert payload["resource_count"] >= 10
    assert payload["bundle"]["resourceType"] == "Bundle"
    assert payload["bundle"]["type"] == "transaction"

    resource_types = [entry["resource"]["resourceType"] for entry in payload["bundle"]["entry"]]
    assert {"Patient", "Practitioner", "PractitionerRole", "Condition", "Encounter", "Media", "Observation", "DiagnosticReport", "CarePlan", "Provenance"}.issubset(resource_types)

    resources_by_type: dict[str, list[dict]] = {}
    for entry in payload["bundle"]["entry"]:
        resources_by_type.setdefault(entry["resource"]["resourceType"], []).append(entry["resource"])

    practitioner = resources_by_type["Practitioner"][0]
    practitioner_role = resources_by_type["PractitionerRole"][0]
    encounter = resources_by_type["Encounter"][0]
    condition = resources_by_type["Condition"][0]
    media = resources_by_type["Media"][0]
    observation = resources_by_type["Observation"][0]
    care_plan = resources_by_type["CarePlan"][0]
    report = resources_by_type["DiagnosticReport"][0]
    provenance = resources_by_type["Provenance"][0]

    assert practitioner["name"][0]["text"] == "local-dev"
    assert encounter["participant"][0]["individual"]["reference"] == (
        f"Practitioner/{practitioner['id']}"
    )
    assert practitioner_role["practitioner"]["reference"] == f"Practitioner/{practitioner['id']}"
    assert encounter["diagnosis"][0]["condition"]["reference"] == (
        f"Condition/{condition['id']}"
    )
    assert observation["encounter"]["reference"] == f"Encounter/{encounter['id']}"
    assert care_plan["author"]["reference"] == f"Practitioner/{practitioner['id']}"
    assert report["media"][0]["link"]["reference"] == f"Media/{media['id']}"
    assert report["presentedForm"]
    provenance_targets = {item["reference"] for item in provenance["target"]}
    assert f"DiagnosticReport/{report['id']}" in provenance_targets
    assert f"Media/{media['id']}" in provenance_targets

    if "Organization" in resources_by_type:
        organization_ids = {resource["id"] for resource in resources_by_type["Organization"]}
        service_provider_ref = encounter.get("serviceProvider", {}).get("reference", "")
        assert service_provider_ref.split("/", 1)[-1] in organization_ids

    for entry in payload["bundle"]["entry"]:
        assert entry["request"]["method"] == "PUT"
        assert entry["request"]["url"].endswith(entry["resource"]["id"])


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


def test_case_fhir_export_rejects_invalid_bundle_type_before_lookup(client):
    create_response = client.post(
        "/api/v1/evaluations",
        json={
            "patient_id": "p001",
            "evaluation_date": "2026-04-21",
            "wound_type": "venous_ulcer",
            "wound_location": "perna direita",
            "clinical_description": "contrato de bundle invalido",
            "wound_area_cm2": 7.0,
            "depth_mm": 1.0,
            "pain_score": 2,
            "tissue_composition": {"granulation": 70, "slough": 20, "necrosis": 10},
        },
    )
    assert create_response.status_code == 201
    case_id = create_response.get_json()["case_id"]

    response = client.get(f"/api/v1/lesions/{case_id}/fhir?bundleType=batch")

    assert response.status_code == 400
    payload = response.get_json()
    assert payload == {
        "error": "bundle_type_invalido",
        "detail": "bundleType must be collection or transaction",
    }
