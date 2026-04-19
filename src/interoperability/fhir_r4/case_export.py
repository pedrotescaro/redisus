from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .mappers import RedisusFHIRMapper
from .models import fhir_now


def _as_dict(value: Any) -> dict[str, Any]:
    if hasattr(value, "to_dict"):
        data = value.to_dict()
        if isinstance(data, Mapping):
            return dict(data)
    if isinstance(value, Mapping):
        return dict(value)
    return {}


@dataclass(slots=True)
class ClinicalCaseFHIRExportService:
    mapper: RedisusFHIRMapper

    def __init__(self, *, strict_validation: bool = False, mapper: RedisusFHIRMapper | None = None):
        self.mapper = mapper or RedisusFHIRMapper(strict_validation=strict_validation)

    def export_case(
        self,
        raw_timeline: Mapping[str, Any],
        *,
        evaluation_id: str | None = None,
        bundle_type: str = "collection",
    ) -> dict[str, Any]:
        normalized_bundle_type = str(bundle_type or "collection").strip().lower()
        if normalized_bundle_type not in {"collection", "transaction"}:
            raise ValueError("bundle_type must be 'collection' or 'transaction'")

        lesion = _as_dict(raw_timeline.get("lesion"))
        patient = _as_dict(raw_timeline.get("patient"))
        evaluations = [_as_dict(item) for item in (raw_timeline.get("evaluations") or [])]
        care_plans = [_as_dict(item) for item in (raw_timeline.get("care_plans") or [])]

        selected_evaluation = self._select_evaluation(evaluations, evaluation_id=evaluation_id)
        if not selected_evaluation:
            raise LookupError("fhir_export_requires_at_least_one_evaluation")

        selected_care_plan = self._select_care_plan(care_plans, evaluation_id=selected_evaluation.get("id"))
        patient_payload = self._build_patient_payload(patient)
        evaluation_payload = self._build_evaluation_payload(selected_evaluation, lesion=lesion)
        practitioner_payload = self._build_practitioner_payload(selected_evaluation, lesion=lesion)
        encounter_payload = self._build_encounter_payload(selected_evaluation, lesion=lesion)
        inference_payload = _as_dict(selected_evaluation.get("inference_result"))
        bundle = self.mapper.map_case_to_bundle(
            patient_data=patient_payload,
            evaluation_data=evaluation_payload,
            inference_result=inference_payload or None,
            care_plan_data=selected_care_plan or None,
            practitioner_data=practitioner_payload,
            encounter_data=encounter_payload,
            images=evaluation_payload.get("images") or [],
            bundle_type=normalized_bundle_type,
        )
        return {
            "generated_at": fhir_now(),
            "case_id": lesion.get("id"),
            "patient_id": patient_payload.get("id"),
            "evaluation_id": evaluation_payload.get("id"),
            "care_plan_id": selected_care_plan.get("id") if selected_care_plan else None,
            "bundle_type": normalized_bundle_type,
            "resource_count": len(bundle.get("entry") or []),
            "bundle": bundle,
        }

    def _select_evaluation(
        self,
        evaluations: list[dict[str, Any]],
        *,
        evaluation_id: str | None = None,
    ) -> dict[str, Any] | None:
        if not evaluations:
            return None
        if evaluation_id:
            for evaluation in evaluations:
                if str(evaluation.get("id") or "") == str(evaluation_id):
                    return evaluation
            raise LookupError("fhir_export_evaluation_not_found_for_case")
        return sorted(
            evaluations,
            key=lambda item: (
                str(item.get("evaluation_date") or ""),
                str(item.get("created_at") or ""),
                str(item.get("id") or ""),
            ),
        )[-1]

    def _select_care_plan(
        self,
        care_plans: list[dict[str, Any]],
        *,
        evaluation_id: str | None = None,
    ) -> dict[str, Any] | None:
        if not care_plans:
            return None
        if evaluation_id:
            matching = [
                plan
                for plan in care_plans
                if str(plan.get("source_evaluation_id") or "") == str(evaluation_id)
            ]
            if matching:
                return sorted(
                    matching,
                    key=lambda item: (
                        str(item.get("created_at") or ""),
                        int(item.get("version") or 0),
                    ),
                )[-1]
        active = [plan for plan in care_plans if str(plan.get("status") or "").lower() == "active"]
        candidates = active or care_plans
        return sorted(
            candidates,
            key=lambda item: (
                str(item.get("created_at") or ""),
                int(item.get("version") or 0),
            ),
        )[-1]

    def _build_patient_payload(self, patient: dict[str, Any]) -> dict[str, Any]:
        metadata = patient.get("metadata") if isinstance(patient.get("metadata"), Mapping) else {}
        address = self._build_address_payload(patient, metadata)
        payload = {
            "id": patient.get("id"),
            "name": patient.get("name"),
            "birth_date": patient.get("birth_date") or metadata.get("birth_date"),
            "gender": patient.get("gender") or metadata.get("gender") or metadata.get("sex"),
            "cpf": patient.get("cpf") or metadata.get("cpf"),
            "cns": patient.get("cns") or metadata.get("cns"),
            "phone": patient.get("phone") or metadata.get("phone") or metadata.get("telefone"),
            "email": patient.get("email") or metadata.get("email"),
            "address": address,
        }
        return {key: value for key, value in payload.items() if value not in (None, "", {}, [])}

    def _build_address_payload(self, patient: dict[str, Any], metadata: Mapping[str, Any]) -> dict[str, Any] | None:
        if isinstance(patient.get("address"), Mapping):
            return dict(patient.get("address") or {})
        if isinstance(metadata.get("address"), Mapping):
            return dict(metadata.get("address") or {})

        address = {
            "line": metadata.get("address_line") or metadata.get("logradouro"),
            "city": metadata.get("city") or metadata.get("cidade"),
            "state": metadata.get("state") or metadata.get("uf"),
            "postalCode": metadata.get("postal_code") or metadata.get("cep"),
            "country": metadata.get("country") or metadata.get("pais") or "BR",
        }
        if any(address.values()):
            return {key: value for key, value in address.items() if value}
        return None

    def _build_evaluation_payload(self, evaluation: dict[str, Any], *, lesion: dict[str, Any]) -> dict[str, Any]:
        payload = dict(evaluation)
        if not payload.get("case_id"):
            payload["case_id"] = lesion.get("id")
        if not payload.get("wound_type"):
            payload["wound_type"] = lesion.get("wound_type")
        if not payload.get("wound_location"):
            payload["wound_location"] = lesion.get("location")
        payload["images"] = list(payload.get("images") or [])
        return payload

    def _build_practitioner_payload(
        self,
        evaluation: dict[str, Any],
        *,
        lesion: dict[str, Any],
    ) -> dict[str, Any] | None:
        evaluation_metadata = evaluation.get("metadata") if isinstance(evaluation.get("metadata"), Mapping) else {}
        lesion_metadata = lesion.get("metadata") if isinstance(lesion.get("metadata"), Mapping) else {}

        payload = {
            "id": (
                evaluation.get("professional_id")
                or evaluation_metadata.get("professional_id")
                or evaluation_metadata.get("practitioner_id")
                or lesion.get("assigned_to_uid")
                or lesion.get("claimed_by_uid")
                or lesion.get("handoff_to_uid")
            ),
            "name": (
                evaluation.get("professional_name")
                or evaluation_metadata.get("professional_name")
                or lesion.get("assigned_to_name")
                or lesion.get("claimed_by_name")
                or lesion.get("handoff_to_name")
            ),
            "role": (
                evaluation.get("professional_role")
                or evaluation_metadata.get("professional_role")
                or lesion.get("assigned_to_role")
                or lesion.get("claimed_by_role")
                or lesion.get("handoff_to_role")
            ),
            "unit_id": lesion.get("unit_id") or lesion_metadata.get("unit_id") or lesion_metadata.get("unit"),
            "team_id": lesion.get("team_id") or lesion_metadata.get("team_id") or lesion_metadata.get("team"),
        }
        normalized = {key: value for key, value in payload.items() if value not in (None, "", {}, [])}
        return normalized or None

    def _build_encounter_payload(self, evaluation: dict[str, Any], *, lesion: dict[str, Any]) -> dict[str, Any]:
        lesion_metadata = lesion.get("metadata") if isinstance(lesion.get("metadata"), Mapping) else {}
        payload = {
            "id": evaluation.get("encounter_id"),
            "case_id": lesion.get("id") or evaluation.get("case_id"),
            "evaluation_id": evaluation.get("id"),
            "status": evaluation.get("encounter_status") or "finished",
            "class_code": evaluation.get("encounter_class") or "AMB",
            "type_text": lesion.get("title") or "REDISUS wound assessment encounter",
            "service_type_text": "Wound care follow-up",
            "reason_text": (
                evaluation.get("clinical_description")
                or lesion.get("title")
                or evaluation.get("wound_type")
                or lesion.get("wound_type")
            ),
            "period_start": evaluation.get("evaluation_date") or evaluation.get("created_at"),
            "period_end": evaluation.get("updated_at") or evaluation.get("evaluation_date"),
            "wound_type": evaluation.get("wound_type") or lesion.get("wound_type"),
            "wound_location": evaluation.get("wound_location") or lesion.get("location"),
            "unit_id": lesion.get("unit_id") or lesion_metadata.get("unit_id") or lesion_metadata.get("unit"),
            "team_id": lesion.get("team_id") or lesion_metadata.get("team_id") or lesion_metadata.get("team"),
        }
        return {key: value for key, value in payload.items() if value not in (None, "", {}, [])}
