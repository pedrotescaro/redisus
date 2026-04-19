from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .common import FHIRResourceModel, compact_dict


@dataclass(slots=True)
class DiagnosticReportResource(FHIRResourceModel):
    resource_type = "DiagnosticReport"

    status: str = "final"
    category: list[dict[str, Any]] = field(default_factory=list)
    code: dict[str, Any] = field(default_factory=dict)
    subject: dict[str, Any] = field(default_factory=dict)
    encounter: dict[str, Any] | None = None
    effective_date_time: str | None = None
    issued: str | None = None
    performer: list[dict[str, Any]] = field(default_factory=list)
    result: list[dict[str, Any]] = field(default_factory=list)
    conclusion: str | None = None
    conclusion_code: list[dict[str, Any]] = field(default_factory=list)
    presented_form: list[dict[str, Any]] = field(default_factory=list)
    note: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return compact_dict(
            {
                **self.base_dict(),
                "status": self.status,
                "category": self.category,
                "code": self.code,
                "subject": self.subject,
                "encounter": self.encounter,
                "effectiveDateTime": self.effective_date_time,
                "issued": self.issued,
                "performer": self.performer,
                "result": self.result,
                "conclusion": self.conclusion,
                "conclusionCode": self.conclusion_code,
                "presentedForm": self.presented_form,
                "note": self.note,
            }
        )
