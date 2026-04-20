from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .common import FHIRResourceModel, REDISUS_PROVENANCE_PROFILE, compact_dict, ensure_meta_profile


@dataclass(slots=True)
class ProvenanceResource(FHIRResourceModel):
    resource_type = "Provenance"

    target: list[dict[str, Any]] = field(default_factory=list)
    recorded: str | None = None
    reason: list[dict[str, Any]] = field(default_factory=list)
    activity: dict[str, Any] | None = None
    agent: list[dict[str, Any]] = field(default_factory=list)
    entity: list[dict[str, Any]] = field(default_factory=list)
    signature: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        meta = ensure_meta_profile(self.meta, REDISUS_PROVENANCE_PROFILE)
        return compact_dict(
            {
                **self.base_dict(),
                "meta": meta,
                "target": self.target,
                "recorded": self.recorded,
                "reason": self.reason,
                "activity": self.activity,
                "agent": self.agent,
                "entity": self.entity,
                "signature": self.signature,
            }
        )
