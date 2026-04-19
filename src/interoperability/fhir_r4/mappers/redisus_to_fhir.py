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
    ObservationResource,
    PatientResource,
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

    def map_observation(
        self,
        patient_id: str,
        *,
        evaluation_data: Mapping[str, Any] | None = None,
        inference_result: Mapping[str, Any] | None = None,
        practitioner_id: str | None = None,
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
        images: list[Any] | None = None,
        bundle_type: str = "collection",
    ) -> dict[str, Any]:
        patient = self.map_patient(patient_data)
        observation = self.map_observation(
            patient["id"],
            evaluation_data=evaluation_data,
            inference_result=inference_result,
        )
        condition = self.map_condition(
            patient["id"],
            evaluation_data=evaluation_data,
            inference_result=inference_result,
        )
        report = self.map_diagnostic_report(
            patient["id"],
            observation=observation,
            condition=condition,
            evaluation_data=evaluation_data,
            inference_result=inference_result,
            images=images,
        )

        resources: list[dict[str, Any]] = [patient, observation, condition, report]
        if care_plan_data:
            resources.append(self.map_care_plan(patient["id"], care_plan_data, condition=condition))
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

    def _validate_resource(self, resource: Mapping[str, Any]) -> None:
        validate_resource(resource, strict=self.strict_validation)

    def _validate_bundle(self, bundle: Mapping[str, Any]) -> None:
        validate_bundle(bundle, strict=self.strict_validation)
