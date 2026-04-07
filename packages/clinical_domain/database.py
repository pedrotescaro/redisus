"""Canonical wrappers for database models and manager."""

from packages.shared.runtime import ensure_project_root_on_path

ensure_project_root_on_path()

from src.data.database import AnalysisRecord, Database, PatientRecord  # noqa: E402

__all__ = ["AnalysisRecord", "Database", "PatientRecord"]
