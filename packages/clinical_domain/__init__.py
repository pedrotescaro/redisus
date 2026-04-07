from __future__ import annotations

from .database import AnalysisRecord, Database, PatientRecord
from .models import (
    AlertRecord,
    AssessmentRecord,
    CarePlanRecord,
    ClinicalImageRecord,
    InferenceResultRecord,
    LesionRecord,
    FollowUpRecord,
)

__all__ = [
    "AlertRecord",
    "AnalysisRecord",
    "AssessmentRecord",
    "CarePlanRecord",
    "ClinicalImageRecord",
    "ClinicalAPI",
    "ClinicalDashboard",
    "Database",
    "FollowUpRecord",
    "InferenceResultRecord",
    "LesionRecord",
    "PatientRecord",
]


def __getattr__(name: str):
    if name in {"ClinicalAPI", "ClinicalDashboard"}:
        from .api import ClinicalAPI, ClinicalDashboard

        exports = {
            "ClinicalAPI": ClinicalAPI,
            "ClinicalDashboard": ClinicalDashboard,
        }
        return exports[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
