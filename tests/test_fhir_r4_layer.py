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
    assert resource_types == ["Patient", "Practitioner", "Condition", "Encounter", "Observation", "DiagnosticReport", "CarePlan"]

    resources = {entry["resource"]["resourceType"]: entry["resource"] for entry in bundle["entry"]}
    assert resources["Encounter"]["subject"]["reference"] == "Patient/patient-redisus-001"
    assert resources["Encounter"]["participant"][0]["individual"]["reference"] == (
        f"Practitioner/{resources['Practitioner']['id']}"
    )
    assert resources["Observation"]["encounter"]["reference"] == f"Encounter/{resources['Encounter']['id']}"
    assert resources["DiagnosticReport"]["encounter"]["reference"] == f"Encounter/{resources['Encounter']['id']}"


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
