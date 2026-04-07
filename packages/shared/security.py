"""Shared security helpers for backend zero-trust enforcement."""

from __future__ import annotations

import os
import threading
import time
from typing import Any, Callable, Mapping, Sequence

from flask import abort, current_app, g, request

ADMIN_ROLES = {"admin", "superadmin", "security-admin", "clinical-admin"}
CLINICAL_ROLES = {
    "admin",
    "superadmin",
    "security-admin",
    "clinical-admin",
    "clinician",
    "nurse",
    "doctor",
    "estomaterapeuta",
}
RESEARCH_ROLES = {"researcher"}
PATIENT_SCOPED_ROLES = CLINICAL_ROLES | RESEARCH_ROLES
CLINICAL_WRITE_ROLES = CLINICAL_ROLES

_RATE_LIMIT_STATE: dict[tuple[str, str], list[float]] = {}
_RATE_LIMIT_LOCK = threading.Lock()


def _env_flag(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() not in {"0", "false", "no", "off"}


def auth_required() -> bool:
    return _env_flag("CLINICAL_API_REQUIRE_AUTH", True)


def auth_disabled() -> bool:
    return not auth_required()


def allow_legacy_unscoped_patient_access() -> bool:
    return _env_flag("REDISUS_ALLOW_LEGACY_UNSCOPED_PATIENT_ACCESS", False)


def _normalize_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray, str)):
        return [str(item).strip() for item in value if str(item).strip()]
    return [str(value).strip()] if str(value).strip() else []


def current_user() -> dict[str, Any] | None:
    user = getattr(g, "redisus_user", None)
    if user is None and auth_disabled():
        user = {"uid": "local-dev", "roles": ["local-dev"], "auth_disabled": True}
        g.redisus_user = user
        g.redisus_auth_disabled = True
    return user


def current_user_required() -> dict[str, Any]:
    user = current_user()
    if user is None:
        abort(401, description="authentication required")
    return user


def user_uid(user: Mapping[str, Any] | None) -> str | None:
    if not user:
        return None
    for key in ("uid", "user_id", "sub"):
        value = user.get(key)
        if value:
            return str(value)
    return None


def user_display_name(user: Mapping[str, Any] | None) -> str:
    if not user:
        return "system"
    for key in ("name", "display_name", "email", "uid", "sub"):
        value = user.get(key)
        if value:
            return str(value)
    return "system"


def user_roles(user: Mapping[str, Any] | None) -> set[str]:
    if auth_disabled():
        return {"admin", "local-dev"}
    if not user:
        return set()

    roles: list[str] = []
    for key in ("roles", "redisus_roles", "patient_roles"):
        roles.extend(_normalize_list(user.get(key)))

    for key in ("role", "redisus_role"):
        value = user.get(key)
        if value:
            roles.append(str(value))

    claims = user.get("claims")
    if isinstance(claims, Mapping):
        roles.extend(_normalize_list(claims.get("roles")))
        if claims.get("role"):
            roles.append(str(claims["role"]))

    if user.get("admin") is True:
        roles.append("admin")

    return {role.strip().lower() for role in roles if role and str(role).strip()}


def user_units(user: Mapping[str, Any] | None) -> set[str]:
    if not user:
        return set()

    units: list[str] = []
    for key in ("unit_ids", "allowed_unit_ids"):
        units.extend(_normalize_list(user.get(key)))
    for key in ("unit_id", "unit"):
        value = user.get(key)
        if value:
            units.append(str(value))

    claims = user.get("claims")
    if isinstance(claims, Mapping):
        units.extend(_normalize_list(claims.get("unit_ids")))
        if claims.get("unit_id"):
            units.append(str(claims["unit_id"]))

    return {unit.strip() for unit in units if unit and str(unit).strip()}


def is_admin(user: Mapping[str, Any] | None = None) -> bool:
    if auth_disabled():
        return True
    return bool(user_roles(user or current_user()) & ADMIN_ROLES)


def is_clinical_user(user: Mapping[str, Any] | None = None) -> bool:
    if auth_disabled():
        return True
    return bool(user_roles(user or current_user()) & CLINICAL_ROLES)


def has_patient_scope_access(user: Mapping[str, Any] | None = None) -> bool:
    if auth_disabled():
        return True
    return bool(user_roles(user or current_user()) & PATIENT_SCOPED_ROLES)


def can_write_clinical_data(user: Mapping[str, Any] | None = None) -> bool:
    if auth_disabled():
        return True
    return bool(user_roles(user or current_user()) & CLINICAL_WRITE_ROLES)


def _extract_metadata(obj: Any) -> dict[str, Any]:
    if obj is None:
        return {}
    if isinstance(obj, Mapping):
        metadata = obj.get("metadata")
        return dict(metadata) if isinstance(metadata, Mapping) else {}
    metadata = getattr(obj, "metadata", {})
    return dict(metadata) if isinstance(metadata, Mapping) else {}


def _extract_identifier(obj: Any, field: str = "id") -> str | None:
    if obj is None:
        return None
    if isinstance(obj, Mapping):
        value = obj.get(field)
        return str(value) if value else None
    value = getattr(obj, field, None)
    return str(value) if value else None


def can_access_patient_record(user: Mapping[str, Any] | None, patient: Any) -> bool:
    if auth_disabled():
        return True
    if is_admin(user):
        return True
    if not patient or not user:
        return False

    uid = user_uid(user)
    if not uid:
        return False

    metadata = _extract_metadata(patient)
    patient_id = _extract_identifier(patient, "id")

    direct_user_fields = (
        "owner_uid",
        "created_by",
        "assigned_user_id",
        "assigned_uid",
        "responsible_uid",
    )
    for field in direct_user_fields:
        if metadata.get(field) and str(metadata[field]) == uid:
            return True

    list_user_fields = ("assigned_user_ids", "allowed_user_ids", "team_user_ids", "care_team_user_ids")
    for field in list_user_fields:
        if uid in _normalize_list(metadata.get(field)):
            return True

    claim_patient_ids = {
        *(_normalize_list(user.get("patient_ids"))),
        *(_normalize_list((user.get("claims") or {}).get("patient_ids") if isinstance(user.get("claims"), Mapping) else [])),
    }
    if patient_id and patient_id in claim_patient_ids:
        return True

    metadata_units = {
        *(_normalize_list(metadata.get("unit_id"))),
        *(_normalize_list(metadata.get("unit_ids"))),
        *(_normalize_list(metadata.get("allowed_unit_ids"))),
    }
    if metadata_units and user_units(user) & metadata_units and has_patient_scope_access(user):
        return True

    return allow_legacy_unscoped_patient_access() and not metadata


def filter_patients_for_user(patients: Sequence[Any], user: Mapping[str, Any] | None = None) -> list[Any]:
    user = user or current_user()
    if auth_disabled() or is_admin(user):
        return list(patients)
    return [patient for patient in patients if can_access_patient_record(user, patient)]


def ensure_admin_access(user: Mapping[str, Any] | None = None) -> dict[str, Any]:
    user = user or current_user_required()
    if not is_admin(user):
        abort(403, description="admin access required")
    return dict(user)


def ensure_clinical_write_access(
    user: Mapping[str, Any] | None = None,
    *,
    action: str = "write clinical data",
) -> dict[str, Any]:
    user = user or current_user_required()
    if not can_write_clinical_data(user):
        abort(403, description=f"{action} requires nurse, doctor, or admin role")
    return dict(user)


def ensure_patient_access(database: Any, patient_id: str, user: Mapping[str, Any] | None = None) -> Any:
    user = user or current_user_required()
    patient = database.get_patient(patient_id)
    if not patient:
        abort(404, description="patient not found")
    if not can_access_patient_record(user, patient):
        abort(403, description="patient access denied")
    return patient


def ensure_evaluation_access(database: Any, evaluation_id: str, user: Mapping[str, Any] | None = None) -> dict[str, Any]:
    user = user or current_user_required()
    evaluation = database.get_wound_evaluation(evaluation_id)
    if not evaluation:
        abort(404, description="evaluation not found")
    ensure_patient_access(database, str(evaluation["patient_id"]), user=user)
    return evaluation


def ensure_job_access(database: Any, job_id: str, user: Mapping[str, Any] | None = None) -> dict[str, Any]:
    user = user or current_user_required()
    run = database.get_ai_run(job_id)
    if not run:
        abort(404, description="analysis job not found")
    ensure_evaluation_access(database, str(run["evaluation_id"]), user=user)
    return run


def ensure_report_access(database: Any, report_id: str, user: Mapping[str, Any] | None = None) -> dict[str, Any]:
    user = user or current_user_required()
    report = database.get_structured_report(report_id)
    if not report:
        abort(404, description="report not found")
    ensure_patient_access(database, str(report["patient_id"]), user=user)
    return report


def ensure_case_access(database: Any, case_id: str, user: Mapping[str, Any] | None = None) -> dict[str, Any]:
    user = user or current_user_required()
    wound_case = database.get_wound_case(case_id)
    if not wound_case:
        abort(404, description="lesion not found")
    ensure_patient_access(database, str(wound_case["patient_id"]), user=user)
    return wound_case


def enforce_request_auth(auth_verifier: Any | None = None) -> dict[str, Any] | None:
    if auth_disabled():
        return current_user()

    existing = getattr(g, "redisus_user", None)
    if existing is not None:
        return existing

    verifier = auth_verifier
    if verifier is None:
        verifier = current_app.config.get("REDISUS_AUTH_VERIFIER")
    if verifier is None:
        verifier = current_app.extensions.get("redisus_auth_verifier")

    if verifier is None:
        abort(503, description="authentication backend unavailable")

    auth_header = request.headers.get("Authorization", "").strip()
    if not auth_header.startswith("Bearer "):
        abort(401, description="missing bearer token")

    token = auth_header.replace("Bearer ", "", 1).strip()
    if not token:
        abort(401, description="empty bearer token")

    try:
        user = verifier(token) if callable(verifier) else verifier.verify_id_token(token)
    except Exception:
        abort(401, description="invalid authentication token")

    if not isinstance(user, Mapping):
        abort(401, description="invalid authentication token")

    user_dict = dict(user)
    if not user_uid(user_dict):
        abort(401, description="token missing user identity")

    g.redisus_user = user_dict
    g.redisus_auth_disabled = False
    return user_dict


def get_rate_limit(bucket: str, default_limit: int) -> int:
    env_name = f"REDISUS_RATE_LIMIT_{bucket.upper()}"
    raw = os.getenv(env_name)
    if not raw:
        return default_limit
    try:
        value = int(raw)
    except ValueError:
        return default_limit
    return max(1, value)


def get_rate_limit_window(default_window_seconds: int = 60) -> int:
    raw = os.getenv("REDISUS_RATE_LIMIT_WINDOW_SECONDS")
    if not raw:
        return default_window_seconds
    try:
        return max(1, int(raw))
    except ValueError:
        return default_window_seconds


def enforce_rate_limit(bucket: str, default_limit: int, subject: str | None = None) -> None:
    if request.method == "OPTIONS":
        return

    window_seconds = get_rate_limit_window()
    limit = get_rate_limit(bucket, default_limit)
    user = current_user()
    actor = subject or user_uid(user) or request.remote_addr or "anonymous"
    state_key = (bucket, actor)
    now = time.time()

    with _RATE_LIMIT_LOCK:
        timestamps = [stamp for stamp in _RATE_LIMIT_STATE.get(state_key, []) if now - stamp < window_seconds]
        if len(timestamps) >= limit:
            abort(429, description=f"rate limit exceeded for {bucket}")
        timestamps.append(now)
        _RATE_LIMIT_STATE[state_key] = timestamps
