from __future__ import annotations

from typing import Any

from .models import (
    ICD10_SYSTEM,
    LOINC_SYSTEM,
    MEDIA_CATEGORY_SYSTEM,
    PRACTITIONER_ROLE_SYSTEM,
    PROVENANCE_PARTICIPANT_TYPE_SYSTEM,
    REDISUS_CODE_SYSTEM,
    REDISUS_STRUCTURE_DEFINITION,
    REDISUS_VALUE_SET,
    SNOMED_SYSTEM,
    build_codeable_concept,
    build_coding,
)

TARGET_PROFILE_REGISTRY = {
    "patient": "http://www.saude.gov.br/fhir/r4/StructureDefinition/BRIndividuo-1.0",
    "bundle-export": f"{REDISUS_STRUCTURE_DEFINITION}/redisus-wound-case-bundle",
    "organization": f"{REDISUS_STRUCTURE_DEFINITION}/redisus-organization",
    "practitioner": f"{REDISUS_STRUCTURE_DEFINITION}/redisus-practitioner",
    "practitioner-role": f"{REDISUS_STRUCTURE_DEFINITION}/redisus-practitioner-role",
    "encounter": f"{REDISUS_STRUCTURE_DEFINITION}/redisus-encounter",
    "observation": f"{REDISUS_STRUCTURE_DEFINITION}/redisus-wound-observation",
    "condition": f"{REDISUS_STRUCTURE_DEFINITION}/redisus-wound-condition",
    "diagnostic-report": f"{REDISUS_STRUCTURE_DEFINITION}/redisus-wound-diagnostic-report",
    "care-plan": f"{REDISUS_STRUCTURE_DEFINITION}/redisus-wound-care-plan",
    "media": f"{REDISUS_STRUCTURE_DEFINITION}/redisus-wound-media",
    "provenance": f"{REDISUS_STRUCTURE_DEFINITION}/redisus-provenance",
}

TARGET_VALUE_SET_REGISTRY = {
    "clinical-role": f"{REDISUS_VALUE_SET}/clinical-role",
    "organization-type": f"{REDISUS_VALUE_SET}/organization-type",
    "encounter-type": f"{REDISUS_VALUE_SET}/encounter-type",
    "service-type": f"{REDISUS_VALUE_SET}/service-type",
    "wound-classification": f"{REDISUS_VALUE_SET}/wound-classification",
    "clinical-score": f"{REDISUS_VALUE_SET}/clinical-score",
    "risk-level": f"{REDISUS_VALUE_SET}/risk-level",
    "media-category": f"{REDISUS_VALUE_SET}/media-category",
    "provenance-agent-type": f"{REDISUS_VALUE_SET}/provenance-agent-type",
}

CLINICAL_ROLE_CONCEPTS = {
    "doctor": {
        "display": "Doctor",
        "standard": build_coding(PRACTITIONER_ROLE_SYSTEM, "doctor", "Doctor"),
    },
    "nurse": {
        "display": "Nurse",
        "standard": build_coding(PRACTITIONER_ROLE_SYSTEM, "nurse", "Nurse"),
    },
    "researcher": {
        "display": "Researcher",
        "standard": build_coding(PRACTITIONER_ROLE_SYSTEM, "researcher", "Researcher"),
    },
    "clinician": {
        "display": "Clinician",
        "standard": None,
    },
    "estomaterapeuta": {
        "display": "Stomatherapy specialist",
        "standard": None,
    },
}

WOUND_CLASSIFICATION_CONCEPTS = {
    "venous_ulcer": {
        "display": "Venous ulcer",
        "standard": [
            build_coding(SNOMED_SYSTEM, "404684003", "Venous leg ulcer"),
            build_coding(ICD10_SYSTEM, "I83.0", "Varicose veins of lower extremities with ulcer"),
        ],
    },
    "arterial_ulcer": {
        "display": "Arterial ulcer",
        "standard": [
            build_coding(SNOMED_SYSTEM, "238792006", "Arterial ulcer"),
            build_coding(ICD10_SYSTEM, "I70.2", "Atherosclerosis of arteries of extremities"),
        ],
    },
    "diabetic_foot": {
        "display": "Diabetic foot ulcer",
        "standard": [
            build_coding(SNOMED_SYSTEM, "280137006", "Diabetic foot ulcer"),
            build_coding(ICD10_SYSTEM, "E11.621", "Type 2 diabetes mellitus with foot ulcer"),
        ],
    },
    "pressure_injury": {
        "display": "Pressure injury",
        "standard": [
            build_coding(SNOMED_SYSTEM, "399912005", "Pressure ulcer"),
            build_coding(ICD10_SYSTEM, "L89", "Pressure ulcer"),
        ],
    },
    "surgical_wound": {
        "display": "Surgical wound",
        "standard": [
            build_coding(SNOMED_SYSTEM, "225552003", "Surgical wound"),
            build_coding(ICD10_SYSTEM, "T81.4", "Infection following a procedure"),
        ],
    },
}

CLINICAL_SCORE_CONCEPTS = {
    "pain-score": {"display": "Pain score"},
    "push-score": {"display": "PUSH score"},
    "bwat-score": {"display": "BWAT score"},
    "wound-health-score": {"display": "REDISUS wound health score"},
    "ai-confidence": {"display": "AI confidence"},
    "risk-level": {"display": "REDISUS risk level"},
    "wound-area": {
        "display": "Wound area",
        "standard": build_coding(LOINC_SYSTEM, "89260-9", "Wound area"),
    },
    "granulation": {
        "display": "Wound bed granulation tissue percentage",
        "standard": build_coding(LOINC_SYSTEM, "72514-3", "Wound bed granulation tissue percentage"),
    },
    "slough": {
        "display": "Wound bed slough percentage",
        "standard": build_coding(LOINC_SYSTEM, "72287-6", "Wound bed slough percentage"),
    },
    "necrosis": {
        "display": "Wound bed necrotic tissue percentage",
        "standard": build_coding(LOINC_SYSTEM, "72288-4", "Wound bed necrotic tissue percentage"),
    },
}

ORGANIZATION_TYPE_CONCEPTS = {
    "health-unit": "Health unit",
    "care-team": "Care team",
    "ai-system": "AI clinical system",
}

ENCOUNTER_TYPE_CONCEPTS = {
    "wound-evaluation": "Wound evaluation encounter",
}

SERVICE_TYPE_CONCEPTS = {
    "wound-care-follow-up": "Wound care follow-up",
}

MEDIA_CATEGORY_CONCEPTS = {
    "image": build_coding(MEDIA_CATEGORY_SYSTEM, "image", "Image"),
    "video": build_coding(MEDIA_CATEGORY_SYSTEM, "video", "Video"),
    "audio": build_coding(MEDIA_CATEGORY_SYSTEM, "audio", "Audio"),
}

PROVENANCE_AGENT_TYPE_CONCEPTS = {
    "author": build_coding(PROVENANCE_PARTICIPANT_TYPE_SYSTEM, "author", "Author"),
    "assembler": build_coding(PROVENANCE_PARTICIPANT_TYPE_SYSTEM, "assembler", "Assembler"),
    "performer": build_coding(PROVENANCE_PARTICIPANT_TYPE_SYSTEM, "performer", "Performer"),
}

RISK_LEVEL_CONCEPTS = {
    "baixo": "Low risk",
    "moderado": "Moderate risk",
    "alto": "High risk",
    "critico": "Critical risk",
}

MEDIA_TYPE_CODES = {
    "image": "photo",
    "video": "video",
    "audio": "audio",
}


def build_target_codeable_concept(
    *,
    local_namespace: str,
    local_code: str,
    text: str,
    standard_coding: dict[str, Any] | None = None,
) -> dict[str, Any]:
    local_coding = build_coding(f"{REDISUS_CODE_SYSTEM}/{local_namespace}", local_code, text)
    if standard_coding:
        return build_codeable_concept(standard_coding, local_coding, text=text)
    return build_codeable_concept(local_coding, text=text)


def practitioner_role_concept(role: str) -> dict[str, Any]:
    normalized = str(role or "").strip().lower()
    concept = CLINICAL_ROLE_CONCEPTS.get(normalized)
    display = concept["display"] if concept else (normalized.replace("-", " ").replace("_", " ").title() or "Clinician")
    return build_target_codeable_concept(
        local_namespace="clinical-role",
        local_code=normalized or "clinician",
        text=display,
        standard_coding=(concept or {}).get("standard"),
    )


def organization_type_concept(kind: str) -> dict[str, Any]:
    normalized = str(kind or "").strip().lower()
    display = ORGANIZATION_TYPE_CONCEPTS.get(normalized, normalized.replace("-", " ").title() or "Organization")
    return build_target_codeable_concept(
        local_namespace="organization-type",
        local_code=normalized or "organization",
        text=display,
    )


def encounter_type_concept(code: str) -> dict[str, Any]:
    normalized = str(code or "").strip().lower()
    display = ENCOUNTER_TYPE_CONCEPTS.get(normalized, normalized.replace("-", " ").title() or "Encounter")
    return build_target_codeable_concept(
        local_namespace="encounter-type",
        local_code=normalized or "encounter",
        text=display,
    )


def service_type_concept(code: str) -> dict[str, Any]:
    normalized = str(code or "").strip().lower()
    display = SERVICE_TYPE_CONCEPTS.get(normalized, normalized.replace("-", " ").title() or "Service")
    return build_target_codeable_concept(
        local_namespace="service-type",
        local_code=normalized or "service",
        text=display,
    )


def media_category_concept(code: str) -> dict[str, Any]:
    normalized = str(code or "").strip().lower()
    standard = MEDIA_CATEGORY_CONCEPTS.get(normalized)
    display = (standard or {}).get("display") or normalized.replace("-", " ").title() or "Image"
    return build_target_codeable_concept(
        local_namespace="media-category",
        local_code=normalized or "image",
        text=display,
        standard_coding=standard,
    )


def media_type_code(code: str) -> str:
    normalized = str(code or "").strip().lower()
    return MEDIA_TYPE_CODES.get(normalized, "photo")


def provenance_agent_type_concept(code: str) -> dict[str, Any]:
    normalized = str(code or "").strip().lower()
    standard = PROVENANCE_AGENT_TYPE_CONCEPTS.get(normalized)
    display = (standard or {}).get("display") or normalized.replace("-", " ").title() or "Author"
    return build_target_codeable_concept(
        local_namespace="provenance-agent-type",
        local_code=normalized or "author",
        text=display,
        standard_coding=standard,
    )


def clinical_score_concept(code: str, display: str | None = None) -> dict[str, Any]:
    normalized = str(code or "").strip().lower()
    concept = CLINICAL_SCORE_CONCEPTS.get(normalized, {})
    resolved_display = concept.get("display") or display or normalized.replace("-", " ").title() or "Clinical score"
    return build_target_codeable_concept(
        local_namespace="clinical-score",
        local_code=normalized or "clinical-score",
        text=resolved_display,
        standard_coding=concept.get("standard"),
    )


def wound_classification_concept(code: str) -> dict[str, Any]:
    normalized = str(code or "").strip().lower()
    concept = WOUND_CLASSIFICATION_CONCEPTS.get(normalized, {})
    resolved_display = concept.get("display") or normalized.replace("_", " ").replace("-", " ").title() or "Wound"
    return build_target_codeable_concept(
        local_namespace="wound-classification",
        local_code=normalized or "unspecified-wound",
        text=resolved_display,
        standard_coding=None,
    ) | {
        "coding": [
            *(concept.get("standard") or []),
            build_coding(f"{REDISUS_CODE_SYSTEM}/wound-classification", normalized or "unspecified-wound", resolved_display),
        ],
        "text": resolved_display,
    }


def encounter_reason_concept(code: str, text: str) -> dict[str, Any]:
    normalized = str(code or "").strip().lower()
    return build_target_codeable_concept(
        local_namespace="encounter-reason",
        local_code=normalized or "wound-assessment",
        text=text or "Clinical wound assessment",
    )


def risk_level_concept(code: str) -> dict[str, Any]:
    normalized = str(code or "").strip().lower()
    display = RISK_LEVEL_CONCEPTS.get(normalized, normalized.replace("-", " ").title() or "Risk")
    return build_target_codeable_concept(
        local_namespace="risk-level",
        local_code=normalized or "moderado",
        text=display,
    )
