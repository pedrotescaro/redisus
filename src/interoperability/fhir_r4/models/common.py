from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, ClassVar
from uuid import uuid4

FHIR_VERSION = "4.0.1"
REDISUS_FHIR_BASE = "https://heal.redisus.org.br/fhir"
REDISUS_CODE_SYSTEM = f"{REDISUS_FHIR_BASE}/CodeSystem"
REDISUS_STRUCTURE_DEFINITION = f"{REDISUS_FHIR_BASE}/StructureDefinition"

LOINC_SYSTEM = "http://loinc.org"
SNOMED_SYSTEM = "http://snomed.info/sct"
ICD10_SYSTEM = "http://hl7.org/fhir/sid/icd-10"
UCUM_SYSTEM = "http://unitsofmeasure.org"

BR_PATIENT_PROFILE = "http://www.saude.gov.br/fhir/r4/StructureDefinition/BRIndividuo-1.0"


def fhir_now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def generate_id(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:12]}"


def build_identifier(system: str, value: str, use: str | None = "official") -> dict[str, Any]:
    payload: dict[str, Any] = {"system": system, "value": value}
    if use:
        payload["use"] = use
    return payload


def build_reference(resource_type: str, resource_id: str | None) -> dict[str, str]:
    if not resource_id:
        raise ValueError(f"{resource_type} reference requires a resource id")
    if "/" in resource_id:
        return {"reference": resource_id}
    return {"reference": f"{resource_type}/{resource_id}"}


def compact_dict(data: dict[str, Any]) -> dict[str, Any]:
    compacted: dict[str, Any] = {}
    for key, value in data.items():
        if value is None:
            continue
        if value == "":
            continue
        if isinstance(value, list) and not value:
            continue
        if isinstance(value, dict) and not value:
            continue
        compacted[key] = value
    return compacted


@dataclass(slots=True)
class FHIRResourceModel:
    id: str
    meta: dict[str, Any] = field(default_factory=lambda: {"lastUpdated": fhir_now()})

    resource_type: ClassVar[str]

    def base_dict(self) -> dict[str, Any]:
        return {
            "resourceType": self.resource_type,
            "id": self.id,
            "meta": self.meta,
        }

    def as_reference(self) -> dict[str, str]:
        return {"reference": f"{self.resource_type}/{self.id}"}

