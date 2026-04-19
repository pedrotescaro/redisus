from __future__ import annotations

from typing import Any

from ..mappers import RedisusFHIRMapper


def sample_patient_data() -> dict[str, Any]:
    return {
        "id": "patient-redisus-001",
        "name": "Maria de Souza",
        "birth_date": "1954-08-14",
        "gender": "female",
        "cpf": "12345678901",
        "cns": "700000000000001",
        "phone": "+55-11-99999-0001",
        "address": {
            "line": "Rua das Flores, 100",
            "city": "Sao Paulo",
            "state": "SP",
            "postalCode": "01000-000",
            "country": "BR",
        },
    }


def sample_evaluation_data() -> dict[str, Any]:
    return {
        "id": "evaluation-2026-04-19-001",
        "case_id": "lesion-venous-001",
        "evaluation_date": "2026-04-19T14:30:00-03:00",
        "wound_type": "venous_ulcer",
        "wound_location": "left medial malleolus",
        "clinical_description": "Chronic venous ulcer with moderate exudate and regular borders.",
        "wound_area_cm2": 12.4,
        "depth_mm": 2.5,
        "pain_score": 5,
        "push_score": 11,
        "bwat_score": 27,
        "health_score": 68.5,
        "tissue_composition": {
            "granulation": 62.0,
            "slough": 28.0,
            "necrosis": 10.0,
        },
        "images": [
            {
                "url": "https://storage.googleapis.com/redisus-demo/wounds/patient-001-day-0.jpg",
                "content_type": "image/jpeg",
                "title": "Initial wound photo",
                "captured_at": "2026-04-19T14:31:00-03:00",
            }
        ],
    }


def sample_inference_result() -> dict[str, Any]:
    return {
        "contract_version": "2026-04-07",
        "analysis_type": "wound_assessment",
        "model_version": "redisus-fhir-demo-v1",
        "generated_at": "2026-04-19T14:35:00-03:00",
        "patient_id": "patient-redisus-001",
        "case_id": "lesion-venous-001",
        "evaluation_id": "evaluation-2026-04-19-001",
        "inference": {
            "etiology": "VENOUS_ULCER",
            "etiology_label": "Venous ulcer",
            "confidence": 0.86,
            "tissue_percentages": {
                "granulation": 62.0,
                "slough": 28.0,
                "necrosis": 10.0,
            },
            "wound_area_cm2": 12.4,
            "health_score": 68.5,
            "fallback_used": False,
            "needs_expert_review": False,
            "confidence_level": "high",
            "confidence_entropy": 0.18,
            "confidence_margin": 0.42,
        },
        "interpretation": {
            "summary": "Venous ulcer with predominant granulation tissue and moderate follow-up risk.",
            "risk_level": "moderado",
            "priority": "moderado",
            "follow_up_days": 7,
            "requires_expert_review": False,
            "recommendations": [
                "Keep the wound bed moist and protected according to protocol.",
                "Maintain compression therapy after vascular assessment confirms indication.",
                "Repeat photo capture in 7 days to monitor tissue progression.",
            ],
        },
        "metadata": {
            "source": "clinical_api_pipeline",
            "evaluation_date": "2026-04-19T14:30:00-03:00",
        },
    }


def sample_care_plan_data() -> dict[str, Any]:
    return {
        "id": "careplan-venous-001",
        "title": "Venous ulcer care plan - lesion 001",
        "status": "active",
        "risk_level": "moderado",
        "goals": [
            "Reduce devitalized tissue below 10 percent.",
            "Control edema and pain within two weeks.",
            "Document weekly image-based evolution.",
        ],
        "tasks": [
            {
                "title": "Dressing change",
                "description": "Perform protocol-based dressing change.",
                "instructions": "Clean with saline, inspect the wound bed, and apply primary and secondary coverings.",
                "frequency": "twice_weekly",
                "materials": ["saline", "primary dressing", "secondary dressing"],
                "precautions": ["watch for infection", "avoid trauma during exchange"],
            },
            {
                "title": "Compression therapy",
                "description": "Maintain compression after vascular check.",
                "instructions": "Use compression bandaging or elastic stocking as prescribed.",
                "frequency": "daily",
            },
            {
                "title": "Clinical review",
                "description": "Return for reassessment and new photo capture.",
                "frequency": "weekly",
            },
        ],
        "alerts": [
            {
                "type": "follow_up_due",
                "severity": "moderado",
                "reason": "Weekly reassessment required",
            }
        ],
        "metadata": {
            "summary": "Care plan generated from REDISUS wound assessment for venous ulcer follow-up.",
        },
        "created_at": "2026-04-19T14:35:00-03:00",
        "review_due_date": "2026-04-26",
    }


def build_example_artifacts() -> dict[str, Any]:
    mapper = RedisusFHIRMapper(strict_validation=False)
    patient_data = sample_patient_data()
    evaluation_data = sample_evaluation_data()
    inference_result = sample_inference_result()
    care_plan_data = sample_care_plan_data()

    patient = mapper.map_patient(patient_data)
    observation = mapper.map_observation(
        patient["id"],
        evaluation_data=evaluation_data,
        inference_result=inference_result,
    )
    condition = mapper.map_condition(
        patient["id"],
        evaluation_data=evaluation_data,
        inference_result=inference_result,
    )
    diagnostic_report = mapper.map_diagnostic_report(
        patient["id"],
        observation=observation,
        condition=condition,
        evaluation_data=evaluation_data,
        inference_result=inference_result,
    )
    care_plan = mapper.map_care_plan(patient["id"], care_plan_data, condition=condition)
    bundle = mapper.map_case_to_bundle(
        patient_data=patient_data,
        evaluation_data=evaluation_data,
        inference_result=inference_result,
        care_plan_data=care_plan_data,
        bundle_type="collection",
    )
    return {
        "patient": patient,
        "observation": observation,
        "condition": condition,
        "diagnostic_report": diagnostic_report,
        "care_plan": care_plan,
        "bundle": bundle,
    }
