"""Canonical wrappers for clinical API modules."""

from packages.shared.runtime import ensure_project_root_on_path

ensure_project_root_on_path()

from src.dashboard.clinical_api import ClinicalAPI  # noqa: E402
from src.dashboard.clinical_dashboard import ClinicalDashboard  # noqa: E402

__all__ = ["ClinicalAPI", "ClinicalDashboard"]
