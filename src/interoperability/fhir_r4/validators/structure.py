from __future__ import annotations

from typing import Any, Mapping

REQUIRED_FIELDS: dict[str, tuple[str, ...]] = {
    "Patient": ("resourceType", "id", "name"),
    "Organization": ("resourceType", "id", "name"),
    "Practitioner": ("resourceType", "id", "name"),
    "PractitionerRole": ("resourceType", "id"),
    "Encounter": ("resourceType", "id", "status", "class", "subject"),
    "Media": ("resourceType", "id", "status", "content", "subject"),
    "Provenance": ("resourceType", "id", "target", "recorded", "agent"),
    "Observation": ("resourceType", "id", "status", "code", "subject"),
    "Condition": ("resourceType", "id", "clinicalStatus", "verificationStatus", "code", "subject"),
    "DiagnosticReport": ("resourceType", "id", "status", "code", "subject"),
    "CarePlan": ("resourceType", "id", "status", "intent", "subject"),
    "Bundle": ("resourceType", "type", "entry"),
}


class FHIRValidationError(ValueError):
    pass


def _require_mapping(resource: Mapping[str, Any] | Any) -> Mapping[str, Any]:
    if not isinstance(resource, Mapping):
        raise FHIRValidationError("FHIR payload must be a mapping")
    return resource


def validate_resource_structure(resource: Mapping[str, Any] | Any) -> list[str]:
    payload = _require_mapping(resource)
    resource_type = str(payload.get("resourceType") or "").strip()
    if not resource_type:
        return ["resourceType is required"]

    errors: list[str] = []
    for field_name in REQUIRED_FIELDS.get(resource_type, ("resourceType",)):
        value = payload.get(field_name)
        if value is None or value == "" or value == [] or value == {}:
            errors.append(f"{resource_type}.{field_name} is required")

    if resource_type in {"Patient", "Practitioner"}:
        name = payload.get("name") or []
        if not isinstance(name, list):
            errors.append(f"{resource_type}.name must be a list")

    if resource_type == "Organization":
        name = str(payload.get("name") or "").strip()
        if not name:
            errors.append("Organization.name is required")

    if resource_type in {"Observation", "Condition", "DiagnosticReport", "CarePlan", "Encounter", "Media"}:
        subject = payload.get("subject") or {}
        if not isinstance(subject, Mapping) or not str(subject.get("reference") or "").strip():
            errors.append(f"{resource_type}.subject.reference is required")

    if resource_type == "PractitionerRole":
        practitioner = payload.get("practitioner")
        organization = payload.get("organization")
        if not practitioner and not organization:
            errors.append("PractitionerRole.practitioner or PractitionerRole.organization is required")

    if resource_type == "Media":
        content = payload.get("content") or {}
        if not isinstance(content, Mapping):
            errors.append("Media.content must be a mapping")
        elif not (
            str(content.get("url") or "").strip()
            or str(content.get("data") or "").strip()
            or str(content.get("title") or "").strip()
        ):
            errors.append("Media.content must include url, data, or title")

    if resource_type == "Provenance":
        target = payload.get("target") or []
        if not isinstance(target, list) or not target:
            errors.append("Provenance.target must be a non-empty list")
        agent = payload.get("agent") or []
        if not isinstance(agent, list) or not agent:
            errors.append("Provenance.agent must be a non-empty list")

    if resource_type == "Encounter":
        class_payload = payload.get("class") or {}
        if not isinstance(class_payload, Mapping) or not str(class_payload.get("code") or "").strip():
            errors.append("Encounter.class.code is required")

    if resource_type == "Bundle":
        entry = payload.get("entry") or []
        if not isinstance(entry, list) or not entry:
            errors.append("Bundle.entry must be a non-empty list")
        for index, item in enumerate(entry):
            if not isinstance(item, Mapping):
                errors.append(f"Bundle.entry[{index}] must be a mapping")
                continue
            if "resource" not in item:
                errors.append(f"Bundle.entry[{index}].resource is required")

    return errors


def validate_with_fhir_models(resource: Mapping[str, Any] | Any) -> list[str]:
    payload = _require_mapping(resource)
    resource_type = str(payload.get("resourceType") or "").strip()
    if not resource_type:
        return ["resourceType is required"]

    model_map = {
        "Patient": ("fhir.resources.patient", "Patient"),
        "Organization": ("fhir.resources.organization", "Organization"),
        "Practitioner": ("fhir.resources.practitioner", "Practitioner"),
        "PractitionerRole": ("fhir.resources.practitionerrole", "PractitionerRole"),
        "Encounter": ("fhir.resources.encounter", "Encounter"),
        "Media": ("fhir.resources.media", "Media"),
        "Provenance": ("fhir.resources.provenance", "Provenance"),
        "Observation": ("fhir.resources.observation", "Observation"),
        "Condition": ("fhir.resources.condition", "Condition"),
        "DiagnosticReport": ("fhir.resources.diagnosticreport", "DiagnosticReport"),
        "CarePlan": ("fhir.resources.careplan", "CarePlan"),
        "Bundle": ("fhir.resources.bundle", "Bundle"),
    }
    module_info = model_map.get(resource_type)
    if not module_info:
        return []

    try:
        module = __import__(module_info[0], fromlist=[module_info[1]])
        model_class = getattr(module, module_info[1])
        model_class.model_validate(dict(payload))
        return []
    except ModuleNotFoundError:
        return []
    except Exception as exc:  # pragma: no cover - depends on optional library internals
        return [str(exc)]


def validate_resource(resource: Mapping[str, Any] | Any, strict: bool = True) -> None:
    errors = validate_resource_structure(resource)
    if strict:
        errors.extend(validate_with_fhir_models(resource))
    if errors:
        raise FHIRValidationError("; ".join(errors))


def validate_bundle(bundle: Mapping[str, Any] | Any, strict: bool = True) -> None:
    validate_resource(bundle, strict=strict)
    payload = _require_mapping(bundle)
    for item in payload.get("entry") or []:
        validate_resource(item.get("resource"), strict=strict)
