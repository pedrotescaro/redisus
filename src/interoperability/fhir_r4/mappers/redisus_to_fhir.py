from __future__ import annotations

import base64
import mimetypes
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from ..models import (
    ICD10_SYSTEM,
    LOINC_SYSTEM,
    REDISUS_CODE_SYSTEM,
    REDISUS_STRUCTURE_DEFINITION,
    SNOMED_SYSTEM,
    UCUM_SYSTEM,
    CarePlanResource,
    ConditionResource,
    DiagnosticReportResource,
    EncounterResource,
    ObservationResource,
    PatientResource,
    PractitionerResource,
    build_identifier,
    build_reference,
    compact_dict,
    fhir_now,
    generate_id,
)
from ..validators import validate_bundle, validate_resource

WOUND_SNOMED_CODES = {
    "VENOUS_ULCER": {"code": "404684003", "display": "Venous leg ulcer"},
    "ARTERIAL_ULCER": {"code": "238792006", "display": "Arterial ulcer"},
    "DIABETIC_FOOT": {"code": "280137006", "display": "Diabetic foot ulcer"},
    "PRESSURE_INJURY": {"code": "399912005", "display": "Pressure ulcer"},
    "SURGICAL_WOUND": {"code": "225552003", "display": "Surgical wound"},
}

WOUND_ICD10_CODES = {
    "VENOUS_ULCER": {"code": "I83.0", "display": "Varicose veins of lower extremities with ulcer"},
    "ARTERIAL_ULCER": {"code": "I70.2", "display": "Atherosclerosis of arteries of extremities"},
    "DIABETIC_FOOT": {"code": "E11.621", "display": "Type 2 diabetes mellitus with foot ulcer"},
    "PRESSURE_INJURY": {"code": "L89", "display": "Pressure ulcer"},
    "SURGICAL_WOUND": {"code": "T81.4", "display": "Infection following a procedure"},
}

TISSUE_COMPONENT_CODES = {
    "granulation": {"system": LOINC_SYSTEM, "code": "72514-3", "display": "Wound bed granulation tissue percentage"},
    "slough": {"system": LOINC_SYSTEM, "code": "72287-6", "display": "Wound bed slough percentage"},
    "necrosis": {"system": LOINC_SYSTEM, "code": "72288-4", "display": "Wound bed necrotic tissue percentage"},
}

RISK_SEVERITY_CODES = {
    "baixo": {"system": SNOMED_SYSTEM, "code": "255604002", "display": "Mild"},
    "moderado": {"system": SNOMED_SYSTEM, "code": "6736007", "display": "Moderate"},
    "alto": {"system": SNOMED_SYSTEM, "code": "24484000", "display": "Severe"},
    "critico": {"system": SNOMED_SYSTEM, "code": "442452003", "display": "Life threatening severity"},
}

RISK_INTERPRETATION_CODES = {
    "baixo": {"system": f"{REDISUS_CODE_SYSTEM}/risk-level", "code": "baixo", "display": "Low risk"},
    "moderado": {"system": f"{REDISUS_CODE_SYSTEM}/risk-level", "code": "moderado", "display": "Moderate risk"},
    "alto": {"system": f"{REDISUS_CODE_SYSTEM}/risk-level", "code": "alto", "display": "High risk"},
    "critico": {"system": f"{REDISUS_CODE_SYSTEM}/risk-level", "code": "critico", "display": "Critical risk"},
}

ENCOUNTER_CLASS_CODES = {
    "AMB": {
        "system": "http://terminology.hl7.org/CodeSystem/v3-ActCode",
        "code": "AMB",
        "display": "ambulatory",
    },
    "AMBULATORY": {
        "system": "http://terminology.hl7.org/CodeSystem/v3-ActCode",
        "code": "AMB",
        "display": "ambulatory",
    },
    "OUTPATIENT": {
        "system": "http://terminology.hl7.org/CodeSystem/v3-ActCode",
        "code": "AMB",
        "display": "ambulatory",
    },
    "EMER": {
        "system": "http://terminology.hl7.org/CodeSystem/v3-ActCode",
        "code": "EMER",
        "display": "emergency",
    },
    "EMERGENCY": {
        "system": "http://terminology.hl7.org/CodeSystem/v3-ActCode",
        "code": "EMER",
        "display": "emergency",
    },
    "IMP": {
        "system": "http://terminology.hl7.org/CodeSystem/v3-ActCode",
        "code": "IMP",
        "display": "inpatient encounter",
    },
    "INPATIENT": {
        "system": "http://terminology.hl7.org/CodeSystem/v3-ActCode",
        "code": "IMP",
        "display": "inpatient encounter",
    },
    "VR": {
        "system": "http://terminology.hl7.org/CodeSystem/v3-ActCode",
        "code": "VR",
        "display": "virtual",
    },
    "VIRTUAL": {
        "system": "http://terminology.hl7.org/CodeSystem/v3-ActCode",
        "code": "VR",
        "display": "virtual",
    },
}

TISSUE_ALIASES = {
    "granulation": "granulation",
    "granulacao": "granulation",
    "tecido_de_granulacao": "granulation",
    "slough": "slough",
    "esfacelo": "slough",
    "fibrina": "slough",
    "slough_fibrin": "slough",
    "necrosis": "necrosis",
    "necrose": "necrosis",
    "coagulation_necrosis_eschar": "necrosis",
}

ETIOLOGY_ALIASES = {
    "venous_ulcer": "VENOUS_ULCER",
    "ulcera_venosa": "VENOUS_ULCER",
    "arterial_ulcer": "ARTERIAL_ULCER",
    "ulcera_arterial": "ARTERIAL_ULCER",
    "diabetic_foot": "DIABETIC_FOOT",
    "pe_diabetico": "DIABETIC_FOOT",
    "pressure_injury": "PRESSURE_INJURY",
    "lesao_pressao": "PRESSURE_INJURY",
    "surgical_wound": "SURGICAL_WOUND",
    "ferida_cirurgica": "SURGICAL_WOUND",
}


def _slugify(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode("ascii")
    chars: list[str] = []
    last_separator = False
    for char in text.lower():
        if char.isalnum():
            chars.append(char)
            last_separator = False
            continue
        if not last_separator:
            chars.append("_")
            last_separator = True
    return "".join(chars).strip("_")


def _resource_slug(value: Any) -> str:
    return _slugify(value).replace("_", "-")


def _stable_resource_id(prefix: str, *values: Any) -> str:
    normalized_prefix = _resource_slug(prefix) or prefix
    max_length = max(1, 64 - len(normalized_prefix) - 1)
    for value in values:
        slug = _resource_slug(value)
        if slug:
            if slug.startswith(f"{normalized_prefix}-"):
                return slug[:64]
            return f"{normalized_prefix}-{slug[:max_length]}"
    return generate_id(normalized_prefix)


def _safe_float(value: Any, default: float | None = None) -> float | None:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _ensure_datetime(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return fhir_now()
    if "T" in text:
        return text
    return f"{text}T00:00:00"


def _normalize_gender(value: Any) -> str:
    mapping = {
        "m": "male",
        "male": "male",
        "masculino": "male",
        "f": "female",
        "female": "female",
        "feminino": "female",
        "other": "other",
        "outro": "other",
        "unknown": "unknown",
        "desconhecido": "unknown",
    }
    return mapping.get(_slugify(value), "unknown")


def _normalize_risk(value: Any) -> str:
    mapping = {
        "low": "baixo",
        "baixo": "baixo",
        "medium": "moderado",
        "moderate": "moderado",
        "moderado": "moderado",
        "high": "alto",
        "alto": "alto",
        "critical": "critico",
        "critico": "critico",
    }
    return mapping.get(_slugify(value), "moderado")


def _normalize_etiology(value: Any) -> str:
    slug = _slugify(value)
    if not slug:
        return "UNSPECIFIED_WOUND"
    return ETIOLOGY_ALIASES.get(slug, slug.upper())


def _extract_tissue_percentages(*sources: Mapping[str, Any] | None) -> dict[str, float]:
    normalized = {"granulation": 0.0, "slough": 0.0, "necrosis": 0.0}
    for source in sources:
        if not isinstance(source, Mapping):
            continue
        tissue_candidates = [
            source.get("tissue_percentages"),
            source.get("tissue_composition"),
            (source.get("segmentation") or {}).get("tissue_percentages"),
            (source.get("inference") or {}).get("tissue_percentages"),
        ]
        for candidate in tissue_candidates:
            if not isinstance(candidate, Mapping):
                continue
            for raw_key, raw_value in candidate.items():
                key = TISSUE_ALIASES.get(_slugify(raw_key))
                if not key:
                    continue
                normalized[key] = round(_safe_float(raw_value, 0.0) or 0.0, 2)
    return normalized


def _extract_images(*sources: Mapping[str, Any] | None, explicit_images: list[Any] | None = None) -> list[Any]:
    images: list[Any] = list(explicit_images or [])
    for source in sources:
        if not isinstance(source, Mapping):
            continue
        candidate = source.get("images")
        if isinstance(candidate, list):
            images.extend(candidate)
        image_path = source.get("image_path")
        if image_path:
            images.append({"image_path": image_path})
    return images


def _split_human_name(name: str) -> tuple[str, list[str]]:
    parts = [part for part in str(name or "").strip().split() if part]
    if not parts:
        return "Paciente", ["Paciente"]
    if len(parts) == 1:
        return parts[0], [parts[0]]
    return parts[-1], parts[:-1]


def _attachment_from_image(image: Any) -> dict[str, Any] | None:
    if isinstance(image, Mapping):
        payload = dict(image)
    else:
        payload = {"image_path": image}

    content_type = str(payload.get("content_type") or payload.get("mime_type") or "").strip()
    title = str(payload.get("title") or payload.get("name") or "").strip()
    creation = str(payload.get("captured_at") or payload.get("created_at") or payload.get("date") or fhir_now())

    if payload.get("data"):
        return compact_dict(
            {
                "contentType": content_type or "image/jpeg",
                "data": payload.get("data"),
                "title": title or "Clinical wound image",
                "creation": creation,
            }
        )

    image_url = str(payload.get("url") or payload.get("image_url") or payload.get("storage_url") or "").strip()
    if image_url:
        guessed = content_type or mimetypes.guess_type(image_url)[0] or "image/jpeg"
        return compact_dict(
            {
                "contentType": guessed,
                "url": image_url,
                "title": title or Path(image_url).name or "Clinical wound image",
                "creation": creation,
            }
        )

    image_path = str(payload.get("image_path") or payload.get("path") or "").strip()
    if image_path:
        path = Path(image_path)
        if path.exists():
            guessed = content_type or mimetypes.guess_type(path.name)[0] or "image/jpeg"
            return compact_dict(
                {
                    "contentType": guessed,
                    "data": base64.b64encode(path.read_bytes()).decode("ascii"),
                    "title": title or path.name,
                    "creation": creation,
                }
            )
    return None


def _build_quantity_component(code: dict[str, Any], value: float, unit: str, code_value: str) -> dict[str, Any]:
    return {
        "code": {"coding": [code], "text": code.get("display")},
        "valueQuantity": {
            "value": round(value, 2),
            "unit": unit,
            "system": UCUM_SYSTEM,
            "code": code_value,
        },
    }


def _build_score_component(code: str, display: str, value: float) -> dict[str, Any]:
    return {
        "code": {
            "coding": [
                {
                    "system": f"{REDISUS_CODE_SYSTEM}/clinical-score",
                    "code": code,
                    "display": display,
                }
            ],
            "text": display,
        },
        "valueQuantity": {
            "value": round(value, 2),
            "unit": "score",
        },
    }


def _build_note(*texts: Any) -> list[dict[str, str]]:
    notes: list[dict[str, str]] = []
    for text in texts:
        value = str(text or "").strip()
        if value:
            notes.append({"text": value})
    return notes


@dataclass(slots=True)
class RedisusFHIRMapper:
    strict_validation: bool = False

    def map_patient(self, patient_data: Mapping[str, Any]) -> dict[str, Any]:
        patient_id = str(patient_data.get("id") or patient_data.get("patient_id") or generate_id("patient"))
        full_name = str(patient_data.get("name") or patient_data.get("full_name") or "Paciente REDISUS")
        family, given = _split_human_name(full_name)

        identifiers: list[dict[str, Any]] = [
            build_identifier(f"{REDISUS_CODE_SYSTEM}/patient-id", patient_id),
        ]
        cpf = str(patient_data.get("cpf") or "").strip()
        cns = str(patient_data.get("cns") or patient_data.get("cns_number") or "").strip()
        if cpf:
            identifiers.append(build_identifier("https://saude.gov.br/fhir/r4/NamingSystem/cpf", cpf))
        if cns:
            identifiers.append(build_identifier("https://saude.gov.br/fhir/r4/NamingSystem/cns", cns))

        telecom: list[dict[str, Any]] = []
        phone = str(patient_data.get("phone") or patient_data.get("telefone") or "").strip()
        email = str(patient_data.get("email") or "").strip()
        if phone:
            telecom.append({"system": "phone", "value": phone, "use": "mobile"})
        if email:
            telecom.append({"system": "email", "value": email, "use": "home"})

        address_data = patient_data.get("address") if isinstance(patient_data.get("address"), Mapping) else {}
        address: list[dict[str, Any]] = []
        if address_data:
            address.append(
                compact_dict(
                    {
                        "use": "home",
                        "type": "physical",
                        "line": [str(address_data.get("line") or "")] if address_data.get("line") else [],
                        "city": address_data.get("city"),
                        "state": address_data.get("state"),
                        "postalCode": address_data.get("postalCode"),
                        "country": address_data.get("country") or "BR",
                    }
                )
            )

        resource = PatientResource(
            id=patient_id,
            identifier=identifiers,
            name=[
                {
                    "use": "official",
                    "family": family,
                    "given": given,
                    "text": full_name,
                }
            ],
            gender=_normalize_gender(patient_data.get("gender")),
            birth_date=str(patient_data.get("birth_date") or patient_data.get("birthDate") or "").strip() or None,
            telecom=telecom,
            address=address,
        ).to_dict()
        self._validate_resource(resource)
        return resource

    def map_practitioner(
        self,
        practitioner_data: Mapping[str, Any] | None = None,
        *,
        evaluation_data: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload = dict(practitioner_data or {})
        evaluation_payload = dict(evaluation_data or {})
        payload_metadata = payload.get("metadata") if isinstance(payload.get("metadata"), Mapping) else {}
        evaluation_metadata = (
            evaluation_payload.get("metadata") if isinstance(evaluation_payload.get("metadata"), Mapping) else {}
        )

        practitioner_uid = (
            payload.get("id")
            or payload.get("practitioner_id")
            or payload.get("professional_id")
            or payload.get("uid")
            or payload.get("user_id")
            or payload_metadata.get("practitioner_id")
            or payload_metadata.get("professional_id")
            or evaluation_payload.get("practitioner_id")
            or evaluation_payload.get("professional_id")
            or evaluation_metadata.get("practitioner_id")
            or evaluation_metadata.get("professional_id")
        )
        full_name = str(
            payload.get("name")
            or payload.get("full_name")
            or payload.get("professional_name")
            or payload.get("display_name")
            or payload_metadata.get("professional_name")
            or evaluation_payload.get("professional_name")
            or evaluation_metadata.get("professional_name")
            or ""
        ).strip()
        role = str(
            payload.get("role")
            or payload.get("professional_role")
            or payload_metadata.get("professional_role")
            or evaluation_payload.get("professional_role")
            or evaluation_metadata.get("professional_role")
            or ""
        ).strip()
        unit_id = str(
            payload.get("unit_id")
            or payload_metadata.get("unit_id")
            or payload_metadata.get("unit")
            or evaluation_payload.get("unit_id")
            or evaluation_metadata.get("unit_id")
            or evaluation_metadata.get("unit")
            or ""
        ).strip()
        team_id = str(
            payload.get("team_id")
            or payload_metadata.get("team_id")
            or payload_metadata.get("team")
            or evaluation_payload.get("team_id")
            or evaluation_metadata.get("team_id")
            or evaluation_metadata.get("team")
            or ""
        ).strip()

        if not practitioner_uid and not full_name:
            raise ValueError("practitioner data requires at least a local id or display name")

        resolved_name = full_name or "Profissional REDISUS"
        family, given = _split_human_name(resolved_name)

        identifiers: list[dict[str, Any]] = []
        if practitioner_uid:
            identifiers.append(build_identifier(f"{REDISUS_CODE_SYSTEM}/practitioner-id", str(practitioner_uid)))

        professional_registration = str(
            payload.get("registration_number")
            or payload.get("professional_registration")
            or payload.get("license_number")
            or payload_metadata.get("registration_number")
            or payload_metadata.get("professional_registration")
            or ""
        ).strip()
        if professional_registration:
            identifiers.append(
                build_identifier(
                    f"{REDISUS_CODE_SYSTEM}/professional-registration",
                    professional_registration,
                )
            )

        telecom: list[dict[str, Any]] = []
        phone = str(
            payload.get("phone")
            or payload.get("telefone")
            or payload_metadata.get("phone")
            or payload_metadata.get("telefone")
            or ""
        ).strip()
        email = str(payload.get("email") or payload_metadata.get("email") or "").strip()
        if phone:
            telecom.append({"system": "phone", "value": phone, "use": "work"})
        if email:
            telecom.append({"system": "email", "value": email, "use": "work"})

        extensions: list[dict[str, Any]] = []
        if role:
            extensions.append(
                {
                    "url": f"{REDISUS_STRUCTURE_DEFINITION}/practitioner-role-label",
                    "valueCodeableConcept": {
                        "coding": [
                            {
                                "system": f"{REDISUS_CODE_SYSTEM}/clinical-role",
                                "code": _resource_slug(role),
                                "display": role,
                            }
                        ],
                        "text": role,
                    },
                }
            )
        if unit_id:
            extensions.append(
                {
                    "url": f"{REDISUS_STRUCTURE_DEFINITION}/practitioner-unit-id",
                    "valueString": unit_id,
                }
            )
        if team_id:
            extensions.append(
                {
                    "url": f"{REDISUS_STRUCTURE_DEFINITION}/practitioner-team-id",
                    "valueString": team_id,
                }
            )

        resource = PractitionerResource(
            id=self._resolve_practitioner_id(payload, evaluation_payload),
            identifier=identifiers,
            active=True,
            name=[
                {
                    "use": "official",
                    "family": family,
                    "given": given,
                    "text": resolved_name,
                }
            ],
            telecom=telecom,
            extension=extensions,
        ).to_dict()
        self._validate_resource(resource)
        return resource

    def map_encounter(
        self,
        patient_id: str,
        *,
        encounter_data: Mapping[str, Any] | None = None,
        evaluation_data: Mapping[str, Any] | None = None,
        inference_result: Mapping[str, Any] | None = None,
        practitioner_id: str | None = None,
        condition: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload = dict(encounter_data or {})
        evaluation_payload = dict(evaluation_data or {})
        payload_metadata = payload.get("metadata") if isinstance(payload.get("metadata"), Mapping) else {}
        evaluation_metadata = (
            evaluation_payload.get("metadata") if isinstance(evaluation_payload.get("metadata"), Mapping) else {}
        )

        status_key = _slugify(
            payload.get("status")
            or payload.get("encounter_status")
            or payload_metadata.get("encounter_status")
            or evaluation_payload.get("encounter_status")
            or evaluation_metadata.get("encounter_status")
            or "finished"
        )
        status = {
            "completed": "finished",
            "complete": "finished",
            "finished": "finished",
            "in_progress": "in-progress",
            "inprogress": "in-progress",
            "planned": "planned",
            "cancelled": "cancelled",
            "canceled": "cancelled",
            "arrived": "arrived",
            "triaged": "triaged",
        }.get(status_key, "finished")

        raw_class = str(
            payload.get("class_code")
            or payload.get("encounter_class")
            or payload_metadata.get("encounter_class")
            or evaluation_payload.get("encounter_class")
            or evaluation_metadata.get("encounter_class")
            or "AMB"
        ).strip()
        class_key = _resource_slug(raw_class).upper().replace("-", "_") or "AMB"
        class_payload = ENCOUNTER_CLASS_CODES.get(class_key, ENCOUNTER_CLASS_CODES["AMB"])

        case_id = str(payload.get("case_id") or evaluation_payload.get("case_id") or "").strip()
        evaluation_id = str(payload.get("evaluation_id") or evaluation_payload.get("id") or "").strip()
        wound_type = str(payload.get("wound_type") or evaluation_payload.get("wound_type") or "").strip()
        wound_location = str(
            payload.get("wound_location")
            or evaluation_payload.get("wound_location")
            or evaluation_payload.get("body_site")
            or ""
        ).strip()
        reason_text = str(
            payload.get("reason_text")
            or payload.get("clinical_description")
            or evaluation_payload.get("clinical_description")
            or wound_type
            or "Clinical wound follow-up"
        ).strip()
        type_text = str(
            payload.get("type_text")
            or payload.get("title")
            or evaluation_payload.get("encounter_title")
            or "REDISUS wound assessment encounter"
        ).strip()
        service_type_text = str(
            payload.get("service_type_text")
            or payload.get("service_type")
            or "Wound care follow-up"
        ).strip()
        unit_id = str(
            payload.get("unit_id")
            or payload_metadata.get("unit_id")
            or payload_metadata.get("unit")
            or evaluation_payload.get("unit_id")
            or evaluation_metadata.get("unit_id")
            or evaluation_metadata.get("unit")
            or ""
        ).strip()
        team_id = str(
            payload.get("team_id")
            or payload_metadata.get("team_id")
            or payload_metadata.get("team")
            or evaluation_payload.get("team_id")
            or evaluation_metadata.get("team_id")
            or evaluation_metadata.get("team")
            or ""
        ).strip()

        identifiers: list[dict[str, Any]] = []
        if case_id:
            identifiers.append(build_identifier(f"{REDISUS_CODE_SYSTEM}/case-id", case_id))
        if evaluation_id:
            identifiers.append(build_identifier(f"{REDISUS_CODE_SYSTEM}/evaluation-id", evaluation_id))

        participant = [
            {
                "type": [{"text": "Performer"}],
                "individual": build_reference("Practitioner", practitioner_id),
            }
        ] if practitioner_id else []

        start = _ensure_datetime(
            payload.get("period_start")
            or evaluation_payload.get("evaluation_date")
            or evaluation_payload.get("created_at")
        )
        end = _ensure_datetime(
            payload.get("period_end")
            or (inference_result or {}).get("generated_at")
            or evaluation_payload.get("updated_at")
            or evaluation_payload.get("created_at")
            or evaluation_payload.get("evaluation_date")
        )

        notes: list[str] = []
        if wound_location:
            notes.append(f"Wound location: {wound_location}")
        if unit_id:
            notes.append(f"Unit scope: {unit_id}")
        if team_id:
            notes.append(f"Team scope: {team_id}")

        diagnosis = []
        if condition and condition.get("id"):
            diagnosis.append({"condition": build_reference("Condition", condition.get("id")), "rank": 1})

        resource = EncounterResource(
            id=self._resolve_encounter_id(payload, evaluation_payload),
            identifier=identifiers,
            status=status,
            class_fhir=class_payload,
            encounter_type=[
                {
                    "coding": [
                        {
                            "system": f"{REDISUS_CODE_SYSTEM}/encounter-type",
                            "code": "wound-evaluation",
                            "display": "Wound evaluation encounter",
                        }
                    ],
                    "text": type_text,
                }
            ],
            service_type={
                "coding": [
                    {
                        "system": f"{REDISUS_CODE_SYSTEM}/service-type",
                        "code": "wound-care-follow-up",
                        "display": "Wound care follow-up",
                    }
                ],
                "text": service_type_text,
            },
            subject=build_reference("Patient", patient_id),
            participant=participant,
            period=compact_dict({"start": start, "end": end}),
            reason_code=[
                {
                    "coding": [
                        {
                            "system": f"{REDISUS_CODE_SYSTEM}/encounter-reason",
                            "code": _resource_slug(wound_type or "wound-assessment"),
                            "display": (wound_type or "Wound assessment").replace("_", " ").title(),
                        }
                    ],
                    "text": reason_text,
                }
            ],
            diagnosis=diagnosis,
            note=_build_note(*notes),
        ).to_dict()
        self._validate_resource(resource)
        return resource

    def map_observation(
        self,
        patient_id: str,
        *,
        evaluation_data: Mapping[str, Any] | None = None,
        inference_result: Mapping[str, Any] | None = None,
        practitioner_id: str | None = None,
        encounter_id: str | None = None,
    ) -> dict[str, Any]:
        inference = self._extract_inference(inference_result)
        interpretation = self._extract_interpretation(inference_result)
        tissue = _extract_tissue_percentages(evaluation_data, inference_result, inference)

        components: list[dict[str, Any]] = []
        for tissue_key, code in TISSUE_COMPONENT_CODES.items():
            value = tissue.get(tissue_key, 0.0)
            components.append(_build_quantity_component(code, value, "%", "%"))

        area_cm2 = _safe_float(
            inference.get("wound_area_cm2")
            or (evaluation_data or {}).get("wound_area_cm2")
            or (inference_result or {}).get("wound_area_cm2")
            or (inference_result or {}).get("area_cm2")
        )
        if area_cm2 is not None:
            components.append(
                _build_quantity_component(
                    {"system": LOINC_SYSTEM, "code": "89260-9", "display": "Wound area"},
                    area_cm2,
                    "cm2",
                    "cm2",
                )
            )

        depth_mm = _safe_float((evaluation_data or {}).get("depth_mm"))
        if depth_mm is not None:
            components.append(
                _build_quantity_component(
                    {
                        "system": f"{REDISUS_CODE_SYSTEM}/measurement",
                        "code": "wound-depth",
                        "display": "Wound depth",
                    },
                    depth_mm,
                    "mm",
                    "mm",
                )
            )

        pain_score = _safe_float((evaluation_data or {}).get("pain_score"))
        if pain_score is not None:
            components.append(_build_score_component("pain-score", "Pain score", pain_score))

        push_score = _safe_float((evaluation_data or {}).get("push_score"))
        if push_score is not None:
            components.append(_build_score_component("push-score", "PUSH score", push_score))

        bwat_score = _safe_float((evaluation_data or {}).get("bwat_score"))
        if bwat_score is not None:
            components.append(_build_score_component("bwat-score", "BWAT score", bwat_score))

        health_score = _safe_float(
            (evaluation_data or {}).get("health_score")
            or inference.get("health_score")
            or (inference_result or {}).get("health_score")
        )
        if health_score is not None:
            components.append(_build_score_component("wound-health-score", "REDISUS wound health score", health_score))

        confidence = _safe_float(inference.get("confidence"))
        if confidence is not None:
            components.append(_build_score_component("ai-confidence", "AI confidence", confidence * 100.0))

        risk_level = _normalize_risk(interpretation.get("risk_level") or (inference_result or {}).get("risk_level"))
        components.append(
            {
                "code": {
                    "coding": [
                        {
                            "system": f"{REDISUS_CODE_SYSTEM}/risk-level",
                            "code": "risk-level",
                            "display": "REDISUS risk level",
                        }
                    ],
                    "text": "REDISUS risk level",
                },
                "valueCodeableConcept": {
                    "coding": [RISK_INTERPRETATION_CODES[risk_level]],
                    "text": risk_level,
                },
            }
        )

        performer = [build_reference("Practitioner", practitioner_id)] if practitioner_id else []
        body_site = str((evaluation_data or {}).get("wound_location") or (evaluation_data or {}).get("body_site") or "").strip()
        summary = interpretation.get("summary") or (inference_result or {}).get("diagnosis_summary")

        resource = ObservationResource(
            id=str((evaluation_data or {}).get("id") or generate_id("observation")),
            status="final",
            category=[
                {
                    "coding": [
                        {
                            "system": "http://terminology.hl7.org/CodeSystem/observation-category",
                            "code": "exam",
                            "display": "Exam",
                        }
                    ]
                }
            ],
            code={
                "coding": [
                    {
                        "system": LOINC_SYSTEM,
                        "code": "72170-4",
                        "display": "Wound assessment panel",
                    }
                ],
                "text": "REDISUS wound assessment",
            },
            subject=build_reference("Patient", patient_id),
            encounter=build_reference("Encounter", encounter_id) if encounter_id else None,
            effective_date_time=_ensure_datetime((evaluation_data or {}).get("evaluation_date") or (inference_result or {}).get("generated_at")),
            issued=_ensure_datetime((inference_result or {}).get("generated_at") or (evaluation_data or {}).get("evaluation_date")),
            performer=performer,
            body_site={"text": body_site} if body_site else None,
            method={
                "coding": [
                    {
                        "system": f"{REDISUS_CODE_SYSTEM}/analysis-method",
                        "code": "computer-vision-wound-analysis",
                        "display": "Computer vision wound analysis",
                    }
                ]
            },
            component=components,
            note=_build_note(summary),
            interpretation=[{"coding": [RISK_INTERPRETATION_CODES[risk_level]], "text": risk_level}],
        ).to_dict()
        self._validate_resource(resource)
        return resource

    def map_condition(
        self,
        patient_id: str,
        *,
        evaluation_data: Mapping[str, Any] | None = None,
        inference_result: Mapping[str, Any] | None = None,
        practitioner_id: str | None = None,
        encounter_id: str | None = None,
    ) -> dict[str, Any]:
        inference = self._extract_inference(inference_result)
        interpretation = self._extract_interpretation(inference_result)
        etiology_code = _normalize_etiology(
            inference.get("etiology")
            or (evaluation_data or {}).get("wound_type")
            or (inference_result or {}).get("etiology")
        )
        confidence = _safe_float(inference.get("confidence"), 0.0) or 0.0
        risk_level = _normalize_risk(interpretation.get("risk_level") or (inference_result or {}).get("risk_level"))
        snomed = WOUND_SNOMED_CODES.get(etiology_code)
        icd10 = WOUND_ICD10_CODES.get(etiology_code)
        codings: list[dict[str, Any]] = []
        if snomed:
            codings.append({"system": SNOMED_SYSTEM, **snomed})
        if icd10:
            codings.append({"system": ICD10_SYSTEM, **icd10})

        summary = interpretation.get("summary") or (inference_result or {}).get("diagnosis_summary")
        body_site = str((evaluation_data or {}).get("wound_location") or (evaluation_data or {}).get("body_site") or "").strip()

        resource = ConditionResource(
            id=str((evaluation_data or {}).get("case_id") or (inference_result or {}).get("case_id") or generate_id("condition")),
            clinical_status={
                "coding": [
                    {
                        "system": "http://terminology.hl7.org/CodeSystem/condition-clinical",
                        "code": "active",
                        "display": "Active",
                    }
                ]
            },
            verification_status={
                "coding": [
                    {
                        "system": "http://terminology.hl7.org/CodeSystem/condition-ver-status",
                        "code": "confirmed" if confidence >= 0.7 else "provisional",
                        "display": "Confirmed" if confidence >= 0.7 else "Provisional",
                    }
                ]
            },
            category=[
                {
                    "coding": [
                        {
                            "system": "http://terminology.hl7.org/CodeSystem/condition-category",
                            "code": "encounter-diagnosis",
                            "display": "Encounter Diagnosis",
                        }
                    ]
                }
            ],
            severity={"coding": [RISK_SEVERITY_CODES[risk_level]], "text": risk_level},
            code={
                "coding": codings,
                "text": etiology_code.replace("_", " ").title(),
            },
            subject=build_reference("Patient", patient_id),
            encounter=build_reference("Encounter", encounter_id) if encounter_id else None,
            recorder=build_reference("Practitioner", practitioner_id) if practitioner_id else None,
            body_site=[{"text": body_site}] if body_site else [],
            onset_date_time=str((evaluation_data or {}).get("evaluation_date") or "").strip() or None,
            recorded_date=_ensure_datetime((inference_result or {}).get("generated_at") or (evaluation_data or {}).get("evaluation_date")),
            note=_build_note(summary),
            extension=[
                {
                    "url": f"{REDISUS_STRUCTURE_DEFINITION}/ai-confidence",
                    "valueDecimal": round(confidence, 4),
                }
            ],
        ).to_dict()
        self._validate_resource(resource)
        return resource

    def map_diagnostic_report(
        self,
        patient_id: str,
        *,
        observation: Mapping[str, Any],
        condition: Mapping[str, Any] | None = None,
        evaluation_data: Mapping[str, Any] | None = None,
        inference_result: Mapping[str, Any] | None = None,
        images: list[Any] | None = None,
        practitioner_id: str | None = None,
        encounter_id: str | None = None,
    ) -> dict[str, Any]:
        interpretation = self._extract_interpretation(inference_result)
        attachments = [
            attachment
            for attachment in (
                _attachment_from_image(item)
                for item in _extract_images(evaluation_data, inference_result, explicit_images=images)
            )
            if attachment
        ]
        conclusion_codes: list[dict[str, Any]] = []
        if condition:
            conclusion_codes.append(
                {
                    "coding": list(((condition.get("code") or {}).get("coding") or [])),
                    "text": (condition.get("code") or {}).get("text"),
                }
            )

        report_notes = _build_note(*((interpretation.get("recommendations") or []) if isinstance(interpretation.get("recommendations"), list) else []))
        performer = [build_reference("Practitioner", practitioner_id)] if practitioner_id else []

        resource = DiagnosticReportResource(
            id=str((inference_result or {}).get("evaluation_id") or (evaluation_data or {}).get("id") or generate_id("report")),
            status="final",
            category=[
                {
                    "coding": [
                        {
                            "system": "http://terminology.hl7.org/CodeSystem/v2-0074",
                            "code": "IMG",
                            "display": "Diagnostic Imaging",
                        }
                    ]
                }
            ],
            code={
                "coding": [
                    {
                        "system": LOINC_SYSTEM,
                        "code": "72170-4",
                        "display": "Wound assessment panel",
                    }
                ],
                "text": "REDISUS wound diagnostic report",
            },
            subject=build_reference("Patient", patient_id),
            encounter=build_reference("Encounter", encounter_id) if encounter_id else None,
            effective_date_time=_ensure_datetime((evaluation_data or {}).get("evaluation_date") or (inference_result or {}).get("generated_at")),
            issued=_ensure_datetime((inference_result or {}).get("generated_at") or (evaluation_data or {}).get("evaluation_date")),
            performer=performer,
            result=[build_reference("Observation", observation.get("id"))],
            conclusion=str(interpretation.get("summary") or (inference_result or {}).get("diagnosis_summary") or "REDISUS wound assessment report"),
            conclusion_code=conclusion_codes,
            presented_form=attachments,
            note=report_notes,
        ).to_dict()
        self._validate_resource(resource)
        return resource

    def map_care_plan(
        self,
        patient_id: str,
        care_plan_data: Mapping[str, Any],
        *,
        condition: Mapping[str, Any] | None = None,
        practitioner_id: str | None = None,
        encounter_id: str | None = None,
    ) -> dict[str, Any]:
        tasks = care_plan_data.get("tasks") if isinstance(care_plan_data.get("tasks"), list) else care_plan_data.get("activities")
        activity = [self._map_activity(task) for task in (tasks or [])]
        goals = care_plan_data.get("goals") if isinstance(care_plan_data.get("goals"), list) else []
        alerts = care_plan_data.get("alerts") if isinstance(care_plan_data.get("alerts"), list) else []

        period = compact_dict(
            {
                "start": str(care_plan_data.get("created_at") or fhir_now()),
                "end": care_plan_data.get("review_due_date"),
            }
        )

        note_texts: list[str] = []
        note_texts.extend(str(goal) for goal in goals if str(goal).strip())
        note_texts.extend(str(alert.get("reason") or alert.get("type") or "") for alert in alerts if isinstance(alert, Mapping))

        resource = CarePlanResource(
            id=str(care_plan_data.get("id") or generate_id("careplan")),
            status=str(care_plan_data.get("status") or "active"),
            intent="plan",
            title=str(care_plan_data.get("title") or "REDISUS wound care plan"),
            description=str(
                (care_plan_data.get("metadata") or {}).get("summary")
                or care_plan_data.get("description")
                or "Care plan generated from REDISUS wound assessment"
            ),
            subject=build_reference("Patient", patient_id),
            encounter=build_reference("Encounter", encounter_id) if encounter_id else None,
            author=build_reference("Practitioner", practitioner_id) if practitioner_id else None,
            created=str(care_plan_data.get("created_at") or fhir_now()),
            period=period or None,
            addresses=[build_reference("Condition", condition.get("id"))] if condition else [],
            activity=activity,
            note=_build_note(*note_texts),
        ).to_dict()
        self._validate_resource(resource)
        return resource

    def map_case_to_bundle(
        self,
        *,
        patient_data: Mapping[str, Any],
        evaluation_data: Mapping[str, Any] | None = None,
        inference_result: Mapping[str, Any] | None = None,
        care_plan_data: Mapping[str, Any] | None = None,
        practitioner_data: Mapping[str, Any] | None = None,
        encounter_data: Mapping[str, Any] | None = None,
        images: list[Any] | None = None,
        bundle_type: str = "collection",
    ) -> dict[str, Any]:
        patient = self.map_patient(patient_data)
        practitioner = None
        if self._has_practitioner_context(practitioner_data, evaluation_data):
            practitioner = self.map_practitioner(practitioner_data, evaluation_data=evaluation_data)

        encounter_id = self._resolve_encounter_id(encounter_data, evaluation_data) if self._has_encounter_context(
            encounter_data, evaluation_data
        ) else None
        condition = self.map_condition(
            patient["id"],
            evaluation_data=evaluation_data,
            inference_result=inference_result,
            practitioner_id=practitioner["id"] if practitioner else None,
            encounter_id=encounter_id,
        )
        encounter = None
        if encounter_id:
            encounter = self.map_encounter(
                patient["id"],
                encounter_data=encounter_data,
                evaluation_data=evaluation_data,
                inference_result=inference_result,
                practitioner_id=practitioner["id"] if practitioner else None,
                condition=condition,
            )
            encounter_id = encounter["id"]

        observation = self.map_observation(
            patient["id"],
            evaluation_data=evaluation_data,
            inference_result=inference_result,
            practitioner_id=practitioner["id"] if practitioner else None,
            encounter_id=encounter_id,
        )
        report = self.map_diagnostic_report(
            patient["id"],
            observation=observation,
            condition=condition,
            evaluation_data=evaluation_data,
            inference_result=inference_result,
            images=images,
            practitioner_id=practitioner["id"] if practitioner else None,
            encounter_id=encounter_id,
        )

        resources: list[dict[str, Any]] = [patient]
        if practitioner:
            resources.append(practitioner)
        resources.append(condition)
        if encounter:
            resources.append(encounter)
        resources.extend([observation, report])
        if care_plan_data:
            resources.append(
                self.map_care_plan(
                    patient["id"],
                    care_plan_data,
                    condition=condition,
                    practitioner_id=practitioner["id"] if practitioner else None,
                    encounter_id=encounter_id,
                )
            )
        return self.build_bundle(resources, bundle_type=bundle_type)

    def build_bundle(self, resources: list[Mapping[str, Any]], bundle_type: str = "collection") -> dict[str, Any]:
        entries: list[dict[str, Any]] = []
        for resource in resources:
            entry = {
                "fullUrl": f"urn:uuid:{resource['resourceType'].lower()}-{resource['id']}",
                "resource": dict(resource),
            }
            if bundle_type == "transaction":
                entry["request"] = {
                    "method": "PUT",
                    "url": f"{resource['resourceType']}/{resource['id']}",
                }
            entries.append(entry)

        bundle = {
            "resourceType": "Bundle",
            "type": bundle_type,
            "timestamp": fhir_now(),
            "entry": entries,
        }
        self._validate_bundle(bundle)
        return bundle

    def build_transaction_bundle(self, resources: list[Mapping[str, Any]]) -> dict[str, Any]:
        return self.build_bundle(resources, bundle_type="transaction")

    def _extract_inference(self, inference_result: Mapping[str, Any] | None) -> dict[str, Any]:
        if not isinstance(inference_result, Mapping):
            return {}
        if isinstance(inference_result.get("inference"), Mapping):
            payload = dict(inference_result.get("inference") or {})
        else:
            payload = dict(inference_result)

        if isinstance(inference_result.get("etiology"), Mapping):
            etiology_payload = inference_result.get("etiology") or {}
            payload.setdefault("etiology", etiology_payload.get("primary"))
            payload.setdefault("confidence", etiology_payload.get("confidence"))

        if isinstance(inference_result.get("segmentation"), Mapping):
            segmentation_payload = inference_result.get("segmentation") or {}
            payload.setdefault("tissue_percentages", segmentation_payload.get("tissue_percentages"))
            payload.setdefault("wound_area_cm2", segmentation_payload.get("wound_area_cm2"))

        if "area_cm2" in payload and "wound_area_cm2" not in payload:
            payload["wound_area_cm2"] = payload.get("area_cm2")
        if "healthScore" in payload and "health_score" not in payload:
            payload["health_score"] = payload.get("healthScore")
        return payload

    def _extract_interpretation(self, inference_result: Mapping[str, Any] | None) -> dict[str, Any]:
        if not isinstance(inference_result, Mapping):
            return {}
        if isinstance(inference_result.get("interpretation"), Mapping):
            return dict(inference_result.get("interpretation") or {})
        return {
            "summary": inference_result.get("diagnosis_summary") or inference_result.get("summary"),
            "risk_level": inference_result.get("risk_level"),
            "follow_up_days": inference_result.get("follow_up_days") or inference_result.get("days_until_next"),
            "recommendations": inference_result.get("recommendations"),
        }

    def _map_activity(self, task: Any) -> dict[str, Any]:
        if isinstance(task, str):
            description = task.strip()
            return {"detail": {"status": "scheduled", "description": description}}

        if not isinstance(task, Mapping):
            return {"detail": {"status": "scheduled", "description": "Unstructured care task"}}

        frequency = task.get("frequency") or task.get("scheduledString") or task.get("schedule")
        materials = task.get("materials") if isinstance(task.get("materials"), list) else []
        precautions = task.get("precautions") if isinstance(task.get("precautions"), list) else []

        description_parts = [
            str(task.get("title") or task.get("description") or "Care task").strip(),
            str(task.get("instructions") or "").strip(),
        ]
        if materials:
            description_parts.append("Materials: " + ", ".join(str(item) for item in materials if str(item).strip()))
        if precautions:
            description_parts.append("Precautions: " + ", ".join(str(item) for item in precautions if str(item).strip()))

        description = " ".join(part for part in description_parts if part)
        return {
            "detail": compact_dict(
                {
                    "status": "scheduled",
                    "description": description,
                    "scheduledString": str(frequency).strip() if frequency else None,
                }
            )
        }

    def _has_practitioner_context(
        self,
        practitioner_data: Mapping[str, Any] | None,
        evaluation_data: Mapping[str, Any] | None,
    ) -> bool:
        payload = dict(practitioner_data or {})
        evaluation_payload = dict(evaluation_data or {})
        payload_metadata = payload.get("metadata") if isinstance(payload.get("metadata"), Mapping) else {}
        evaluation_metadata = (
            evaluation_payload.get("metadata") if isinstance(evaluation_payload.get("metadata"), Mapping) else {}
        )
        candidates = (
            payload.get("id"),
            payload.get("practitioner_id"),
            payload.get("professional_id"),
            payload.get("uid"),
            payload.get("name"),
            payload.get("full_name"),
            payload.get("professional_name"),
            payload_metadata.get("professional_id"),
            payload_metadata.get("professional_name"),
            evaluation_payload.get("practitioner_id"),
            evaluation_payload.get("professional_id"),
            evaluation_payload.get("professional_name"),
            evaluation_metadata.get("practitioner_id"),
            evaluation_metadata.get("professional_id"),
            evaluation_metadata.get("professional_name"),
        )
        return any(str(value or "").strip() for value in candidates)

    def _has_encounter_context(
        self,
        encounter_data: Mapping[str, Any] | None,
        evaluation_data: Mapping[str, Any] | None,
    ) -> bool:
        if encounter_data:
            return True
        payload = dict(evaluation_data or {})
        return any(
            str(payload.get(key) or "").strip()
            for key in ("id", "case_id", "evaluation_date", "wound_type", "wound_location")
        )

    def _resolve_practitioner_id(
        self,
        practitioner_data: Mapping[str, Any] | None,
        evaluation_data: Mapping[str, Any] | None,
    ) -> str:
        payload = dict(practitioner_data or {})
        evaluation_payload = dict(evaluation_data or {})
        payload_metadata = payload.get("metadata") if isinstance(payload.get("metadata"), Mapping) else {}
        evaluation_metadata = (
            evaluation_payload.get("metadata") if isinstance(evaluation_payload.get("metadata"), Mapping) else {}
        )
        return _stable_resource_id(
            "practitioner",
            payload.get("id"),
            payload.get("practitioner_id"),
            payload.get("professional_id"),
            payload.get("uid"),
            payload_metadata.get("practitioner_id"),
            payload_metadata.get("professional_id"),
            evaluation_payload.get("practitioner_id"),
            evaluation_payload.get("professional_id"),
            evaluation_metadata.get("practitioner_id"),
            evaluation_metadata.get("professional_id"),
            payload.get("name"),
            payload.get("full_name"),
            payload.get("professional_name"),
            evaluation_payload.get("professional_name"),
            evaluation_metadata.get("professional_name"),
        )

    def _resolve_encounter_id(
        self,
        encounter_data: Mapping[str, Any] | None,
        evaluation_data: Mapping[str, Any] | None,
    ) -> str:
        payload = dict(encounter_data or {})
        evaluation_payload = dict(evaluation_data or {})
        payload_metadata = payload.get("metadata") if isinstance(payload.get("metadata"), Mapping) else {}
        evaluation_metadata = (
            evaluation_payload.get("metadata") if isinstance(evaluation_payload.get("metadata"), Mapping) else {}
        )
        return _stable_resource_id(
            "encounter",
            payload.get("id"),
            payload.get("encounter_id"),
            payload_metadata.get("encounter_id"),
            evaluation_payload.get("encounter_id"),
            evaluation_metadata.get("encounter_id"),
            evaluation_payload.get("id"),
            payload.get("evaluation_id"),
            payload.get("case_id"),
            evaluation_payload.get("case_id"),
        )

    def _validate_resource(self, resource: Mapping[str, Any]) -> None:
        validate_resource(resource, strict=self.strict_validation)

    def _validate_bundle(self, bundle: Mapping[str, Any]) -> None:
        validate_bundle(bundle, strict=self.strict_validation)
