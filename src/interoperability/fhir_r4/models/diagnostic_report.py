from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .common import FHIRResourceModel, REDISUS_DIAGNOSTIC_REPORT_PROFILE, compact_dict, ensure_meta_profile


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
    media: list[dict[str, Any]] = field(default_factory=list)
    presented_form: list[dict[str, Any]] = field(default_factory=list)
    note: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        meta = ensure_meta_profile(self.meta, REDISUS_DIAGNOSTIC_REPORT_PROFILE)
        return compact_dict(
            {
                **self.base_dict(),
                "meta": meta,
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
                "media": self.media,
                "presentedForm": self.presented_form,
                "note": self.note,
            }
        )
