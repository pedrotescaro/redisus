from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .common import FHIRResourceModel, compact_dict


@dataclass(slots=True)
class ObservationResource(FHIRResourceModel):
    resource_type = "Observation"

    status: str = "final"
    category: list[dict[str, Any]] = field(default_factory=list)
    code: dict[str, Any] = field(default_factory=dict)
    subject: dict[str, Any] = field(default_factory=dict)
    effective_date_time: str | None = None
    issued: str | None = None
    performer: list[dict[str, Any]] = field(default_factory=list)
    body_site: dict[str, Any] | None = None
    method: dict[str, Any] | None = None
    component: list[dict[str, Any]] = field(default_factory=list)
    note: list[dict[str, Any]] = field(default_factory=list)
    interpretation: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return compact_dict(
            {
                **self.base_dict(),
                "status": self.status,
                "category": self.category,
                "code": self.code,
                "subject": self.subject,
                "effectiveDateTime": self.effective_date_time,
                "issued": self.issued,
                "performer": self.performer,
                "bodySite": self.body_site,
                "method": self.method,
                "component": self.component,
                "note": self.note,
                "interpretation": self.interpretation,
            }
        )
