from __future__ import annotations

from typing import Any, Mapping

REQUIRED_FIELDS: dict[str, tuple[str, ...]] = {
    "Patient": ("resourceType", "id", "name"),
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

    if resource_type == "Patient":
        name = payload.get("name") or []
        if not isinstance(name, list):
            errors.append("Patient.name must be a list")

    if resource_type in {"Observation", "Condition", "DiagnosticReport", "CarePlan"}:
        subject = payload.get("subject") or {}
        if not isinstance(subject, Mapping) or not str(subject.get("reference") or "").strip():
            errors.append(f"{resource_type}.subject.reference is required")

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

