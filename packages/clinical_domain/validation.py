"""Clinical payload and file validation helpers."""

from __future__ import annotations

import io
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from flask import abort, current_app, request
from PIL import Image, ImageOps, UnidentifiedImageError
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator
from werkzeug.datastructures import FileStorage

ALLOWED_IMAGE_FORMATS = {
    "JPEG": (".jpg", "image/jpeg"),
    "PNG": (".png", "image/png"),
    "WEBP": (".webp", "image/webp"),
}
ALLOWED_IMAGE_ROLES = {"clinical", "reference", "measurement", "frontal", "lateral"}


class StrictPayloadModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


def _validate_identifier(value: str | None, field_name: str) -> str | None:
    if value is None or value == "":
        return None
    try:
        return str(uuid.UUID(str(value)))
    except ValueError:
        if len(str(value)) > 80:
            raise ValueError(f"{field_name} must be a valid identifier")
        return str(value)


class CreateEvaluationPayload(StrictPayloadModel):
    patient_id: str = Field(min_length=1, max_length=80)
    case_id: str | None = Field(default=None, max_length=80)
    lesion_id: str | None = Field(default=None, max_length=80)
    evaluation_date: str | None = Field(default=None, max_length=32)
    wound_type: str | None = Field(default=None, max_length=80)
    wound_location: str | None = Field(default=None, max_length=120)
    clinical_description: str | None = Field(default=None, max_length=4000)
    push_score: float | None = Field(default=None, ge=0, le=50)
    braden_score: float | None = Field(default=None, ge=0, le=50)
    bwat_score: float | None = Field(default=None, ge=0, le=100)
    pain_score: float | None = Field(default=None, ge=0, le=10)
    wound_area_cm2: float | None = Field(default=None, ge=0, le=5000)
    depth_mm: float | None = Field(default=None, ge=0, le=500)
    tissue_composition: dict[str, float] = Field(default_factory=dict)
    timers_payload: dict[str, Any] = Field(default_factory=dict)

    @field_validator("patient_id", "case_id", "lesion_id")
    @classmethod
    def validate_ids(cls, value: str | None, info):  # type: ignore[override]
        return _validate_identifier(value, info.field_name)

    @model_validator(mode="after")
    def validate_case_alias(self):
        if self.case_id and self.lesion_id and self.case_id != self.lesion_id:
            raise ValueError("case_id and lesion_id must reference the same lesion")
        return self

    @field_validator("tissue_composition")
    @classmethod
    def validate_tissue_composition(cls, value: dict[str, float]) -> dict[str, float]:
        cleaned: dict[str, float] = {}
        total = 0.0
        for key, percentage in value.items():
            numeric = float(percentage)
            if numeric < 0 or numeric > 100:
                raise ValueError("tissue composition values must stay between 0 and 100")
            cleaned[str(key)] = numeric
            total += numeric
        if cleaned and total > 100.5:
            raise ValueError("tissue composition total cannot exceed 100")
        return cleaned

    @field_validator("timers_payload")
    @classmethod
    def validate_timers_payload(cls, value: dict[str, Any]) -> dict[str, Any]:
        if len(value) > 30:
            raise ValueError("timers payload exceeds allowed field count")
        return value


class AnalyzeEvaluationPayload(StrictPayloadModel):
    forceFallback: bool = False


class GenerateReportPayload(StrictPayloadModel):
    patient_id: str = Field(min_length=1, max_length=80)
    case_id: str | None = Field(default=None, max_length=80)
    lesion_id: str | None = Field(default=None, max_length=80)
    report_type: Literal["evolution", "summary", "followup", "discharge"] = "evolution"

    @field_validator("patient_id", "case_id", "lesion_id")
    @classmethod
    def validate_ids(cls, value: str | None, info):  # type: ignore[override]
        return _validate_identifier(value, info.field_name)

    @model_validator(mode="after")
    def validate_case_alias(self):
        if self.case_id and self.lesion_id and self.case_id != self.lesion_id:
            raise ValueError("case_id and lesion_id must reference the same lesion")
        return self


class CreateCarePlanPayload(StrictPayloadModel):
    patient_id: str = Field(min_length=1, max_length=80)
    lesion_id: str = Field(min_length=1, max_length=80)
    title: str = Field(min_length=1, max_length=200)
    status: Literal["draft", "active", "completed", "cancelled"] = "active"
    risk_level: Literal["baixo", "moderado", "alto", "critico"] = "moderado"
    goals: list[str] = Field(default_factory=list, max_length=20)
    frequency: str | None = Field(default=None, max_length=80)
    tasks: list[dict[str, Any]] = Field(default_factory=list, max_length=30)
    alerts: list[dict[str, Any]] = Field(default_factory=list, max_length=20)
    review_due_date: str | None = Field(default=None, max_length=32)
    notes: str | None = Field(default=None, max_length=2000)

    @field_validator("patient_id", "lesion_id")
    @classmethod
    def validate_ids(cls, value: str | None, info):  # type: ignore[override]
        return _validate_identifier(value, info.field_name)


class CreateFollowUpPayload(StrictPayloadModel):
    patient_id: str = Field(min_length=1, max_length=80)
    lesion_id: str = Field(min_length=1, max_length=80)
    care_plan_id: str | None = Field(default=None, max_length=80)
    evaluation_id: str | None = Field(default=None, max_length=80)
    scheduled_for: str = Field(min_length=1, max_length=32)
    status: Literal["scheduled", "completed", "cancelled", "missed"] = "scheduled"
    reason: str | None = Field(default=None, max_length=120)
    assigned_role: Literal["nurse", "doctor", "admin", "researcher"] | None = None
    notes: str | None = Field(default=None, max_length=2000)

    @field_validator("patient_id", "lesion_id", "care_plan_id", "evaluation_id")
    @classmethod
    def validate_ids(cls, value: str | None, info):  # type: ignore[override]
        return _validate_identifier(value, info.field_name)


class UpdateCarePlanPayload(StrictPayloadModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    status: Literal["draft", "active", "completed", "cancelled", "superseded"] | None = None
    risk_level: Literal["baixo", "moderado", "alto", "critico"] | None = None
    goals: list[str] | None = Field(default=None, max_length=20)
    frequency: str | None = Field(default=None, max_length=80)
    tasks: list[dict[str, Any]] | None = Field(default=None, max_length=30)
    alerts: list[dict[str, Any]] | None = Field(default=None, max_length=20)
    review_due_date: str | None = Field(default=None, max_length=32)
    notes: str = Field(min_length=3, max_length=2000)

    @model_validator(mode="after")
    def validate_non_empty_update(self):
        fields = (
            self.title,
            self.status,
            self.risk_level,
            self.goals,
            self.frequency,
            self.tasks,
            self.alerts,
            self.review_due_date,
            self.notes,
        )
        if all(value is None for value in fields):
            raise ValueError("at least one care plan field must be provided")
        return self


class CompleteFollowUpPayload(StrictPayloadModel):
    status: Literal["completed", "missed", "cancelled"] = "completed"
    scheduled_for: str | None = Field(default=None, max_length=32)
    reason: str | None = Field(default=None, max_length=120)
    assigned_role: Literal["nurse", "doctor", "admin", "researcher"] | None = None
    notes: str = Field(min_length=3, max_length=2000)


class AlertActionPayload(StrictPayloadModel):
    notes: str = Field(min_length=3, max_length=2000)
    reason: str | None = Field(default=None, max_length=200)


class ClaimCasePayload(StrictPayloadModel):
    notes: str = Field(min_length=3, max_length=2000)


class HandoffCasePayload(StrictPayloadModel):
    assigned_to_uid: str = Field(min_length=1, max_length=120)
    assigned_to_name: str = Field(min_length=1, max_length=200)
    assigned_to_role: Literal["nurse", "doctor", "admin", "researcher", "clinician", "estomaterapeuta"]
    unit_id: str | None = Field(default=None, max_length=120)
    team_id: str | None = Field(default=None, max_length=120)
    notes: str = Field(min_length=3, max_length=2000)


class ClaimAlertPayload(StrictPayloadModel):
    notes: str = Field(min_length=3, max_length=2000)


class HandoffAlertPayload(StrictPayloadModel):
    assigned_to_uid: str = Field(min_length=1, max_length=120)
    assigned_to_name: str = Field(min_length=1, max_length=200)
    assigned_to_role: Literal["nurse", "doctor", "admin", "researcher", "clinician", "estomaterapeuta"]
    notes: str = Field(min_length=3, max_length=2000)


class AIChatContextPayload(StrictPayloadModel):
    patient_id: str | None = Field(default=None, max_length=80)

    @field_validator("patient_id")
    @classmethod
    def validate_patient_id(cls, value: str | None):
        return _validate_identifier(value, "patient_id")


class AIChatPayload(StrictPayloadModel):
    message: str = Field(min_length=1, max_length=4000)
    conversation_id: str | None = Field(default=None, max_length=80)
    context: AIChatContextPayload = Field(default_factory=AIChatContextPayload)

    @field_validator("conversation_id")
    @classmethod
    def validate_conversation_id(cls, value: str | None):
        return _validate_identifier(value, "conversation_id")


@dataclass
class ValidatedImage:
    content: bytes
    mime_type: str
    extension: str
    width: int
    height: int
    original_name: str


def _validation_error_message(exc: ValidationError) -> str:
    parts: list[str] = []
    for error in exc.errors(include_url=False):
        location = ".".join(str(item) for item in error.get("loc", [])) or "payload"
        message = error.get("msg", "invalid field")
        parts.append(f"{location}: {message}")
    return "; ".join(parts) or "invalid request payload"


def validate_json_request(model_cls: type[StrictPayloadModel]) -> StrictPayloadModel:
    if request.mimetype != "application/json":
        abort(415, description="content-type must be application/json")
    payload = request.get_json(silent=True)
    if payload is None:
        abort(400, description="invalid or empty json payload")
    if not isinstance(payload, dict):
        abort(400, description="json payload must be an object")
    try:
        return model_cls.model_validate(payload)
    except ValidationError as exc:
        abort(400, description=_validation_error_message(exc))


def assert_allowed_form_fields(form_data: dict[str, Any] | Any, allowed: set[str]) -> None:
    present = set(form_data.keys()) if hasattr(form_data, "keys") else set()
    extras = sorted(field for field in present if field not in allowed)
    if extras:
        abort(400, description=f"unexpected form fields: {', '.join(extras)}")


def normalize_image_role(value: str | None) -> str:
    role = (value or "clinical").strip().lower()
    if role not in ALLOWED_IMAGE_ROLES:
        abort(400, description="invalid imageRole")
    return role


def validate_and_sanitize_image_upload(file_storage: FileStorage) -> ValidatedImage:
    original_name = file_storage.filename or "image"
    raw = file_storage.stream.read()
    if not raw:
        abort(400, description="empty image upload")

    max_bytes = int(current_app.config.get("REDISUS_MAX_UPLOAD_BYTES", 10 * 1024 * 1024))
    if len(raw) > max_bytes:
        abort(413, description="uploaded image exceeds maximum size")

    try:
        probe = Image.open(io.BytesIO(raw))
        probe.verify()
        image = Image.open(io.BytesIO(raw))
        detected_format = (image.format or "").upper()
        image = ImageOps.exif_transpose(image)
        image.load()
    except (UnidentifiedImageError, OSError):
        abort(415, description="uploaded file is not a valid image")

    fmt = detected_format
    if fmt not in ALLOWED_IMAGE_FORMATS:
        abort(415, description="unsupported image format")

    width, height = image.size
    if width <= 0 or height <= 0:
        abort(415, description="invalid image dimensions")

    max_megapixels = int(current_app.config.get("REDISUS_MAX_IMAGE_MEGAPIXELS", 12))
    if width * height > max_megapixels * 1_000_000:
        abort(413, description="image resolution exceeds maximum megapixels")

    expected_extension, expected_mime = ALLOWED_IMAGE_FORMATS[fmt]
    declared_mime = (file_storage.mimetype or "").strip().lower()
    if declared_mime and declared_mime not in {expected_mime, "application/octet-stream"}:
        abort(415, description="declared mime type does not match image content")

    provided_extension = Path(original_name).suffix.lower()
    if provided_extension and provided_extension not in {expected_extension, ".jpeg" if expected_extension == ".jpg" else expected_extension}:
        abort(415, description="file extension does not match image content")

    sanitized = image
    if fmt == "JPEG" and sanitized.mode not in {"RGB", "L"}:
        sanitized = sanitized.convert("RGB")

    output = io.BytesIO()
    save_kwargs: dict[str, Any] = {"format": fmt}
    if fmt == "JPEG":
        save_kwargs.update({"quality": 95, "optimize": True})
    sanitized.save(output, **save_kwargs)

    return ValidatedImage(
        content=output.getvalue(),
        mime_type=expected_mime,
        extension=expected_extension,
        width=width,
        height=height,
        original_name=original_name,
    )
