from __future__ import annotations

from typing import Any, Mapping

from src.interoperability.fhir_r4.client import SimpleFHIRHttpClient
from src.interoperability.fhir_r4.mappers import (
    TISSUE_COMPONENT_CODES,
    WOUND_ICD10_CODES,
    WOUND_SNOMED_CODES,
    RedisusFHIRMapper,
)
from src.interoperability.fhir_r4.models import LOINC_SYSTEM, REDISUS_CODE_SYSTEM, build_reference, fhir_now, generate_id


class FHIRResourceBuilder:
    FHIR_VERSION = "4.0.1"
    SYSTEM_URL = "https://heal.redisus.org.br"
    SNOMED_SYSTEM = "http://snomed.info/sct"
    LOINC_SYSTEM = "http://loinc.org"
    ICD10_SYSTEM = "http://hl7.org/fhir/sid/icd-10"

    WOUND_SNOMED_CODES = WOUND_SNOMED_CODES
    WOUND_ICD10_CODES = WOUND_ICD10_CODES
    TISSUE_LOINC_CODES = {
        "GRANULATION": TISSUE_COMPONENT_CODES["granulation"],
        "SLOUGH": TISSUE_COMPONENT_CODES["slough"],
        "NECROSIS": TISSUE_COMPONENT_CODES["necrosis"],
    }

    def __init__(self, server_url: str = "https://hapi.fhir.org/baseR4", *, strict_validation: bool = False):
        self.server_url = server_url
        self.mapper = RedisusFHIRMapper(strict_validation=strict_validation)

    def build_patient(
        self,
        patient_id: str,
        name: str,
        birth_date: str | None = None,
        gender: str = "unknown",
        cpf: str | None = None,
        cns: str | None = None,
        address: Mapping[str, Any] | None = None,
        phone: str | None = None,
    ) -> dict[str, Any]:
        return self.mapper.map_patient(
            {
                "id": patient_id,
                "name": name,
                "birth_date": birth_date,
                "gender": gender,
                "cpf": cpf,
                "cns": cns,
                "address": dict(address or {}),
                "phone": phone,
            }
        )

    def build_wound_observation(
        self,
        patient_id: str,
        wound_data: Mapping[str, Any],
        practitioner_id: str | None = None,
    ) -> dict[str, Any]:
        evaluation = {
            "id": str(wound_data.get("id") or generate_id("observation")),
            "evaluation_date": wound_data.get("evaluation_date") or fhir_now(),
            "wound_location": wound_data.get("body_site") or wound_data.get("wound_location"),
            "wound_area_cm2": wound_data.get("area_cm2") or wound_data.get("wound_area_cm2"),
            "depth_mm": wound_data.get("depth_mm"),
            "pain_score": wound_data.get("pain_score"),
            "push_score": wound_data.get("push_score"),
            "bwat_score": wound_data.get("bwat_score"),
            "health_score": wound_data.get("health_score"),
            "tissue_composition": wound_data.get("tissue_percentages") or wound_data.get("tissue_composition") or {},
        }
        inference_result = {
            "generated_at": wound_data.get("generated_at") or fhir_now(),
            "inference": {
                "etiology": wound_data.get("etiology"),
                "confidence": wound_data.get("confidence"),
                "tissue_percentages": wound_data.get("tissue_percentages") or {},
                "wound_area_cm2": wound_data.get("area_cm2") or wound_data.get("wound_area_cm2"),
                "health_score": wound_data.get("health_score"),
            },
            "interpretation": {
                "summary": wound_data.get("conclusion") or wound_data.get("summary"),
                "risk_level": wound_data.get("risk_level"),
            },
        }
        return self.mapper.map_observation(
            patient_id,
            evaluation_data=evaluation,
            inference_result=inference_result,
            practitioner_id=practitioner_id,
        )

    def build_wound_condition(
        self,
        patient_id: str,
        etiology: str,
        confidence: float,
        body_site: str | None = None,
        onset_date: str | None = None,
        risk_level: str | None = None,
    ) -> dict[str, Any]:
        evaluation = {
            "case_id": generate_id("condition"),
            "evaluation_date": onset_date or fhir_now(),
            "wound_location": body_site,
            "wound_type": etiology,
        }
        inference_result = {
            "generated_at": fhir_now(),
            "inference": {
                "etiology": etiology,
                "confidence": confidence,
            },
            "interpretation": {
                "risk_level": risk_level,
            },
        }
        return self.mapper.map_condition(
            patient_id,
            evaluation_data=evaluation,
            inference_result=inference_result,
        )

    def build_diagnostic_report(
        self,
        patient_id: str,
        observation_ids: list[str],
        condition_id: str | None = None,
        conclusion: str = "",
        practitioner_id: str | None = None,
    ) -> dict[str, Any]:
        condition = None
        if condition_id:
            condition = {
                "id": condition_id,
                "code": {
                    "coding": [
                        {
                            "system": f"{REDISUS_CODE_SYSTEM}/condition-id",
                            "code": condition_id,
                            "display": "REDISUS wound condition",
                        }
                    ],
                    "text": condition_id,
                },
            }
        observation = {
            "id": observation_ids[0] if observation_ids else generate_id("observation"),
            "resourceType": "Observation",
        }
        return self.mapper.map_diagnostic_report(
            patient_id,
            observation=observation,
            condition=condition,
            inference_result={
                "generated_at": fhir_now(),
                "interpretation": {
                    "summary": conclusion,
                },
            },
            practitioner_id=practitioner_id,
        )

    def build_care_plan(
        self,
        patient_id: str,
        title: str,
        activities: list[Mapping[str, str]],
        condition_id: str | None = None,
        period_start: str | None = None,
        period_end: str | None = None,
    ) -> dict[str, Any]:
        condition = {"id": condition_id} if condition_id else None
        care_plan_data = {
            "id": generate_id("careplan"),
            "title": title,
            "status": "active",
            "tasks": [dict(activity) for activity in activities],
            "created_at": period_start or fhir_now(),
            "review_due_date": period_end,
        }
        return self.mapper.map_care_plan(patient_id, care_plan_data, condition=condition)

    def build_transaction_bundle(self, resources: list[Mapping[str, Any]]) -> dict[str, Any]:
        return self.mapper.build_transaction_bundle([dict(resource) for resource in resources])

    def export_analysis_as_fhir(
        self,
        patient_data: Mapping[str, Any],
        wound_data: Mapping[str, Any],
        treatment_data: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        evaluation = {
            "id": str(wound_data.get("id") or generate_id("evaluation")),
            "case_id": str(wound_data.get("case_id") or generate_id("lesion")),
            "evaluation_date": wound_data.get("evaluation_date") or fhir_now(),
            "professional_name": wound_data.get("professional_name") or wound_data.get("practitioner_name"),
            "professional_role": wound_data.get("professional_role"),
            "encounter_id": wound_data.get("encounter_id"),
            "wound_type": wound_data.get("etiology"),
            "wound_location": wound_data.get("body_site") or wound_data.get("wound_location"),
            "wound_area_cm2": wound_data.get("wound_area_cm2") or wound_data.get("area_cm2"),
            "depth_mm": wound_data.get("depth_mm"),
            "pain_score": wound_data.get("pain_score"),
            "push_score": wound_data.get("push_score"),
            "bwat_score": wound_data.get("bwat_score"),
            "health_score": wound_data.get("health_score"),
            "tissue_composition": wound_data.get("tissue_percentages") or {},
            "images": wound_data.get("images") or ([{"image_path": wound_data.get("image_path")}] if wound_data.get("image_path") else []),
        }
        inference_result = {
            "generated_at": wound_data.get("generated_at") or fhir_now(),
            "inference": {
                "etiology": wound_data.get("etiology"),
                "confidence": wound_data.get("confidence"),
                "tissue_percentages": wound_data.get("tissue_percentages") or {},
                "wound_area_cm2": wound_data.get("wound_area_cm2") or wound_data.get("area_cm2"),
                "health_score": wound_data.get("health_score"),
                "needs_expert_review": wound_data.get("needs_expert_review"),
                "confidence_level": wound_data.get("confidence_level"),
            },
            "interpretation": {
                "summary": wound_data.get("conclusion") or wound_data.get("summary"),
                "risk_level": wound_data.get("risk_level"),
                "recommendations": wound_data.get("recommendations"),
                "follow_up_days": wound_data.get("days_until_next"),
            },
        }
        care_plan_data = None
        if treatment_data:
            steps = treatment_data.get("steps") if isinstance(treatment_data.get("steps"), list) else []
            care_plan_data = {
                "id": str(treatment_data.get("id") or generate_id("careplan")),
                "title": str(treatment_data.get("title") or "REDISUS wound care plan"),
                "status": "active",
                "tasks": [{"description": str(step), "frequency": "as_prescribed"} for step in steps],
                "created_at": fhir_now(),
            }

        return self.mapper.map_case_to_bundle(
            patient_data=dict(patient_data),
            evaluation_data=evaluation,
            inference_result=inference_result,
            care_plan_data=care_plan_data,
            images=evaluation.get("images"),
            bundle_type="transaction",
        )


class FHIRClient(SimpleFHIRHttpClient):
    def __init__(self, server_url: str = "https://hapi.fhir.org/baseR4", *, strict_validation: bool = False):
        super().__init__(server_url, strict_validation=strict_validation)
        self.builder = FHIRResourceBuilder(server_url=server_url, strict_validation=strict_validation)

    def get_patient(self, patient_id: str) -> dict[str, Any] | None:
        return self.read("Patient", patient_id)

    def search_patients(self, name: str | None = None, identifier: str | None = None) -> list[dict[str, Any]]:
        bundle = self.search("Patient", params={"name": name, "identifier": identifier})
        return [entry.get("resource", {}) for entry in bundle.get("entry", [])]
