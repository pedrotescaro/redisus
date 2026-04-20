from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .common import FHIRResourceModel, REDISUS_MEDIA_PROFILE, compact_dict, ensure_meta_profile


@dataclass(slots=True)
class MediaResource(FHIRResourceModel):
    resource_type = "Media"

    identifier: list[dict[str, Any]] = field(default_factory=list)
    status: str = "completed"
    media_type: str | None = None
    modality: dict[str, Any] | None = None
    subject: dict[str, Any] = field(default_factory=dict)
    encounter: dict[str, Any] | None = None
    created_date_time: str | None = None
    operator: dict[str, Any] | None = None
    reason_code: list[dict[str, Any]] = field(default_factory=list)
    body_site: dict[str, Any] | None = None
    content: dict[str, Any] = field(default_factory=dict)
    note: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        meta = ensure_meta_profile(self.meta, REDISUS_MEDIA_PROFILE)
        return compact_dict(
            {
                **self.base_dict(),
                "meta": meta,
                "identifier": self.identifier,
                "status": self.status,
                "type": self.media_type,
                "modality": self.modality,
                "subject": self.subject,
                "encounter": self.encounter,
                "createdDateTime": self.created_date_time,
                "operator": self.operator,
                "reasonCode": self.reason_code,
                "bodySite": self.body_site,
                "content": self.content,
                "note": self.note,
            }
        )
