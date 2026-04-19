from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .common import FHIRResourceModel, compact_dict


@dataclass(slots=True)
class EncounterResource(FHIRResourceModel):
    resource_type = "Encounter"

    identifier: list[dict[str, Any]] = field(default_factory=list)
    status: str = "finished"
    class_fhir: dict[str, Any] = field(default_factory=dict)
    encounter_type: list[dict[str, Any]] = field(default_factory=list)
    service_type: dict[str, Any] | None = None
    subject: dict[str, Any] = field(default_factory=dict)
    participant: list[dict[str, Any]] = field(default_factory=list)
    period: dict[str, Any] | None = None
    reason_code: list[dict[str, Any]] = field(default_factory=list)
    diagnosis: list[dict[str, Any]] = field(default_factory=list)
    note: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return compact_dict(
            {
                **self.base_dict(),
                "identifier": self.identifier,
                "status": self.status,
                "class": self.class_fhir,
                "type": self.encounter_type,
                "serviceType": self.service_type,
                "subject": self.subject,
                "participant": self.participant,
                "period": self.period,
                "reasonCode": self.reason_code,
                "diagnosis": self.diagnosis,
                "note": self.note,
            }
        )
