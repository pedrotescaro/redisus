from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .common import FHIRResourceModel, compact_dict


@dataclass(slots=True)
class PractitionerResource(FHIRResourceModel):
    resource_type = "Practitioner"

    identifier: list[dict[str, Any]] = field(default_factory=list)
    active: bool = True
    name: list[dict[str, Any]] = field(default_factory=list)
    telecom: list[dict[str, Any]] = field(default_factory=list)
    qualification: list[dict[str, Any]] = field(default_factory=list)
    extension: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return compact_dict(
            {
                **self.base_dict(),
                "identifier": self.identifier,
                "active": self.active,
                "name": self.name,
                "telecom": self.telecom,
                "qualification": self.qualification,
                "extension": self.extension,
            }
        )
