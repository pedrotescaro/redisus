from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .common import FHIRResourceModel, REDISUS_PRACTITIONER_ROLE_PROFILE, compact_dict, ensure_meta_profile


@dataclass(slots=True)
class PractitionerRoleResource(FHIRResourceModel):
    resource_type = "PractitionerRole"

    identifier: list[dict[str, Any]] = field(default_factory=list)
    active: bool = True
    period: dict[str, Any] | None = None
    practitioner: dict[str, Any] | None = None
    organization: dict[str, Any] | None = None
    code: list[dict[str, Any]] = field(default_factory=list)
    specialty: list[dict[str, Any]] = field(default_factory=list)
    telecom: list[dict[str, Any]] = field(default_factory=list)
    available_time: list[dict[str, Any]] = field(default_factory=list)
    extension: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        meta = ensure_meta_profile(self.meta, REDISUS_PRACTITIONER_ROLE_PROFILE)
        return compact_dict(
            {
                **self.base_dict(),
                "meta": meta,
                "identifier": self.identifier,
                "active": self.active,
                "period": self.period,
                "practitioner": self.practitioner,
                "organization": self.organization,
                "code": self.code,
                "specialty": self.specialty,
                "telecom": self.telecom,
                "availableTime": self.available_time,
                "extension": self.extension,
            }
        )
