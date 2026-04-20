from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

import pytest

from src.interoperability.fhir_r4 import FHIRPublicationError, FHIRPublicationService, RedisusFHIRMapper
from src.interoperability.fhir_r4.client import AbstractFHIRClient
from src.interoperability.fhir_r4.examples import (
    sample_care_plan_data,
    sample_evaluation_data,
    sample_inference_result,
    sample_patient_data,
)


class RecordingFHIRClient(AbstractFHIRClient):
    def __init__(self, *, failures_before_success: int = 0):
        super().__init__(strict_validation=False)
        self.server_url = "https://example.org/fhir"
        self.failures_before_success = failures_before_success
        self.sent_bundles: list[dict[str, Any]] = []

    def send_resource(self, resource: Mapping[str, Any]) -> dict[str, Any]:
        raise NotImplementedError

    def send_bundle(self, bundle: Mapping[str, Any]) -> dict[str, Any]:
        self.sent_bundles.append(dict(bundle))
        if self.failures_before_success > 0:
            self.failures_before_success -= 1
            raise RuntimeError("temporary upstream failure")
        return {
            "resourceType": "Bundle",
            "type": "transaction-response",
            "entry": [{"response": {"status": "200 OK"}}],
        }

    def read(self, resource_type: str, resource_id: str) -> dict[str, Any] | None:
        return None

    def search(self, resource_type: str, params: Mapping[str, Any] | None = None) -> dict[str, Any]:
        return {"resourceType": "Bundle", "type": "searchset", "entry": []}


def _build_bundle() -> dict[str, Any]:
    mapper = RedisusFHIRMapper(strict_validation=False)
    return mapper.map_case_to_bundle(
        patient_data=sample_patient_data(),
        evaluation_data=sample_evaluation_data(),
        inference_result=sample_inference_result(),
        care_plan_data=sample_care_plan_data(),
        bundle_type="transaction",
    )


def test_publication_service_is_idempotent_for_same_logical_bundle(tmp_path: Path):
    client = RecordingFHIRClient()
    service = FHIRPublicationService(client, audit_dir=tmp_path / "audit", retry_delay_seconds=0)

    first_bundle = _build_bundle()
    second_bundle = _build_bundle()

    first = service.publish_bundle(
        first_bundle,
        case_id="lesion-venous-001",
        evaluation_id="evaluation-2026-04-19-001",
    )
    second = service.publish_bundle(
        second_bundle,
        case_id="lesion-venous-001",
        evaluation_id="evaluation-2026-04-19-001",
    )

    assert first.status == "published"
    assert second.status == "skipped"
    assert len(client.sent_bundles) == 1
    assert first.idempotency_key == second.idempotency_key

    audit_events = [
        json.loads(line)
        for line in (tmp_path / "audit" / "publication_audit.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert {event["event_type"] for event in audit_events} >= {"attempt_started", "published", "idempotent_skip"}


def test_publication_service_retries_before_succeeding(tmp_path: Path):
    client = RecordingFHIRClient(failures_before_success=1)
    service = FHIRPublicationService(client, audit_dir=tmp_path / "audit", retry_delay_seconds=0)

    result = service.publish_bundle(
        _build_bundle(),
        case_id="lesion-venous-001",
        evaluation_id="evaluation-2026-04-19-001",
    )

    assert result.status == "published"
    assert result.attempts == 2
    assert len(client.sent_bundles) == 2

    audit_events = [
        json.loads(line)
        for line in (tmp_path / "audit" / "publication_audit.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert any(event["event_type"] == "attempt_failed" for event in audit_events)


def test_publication_service_raises_after_exhausting_retries(tmp_path: Path):
    client = RecordingFHIRClient(failures_before_success=3)
    service = FHIRPublicationService(client, audit_dir=tmp_path / "audit", max_retries=1, retry_delay_seconds=0)

    with pytest.raises(FHIRPublicationError):
        service.publish_bundle(
            _build_bundle(),
            case_id="lesion-venous-001",
            evaluation_id="evaluation-2026-04-19-001",
        )

    assert len(client.sent_bundles) == 2
