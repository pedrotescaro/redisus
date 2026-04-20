from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.interoperability.fhir_r4.examples import build_example_artifacts
from src.interoperability.fhir_r4.validators import validate_bundle, validate_resource


EXAMPLES_DIR = Path("src/interoperability/fhir_r4/examples")


def _normalize_snapshot(value: Any) -> Any:
    if isinstance(value, dict):
        normalized: dict[str, Any] = {}
        for key in sorted(value.keys()):
            if key in {"lastUpdated", "timestamp"}:
                continue
            normalized[key] = _normalize_snapshot(value[key])
        return normalized
    if isinstance(value, list):
        return [_normalize_snapshot(item) for item in value]
    return value


def test_example_json_snapshots_match_generated_artifacts():
    artifacts = build_example_artifacts()
    expected_files = {
        "patient": "patient_example.json",
        "organization": "organization_example.json",
        "practitioner": "practitioner_example.json",
        "practitioner_role": "practitioner_role_example.json",
        "encounter": "encounter_example.json",
        "media": "media_example.json",
        "observation": "observation_example.json",
        "condition": "condition_example.json",
        "diagnostic_report": "diagnostic_report_example.json",
        "care_plan": "care_plan_example.json",
        "provenance": "provenance_example.json",
        "bundle": "wound_case_bundle.json",
    }

    for artifact_name, filename in expected_files.items():
        example_payload = json.loads((EXAMPLES_DIR / filename).read_text(encoding="utf-8"))
        generated_payload = artifacts[artifact_name]
        assert _normalize_snapshot(generated_payload) == _normalize_snapshot(example_payload)


def test_example_artifacts_pass_structural_validation():
    artifacts = build_example_artifacts()
    for resource_name in (
        "patient",
        "organization",
        "practitioner",
        "practitioner_role",
        "encounter",
        "media",
        "observation",
        "condition",
        "diagnostic_report",
        "care_plan",
        "provenance",
    ):
        validate_resource(artifacts[resource_name], strict=False)
    validate_bundle(artifacts["bundle"], strict=False)
