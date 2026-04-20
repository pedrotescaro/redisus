from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .common import FHIRResourceModel, REDISUS_ORGANIZATION_PROFILE, compact_dict, ensure_meta_profile


@dataclass(slots=True)
class OrganizationResource(FHIRResourceModel):
    resource_type = "Organization"

    identifier: list[dict[str, Any]] = field(default_factory=list)
    active: bool = True
    organization_type: list[dict[str, Any]] = field(default_factory=list)
    name: str | None = None
    alias: list[str] = field(default_factory=list)
    part_of: dict[str, Any] | None = None
    telecom: list[dict[str, Any]] = field(default_factory=list)
    address: list[dict[str, Any]] = field(default_factory=list)
    extension: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        meta = ensure_meta_profile(self.meta, REDISUS_ORGANIZATION_PROFILE)
        return compact_dict(
            {
                **self.base_dict(),
                "meta": meta,
                "identifier": self.identifier,
                "active": self.active,
                "type": self.organization_type,
                "name": self.name,
                "alias": self.alias,
                "partOf": self.part_of,
                "telecom": self.telecom,
                "address": self.address,
                "extension": self.extension,
            }
        )
