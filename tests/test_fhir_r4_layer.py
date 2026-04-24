from __future__ import annotations

import pytest

from src.interoperability.fhir_r4 import GoogleCloudHealthcareFHIRAdapter, RedisusFHIRMapper
from src.interoperability.fhir_r4.examples import (
    sample_care_plan_data,
    sample_evaluation_data,
    sample_inference_result,
    sample_patient_data,
)
from src.interoperability.fhir_r4.validators import FHIRValidationError, validate_bundle

pytestmark = [pytest.mark.contract, pytest.mark.fhir]


def test_mapper_creates_complete_wound_case_bundle():
    mapper = RedisusFHIRMapper()
    bundle = mapper.map_case_to_bundle(
        patient_data=sample_patient_data(),
        evaluation_data=sample_evaluation_data(),
        inference_result=sample_inference_result(),
        care_plan_data=sample_care_plan_data(),
        bundle_type="collection",
    )

    resource_types = [entry["resource"]["resourceType"] for entry in bundle["entry"]]
    assert bundle["resourceType"] == "Bundle"
    assert bundle["type"] == "collection"
    assert resource_types == [
        "Patient",
        "Organization",
        "Organization",
        "Practitioner",
        "PractitionerRole",
        "Condition",
        "Encounter",
        "Media",
        "Observation",
        "DiagnosticReport",
        "CarePlan",
        "Provenance",
    ]

    resources_by_type: dict[str, list[dict]] = {}
    for entry in bundle["entry"]:
        resources_by_type.setdefault(entry["resource"]["resourceType"], []).append(entry["resource"])

    patient = resources_by_type["Patient"][0]
    unit_organization, team_organization = resources_by_type["Organization"]
    practitioner = resources_by_type["Practitioner"][0]
    practitioner_role = resources_by_type["PractitionerRole"][0]
    encounter = resources_by_type["Encounter"][0]
    media = resources_by_type["Media"][0]
    observation = resources_by_type["Observation"][0]
    report = resources_by_type["DiagnosticReport"][0]
    care_plan = resources_by_type["CarePlan"][0]
    provenance = resources_by_type["Provenance"][0]

    assert encounter["subject"]["reference"] == f"Patient/{patient['id']}"
    assert encounter["participant"][0]["individual"]["reference"] == (
        f"Practitioner/{practitioner['id']}"
    )
    assert encounter["serviceProvider"]["reference"] == f"Organization/{unit_organization['id']}"
    assert team_organization["partOf"]["reference"] == f"Organization/{unit_organization['id']}"
    assert practitioner_role["practitioner"]["reference"] == f"Practitioner/{practitioner['id']}"
    assert practitioner_role["organization"]["reference"] == f"Organization/{team_organization['id']}"
    assert observation["encounter"]["reference"] == f"Encounter/{encounter['id']}"
    assert report["encounter"]["reference"] == f"Encounter/{encounter['id']}"
    assert report["media"][0]["link"]["reference"] == f"Media/{media['id']}"
    assert report["presentedForm"]
    assert care_plan["author"]["reference"] == f"Practitioner/{practitioner['id']}"
    provenance_targets = {item["reference"] for item in provenance["target"]}
    assert f"DiagnosticReport/{report['id']}" in provenance_targets
    assert f"Media/{media['id']}" in provenance_targets


def test_validate_bundle_rejects_missing_entry_resource():
    with pytest.raises(FHIRValidationError):
        validate_bundle(
            {
                "resourceType": "Bundle",
                "type": "collection",
                "entry": [{"fullUrl": "urn:uuid:missing-resource"}],
            },
            strict=False,
        )


def test_mapper_creates_transaction_bundle_with_put_requests():
    mapper = RedisusFHIRMapper()
    bundle = mapper.map_case_to_bundle(
        patient_data=sample_patient_data(),
        evaluation_data=sample_evaluation_data(),
        inference_result=sample_inference_result(),
        care_plan_data=sample_care_plan_data(),
        bundle_type="transaction",
    )

    assert bundle["type"] == "transaction"
    validate_bundle(bundle, strict=False)

    for entry in bundle["entry"]:
        resource = entry["resource"]
        assert entry["fullUrl"] == f"urn:uuid:{resource['resourceType'].lower()}-{resource['id']}"
        assert entry["request"] == {
            "method": "PUT",
            "url": f"{resource['resourceType']}/{resource['id']}",
        }


def test_mapper_normalizes_portuguese_clinical_aliases():
    mapper = RedisusFHIRMapper()
    patient_data = sample_patient_data()
    patient_data["gender"] = "feminino"

    evaluation_data = sample_evaluation_data()
    evaluation_data["wound_type"] = "lesao_pressao"

    inference_result = sample_inference_result()
    inference_result["inference"]["etiology"] = "lesao_pressao"
    inference_result["inference"]["tissue_percentages"] = {
        "granulacao": 50,
        "esfacelo": 25,
        "necrose": 25,
    }
    inference_result["etiology"] = {"primary": "lesao_pressao", "confidence": 0.9}

    bundle = mapper.map_case_to_bundle(
        patient_data=patient_data,
        evaluation_data=evaluation_data,
        inference_result=inference_result,
        care_plan_data=sample_care_plan_data(),
        bundle_type="collection",
    )
    resources_by_type: dict[str, list[dict]] = {}
    for entry in bundle["entry"]:
        resources_by_type.setdefault(entry["resource"]["resourceType"], []).append(entry["resource"])

    patient = resources_by_type["Patient"][0]
    condition = resources_by_type["Condition"][0]
    observation = resources_by_type["Observation"][0]

    assert patient["gender"] == "female"
    assert condition["code"]["coding"][0]["code"] == "399912005"
    assert condition["code"]["coding"][-1]["code"] == "pressure_injury"

    tissue_components = {
        component["code"]["coding"][-1]["code"]: component["valueQuantity"]["value"]
        for component in observation["component"]
        if component["code"]["coding"][-1]["code"] in {"granulation", "slough", "necrosis"}
    }
    assert tissue_components == {
        "granulation": 50.0,
        "slough": 25.0,
        "necrosis": 25.0,
    }


def test_google_adapter_uses_env_configuration(monkeypatch):
    monkeypatch.setenv("REDISUS_FHIR_GCP_PROJECT_ID", "demo-project")
    monkeypatch.setenv("REDISUS_FHIR_GCP_LOCATION", "southamerica-east1")
    monkeypatch.setenv("REDISUS_FHIR_GCP_DATASET_ID", "redisus-dataset")
    monkeypatch.setenv("REDISUS_FHIR_GCP_STORE_ID", "redisus-store")
    monkeypatch.setenv("REDISUS_FHIR_GCP_BEARER_TOKEN", "token-123")

    adapter = GoogleCloudHealthcareFHIRAdapter.from_environment()

    assert adapter.fhir_store_url == (
        "https://healthcare.googleapis.com/v1/projects/demo-project/locations/southamerica-east1/"
        "datasets/redisus-dataset/fhirStores/redisus-store/fhir"
    )
    assert adapter._headers()["Authorization"] == "Bearer token-123"
