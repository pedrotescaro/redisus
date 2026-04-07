from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Mapping


def _now_iso() -> str:
    return datetime.now().isoformat()


def _as_dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _as_list_of_dicts(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [dict(item) for item in value if isinstance(item, Mapping)]


def _as_list_of_strings(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


@dataclass(slots=True)
class LesionRecord:
    id: str
    patient_id: str
    title: str | None = None
    wound_type: str | None = None
    location: str | None = None
    status: str = "active"
    opened_at: str = field(default_factory=_now_iso)
    closed_at: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "patient_id": self.patient_id,
            "title": self.title,
            "wound_type": self.wound_type,
            "location": self.location,
            "status": self.status,
            "opened_at": self.opened_at,
            "closed_at": self.closed_at,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "LesionRecord":
        return cls(
            id=str(data.get("id") or ""),
            patient_id=str(data.get("patient_id") or ""),
            title=data.get("title"),
            wound_type=data.get("wound_type"),
            location=data.get("location"),
            status=str(data.get("status") or "active"),
            opened_at=str(data.get("opened_at") or data.get("created_at") or _now_iso()),
            closed_at=data.get("closed_at"),
            metadata=_as_dict(data.get("metadata")),
        )


@dataclass(slots=True)
class ClinicalImageRecord:
    id: str
    patient_id: str
    lesion_id: str
    evaluation_id: str
    image_role: str = "clinical"
    image_path: str = ""
    content_type: str = "image/jpeg"
    version: int = 1
    review_status: str = "nao_revisada"
    captured_at: str | None = None
    created_at: str = field(default_factory=_now_iso)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "patient_id": self.patient_id,
            "lesion_id": self.lesion_id,
            "evaluation_id": self.evaluation_id,
            "image_role": self.image_role,
            "image_path": self.image_path,
            "content_type": self.content_type,
            "version": self.version,
            "review_status": self.review_status,
            "captured_at": self.captured_at,
            "created_at": self.created_at,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(
        cls,
        data: Mapping[str, Any],
        *,
        patient_id: str | None = None,
        lesion_id: str | None = None,
    ) -> "ClinicalImageRecord":
        metadata = _as_dict(data.get("metadata"))
        version = data.get("version", metadata.get("version", 1))
        try:
            version_int = int(version)
        except (TypeError, ValueError):
            version_int = 1

        return cls(
            id=str(data.get("id") or ""),
            patient_id=str(data.get("patient_id") or metadata.get("patient_id") or patient_id or ""),
            lesion_id=str(data.get("lesion_id") or data.get("case_id") or metadata.get("case_id") or lesion_id or ""),
            evaluation_id=str(data.get("evaluation_id") or ""),
            image_role=str(data.get("image_role") or "clinical"),
            image_path=str(data.get("image_path") or ""),
            content_type=str(data.get("content_type") or "image/jpeg"),
            version=max(1, version_int),
            review_status=str(data.get("review_status") or metadata.get("review_status") or "nao_revisada"),
            captured_at=data.get("captured_at") or metadata.get("captured_at"),
            created_at=str(data.get("created_at") or _now_iso()),
            metadata=metadata,
        )


@dataclass(slots=True)
class InferenceResultRecord:
    id: str
    run_id: str
    patient_id: str
    lesion_id: str
    evaluation_id: str
    contract_version: str
    model_version: str
    inference: dict[str, Any]
    interpretation: dict[str, Any]
    created_at: str = field(default_factory=_now_iso)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "run_id": self.run_id,
            "patient_id": self.patient_id,
            "lesion_id": self.lesion_id,
            "evaluation_id": self.evaluation_id,
            "contract_version": self.contract_version,
            "model_version": self.model_version,
            "inference": self.inference,
            "interpretation": self.interpretation,
            "created_at": self.created_at,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(
        cls,
        data: Mapping[str, Any],
        *,
        patient_id: str | None = None,
        lesion_id: str | None = None,
        evaluation_id: str | None = None,
    ) -> "InferenceResultRecord":
        payload = _as_dict(data.get("payload"))
        inference = _as_dict(data.get("inference") or payload.get("inference"))
        interpretation = _as_dict(data.get("interpretation") or payload.get("interpretation"))
        metadata = _as_dict(data.get("metadata"))

        if not inference:
            inference = {
                "etiology": data.get("etiology"),
                "confidence": data.get("confidence"),
                "tissue_percentages": data.get("tissue_percentages", {}),
                "wound_area_cm2": data.get("wound_area_cm2"),
                "fallback_used": data.get("fallback_used", False),
            }
        if not interpretation:
            interpretation = {
                "summary": data.get("diagnosis_summary"),
                "recommendations": data.get("recommendations", []),
                "risk_level": data.get("risk_level"),
                "priority": data.get("priority"),
                "follow_up_days": data.get("follow_up_days"),
            }

        return cls(
            id=str(data.get("id") or ""),
            run_id=str(data.get("run_id") or ""),
            patient_id=str(
                data.get("patient_id")
                or payload.get("patient_id")
                or metadata.get("patient_id")
                or patient_id
                or ""
            ),
            lesion_id=str(
                data.get("lesion_id")
                or data.get("case_id")
                or payload.get("case_id")
                or metadata.get("case_id")
                or lesion_id
                or ""
            ),
            evaluation_id=str(
                data.get("evaluation_id")
                or payload.get("evaluation_id")
                or metadata.get("evaluation_id")
                or evaluation_id
                or ""
            ),
            contract_version=str(data.get("contract_version") or payload.get("contract_version") or "unknown"),
            model_version=str(data.get("model_version") or payload.get("model_version") or "unknown"),
            inference=inference,
            interpretation=interpretation,
            created_at=str(data.get("created_at") or payload.get("generated_at") or _now_iso()),
            metadata=metadata,
        )


@dataclass(slots=True)
class AssessmentRecord:
    id: str
    patient_id: str
    lesion_id: str
    evaluation_date: str
    professional_name: str | None = None
    wound_type: str | None = None
    wound_location: str | None = None
    clinical_description: str | None = None
    push_score: float | None = None
    braden_score: float | None = None
    bwat_score: float | None = None
    pain_score: float | None = None
    wound_area_cm2: float | None = None
    depth_mm: float | None = None
    tissue_composition: dict[str, float] = field(default_factory=dict)
    timers_payload: dict[str, Any] = field(default_factory=dict)
    images: list[dict[str, Any]] = field(default_factory=list)
    inference_result: dict[str, Any] | None = None
    created_at: str = field(default_factory=_now_iso)
    updated_at: str = field(default_factory=_now_iso)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "patient_id": self.patient_id,
            "lesion_id": self.lesion_id,
            "evaluation_date": self.evaluation_date,
            "professional_name": self.professional_name,
            "wound_type": self.wound_type,
            "wound_location": self.wound_location,
            "clinical_description": self.clinical_description,
            "push_score": self.push_score,
            "braden_score": self.braden_score,
            "bwat_score": self.bwat_score,
            "pain_score": self.pain_score,
            "wound_area_cm2": self.wound_area_cm2,
            "depth_mm": self.depth_mm,
            "tissue_composition": self.tissue_composition,
            "timers_payload": self.timers_payload,
            "images": self.images,
            "inference_result": self.inference_result,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(
        cls,
        data: Mapping[str, Any],
        *,
        lesion_id: str | None = None,
        images: list[dict[str, Any]] | None = None,
        inference_result: dict[str, Any] | None = None,
    ) -> "AssessmentRecord":
        return cls(
            id=str(data.get("id") or ""),
            patient_id=str(data.get("patient_id") or ""),
            lesion_id=str(data.get("lesion_id") or data.get("case_id") or lesion_id or ""),
            evaluation_date=str(data.get("evaluation_date") or data.get("created_at") or _now_iso()),
            professional_name=data.get("professional_name"),
            wound_type=data.get("wound_type"),
            wound_location=data.get("wound_location"),
            clinical_description=data.get("clinical_description"),
            push_score=data.get("push_score"),
            braden_score=data.get("braden_score"),
            bwat_score=data.get("bwat_score"),
            pain_score=data.get("pain_score"),
            wound_area_cm2=data.get("wound_area_cm2"),
            depth_mm=data.get("depth_mm"),
            tissue_composition=dict(data.get("tissue_composition") or {}),
            timers_payload=dict(data.get("timers_payload") or {}),
            images=images or _as_list_of_dicts(data.get("images")),
            inference_result=inference_result or data.get("inference_result"),
            created_at=str(data.get("created_at") or _now_iso()),
            updated_at=str(data.get("updated_at") or data.get("created_at") or _now_iso()),
            metadata=_as_dict(data.get("metadata")),
        )


@dataclass(slots=True)
class CarePlanRecord:
    id: str
    patient_id: str
    lesion_id: str
    version: int
    title: str
    status: str
    risk_level: str
    goals: list[str] = field(default_factory=list)
    frequency: str | None = None
    tasks: list[dict[str, Any]] = field(default_factory=list)
    alerts: list[dict[str, Any]] = field(default_factory=list)
    source_evaluation_id: str | None = None
    source_result_id: str | None = None
    review_due_date: str | None = None
    created_by: str | None = None
    created_at: str = field(default_factory=_now_iso)
    updated_at: str = field(default_factory=_now_iso)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "patient_id": self.patient_id,
            "lesion_id": self.lesion_id,
            "version": self.version,
            "title": self.title,
            "status": self.status,
            "risk_level": self.risk_level,
            "goals": self.goals,
            "frequency": self.frequency,
            "tasks": self.tasks,
            "alerts": self.alerts,
            "source_evaluation_id": self.source_evaluation_id,
            "source_result_id": self.source_result_id,
            "review_due_date": self.review_due_date,
            "created_by": self.created_by,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any], *, lesion_id: str | None = None) -> "CarePlanRecord":
        version = data.get("version", 1)
        try:
            version_int = int(version)
        except (TypeError, ValueError):
            version_int = 1

        return cls(
            id=str(data.get("id") or ""),
            patient_id=str(data.get("patient_id") or ""),
            lesion_id=str(data.get("lesion_id") or data.get("case_id") or lesion_id or ""),
            version=max(1, version_int),
            title=str(data.get("title") or "Care plan"),
            status=str(data.get("status") or "draft"),
            risk_level=str(data.get("risk_level") or "moderado"),
            goals=_as_list_of_strings(data.get("goals")),
            frequency=data.get("frequency"),
            tasks=_as_list_of_dicts(data.get("tasks")),
            alerts=_as_list_of_dicts(data.get("alerts")),
            source_evaluation_id=data.get("source_evaluation_id"),
            source_result_id=data.get("source_result_id"),
            review_due_date=data.get("review_due_date"),
            created_by=data.get("created_by"),
            created_at=str(data.get("created_at") or _now_iso()),
            updated_at=str(data.get("updated_at") or data.get("created_at") or _now_iso()),
            metadata=_as_dict(data.get("metadata")),
        )


@dataclass(slots=True)
class FollowUpRecord:
    id: str
    patient_id: str
    lesion_id: str
    care_plan_id: str | None
    evaluation_id: str | None
    scheduled_for: str
    status: str
    reason: str | None = None
    assigned_role: str | None = None
    created_by: str | None = None
    notes: str | None = None
    created_at: str = field(default_factory=_now_iso)
    completed_at: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "patient_id": self.patient_id,
            "lesion_id": self.lesion_id,
            "care_plan_id": self.care_plan_id,
            "evaluation_id": self.evaluation_id,
            "scheduled_for": self.scheduled_for,
            "status": self.status,
            "reason": self.reason,
            "assigned_role": self.assigned_role,
            "created_by": self.created_by,
            "notes": self.notes,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any], *, lesion_id: str | None = None) -> "FollowUpRecord":
        return cls(
            id=str(data.get("id") or ""),
            patient_id=str(data.get("patient_id") or ""),
            lesion_id=str(data.get("lesion_id") or data.get("case_id") or lesion_id or ""),
            care_plan_id=data.get("care_plan_id"),
            evaluation_id=data.get("evaluation_id"),
            scheduled_for=str(data.get("scheduled_for") or data.get("due_at") or _now_iso()),
            status=str(data.get("status") or "scheduled"),
            reason=data.get("reason"),
            assigned_role=data.get("assigned_role"),
            created_by=data.get("created_by"),
            notes=data.get("notes"),
            created_at=str(data.get("created_at") or _now_iso()),
            completed_at=data.get("completed_at"),
            metadata=_as_dict(data.get("metadata")),
        )


@dataclass(slots=True)
class AlertRecord:
    id: str
    patient_id: str
    lesion_id: str
    care_plan_id: str | None
    follow_up_id: str | None
    alert_type: str
    severity: str
    status: str
    title: str
    message: str
    due_at: str | None = None
    created_at: str = field(default_factory=_now_iso)
    resolved_at: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "patient_id": self.patient_id,
            "lesion_id": self.lesion_id,
            "care_plan_id": self.care_plan_id,
            "follow_up_id": self.follow_up_id,
            "alert_type": self.alert_type,
            "severity": self.severity,
            "status": self.status,
            "title": self.title,
            "message": self.message,
            "due_at": self.due_at,
            "created_at": self.created_at,
            "resolved_at": self.resolved_at,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any], *, lesion_id: str | None = None) -> "AlertRecord":
        return cls(
            id=str(data.get("id") or ""),
            patient_id=str(data.get("patient_id") or ""),
            lesion_id=str(data.get("lesion_id") or data.get("case_id") or lesion_id or ""),
            care_plan_id=data.get("care_plan_id"),
            follow_up_id=data.get("follow_up_id"),
            alert_type=str(data.get("alert_type") or "clinical"),
            severity=str(data.get("severity") or "moderado"),
            status=str(data.get("status") or "open"),
            title=str(data.get("title") or "Clinical alert"),
            message=str(data.get("message") or ""),
            due_at=data.get("due_at"),
            created_at=str(data.get("created_at") or _now_iso()),
            resolved_at=data.get("resolved_at"),
            metadata=_as_dict(data.get("metadata")),
        )
