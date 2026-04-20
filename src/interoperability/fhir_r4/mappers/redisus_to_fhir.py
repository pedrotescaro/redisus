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
    MEDIA_CATEGORY_SYSTEM,
    PRACTITIONER_ROLE_SYSTEM,
    PROVENANCE_PARTICIPANT_TYPE_SYSTEM,
    REDISUS_CODE_SYSTEM,
    REDISUS_STRUCTURE_DEFINITION,
    SNOMED_SYSTEM,
    UCUM_SYSTEM,
    CarePlanResource,
    ConditionResource,
    DiagnosticReportResource,
    EncounterResource,
    MediaResource,
    ObservationResource,
    OrganizationResource,
    PatientResource,
    PractitionerResource,
    PractitionerRoleResource,
    ProvenanceResource,
    build_codeable_concept,
    build_coding,
    build_identifier,
    build_reference,
    compact_dict,
    fhir_now,
    generate_id,
)
from ..terminology import (
    TARGET_PROFILE_REGISTRY,
    clinical_score_concept,
    encounter_type_concept,
    encounter_reason_concept,
    media_category_concept,
    media_type_code,
    organization_type_concept,
    practitioner_role_concept,
    provenance_agent_type_concept,
    risk_level_concept,
    service_type_concept,
    wound_classification_concept,
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

ORGANIZATION_KIND_ALIASES = {
    "unit": "health-unit",
    "health_unit": "health-unit",
    "facility": "health-unit",
    "team": "care-team",
    "care_team": "care-team",
}

MEDIA_CATEGORY_BY_CONTENT_TYPE = {
    "image": "image",
    "video": "video",
    "audio": "audio",
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


def _first_non_empty(*values: Any) -> Any:
    for value in values:
        if isinstance(value, str):
            if value.strip():
                return value
            continue
        if value not in (None, "", [], {}):
            return value
    return None


def _display_from_code(code: Any, default: str) -> str:
    text = str(code or "").strip()
    if not text:
        return default
    return text.replace("-", " ").replace("_", " ").title()


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


def _build_reference_with_identifier(
    *,
    system: str,
    value: str,
    display: str | None = None,
    reference: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {"identifier": build_identifier(system, value)}
    if reference:
        payload["reference"] = reference
    if display:
        payload["display"] = display
    return payload


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
        "code": clinical_score_concept(code, display),
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
        ).to_dict()
        self._validate_resource(resource)
        return resource

    def map_organization(
        self,
        organization_data: Mapping[str, Any],
        *,
        kind: str,
        parent_organization_id: str | None = None,
    ) -> dict[str, Any]:
        payload = dict(organization_data)
        normalized_kind = ORGANIZATION_KIND_ALIASES.get(_slugify(kind), _resource_slug(kind) or "organization")
        organization_id = self._resolve_organization_id(payload, normalized_kind)
        identifier_value = str(payload.get("identifier") or payload.get("id") or organization_id).strip()
        name = str(
            payload.get("name")
            or payload.get("display")
            or payload.get("display_name")
            or payload.get("unit_name")
            or payload.get("team_name")
            or payload.get("label")
            or payload.get("id")
            or identifier_value
        ).strip()

        alias = []
        if identifier_value and identifier_value != name:
            alias.append(identifier_value)

        extensions: list[dict[str, Any]] = []
        scope_code = str(payload.get("scope_code") or normalized_kind).strip()
        if scope_code:
            extensions.append(
                {
                    "url": f"{REDISUS_STRUCTURE_DEFINITION}/organization-scope",
                    "valueCodeableConcept": organization_type_concept(scope_code),
                }
            )

        resource = OrganizationResource(
            id=organization_id,
            identifier=[build_identifier(f"{REDISUS_CODE_SYSTEM}/organization-id", identifier_value)],
            active=True,
            organization_type=[organization_type_concept(normalized_kind)],
            name=name,
            alias=alias,
            part_of=build_reference("Organization", parent_organization_id) if parent_organization_id else None,
            extension=extensions,
        ).to_dict()
        self._validate_resource(resource)
        return resource

    def map_practitioner_role(
        self,
        practitioner_id: str,
        *,
        practitioner_data: Mapping[str, Any] | None = None,
        evaluation_data: Mapping[str, Any] | None = None,
        organization_id: str | None = None,
    ) -> dict[str, Any]:
        payload = dict(practitioner_data or {})
        evaluation_payload = dict(evaluation_data or {})
        payload_metadata = payload.get("metadata") if isinstance(payload.get("metadata"), Mapping) else {}
        evaluation_metadata = (
            evaluation_payload.get("metadata") if isinstance(evaluation_payload.get("metadata"), Mapping) else {}
        )

        role = str(
            _first_non_empty(
                payload.get("role"),
                payload.get("professional_role"),
                payload_metadata.get("professional_role"),
                evaluation_payload.get("professional_role"),
                evaluation_metadata.get("professional_role"),
                "clinician",
            )
        ).strip()
        organization_reference = build_reference("Organization", organization_id) if organization_id else None
        evaluation_date = _ensure_datetime(
            _first_non_empty(
                evaluation_payload.get("evaluation_date"),
                evaluation_payload.get("created_at"),
                fhir_now(),
            )
        )

        resource = PractitionerRoleResource(
            id=self._resolve_practitioner_role_id(payload, evaluation_payload, organization_id=organization_id),
            identifier=[
                build_identifier(
                    f"{REDISUS_CODE_SYSTEM}/practitioner-role-id",
                    str(
                        _first_non_empty(
                            payload.get("role_id"),
                            payload.get("id"),
                            evaluation_payload.get("professional_id"),
                            f"{practitioner_id}:{organization_id or 'unscoped'}:{_resource_slug(role)}",
                        )
                    ),
                )
            ],
            active=True,
            period={"start": evaluation_date},
            practitioner=build_reference("Practitioner", practitioner_id),
            organization=organization_reference,
            code=[practitioner_role_concept(role)],
            specialty=[
                build_codeable_concept(
                    build_coding(
                        f"{REDISUS_CODE_SYSTEM}/practice-setting",
                        "wound-care",
                        "Wound care",
                    ),
                    text="Wound care",
                )
            ],
        ).to_dict()
        self._validate_resource(resource)
        return resource

    def map_media(
        self,
        patient_id: str,
        image: Any,
        *,
        evaluation_data: Mapping[str, Any] | None = None,
        practitioner_id: str | None = None,
        encounter_id: str | None = None,
        index: int = 0,
    ) -> dict[str, Any]:
        attachment = _attachment_from_image(image)
        if not attachment:
            raise ValueError("media mapping requires a resolvable image attachment")

        payload = dict(image) if isinstance(image, Mapping) else {"image_path": image}
        content_type = str(attachment.get("contentType") or "").strip()
        media_category = MEDIA_CATEGORY_BY_CONTENT_TYPE.get(content_type.split("/")[0].lower(), "image")
        evaluation_payload = dict(evaluation_data or {})
        wound_type = str(evaluation_payload.get("wound_type") or "wound-assessment").strip()
        wound_location = str(
            evaluation_payload.get("wound_location") or evaluation_payload.get("body_site") or ""
        ).strip()

        identifier_value = str(
            _first_non_empty(
                payload.get("id"),
                payload.get("image_id"),
                payload.get("storage_key"),
                payload.get("url"),
                payload.get("image_path"),
                f"{evaluation_payload.get('id') or 'evaluation'}-{index + 1}",
            )
        ).strip()
        media_id = self._resolve_media_id(payload, evaluation_payload, index=index)

        resource = MediaResource(
            id=media_id,
            identifier=[build_identifier(f"{REDISUS_CODE_SYSTEM}/media-id", identifier_value)],
            status="completed",
            media_type=media_type_code(media_category),
            modality=build_codeable_concept(
                build_coding(
                    f"{REDISUS_CODE_SYSTEM}/media-modality",
                    "clinical-wound-image",
                    "Clinical wound image",
                ),
                text="Clinical wound image",
            ),
            subject=build_reference("Patient", patient_id),
            encounter=build_reference("Encounter", encounter_id) if encounter_id else None,
            created_date_time=_ensure_datetime(
                _first_non_empty(
                    payload.get("captured_at"),
                    payload.get("created_at"),
                    payload.get("date"),
                    evaluation_payload.get("evaluation_date"),
                )
            ),
            operator=build_reference("Practitioner", practitioner_id) if practitioner_id else None,
            reason_code=[
                build_codeable_concept(
                    build_coding(
                        f"{REDISUS_CODE_SYSTEM}/media-reason",
                        _resource_slug(wound_type or "wound-assessment"),
                        _display_from_code(wound_type, "Wound assessment"),
                    ),
                    text=str(
                        _first_non_empty(
                            payload.get("reason_text"),
                            evaluation_payload.get("clinical_description"),
                            "Clinical wound assessment image capture",
                        )
                    ),
                )
            ],
            body_site={"text": wound_location} if wound_location else None,
            content=attachment,
            note=_build_note(payload.get("title") or payload.get("name")),
        ).to_dict()
        self._validate_resource(resource)
        return resource

    def map_provenance(
        self,
        *,
        target_resources: list[Mapping[str, Any]],
        evaluation_data: Mapping[str, Any] | None = None,
        inference_result: Mapping[str, Any] | None = None,
        practitioner_id: str | None = None,
        practitioner_role_id: str | None = None,
        organization_id: str | None = None,
        media_resources: list[Mapping[str, Any]] | None = None,
    ) -> dict[str, Any]:
        evaluation_payload = dict(evaluation_data or {})
        inference_payload = dict(inference_result or {})
        targets = [
            build_reference(str(resource.get("resourceType")), str(resource.get("id")))
            for resource in target_resources
            if resource.get("resourceType") and resource.get("id")
        ]

        if not targets:
            raise ValueError("provenance mapping requires at least one target resource")

        agents: list[dict[str, Any]] = []
        if practitioner_id:
            agents.append(
                compact_dict(
                    {
                        "type": provenance_agent_type_concept("author"),
                        "role": [practitioner_role_concept(evaluation_payload.get("professional_role") or "clinician")],
                        "who": build_reference("Practitioner", practitioner_id),
                        "onBehalfOf": build_reference("Organization", organization_id) if organization_id else None,
                    }
                )
            )
        if inference_payload:
            model_version = str(
                _first_non_empty(
                    inference_payload.get("model_version"),
                    inference_payload.get("contract_version"),
                    (inference_payload.get("inference") or {}).get("model_version"),
                    "redisus-fhir-pipeline",
                )
            ).strip()
            agents.append(
                {
                    "type": provenance_agent_type_concept("assembler"),
                    "role": [
                        build_codeable_concept(
                            build_coding(
                                f"{REDISUS_CODE_SYSTEM}/automation-role",
                                "clinical-ai-pipeline",
                                "Clinical AI pipeline",
                            ),
                            text="Clinical AI pipeline",
                        )
                    ],
                    "who": _build_reference_with_identifier(
                        system=f"{REDISUS_CODE_SYSTEM}/ai-pipeline",
                        value=model_version,
                        display=str(
                            _first_non_empty(
                                inference_payload.get("analysis_type"),
                                "REDISUS AI wound assessment pipeline",
                            )
                        ),
                    ),
                    "onBehalfOf": (
                        build_reference("PractitionerRole", practitioner_role_id) if practitioner_role_id else None
                    ),
                }
            )

        entities: list[dict[str, Any]] = []
        for media in media_resources or []:
            if media.get("id"):
                entities.append({"role": "source", "what": build_reference("Media", str(media.get("id")))})

        evaluation_id = str(evaluation_payload.get("id") or "").strip()
        if evaluation_id:
            entities.append(
                {
                    "role": "source",
                    "what": _build_reference_with_identifier(
                        system=f"{REDISUS_CODE_SYSTEM}/evaluation-id",
                        value=evaluation_id,
                        display="REDISUS wound evaluation",
                    ),
                }
            )

        resource = ProvenanceResource(
            id=self._resolve_provenance_id(evaluation_payload, inference_payload, target_resources),
            target=targets,
            recorded=_ensure_datetime(
                _first_non_empty(
                    inference_payload.get("generated_at"),
                    evaluation_payload.get("updated_at"),
                    evaluation_payload.get("evaluation_date"),
                    fhir_now(),
                )
            ),
            reason=[
                build_codeable_concept(
                    build_coding(
                        f"{REDISUS_CODE_SYSTEM}/provenance-reason",
                        "clinical-interoperability-export",
                        "Clinical interoperability export",
                    ),
                    text="Clinical interoperability export",
                )
            ],
            activity=build_codeable_concept(
                build_coding(
                    f"{REDISUS_CODE_SYSTEM}/provenance-activity",
                    "derive-fhir-wound-case",
                    "Derive wound case bundle",
                ),
                text="Derive wound case bundle",
            ),
            agent=agents or [
                {
                    "type": provenance_agent_type_concept("author"),
                    "who": _build_reference_with_identifier(
                        system=f"{REDISUS_CODE_SYSTEM}/system-actor",
                        value="redisus-system",
                        display="REDISUS system",
                    ),
                }
            ],
            entity=entities,
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
        service_provider_id: str | None = None,
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
        encounter_type_code = _resource_slug(
            str(
                _first_non_empty(
                    payload.get("encounter_type_code"),
                    payload.get("type_code"),
                    "wound-evaluation",
                )
            )
        ) or "wound-evaluation"
        service_type_code = _resource_slug(
            str(_first_non_empty(payload.get("service_type_code"), payload.get("service_type"), "wound-care-follow-up"))
        ) or "wound-care-follow-up"

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

        diagnosis = []
        if condition and condition.get("id"):
            diagnosis.append({"condition": build_reference("Condition", condition.get("id")), "rank": 1})

        resource = EncounterResource(
            id=self._resolve_encounter_id(payload, evaluation_payload),
            identifier=identifiers,
            status=status,
            class_fhir=class_payload,
            encounter_type=[encounter_type_concept(encounter_type_code)],
            service_type=service_type_concept(service_type_code),
            subject=build_reference("Patient", patient_id),
            participant=participant,
            service_provider=build_reference("Organization", service_provider_id) if service_provider_id else None,
            period=compact_dict({"start": start, "end": end}),
            reason_code=[encounter_reason_concept(_resource_slug(wound_type or "wound-assessment"), reason_text)],
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
            component = _build_quantity_component(code, value, "%", "%")
            component["code"] = clinical_score_concept(tissue_key, code.get("display"))
            components.append(component)

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
            components[-1]["code"] = clinical_score_concept("wound-area", "Wound area")

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
                "code": clinical_score_concept("risk-level", "REDISUS risk level"),
                "valueCodeableConcept": risk_level_concept(risk_level),
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
            interpretation=[risk_level_concept(risk_level)],
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
            code=wound_classification_concept(etiology_code.lower()),
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
        media_resources: list[Mapping[str, Any]] | None = None,
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
        media_entries = []
        for media in media_resources or []:
            if not media.get("id"):
                continue
            media_entries.append(
                compact_dict(
                    {
                        "comment": str(
                            _first_non_empty(
                                (((media.get("content") or {}).get("title")) if isinstance(media.get("content"), Mapping) else None),
                                "Clinical wound media",
                            )
                        ),
                        "link": build_reference("Media", str(media.get("id"))),
                    }
                )
            )

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
            media=media_entries,
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
        scope = self._resolve_scope_context(practitioner_data, evaluation_data, encounter_data)

        organizations: list[dict[str, Any]] = []
        unit_organization = None
        if scope["unit_id"]:
            unit_organization = self.map_organization(
                {
                    "id": scope["unit_id"],
                    "name": scope["unit_name"] or scope["unit_id"],
                    "identifier": scope["unit_id"],
                    "scope_code": "health-unit",
                },
                kind="health-unit",
            )
            organizations.append(unit_organization)

        team_organization = None
        if scope["team_id"]:
            team_organization = self.map_organization(
                {
                    "id": scope["team_id"],
                    "name": scope["team_name"] or scope["team_id"],
                    "identifier": scope["team_id"],
                    "scope_code": "care-team",
                },
                kind="care-team",
                parent_organization_id=unit_organization["id"] if unit_organization else None,
            )
            organizations.append(team_organization)

        practitioner = None
        if self._has_practitioner_context(practitioner_data, evaluation_data):
            practitioner = self.map_practitioner(practitioner_data, evaluation_data=evaluation_data)

        primary_organization_id = (
            (team_organization or unit_organization or {}).get("id")
            if (team_organization or unit_organization)
            else None
        )
        practitioner_role = None
        if practitioner and self._has_practitioner_role_context(practitioner_data, evaluation_data, primary_organization_id):
            practitioner_role = self.map_practitioner_role(
                practitioner["id"],
                practitioner_data=practitioner_data,
                evaluation_data=evaluation_data,
                organization_id=primary_organization_id,
            )

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
                service_provider_id=(unit_organization or team_organization or {}).get("id") if (unit_organization or team_organization) else None,
            )
            encounter_id = encounter["id"]

        media_resources: list[dict[str, Any]] = []
        for index, image in enumerate(_extract_images(evaluation_data, inference_result, explicit_images=images)):
            try:
                media_resources.append(
                    self.map_media(
                        patient["id"],
                        image,
                        evaluation_data=evaluation_data,
                        practitioner_id=practitioner["id"] if practitioner else None,
                        encounter_id=encounter_id,
                        index=index,
                    )
                )
            except ValueError:
                continue

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
            media_resources=media_resources,
            practitioner_id=practitioner["id"] if practitioner else None,
            encounter_id=encounter_id,
        )

        resources: list[dict[str, Any]] = [patient]
        resources.extend(organizations)
        if practitioner:
            resources.append(practitioner)
        if practitioner_role:
            resources.append(practitioner_role)
        resources.append(condition)
        if encounter:
            resources.append(encounter)
        resources.extend(media_resources)
        resources.extend([observation, report])
        care_plan = None
        if care_plan_data:
            care_plan = self.map_care_plan(
                patient["id"],
                care_plan_data,
                condition=condition,
                practitioner_id=practitioner["id"] if practitioner else None,
                encounter_id=encounter_id,
            )
            resources.append(care_plan)

        provenance_targets: list[dict[str, Any]] = [condition]
        if encounter:
            provenance_targets.append(encounter)
        provenance_targets.extend(media_resources)
        provenance_targets.extend([observation, report])
        if care_plan:
            provenance_targets.append(care_plan)
        resources.append(
            self.map_provenance(
                target_resources=provenance_targets,
                evaluation_data=evaluation_data,
                inference_result=inference_result,
                practitioner_id=practitioner["id"] if practitioner else None,
                practitioner_role_id=practitioner_role["id"] if practitioner_role else None,
                organization_id=(unit_organization or team_organization or {}).get("id")
                if (unit_organization or team_organization)
                else None,
                media_resources=media_resources,
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
            "meta": {
                "lastUpdated": fhir_now(),
                "profile": [TARGET_PROFILE_REGISTRY["bundle-export"]],
            },
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

    def _has_practitioner_role_context(
        self,
        practitioner_data: Mapping[str, Any] | None,
        evaluation_data: Mapping[str, Any] | None,
        organization_id: str | None,
    ) -> bool:
        if organization_id:
            return True

        payload = dict(practitioner_data or {})
        evaluation_payload = dict(evaluation_data or {})
        payload_metadata = payload.get("metadata") if isinstance(payload.get("metadata"), Mapping) else {}
        evaluation_metadata = (
            evaluation_payload.get("metadata") if isinstance(evaluation_payload.get("metadata"), Mapping) else {}
        )
        candidates = (
            payload.get("role"),
            payload.get("professional_role"),
            payload_metadata.get("professional_role"),
            evaluation_payload.get("professional_role"),
            evaluation_metadata.get("professional_role"),
        )
        return self._has_practitioner_context(practitioner_data, evaluation_data) or any(
            str(value or "").strip() for value in candidates
        )

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

    def _resolve_scope_context(
        self,
        practitioner_data: Mapping[str, Any] | None,
        evaluation_data: Mapping[str, Any] | None,
        encounter_data: Mapping[str, Any] | None,
    ) -> dict[str, str | None]:
        sources = [
            dict(practitioner_data or {}),
            dict(encounter_data or {}),
            dict(evaluation_data or {}),
        ]
        metadata_sources = [
            source.get("metadata")
            for source in sources
            if isinstance(source.get("metadata"), Mapping)
        ]

        def _pick(*keys: str) -> str | None:
            values: list[Any] = []
            for source in sources:
                values.extend(source.get(key) for key in keys)
            for source in metadata_sources:
                values.extend(source.get(key) for key in keys)
            resolved = _first_non_empty(*values)
            return str(resolved).strip() if str(resolved or "").strip() else None

        unit_id = _pick("unit_id", "unit", "facility_id", "service_provider_id")
        unit_name = _pick("unit_name", "unit_display", "unit_label", "facility_name", "service_provider_name")
        team_id = _pick("team_id", "team", "care_team_id")
        team_name = _pick("team_name", "team_display", "team_label", "care_team_name")

        return {
            "unit_id": unit_id,
            "unit_name": unit_name or unit_id,
            "team_id": team_id,
            "team_name": team_name or team_id,
        }

    def _resolve_organization_id(self, organization_data: Mapping[str, Any], kind: str) -> str:
        payload = dict(organization_data or {})
        normalized_kind = _resource_slug(kind) or "organization"
        return _stable_resource_id(
            f"organization-{normalized_kind}",
            payload.get("id"),
            payload.get("identifier"),
            payload.get("unit_id"),
            payload.get("team_id"),
            payload.get("name"),
            payload.get("display_name"),
        )

    def _resolve_practitioner_role_id(
        self,
        practitioner_data: Mapping[str, Any] | None,
        evaluation_data: Mapping[str, Any] | None,
        *,
        organization_id: str | None = None,
    ) -> str:
        payload = dict(practitioner_data or {})
        evaluation_payload = dict(evaluation_data or {})
        payload_metadata = payload.get("metadata") if isinstance(payload.get("metadata"), Mapping) else {}
        evaluation_metadata = (
            evaluation_payload.get("metadata") if isinstance(evaluation_payload.get("metadata"), Mapping) else {}
        )
        return _stable_resource_id(
            "practitioner-role",
            payload.get("role_id"),
            evaluation_payload.get("role_id"),
            payload.get("id"),
            payload.get("practitioner_id"),
            evaluation_payload.get("professional_id"),
            organization_id,
            payload.get("role"),
            payload.get("professional_role"),
            payload_metadata.get("professional_role"),
            evaluation_payload.get("professional_role"),
            evaluation_metadata.get("professional_role"),
        )

    def _resolve_media_id(
        self,
        image_data: Mapping[str, Any] | None,
        evaluation_data: Mapping[str, Any] | None,
        *,
        index: int = 0,
    ) -> str:
        payload = dict(image_data or {})
        evaluation_payload = dict(evaluation_data or {})
        return _stable_resource_id(
            "media",
            payload.get("id"),
            payload.get("image_id"),
            payload.get("storage_key"),
            payload.get("url"),
            payload.get("image_path"),
            f"{evaluation_payload.get('id') or evaluation_payload.get('case_id') or 'evaluation'}-{index + 1}",
        )

    def _resolve_provenance_id(
        self,
        evaluation_data: Mapping[str, Any] | None,
        inference_result: Mapping[str, Any] | None,
        target_resources: list[Mapping[str, Any]],
    ) -> str:
        evaluation_payload = dict(evaluation_data or {})
        inference_payload = dict(inference_result or {})
        target_signature = ",".join(
            f"{resource.get('resourceType')}:{resource.get('id')}"
            for resource in target_resources
            if resource.get("resourceType") and resource.get("id")
        )
        return _stable_resource_id(
            "provenance",
            evaluation_payload.get("id"),
            inference_payload.get("evaluation_id"),
            inference_payload.get("case_id"),
            inference_payload.get("generated_at"),
            target_signature,
        )

    def _validate_resource(self, resource: Mapping[str, Any]) -> None:
        validate_resource(resource, strict=self.strict_validation)

    def _validate_bundle(self, bundle: Mapping[str, Any]) -> None:
        validate_bundle(bundle, strict=self.strict_validation)
