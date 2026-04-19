from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .common import FHIRResourceModel, compact_dict


@dataclass(slots=True)
class ConditionResource(FHIRResourceModel):
    resource_type = "Condition"

    clinical_status: dict[str, Any] = field(default_factory=dict)
    verification_status: dict[str, Any] = field(default_factory=dict)
    category: list[dict[str, Any]] = field(default_factory=list)
    severity: dict[str, Any] | None = None
    code: dict[str, Any] = field(default_factory=dict)
    subject: dict[str, Any] = field(default_factory=dict)
    encounter: dict[str, Any] | None = None
    recorder: dict[str, Any] | None = None
    body_site: list[dict[str, Any]] = field(default_factory=list)
    onset_date_time: str | None = None
    recorded_date: str | None = None
    note: list[dict[str, Any]] = field(default_factory=list)
    extension: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return compact_dict(
            {
                **self.base_dict(),
                "clinicalStatus": self.clinical_status,
                "verificationStatus": self.verification_status,
                "category": self.category,
                "severity": self.severity,
                "code": self.code,
                "subject": self.subject,
                "encounter": self.encounter,
                "recorder": self.recorder,
                "bodySite": self.body_site,
                "onsetDateTime": self.onset_date_time,
                "recordedDate": self.recorded_date,
                "note": self.note,
                "extension": self.extension,
            }
        )
