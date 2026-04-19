from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .common import BR_PATIENT_PROFILE, FHIRResourceModel, compact_dict


@dataclass(slots=True)
class PatientResource(FHIRResourceModel):
    resource_type = "Patient"

    identifier: list[dict[str, Any]] = field(default_factory=list)
    active: bool = True
    name: list[dict[str, Any]] = field(default_factory=list)
    gender: str = "unknown"
    birth_date: str | None = None
    telecom: list[dict[str, Any]] = field(default_factory=list)
    address: list[dict[str, Any]] = field(default_factory=list)
    extension: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        meta = dict(self.meta)
        profiles = list(meta.get("profile") or [])
        if BR_PATIENT_PROFILE not in profiles:
            profiles.append(BR_PATIENT_PROFILE)
        meta["profile"] = profiles
        return compact_dict(
            {
                **self.base_dict(),
                "meta": meta,
                "identifier": self.identifier,
                "active": self.active,
                "name": self.name,
                "gender": self.gender,
                "birthDate": self.birth_date,
                "telecom": self.telecom,
                "address": self.address,
                "extension": self.extension,
            }
        )

