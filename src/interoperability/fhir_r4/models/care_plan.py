from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .common import FHIRResourceModel, compact_dict


@dataclass(slots=True)
class CarePlanResource(FHIRResourceModel):
    resource_type = "CarePlan"

    status: str = "active"
    intent: str = "plan"
    title: str | None = None
    description: str | None = None
    subject: dict[str, Any] = field(default_factory=dict)
    encounter: dict[str, Any] | None = None
    author: dict[str, Any] | None = None
    created: str | None = None
    period: dict[str, Any] | None = None
    addresses: list[dict[str, Any]] = field(default_factory=list)
    activity: list[dict[str, Any]] = field(default_factory=list)
    note: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return compact_dict(
            {
                **self.base_dict(),
                "status": self.status,
                "intent": self.intent,
                "title": self.title,
                "description": self.description,
                "subject": self.subject,
                "encounter": self.encounter,
                "author": self.author,
                "created": self.created,
                "period": self.period,
                "addresses": self.addresses,
                "activity": self.activity,
                "note": self.note,
            }
        )
