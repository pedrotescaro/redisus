from __future__ import annotations

import unicodedata
from datetime import datetime, timedelta
from typing import Any, Mapping

from src.care_plans.care_plan_manager import CarePlanTemplates

from .models import (
    AlertRecord,
    AssessmentRecord,
    CarePlanRecord,
    ClinicalImageRecord,
    FollowUpRecord,
    InferenceResultRecord,
    LesionRecord,
)

AI_RESULT_CONTRACT_VERSION = "2026-04-07"
DEFAULT_MODEL_VERSION = "fallback-clinical-v1"

_ETIOLOGY_ALIASES = {
    "venous_ulcer": "VENOUS_ULCER",
    "ulcera_venosa": "VENOUS_ULCER",
    "diabetic_foot": "DIABETIC_FOOT",
    "pe_diabetico": "DIABETIC_FOOT",
    "pressure_injury": "PRESSURE_INJURY",
    "lesao_pressao": "PRESSURE_INJURY",
    "arterial_ulcer": "ARTERIAL_ULCER",
    "ulcera_arterial": "ARTERIAL_ULCER",
    "surgical_wound": "SURGICAL_WOUND",
    "ferida_cirurgica": "SURGICAL_WOUND",
}

_ETIOLOGY_LABELS = {
    "VENOUS_ULCER": "Venous ulcer",
    "DIABETIC_FOOT": "Diabetic foot",
    "PRESSURE_INJURY": "Pressure injury",
    "ARTERIAL_ULCER": "Arterial ulcer",
    "SURGICAL_WOUND": "Surgical wound",
}

_HEADLESS_TISSUE_KEY_ALIASES = {
    "coagulation_necrosis_eschar": "necrosis",
    "necrose_de_coagulacao_escara": "necrosis",
    "slough_fibrin": "slough",
    "esfacelo_fibrina": "slough",
    "granulation_tissue": "granulation",
    "tecido_de_granulacao": "granulation",
}

_FOLLOW_UP_DAYS = {
    "critico": 1,
    "alto": 3,
    "moderado": 7,
    "baixo": 14,
}


def _now_iso() -> str:
    return datetime.now().isoformat()


def _slugify(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode("ascii")
    chars: list[str] = []
    last_sep = False
    for char in text.lower():
        if char.isalnum():
            chars.append(char)
            last_sep = False
            continue
        if not last_sep:
            chars.append("_")
            last_sep = True
    return "".join(chars).strip("_")


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def normalize_etiology_code(value: Any) -> str:
    slug = _slugify(value)
    if not slug:
        return "UNSPECIFIED_WOUND"
    return _ETIOLOGY_ALIASES.get(slug, slug.upper())


def humanize_etiology(value: Any) -> str:
    code = normalize_etiology_code(value)
    return _ETIOLOGY_LABELS.get(code, code.replace("_", " ").title())


def derive_risk_level(evaluation: Mapping[str, Any], inference_payload: Mapping[str, Any]) -> str:
    tissue = inference_payload.get("tissue_percentages") or inference_payload.get("tissue_composition") or {}
    area = _safe_float(inference_payload.get("wound_area_cm2") or evaluation.get("wound_area_cm2"))
    depth = _safe_float(evaluation.get("depth_mm"))
    pain = _safe_float(evaluation.get("pain_score"))
    confidence = _safe_float(inference_payload.get("confidence"), 0.0)
    necrosis = _safe_float((tissue or {}).get("necrosis"))
    slough = _safe_float((tissue or {}).get("slough"))
    fallback_used = bool(inference_payload.get("fallback_used"))

    score = 0
    if area >= 20:
        score += 3
    elif area >= 10:
        score += 2
    elif area >= 5:
        score += 1
    if depth >= 10:
        score += 2
    elif depth >= 5:
        score += 1
    if pain >= 7:
        score += 2
    elif pain >= 4:
        score += 1
    if necrosis >= 20:
        score += 3
    elif necrosis >= 10:
        score += 2
    elif necrosis > 0:
        score += 1
    if slough >= 40:
        score += 1
    if confidence < 0.55:
        score += 2
    elif confidence < 0.7:
        score += 1
    if fallback_used:
        score += 1

    if score >= 8:
        return "critico"
    if score >= 5:
        return "alto"
    if score >= 3:
        return "moderado"
    return "baixo"


def derive_follow_up_days(risk_level: str) -> int:
    return _FOLLOW_UP_DAYS.get((risk_level or "").strip().lower(), 7)


def normalize_ai_output(
    raw_output: Mapping[str, Any],
    *,
    patient_id: str,
    lesion_id: str,
    evaluation: Mapping[str, Any],
    fallback_used: bool = False,
    model_version: str = DEFAULT_MODEL_VERSION,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or _now_iso()
    tissue = raw_output.get("tissue_percentages") or raw_output.get("tissue_composition") or {}
    normalized_tissue = {
        "granulation": round(_safe_float((tissue or {}).get("granulation")), 2),
        "slough": round(_safe_float((tissue or {}).get("slough")), 2),
        "necrosis": round(_safe_float((tissue or {}).get("necrosis")), 2),
    }
    inference = {
        "etiology": normalize_etiology_code(raw_output.get("etiology")),
        "etiology_label": humanize_etiology(raw_output.get("etiology")),
        "confidence": round(max(0.0, min(1.0, _safe_float(raw_output.get("confidence"), 0.0))), 4),
        "tissue_percentages": normalized_tissue,
        "wound_area_cm2": round(
            _safe_float(raw_output.get("wound_area_cm2") or evaluation.get("wound_area_cm2")),
            2,
        ),
        "fallback_used": bool(raw_output.get("fallback_used", fallback_used)),
        "needs_expert_review": bool(raw_output.get("needs_expert_review")),
        "confidence_level": str(raw_output.get("confidence_level") or ""),
        "confidence_entropy": round(_safe_float(raw_output.get("confidence_entropy"), 0.0), 4),
        "confidence_margin": round(_safe_float(raw_output.get("confidence_margin"), 0.0), 4),
    }
    risk_level = derive_risk_level(evaluation, inference)
    follow_up_days = derive_follow_up_days(risk_level)
    recommendations = raw_output.get("recommendations")
    if not isinstance(recommendations, list) or not recommendations:
        recommendations = [
            "Keep the wound bed protected according to protocol.",
            f"Schedule clinical review within {follow_up_days} day(s).",
        ]

    interpretation = {
        "summary": str(
            raw_output.get("diagnosis_summary")
            or f"{inference['etiology_label']} with {normalized_tissue['granulation']:.0f}% granulation."
        ),
        "risk_level": risk_level,
        "priority": "urgente" if risk_level == "critico" else risk_level,
        "follow_up_days": follow_up_days,
        "requires_expert_review": bool(inference.get("needs_expert_review")),
        "recommendations": [str(item) for item in recommendations],
    }
    metadata = {
        "source": "clinical_api_pipeline",
        "evaluation_date": evaluation.get("evaluation_date"),
    }
    if isinstance(raw_output.get("metadata"), Mapping):
        metadata.update(dict(raw_output.get("metadata") or {}))
    return {
        "contract_version": AI_RESULT_CONTRACT_VERSION,
        "analysis_type": "wound_assessment",
        "model_version": model_version,
        "generated_at": generated_at,
        "patient_id": patient_id,
        "case_id": lesion_id,
        "evaluation_id": str(evaluation.get("id") or ""),
        "inference": inference,
        "interpretation": interpretation,
        "metadata": metadata,
    }


def _serialize_headless_report_legacy(report: Any) -> dict[str, Any]:
    result = {
        "is_valid_wound": bool(getattr(report, "is_valid_wound", False)),
        "rejection_reason": getattr(report, "rejection_reason", "") or "",
        "primary_tissue": getattr(report, "primary_tissue", "") or "",
        "primary_justification": getattr(report, "primary_justification", "") or "",
        "wound_area_px": int(getattr(report, "wound_area_px", 0) or 0),
        "health_score": float(getattr(report, "health_score", 0.0) or 0.0),
        "processing_time_ms": float(getattr(report, "processing_time_ms", 0.0) or 0.0),
        "tissues": [],
        "border_analysis": None,
    }

    for tissue in getattr(report, "tissues", []) or []:
        result["tissues"].append(
            {
                "name": getattr(tissue, "name", ""),
                "name_en": getattr(tissue, "name_en", ""),
                "percentage": getattr(tissue, "percentage", 0.0),
                "color_hex": getattr(tissue, "color_hex", ""),
                "description": getattr(tissue, "description", ""),
                "clinical_action": getattr(tissue, "clinical_action", ""),
            }
        )

    border = getattr(report, "border_analysis", None)
    if border:
        result["border_analysis"] = {
            "maceration": bool(getattr(border, "maceration", False)),
            "inflammation": bool(getattr(border, "inflammation", False)),
            "regular_borders": bool(getattr(border, "regular_borders", False)),
            "description": getattr(border, "description", "") or "",
        }

    for field in (
        "dl_prediction",
        "resnet_prediction",
        "ensemble_classification",
        "body_part",
        "push_score",
        "lighting_analysis",
        "wound_zones",
        "tissue_analysis_trace",
        "roi",
        "rois",
    ):
        value = getattr(report, field, None)
        if value:
            result[field] = value

    return result


def _extract_headless_tissue_percentages(report: Any) -> dict[str, float]:
    tissue_percentages = {"granulation": 0.0, "slough": 0.0, "necrosis": 0.0}
    for tissue in getattr(report, "tissues", []) or []:
        label = _slugify(getattr(tissue, "name_en", "") or getattr(tissue, "name", ""))
        key = _HEADLESS_TISSUE_KEY_ALIASES.get(label)
        if key:
            tissue_percentages[key] = round(_safe_float(getattr(tissue, "percentage", 0.0)), 2)
    return tissue_percentages


def _resolve_headless_report_etiology(report: Any) -> str:
    resnet_prediction = getattr(report, "resnet_prediction", None) or {}
    if resnet_prediction.get("mapped_etiology"):
        return str(resnet_prediction["mapped_etiology"])

    final_class = str(resnet_prediction.get("final_class") or "").strip()
    if final_class:
        return final_class

    dl_prediction = getattr(report, "dl_prediction", None) or {}
    if dl_prediction.get("class_name"):
        return str(dl_prediction["class_name"])

    ensemble_prediction = getattr(report, "ensemble_classification", None) or {}
    if ensemble_prediction.get("class_name"):
        return str(ensemble_prediction["class_name"])

    return "unspecified_wound"


def _resolve_headless_report_confidence(report: Any) -> float:
    resnet_prediction = getattr(report, "resnet_prediction", None) or {}
    if resnet_prediction.get("final_confidence") is not None:
        return _safe_float(resnet_prediction.get("final_confidence"), 0.0)

    dl_prediction = getattr(report, "dl_prediction", None) or {}
    if dl_prediction.get("confidence") is not None:
        return _safe_float(dl_prediction.get("confidence"), 0.0)

    ensemble_prediction = getattr(report, "ensemble_classification", None) or {}
    if ensemble_prediction.get("confidence") is not None:
        return _safe_float(ensemble_prediction.get("confidence"), 0.0)

    return 0.0


def _resolve_headless_model_version(report: Any) -> str:
    if getattr(report, "resnet_prediction", None):
        return "heal-analyzer-headless-resnet"
    if getattr(report, "dl_prediction", None):
        return "heal-analyzer-headless-dl"
    if getattr(report, "ensemble_classification", None):
        return "heal-analyzer-headless-ensemble"
    return DEFAULT_MODEL_VERSION


def _build_headless_raw_output(report: Any) -> dict[str, Any]:
    confidence = max(0.0, min(1.0, _resolve_headless_report_confidence(report)))
    fallback_used = not bool(
        getattr(report, "resnet_prediction", None)
        or getattr(report, "dl_prediction", None)
        or getattr(report, "ensemble_classification", None)
    )
    resnet_prediction = getattr(report, "resnet_prediction", None) or {}
    primary_tissue = getattr(report, "primary_tissue", "") or "Unspecified wound"
    primary_justification = getattr(report, "primary_justification", "") or getattr(report, "rejection_reason", "")
    recommendations: list[str] = []
    for tissue in getattr(report, "tissues", []) or []:
        if _safe_float(getattr(tissue, "percentage", 0.0)) <= 0:
            continue
        action = str(getattr(tissue, "clinical_action", "") or "").strip()
        if action:
            recommendations.append(action)
            break
    if not recommendations:
        recommendations.append("Validar clinicamente o resultado antes de tomada de decisao.")

    metadata: dict[str, Any] = {
        "source": "integration_headless_analyzer",
        "wound_area_px": int(getattr(report, "wound_area_px", 0) or 0),
        "primary_tissue": primary_tissue,
        "is_valid_wound": bool(getattr(report, "is_valid_wound", False)),
    }
    if getattr(report, "body_part", None):
        metadata["body_part"] = dict(getattr(report, "body_part") or {})
    if getattr(report, "lighting_analysis", None):
        metadata["lighting_analysis"] = dict(getattr(report, "lighting_analysis") or {})

    raw_output = {
        "etiology": _resolve_headless_report_etiology(report),
        "confidence": confidence,
        "tissue_percentages": _extract_headless_tissue_percentages(report),
        "wound_area_cm2": 0.0,
        "diagnosis_summary": primary_justification or f"{primary_tissue} identified in headless integration analysis.",
        "recommendations": recommendations,
        "fallback_used": fallback_used,
        "needs_expert_review": bool(resnet_prediction.get("needs_expert_review")) or fallback_used or confidence < 0.8,
        "confidence_level": str(resnet_prediction.get("confidence_level") or ""),
        "confidence_entropy": _safe_float(resnet_prediction.get("confidence_entropy"), 0.0),
        "confidence_margin": _safe_float(resnet_prediction.get("confidence_margin"), 0.0),
        "metadata": metadata,
    }
    if not getattr(report, "is_valid_wound", False):
        raw_output["diagnosis_summary"] = getattr(report, "rejection_reason", "") or "Image rejected by analyzer."
        raw_output["needs_expert_review"] = True
        raw_output["fallback_used"] = True
    return raw_output


def build_headless_analyzer_result(
    report: Any,
    *,
    analysis_id: str,
    patient_id: str,
    image_filename: str,
    image_content_type: str,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or _now_iso()
    raw_output = _build_headless_raw_output(report)
    evaluation = {
        "id": analysis_id,
        "patient_id": patient_id,
        "evaluation_date": generated_at,
        "wound_type": raw_output.get("etiology"),
        "wound_area_cm2": raw_output.get("wound_area_cm2", 0.0),
        "depth_mm": 0.0,
        "pain_score": 0.0,
        "tissue_composition": dict(raw_output.get("tissue_percentages") or {}),
    }
    official_result = normalize_ai_output(
        raw_output,
        patient_id=patient_id,
        lesion_id=analysis_id,
        evaluation=evaluation,
        fallback_used=bool(raw_output.get("fallback_used")),
        model_version=_resolve_headless_model_version(report),
        generated_at=generated_at,
    )
    official_result.setdefault("metadata", {}).update(
        {
            "analysis_id": analysis_id,
            "image_filename": image_filename or "unknown",
            "image_content_type": image_content_type,
        }
    )
    legacy_result = _serialize_headless_report_legacy(report)
    return {
        **official_result,
        **legacy_result,
        "analysis_id": analysis_id,
    }


def build_care_plan_payload(
    *,
    patient_id: str,
    lesion_id: str,
    evaluation_id: str,
    result_id: str,
    inference_result: Mapping[str, Any],
    created_by: str,
) -> dict[str, Any]:
    inference = dict(inference_result.get("inference") or {})
    interpretation = dict(inference_result.get("interpretation") or {})
    risk_level = str(interpretation.get("risk_level") or "moderado")
    etiology = normalize_etiology_code(inference.get("etiology"))
    template = CarePlanTemplates.get_template_for_etiology(etiology, patient_id, risk_level)
    follow_up_days = derive_follow_up_days(risk_level)
    review_due_date = (
        datetime.fromisoformat(str(inference_result.get("generated_at") or _now_iso()))
        + timedelta(days=follow_up_days)
    ).date().isoformat()

    return {
        "patient_id": patient_id,
        "case_id": lesion_id,
        "title": f"{template.title} - lesion {lesion_id[:8]}",
        "status": "active",
        "risk_level": risk_level,
        "goals": list(template.goals),
        "frequency": f"review_every_{follow_up_days}_days",
        "tasks": [activity.to_dict() for activity in template.activities],
        "alerts": [
            {"type": "follow_up_due", "severity": risk_level, "days_until_due": follow_up_days},
            {"type": "risk_watch", "severity": risk_level, "reason": interpretation.get("summary")},
        ],
        "source_evaluation_id": evaluation_id,
        "source_result_id": result_id,
        "review_due_date": review_due_date,
        "created_by": created_by,
        "metadata": {
            "etiology": etiology,
            "contract_version": inference_result.get("contract_version"),
            "model_version": inference_result.get("model_version"),
            "summary": interpretation.get("summary"),
        },
    }


def build_follow_up_payload(
    *,
    patient_id: str,
    lesion_id: str,
    evaluation_id: str,
    care_plan_id: str,
    inference_result: Mapping[str, Any],
    created_by: str,
) -> dict[str, Any]:
    interpretation = dict(inference_result.get("interpretation") or {})
    risk_level = str(interpretation.get("risk_level") or "moderado")
    follow_up_days = derive_follow_up_days(risk_level)
    scheduled_for = (
        datetime.fromisoformat(str(inference_result.get("generated_at") or _now_iso()))
        + timedelta(days=follow_up_days)
    ).date().isoformat()

    return {
        "patient_id": patient_id,
        "case_id": lesion_id,
        "care_plan_id": care_plan_id,
        "evaluation_id": evaluation_id,
        "scheduled_for": scheduled_for,
        "status": "scheduled",
        "reason": "clinical_review",
        "assigned_role": (
            "doctor"
            if risk_level in {"alto", "critico"} or bool(interpretation.get("requires_expert_review"))
            else "nurse"
        ),
        "created_by": created_by,
        "notes": str(interpretation.get("summary") or ""),
        "metadata": {
            "risk_level": risk_level,
            "follow_up_days": follow_up_days,
            "requires_expert_review": bool(interpretation.get("requires_expert_review")),
        },
    }


def build_alert_payloads(
    *,
    patient_id: str,
    lesion_id: str,
    care_plan_id: str,
    follow_up_id: str,
    inference_result: Mapping[str, Any],
) -> list[dict[str, Any]]:
    interpretation = dict(inference_result.get("interpretation") or {})
    inference = dict(inference_result.get("inference") or {})
    risk_level = str(interpretation.get("risk_level") or "moderado")
    alerts: list[dict[str, Any]] = []

    if risk_level in {"alto", "critico"}:
        alerts.append(
            {
                "patient_id": patient_id,
                "case_id": lesion_id,
                "care_plan_id": care_plan_id,
                "follow_up_id": follow_up_id,
                "alert_type": "clinical_priority",
                "severity": risk_level,
                "status": "open",
                "title": f"Clinical priority: {risk_level}",
                "message": str(interpretation.get("summary") or ""),
                "due_at": (
                    datetime.fromisoformat(str(inference_result.get("generated_at") or _now_iso()))
                    + timedelta(days=derive_follow_up_days(risk_level))
                ).date().isoformat(),
                "metadata": {"etiology": inference.get("etiology")},
            }
        )

    if bool(inference.get("fallback_used")):
        alerts.append(
            {
                "patient_id": patient_id,
                "case_id": lesion_id,
                "care_plan_id": care_plan_id,
                "follow_up_id": follow_up_id,
                "alert_type": "manual_ai_review",
                "severity": "moderado",
                "status": "open",
                "title": "Manual review required",
                "message": "AI fallback was used. Clinical validation is required.",
                "due_at": datetime.now().date().isoformat(),
                "metadata": {"contract_version": inference_result.get("contract_version")},
            }
        )

    if bool(inference.get("needs_expert_review")):
        alerts.append(
            {
                "patient_id": patient_id,
                "case_id": lesion_id,
                "care_plan_id": care_plan_id,
                "follow_up_id": follow_up_id,
                "alert_type": "expert_review_required",
                "severity": "alto" if risk_level in {"alto", "critico"} else "moderado",
                "status": "open",
                "title": "Expert review required",
                "message": "Model confidence requires specialist confirmation before clinical decision.",
                "due_at": datetime.now().date().isoformat(),
                "metadata": {
                    "confidence_level": inference.get("confidence_level"),
                    "confidence_margin": inference.get("confidence_margin"),
                    "confidence_entropy": inference.get("confidence_entropy"),
                },
            }
        )

    return alerts


def _event_time(value: Mapping[str, Any]) -> str:
    for key in ("timestamp", "evaluation_date", "captured_at", "created_at", "scheduled_for", "due_at", "opened_at"):
        if value.get(key):
            return str(value[key])
    return _now_iso()


def build_case_timeline(
    *,
    patient: Any,
    lesion: Mapping[str, Any],
    evaluations: list[Mapping[str, Any]],
    care_plans: list[Mapping[str, Any]],
    follow_ups: list[Mapping[str, Any]],
    alerts: list[Mapping[str, Any]],
    audit_log: list[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    patient_payload = patient.to_dict() if hasattr(patient, "to_dict") else dict(patient or {})
    lesion_record = LesionRecord.from_dict(lesion)
    assessment_records = [AssessmentRecord.from_dict(item, lesion_id=lesion_record.id) for item in evaluations]
    plan_records = [CarePlanRecord.from_dict(item, lesion_id=lesion_record.id) for item in care_plans]
    follow_up_records = [FollowUpRecord.from_dict(item, lesion_id=lesion_record.id) for item in follow_ups]
    alert_records = [AlertRecord.from_dict(item, lesion_id=lesion_record.id) for item in alerts]

    events: list[dict[str, Any]] = []
    for assessment in assessment_records:
        events.append(
            {
                "type": "assessment",
                "timestamp": assessment.evaluation_date,
                "title": "Assessment recorded",
                "status": "completed",
                "data": assessment.to_dict(),
            }
        )
        for image_data in assessment.images:
            image_record = ClinicalImageRecord.from_dict(
                image_data,
                patient_id=assessment.patient_id,
                lesion_id=assessment.lesion_id,
            )
            events.append(
                {
                    "type": "clinical_image",
                    "timestamp": image_record.captured_at or image_record.created_at,
                    "title": f"Image {image_record.version}",
                    "status": image_record.review_status,
                    "data": image_record.to_dict(),
                }
            )
        if assessment.inference_result:
            inference_record = InferenceResultRecord.from_dict(
                assessment.inference_result,
                patient_id=assessment.patient_id,
                lesion_id=assessment.lesion_id,
                evaluation_id=assessment.id,
            )
            events.append(
                {
                    "type": "inference_result",
                    "timestamp": inference_record.created_at,
                    "title": "AI inference completed",
                    "status": inference_record.interpretation.get("risk_level", "completed"),
                    "data": inference_record.to_dict(),
                }
            )

    for plan in plan_records:
        events.append(
            {
                "type": "care_plan",
                "timestamp": plan.created_at,
                "title": f"Care plan v{plan.version}",
                "status": plan.status,
                "data": plan.to_dict(),
            }
        )
    for follow_up in follow_up_records:
        events.append(
            {
                "type": "follow_up",
                "timestamp": follow_up.scheduled_for,
                "title": "Clinical follow-up",
                "status": follow_up.status,
                "data": follow_up.to_dict(),
            }
        )
    for alert in alert_records:
        events.append(
            {
                "type": "alert",
                "timestamp": alert.created_at,
                "title": alert.title,
                "status": alert.status,
                "data": alert.to_dict(),
            }
        )
    for audit_event in audit_log or []:
        payload = dict(audit_event)
        events.append(
            {
                "type": "audit",
                "timestamp": payload.get("created_at"),
                "title": str(payload.get("action") or "clinical_change").replace("_", " ").title(),
                "status": "recorded",
                "data": payload,
            }
        )

    events.sort(key=lambda item: _event_time(item), reverse=False)
    active_plan = next((plan.to_dict() for plan in plan_records if plan.status == "active"), None)
    open_alerts = [alert.to_dict() for alert in alert_records if alert.status in {"open", "acknowledged"}]
    next_follow_up = next(
        (follow.to_dict() for follow in sorted(follow_up_records, key=lambda item: item.scheduled_for) if follow.status == "scheduled"),
        None,
    )
    latest_inference = next((event["data"] for event in reversed(events) if event["type"] == "inference_result"), None)

    return {
        "patient": patient_payload,
        "lesion": lesion_record.to_dict(),
        "evaluations": [record.to_dict() for record in assessment_records],
        "care_plans": [record.to_dict() for record in plan_records],
        "follow_ups": [record.to_dict() for record in follow_up_records],
        "alerts": [record.to_dict() for record in alert_records],
        "audit_log": [dict(item) for item in audit_log or []],
        "events": events,
        "summary": {
            "assessment_count": len(assessment_records),
            "image_count": sum(len(record.images) for record in assessment_records),
            "open_alert_count": len(open_alerts),
            "audit_event_count": len(audit_log or []),
            "active_care_plan_id": active_plan["id"] if active_plan else None,
            "latest_risk_level": (
                (latest_inference or {}).get("interpretation", {}).get("risk_level")
                if isinstance(latest_inference, Mapping)
                else None
            ),
            "next_follow_up": next_follow_up,
        },
    }
