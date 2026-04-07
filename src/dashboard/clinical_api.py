import json
import os
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from flask import Blueprint, abort, jsonify, request, send_file
from loguru import logger

from packages.clinical_domain.validation import (
    AIChatPayload,
    AnalyzeEvaluationPayload,
    AlertActionPayload,
    ClaimAlertPayload,
    ClaimCasePayload,
    CompleteFollowUpPayload,
    CreateCarePlanPayload,
    CreateEvaluationPayload,
    CreateFollowUpPayload,
    GenerateReportPayload,
    HandoffAlertPayload,
    HandoffCasePayload,
    UpdateCarePlanPayload,
    assert_allowed_form_fields,
    normalize_image_role,
    validate_and_sanitize_image_upload,
    validate_json_request,
)
from src.diagnosis.clinical_ml import ClinicalMLService
from packages.clinical_domain.workflow import (
    DEFAULT_MODEL_VERSION,
    build_alert_payloads,
    build_case_timeline,
    build_care_plan_payload,
    build_follow_up_payload,
    normalize_ai_output,
)
from packages.shared.security import (
    ensure_case_access,
    ensure_clinical_write_access,
    current_user_required,
    enforce_rate_limit,
    enforce_request_auth,
    ensure_evaluation_access,
    ensure_job_access,
    ensure_patient_access,
    ensure_report_access,
    user_display_name,
    user_roles,
    user_uid,
)


def _safe_float(value: Any) -> Optional[float]:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _calc_deltas(left: Dict[str, Any], right: Dict[str, Any]) -> Dict[str, Any]:
    def val(key: str) -> float:
        return float(right.get(key) or 0) - float(left.get(key) or 0)

    left_tissue = left.get("tissue_composition", {}) or {}
    right_tissue = right.get("tissue_composition", {}) or {}
    return {
        "area_cm2": val("wound_area_cm2"),
        "depth_mm": val("depth_mm"),
        "pain_score": val("pain_score"),
        "push_score": val("push_score"),
        "bwat_score": val("bwat_score"),
        "tissue": {
            "granulation": float(right_tissue.get("granulation", 0)) - float(left_tissue.get("granulation", 0)),
            "slough": float(right_tissue.get("slough", 0)) - float(left_tissue.get("slough", 0)),
            "necrosis": float(right_tissue.get("necrosis", 0)) - float(left_tissue.get("necrosis", 0)),
        },
    }


class ClinicalAPI:
    def __init__(self, database, service_status_provider: Optional[Callable[[], Dict[str, Any]]] = None):
        self.db = database
        self.blueprint = Blueprint("clinical_api", __name__, url_prefix="/api/v1")
        self.project_root = Path(__file__).resolve().parents[2]
        self.upload_dir = self.project_root / "output" / "uploads"
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        self.report_dir = self.project_root / "output" / "reports"
        self.report_dir.mkdir(parents=True, exist_ok=True)
        self.service_status_provider = service_status_provider
        self.require_auth = os.getenv("CLINICAL_API_REQUIRE_AUTH", "1") != "0"
        self.allowed_origin = os.getenv("CLINICAL_API_ALLOWED_ORIGIN", "http://localhost:3000")
        self.firebase_auth = self._init_firebase_auth()
        self.ml_service = ClinicalMLService()
        if self.require_auth and not self.firebase_auth:
            logger.error(
                "CLINICAL_API_REQUIRE_AUTH=1 mas Firebase Admin nao foi configurado. "
                "Defina FIREBASE_SERVICE_ACCOUNT_FILE para ambiente de producao."
            )
        self.metrics = {
            "started_at": datetime.now().isoformat(),
            "jobs_total": 0,
            "jobs_failed": 0,
            "stage1_latency_ms_sum": 0,
            "stage2_latency_ms_sum": 0,
            "report_generation_ms_sum": 0,
            "report_generation_total": 0,
        }
        self._register_routes()
        self._register_hooks()

    def _init_firebase_auth(self):
        try:
            import firebase_admin
            from firebase_admin import credentials, auth
        except Exception:
            logger.warning("firebase_admin não instalado; validação Firebase indisponível.")
            return None

        if not firebase_admin._apps:
            service_account_json = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON")
            service_account_file = os.getenv("FIREBASE_SERVICE_ACCOUNT_FILE")
            google_credentials_file = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
            if service_account_json:
                cred = credentials.Certificate(json.loads(service_account_json))
            elif service_account_file and Path(service_account_file).exists():
                cred = credentials.Certificate(service_account_file)
            elif google_credentials_file and Path(google_credentials_file).exists():
                cred = credentials.Certificate(google_credentials_file)
            else:
                logger.warning(
                    "Credencial Firebase ausente. Defina FIREBASE_SERVICE_ACCOUNT_JSON, "
                    "FIREBASE_SERVICE_ACCOUNT_FILE ou GOOGLE_APPLICATION_CREDENTIALS."
                )
                return None
            firebase_admin.initialize_app(cred)
        return auth

    @staticmethod
    def _normalize_risk(value: Any) -> str:
        mapping = {
            "low": "baixo",
            "baixo": "baixo",
            "medium": "moderado",
            "moderate": "moderado",
            "moderado": "moderado",
            "high": "alto",
            "alto": "alto",
            "critical": "critico",
            "critico": "critico",
            "crítico": "critico",
        }
        normalized = str(value or "moderado").strip().lower()
        return mapping.get(normalized, normalized or "moderado")

    @staticmethod
    def _primary_role(user: Dict[str, Any] | None) -> str:
        roles = user_roles(user)
        ordered = ("admin", "clinical-admin", "doctor", "nurse", "clinician", "estomaterapeuta", "researcher")
        for role in ordered:
            if role in roles:
                return role
        return "unknown"

    def _record_audit_event(
        self,
        *,
        patient_id: str,
        case_id: str,
        entity_type: str,
        entity_id: str,
        action: str,
        user: Dict[str, Any] | None,
        before: Dict[str, Any] | None = None,
        after: Dict[str, Any] | None = None,
        metadata: Dict[str, Any] | None = None,
    ) -> None:
        if not hasattr(self.db, "create_audit_event"):
            return
        self.db.create_audit_event(
            {
                "patient_id": patient_id,
                "case_id": case_id,
                "entity_type": entity_type,
                "entity_id": entity_id,
                "action": action,
                "actor_uid": user_uid(user),
                "actor_name": user_display_name(user),
                "actor_role": self._primary_role(user),
                "before_json": before,
                "after_json": after,
                "metadata": metadata or {},
            }
        )

    def _ensure_alert_action_allowed(self, user: Dict[str, Any], alert: Dict[str, Any], action: str) -> None:
        roles = user_roles(user)
        severity = self._normalize_risk(alert.get("severity"))
        if {"admin", "clinical-admin", "superadmin"} & roles:
            return
        if action == "acknowledge":
            if roles & {"doctor", "nurse", "clinician", "estomaterapeuta"}:
                return
            abort(403, description="acknowledge alert requires nurse, doctor, or admin role")
        if action == "resolve":
            if "doctor" in roles:
                return
            if roles & {"nurse", "clinician", "estomaterapeuta"} and severity in {"baixo", "moderado"}:
                return
            abort(403, description="resolve alert requires doctor/admin or nurse for low/moderate severity")

    def _ensure_follow_up_completion_allowed(self, user: Dict[str, Any], follow_up: Dict[str, Any]) -> None:
        roles = user_roles(user)
        if {"admin", "clinical-admin", "superadmin"} & roles:
            return
        assigned_role = str(follow_up.get("assigned_role") or "").strip().lower()
        if "doctor" in roles:
            return
        if roles & {"nurse", "clinician", "estomaterapeuta"}:
            if assigned_role in {"", "nurse", "clinician", "estomaterapeuta"}:
                return
        abort(403, description="complete follow-up requires assigned clinical role, doctor, or admin")

    def _ensure_care_plan_update_allowed(self, user: Dict[str, Any], plan: Dict[str, Any], updates: Dict[str, Any]) -> None:
        roles = user_roles(user)
        if {"admin", "clinical-admin", "superadmin", "doctor"} & roles:
            return
        if roles & {"nurse", "clinician", "estomaterapeuta"}:
            restricted = {"status", "risk_level", "title"}
            if any(field in updates for field in restricted):
                abort(403, description="changing care plan status, risk, or title requires doctor or admin")
            if str(plan.get("risk_level") or "").lower() in {"alto", "critico"}:
                abort(403, description="updating high-risk care plans requires doctor or admin")
            return
        abort(403, description="update care plan requires nurse, doctor, or admin role")

    def _ensure_case_assignment_allowed(self, user: Dict[str, Any], wound_case: Dict[str, Any], action: str) -> None:
        roles = user_roles(user)
        if {"admin", "clinical-admin", "superadmin", "doctor"} & roles:
            return
        if action == "claim" and roles & {"nurse", "clinician", "estomaterapeuta"}:
            return
        current_owner = str(wound_case.get("assigned_to_uid") or "").strip()
        if action == "handoff" and roles & {"nurse", "clinician", "estomaterapeuta"}:
            if current_owner and current_owner == str(user_uid(user) or ""):
                return
        abort(403, description=f"{action} case requires assigned owner, doctor, or admin role")

    def _ensure_alert_assignment_allowed(self, user: Dict[str, Any], alert: Dict[str, Any], action: str) -> None:
        roles = user_roles(user)
        if {"admin", "clinical-admin", "superadmin", "doctor"} & roles:
            return
        if action == "claim" and roles & {"nurse", "clinician", "estomaterapeuta"}:
            return
        current_owner = str(alert.get("assigned_to_uid") or "").strip()
        if action == "handoff" and roles & {"nurse", "clinician", "estomaterapeuta"}:
            if current_owner and current_owner == str(user_uid(user) or ""):
                return
        abort(403, description=f"{action} alert requires assigned owner, doctor, or admin role")

    def _register_hooks(self):
        bp = self.blueprint

        @bp.before_request
        def enforce_auth():
            if request.method == "OPTIONS":
                return None
            if request.path.endswith("/health"):
                return None
            enforce_request_auth()
            return None

        @bp.after_request
        def add_cors_headers(response):
            response.headers["Access-Control-Allow-Origin"] = self.allowed_origin
            response.headers["Access-Control-Allow-Headers"] = "Authorization, Content-Type"
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
            response.headers["Access-Control-Allow-Credentials"] = "true"
            response.headers["Cache-Control"] = "no-store"
            response.headers["X-Content-Type-Options"] = "nosniff"
            return response

    def _register_routes(self):
        bp = self.blueprint

        @bp.route("/health", methods=["GET", "OPTIONS"])
        def health():
            report_avg = 0
            if self.metrics["report_generation_total"] > 0:
                report_avg = self.metrics["report_generation_ms_sum"] / self.metrics["report_generation_total"]
            fail_rate = 0
            if self.metrics["jobs_total"] > 0:
                fail_rate = self.metrics["jobs_failed"] / self.metrics["jobs_total"]
            components = {}
            if self.service_status_provider:
                try:
                    components = self.service_status_provider() or {}
                except Exception as exc:
                    logger.warning(f"health service status provider falhou: {exc}")
                    components = {"official_api": "degraded"}
            return jsonify(
                {
                    "status": "ok",
                    "timestamp": datetime.now().isoformat(),
                    "auth_required": self.require_auth,
                    "firebase_ready": bool(self.firebase_auth),
                    "components": components,
                    "metrics": {
                        "jobs_total": self.metrics["jobs_total"],
                        "jobs_failed": self.metrics["jobs_failed"],
                        "job_failure_rate": round(fail_rate, 4),
                        "stage1_latency_avg_ms": round(
                            self.metrics["stage1_latency_ms_sum"] / self.metrics["jobs_total"], 2
                        )
                        if self.metrics["jobs_total"]
                        else 0,
                        "stage2_latency_avg_ms": round(
                            self.metrics["stage2_latency_ms_sum"] / self.metrics["jobs_total"], 2
                        )
                        if self.metrics["jobs_total"]
                        else 0,
                        "report_generation_avg_ms": round(report_avg, 2),
                    },
                }
            )

        @bp.route("/evaluations", methods=["POST"])
        def create_evaluation():
            user = ensure_clinical_write_access(action="create evaluations")
            payload = validate_json_request(CreateEvaluationPayload).model_dump()
            patient = ensure_patient_access(self.db, payload["patient_id"], user=user)

            case_id = payload.get("lesion_id") or payload.get("case_id")
            if case_id:
                existing_case = self.db.get_wound_case(case_id)
                if not existing_case:
                    return jsonify({"error": "caso_clinico_nao_encontrado"}), 404
                if str(existing_case["patient_id"]) != str(patient.id):
                    return jsonify({"error": "case_id_nao_pertence_ao_paciente"}), 400
            else:
                case = self.db.create_wound_case(
                    patient.id,
                    {
                        "title": payload.get("wound_type"),
                        "wound_type": payload.get("wound_type"),
                        "location": payload.get("wound_location"),
                        "metadata": {"created_by": user_display_name(user)},
                    },
                )
                case_id = case["id"] if case else None

            record = self.db.create_wound_evaluation(
                {
                    **payload,
                    "patient_id": patient.id,
                    "case_id": case_id,
                    "professional_name": user_display_name(user),
                    "metadata": {"created_by": user_display_name(user)},
                }
            )
            if not record:
                return jsonify({"error": "evaluation_creation_failed"}), 500
            return jsonify(record), 201

        @bp.route("/evaluations/<evaluation_id>/images", methods=["POST"])
        def upload_evaluation_image(evaluation_id: str):
            user = ensure_clinical_write_access(action="upload clinical images")
            enforce_rate_limit("upload", 30)
            evaluation = ensure_evaluation_access(self.db, evaluation_id, user=user)

            image = request.files.get("image")
            if not image:
                return jsonify({"error": "arquivo 'image' é obrigatório"}), 400

            assert_allowed_form_fields(request.form, allowed={"imageRole"})
            role = normalize_image_role(request.form.get("imageRole", "clinical"))
            validated_image = validate_and_sanitize_image_upload(image)
            image_name = f"{evaluation_id}_{int(time.time() * 1000)}{validated_image.extension}"
            image_path = self.upload_dir / image_name
            image_path.write_bytes(validated_image.content)

            saved = self.db.add_wound_image(
                evaluation_id,
                {
                    "image_role": role,
                    "image_path": str(image_path),
                    "content_type": validated_image.mime_type,
                    "metadata": {
                        "original_name": validated_image.original_name,
                        "uploaded_by": user_display_name(user),
                        "width": validated_image.width,
                        "height": validated_image.height,
                        "size_bytes": len(validated_image.content),
                        "patient_id": evaluation["patient_id"],
                        "case_id": evaluation.get("case_id"),
                        "review_status": "nao_revisada",
                        "captured_at": datetime.now().isoformat(),
                    },
                },
            )
            if not saved:
                return jsonify({"error": "falha ao persistir imagem"}), 500
            return jsonify(saved), 201

        @bp.route("/evaluations/<evaluation_id>/analyze", methods=["POST"])
        def analyze_evaluation(evaluation_id: str):
            user = ensure_clinical_write_access(action="run AI inference")
            ensure_evaluation_access(self.db, evaluation_id, user=user)
            enforce_rate_limit("analyze", 20)
            body = validate_json_request(AnalyzeEvaluationPayload).model_dump()
            force_fallback = bool(body.get("forceFallback", False))
            run = self.db.create_ai_run(evaluation_id, use_fallback=force_fallback)
            if not run:
                return jsonify({"error": "falha ao criar job"}), 500

            thread = threading.Thread(
                target=self._process_ai_pipeline,
                args=(run["id"], evaluation_id, force_fallback),
                daemon=True,
            )
            thread.start()
            return jsonify({"jobId": run["id"], "status": run["status"]}), 202

        @bp.route("/images/<image_id>/content", methods=["GET"])
        def get_image_content(image_id: str):
            user = current_user_required()
            image = self.db.get_wound_image(image_id)
            if not image:
                return jsonify({"error": "image_not_found"}), 404
            ensure_evaluation_access(self.db, str(image["evaluation_id"]), user=user)
            path = Path(str(image.get("image_path") or ""))
            if not path.is_absolute():
                path = (self.project_root / path).resolve()
            if not path.exists():
                return jsonify({"error": "image_file_not_found"}), 404
            return send_file(str(path), mimetype=image.get("content_type") or "image/jpeg")

        @bp.route("/analysis-jobs/<job_id>", methods=["GET"])
        def get_job(job_id: str):
            current_user_required()
            run = ensure_job_access(self.db, job_id)
            result = self.db.get_ai_result_by_run(job_id)
            return jsonify({"job": run, "result": result}), 200

        @bp.route("/patients/<patient_id>/evaluations", methods=["GET"])
        def list_patient_evaluations(patient_id: str):
            user = current_user_required()
            ensure_patient_access(self.db, patient_id, user=user)
            case_id = request.args.get("caseId")
            if case_id:
                wound_case = self.db.get_wound_case(case_id)
                if not wound_case:
                    return jsonify({"error": "caso clínico não encontrado"}), 404
                if str(wound_case["patient_id"]) != str(patient_id):
                    return jsonify({"error": "case_id não pertence ao paciente informado"}), 400
            evaluations = self.db.list_patient_evaluations(patient_id, case_id=case_id)
            return jsonify(evaluations), 200

        @bp.route("/patients/<patient_id>/lesions", methods=["GET"])
        def list_patient_lesions(patient_id: str):
            user = current_user_required()
            ensure_patient_access(self.db, patient_id, user=user)
            lesions = self.db.list_wound_cases(patient_id)
            enriched: list[dict[str, Any]] = []
            for lesion in lesions:
                active_plan = self.db.get_active_care_plan_for_case(lesion["id"])
                evaluations = self.db.list_patient_evaluations(patient_id, case_id=lesion["id"])
                latest = evaluations[0] if evaluations else None
                latest_result = (
                    self.db.get_latest_ai_result_for_evaluation(latest["id"])
                    if latest and latest.get("id")
                    else None
                )
                enriched.append(
                    {
                        **lesion,
                        "latest_evaluation": latest,
                        "latest_inference_result": latest_result,
                        "active_care_plan": active_plan,
                        "open_alert_count": len(self.db.list_case_alerts(lesion["id"], active_only=True)),
                    }
                )
            return jsonify(enriched), 200

        @bp.route("/lesions/<case_id>/timeline", methods=["GET"])
        def lesion_timeline(case_id: str):
            user = current_user_required()
            wound_case = ensure_case_access(self.db, case_id, user=user)
            raw_timeline = self.db.get_case_timeline(wound_case["id"])
            if not raw_timeline:
                return jsonify({"error": "lesion_timeline_not_found"}), 404
            timeline = build_case_timeline(
                patient=raw_timeline["patient"],
                lesion=raw_timeline["lesion"],
                evaluations=raw_timeline["evaluations"],
                care_plans=raw_timeline["care_plans"],
                follow_ups=raw_timeline["follow_ups"],
                alerts=raw_timeline["alerts"],
                audit_log=raw_timeline.get("audit_log", []),
            )
            return jsonify(timeline), 200

        @bp.route("/patients/<patient_id>/timeline", methods=["GET"])
        def patient_timeline(patient_id: str):
            user = current_user_required()
            ensure_patient_access(self.db, patient_id, user=user)
            case_id = request.args.get("lesionId") or request.args.get("caseId")
            if not case_id:
                cases = self.db.list_wound_cases(patient_id)
                if not cases:
                    return jsonify({"patient_id": patient_id, "lesions": [], "timelines": []}), 200
                timelines = []
                for wound_case in cases:
                    raw_timeline = self.db.get_case_timeline(wound_case["id"])
                    if raw_timeline:
                        timelines.append(
                            build_case_timeline(
                                patient=raw_timeline["patient"],
                                lesion=raw_timeline["lesion"],
                                evaluations=raw_timeline["evaluations"],
                                care_plans=raw_timeline["care_plans"],
                                follow_ups=raw_timeline["follow_ups"],
                                alerts=raw_timeline["alerts"],
                                audit_log=raw_timeline.get("audit_log", []),
                            )
                        )
                return jsonify({"patient_id": patient_id, "lesions": cases, "timelines": timelines}), 200
            return lesion_timeline(case_id)

        @bp.route("/lesions/<case_id>/claim", methods=["PATCH"])
        def claim_case(case_id: str):
            user = current_user_required()
            wound_case = ensure_case_access(self.db, case_id, user=user)
            self._ensure_case_assignment_allowed(user, wound_case, "claim")
            payload = validate_json_request(ClaimCasePayload).model_dump()
            updated = self.db.update_wound_case(
                case_id,
                {
                    "assigned_to_uid": user_uid(user),
                    "assigned_to_name": user_display_name(user),
                    "assigned_to_role": self._primary_role(user),
                    "claimed_by_uid": user_uid(user),
                    "claimed_by_name": user_display_name(user),
                    "claimed_by_role": self._primary_role(user),
                    "claimed_at": datetime.now().isoformat(),
                    "metadata": {"last_assignment_note": payload["notes"]},
                },
            )
            if not updated:
                return jsonify({"error": "case_claim_failed"}), 500
            self._record_audit_event(
                patient_id=str(wound_case["patient_id"]),
                case_id=str(case_id),
                entity_type="case",
                entity_id=str(case_id),
                action="case_claimed",
                user=user,
                before=wound_case,
                after=updated,
                metadata=payload,
            )
            return jsonify(updated), 200

        @bp.route("/lesions/<case_id>/handoff", methods=["PATCH"])
        def handoff_case(case_id: str):
            user = current_user_required()
            wound_case = ensure_case_access(self.db, case_id, user=user)
            self._ensure_case_assignment_allowed(user, wound_case, "handoff")
            payload = validate_json_request(HandoffCasePayload).model_dump(exclude_none=True)
            updated = self.db.update_wound_case(
                case_id,
                {
                    "assigned_to_uid": payload["assigned_to_uid"],
                    "assigned_to_name": payload["assigned_to_name"],
                    "assigned_to_role": payload["assigned_to_role"],
                    "handoff_to_uid": payload["assigned_to_uid"],
                    "handoff_to_name": payload["assigned_to_name"],
                    "handoff_to_role": payload["assigned_to_role"],
                    "handoff_at": datetime.now().isoformat(),
                    "unit_id": payload.get("unit_id", wound_case.get("unit_id")),
                    "team_id": payload.get("team_id", wound_case.get("team_id")),
                    "metadata": {
                        "last_assignment_note": payload["notes"],
                        "handoff_from_uid": user_uid(user),
                        "handoff_from_name": user_display_name(user),
                    },
                },
            )
            if not updated:
                return jsonify({"error": "case_handoff_failed"}), 500
            self._record_audit_event(
                patient_id=str(wound_case["patient_id"]),
                case_id=str(case_id),
                entity_type="case",
                entity_id=str(case_id),
                action="case_handoff",
                user=user,
                before=wound_case,
                after=updated,
                metadata=payload,
            )
            return jsonify(updated), 200

        @bp.route("/care-plans", methods=["POST"])
        def create_care_plan():
            user = ensure_clinical_write_access(action="create care plans")
            payload = validate_json_request(CreateCarePlanPayload).model_dump()
            ensure_patient_access(self.db, payload["patient_id"], user=user)
            wound_case = ensure_case_access(self.db, payload["lesion_id"], user=user)
            if str(wound_case["patient_id"]) != str(payload["patient_id"]):
                return jsonify({"error": "lesion_id_nao_pertence_ao_paciente"}), 400
            record = self.db.create_care_plan(
                {
                    "patient_id": payload["patient_id"],
                    "case_id": payload["lesion_id"],
                    "title": payload["title"],
                    "status": payload["status"],
                    "risk_level": payload["risk_level"],
                    "goals": payload.get("goals", []),
                    "frequency": payload.get("frequency"),
                    "tasks": payload.get("tasks", []),
                    "alerts": payload.get("alerts", []),
                    "review_due_date": payload.get("review_due_date"),
                    "created_by": user_display_name(user),
                    "metadata": {"notes": payload.get("notes")},
                }
            )
            if not record:
                return jsonify({"error": "care_plan_creation_failed"}), 500
            self._record_audit_event(
                patient_id=str(record["patient_id"]),
                case_id=str(record["case_id"]),
                entity_type="care_plan",
                entity_id=str(record["id"]),
                action="care_plan_created",
                user=user,
                after=record,
                metadata={"source": "manual_api"},
            )
            return jsonify(record), 201

        @bp.route("/lesions/<case_id>/care-plans", methods=["GET"])
        def list_lesion_care_plans(case_id: str):
            current_user_required()
            ensure_case_access(self.db, case_id)
            return jsonify(self.db.list_case_care_plans(case_id)), 200

        @bp.route("/care-plans/<plan_id>", methods=["PATCH"])
        def update_care_plan(plan_id: str):
            user = current_user_required()
            plan = self.db.get_care_plan(plan_id)
            if not plan:
                return jsonify({"error": "care_plan_not_found"}), 404
            ensure_case_access(self.db, plan["case_id"], user=user)
            payload = validate_json_request(UpdateCarePlanPayload).model_dump(exclude_none=True)
            self._ensure_care_plan_update_allowed(user, plan, payload)
            metadata = {"updated_by": user_display_name(user)}
            if payload.get("notes"):
                metadata["notes"] = payload["notes"]
            updated = self.db.update_care_plan(
                plan_id,
                {
                    key: value
                    for key, value in payload.items()
                    if key in {"title", "status", "risk_level", "goals", "frequency", "tasks", "alerts", "review_due_date"}
                }
                | {"metadata": metadata},
            )
            if not updated:
                return jsonify({"error": "care_plan_update_failed"}), 500
            self._record_audit_event(
                patient_id=str(plan["patient_id"]),
                case_id=str(plan["case_id"]),
                entity_type="care_plan",
                entity_id=plan_id,
                action="care_plan_updated",
                user=user,
                before=plan,
                after=updated,
                metadata={"notes": payload.get("notes")},
            )
            return jsonify(updated), 200

        @bp.route("/follow-ups", methods=["POST"])
        def create_follow_up():
            user = ensure_clinical_write_access(action="create follow-ups")
            payload = validate_json_request(CreateFollowUpPayload).model_dump()
            ensure_patient_access(self.db, payload["patient_id"], user=user)
            wound_case = ensure_case_access(self.db, payload["lesion_id"], user=user)
            if str(wound_case["patient_id"]) != str(payload["patient_id"]):
                return jsonify({"error": "lesion_id_nao_pertence_ao_paciente"}), 400
            record = self.db.create_follow_up(
                {
                    "patient_id": payload["patient_id"],
                    "case_id": payload["lesion_id"],
                    "care_plan_id": payload.get("care_plan_id"),
                    "evaluation_id": payload.get("evaluation_id"),
                    "scheduled_for": payload["scheduled_for"],
                    "status": payload["status"],
                    "reason": payload.get("reason"),
                    "assigned_role": payload.get("assigned_role"),
                    "created_by": user_display_name(user),
                    "notes": payload.get("notes"),
                }
            )
            if not record:
                return jsonify({"error": "follow_up_creation_failed"}), 500
            self._record_audit_event(
                patient_id=str(record["patient_id"]),
                case_id=str(record["case_id"]),
                entity_type="follow_up",
                entity_id=str(record["id"]),
                action="follow_up_created",
                user=user,
                after=record,
                metadata={"source": "manual_api"},
            )
            return jsonify(record), 201

        @bp.route("/lesions/<case_id>/follow-ups", methods=["GET"])
        def list_lesion_follow_ups(case_id: str):
            user = current_user_required()
            ensure_case_access(self.db, case_id, user=user)
            return jsonify(self.db.list_case_follow_ups(case_id)), 200

        @bp.route("/follow-ups/<follow_up_id>/complete", methods=["PATCH"])
        def complete_follow_up(follow_up_id: str):
            user = current_user_required()
            follow_up = self.db.get_follow_up(follow_up_id)
            if not follow_up:
                return jsonify({"error": "follow_up_not_found"}), 404
            ensure_case_access(self.db, follow_up["case_id"], user=user)
            self._ensure_follow_up_completion_allowed(user, follow_up)
            payload = validate_json_request(CompleteFollowUpPayload).model_dump(exclude_none=True)
            status = payload.get("status", "completed")
            completed_at = datetime.now().isoformat() if status == "completed" else follow_up.get("completed_at")
            metadata = {
                "completed_by_uid": user_uid(user),
                "completed_by_name": user_display_name(user),
                "completed_by_role": self._primary_role(user),
            }
            updated = self.db.update_follow_up(
                follow_up_id,
                {
                    "status": status,
                    "scheduled_for": payload.get("scheduled_for", follow_up["scheduled_for"]),
                    "reason": payload.get("reason", follow_up.get("reason")),
                    "assigned_role": payload.get("assigned_role", follow_up.get("assigned_role")),
                    "notes": payload.get("notes", follow_up.get("notes")),
                    "completed_at": completed_at,
                    "metadata": metadata,
                },
            )
            if not updated:
                return jsonify({"error": "follow_up_update_failed"}), 500
            self._record_audit_event(
                patient_id=str(follow_up["patient_id"]),
                case_id=str(follow_up["case_id"]),
                entity_type="follow_up",
                entity_id=follow_up_id,
                action=f"follow_up_{status}",
                user=user,
                before=follow_up,
                after=updated,
                metadata={"notes": payload.get("notes")},
            )
            return jsonify(updated), 200

        @bp.route("/lesions/<case_id>/alerts", methods=["GET"])
        def list_lesion_alerts(case_id: str):
            user = current_user_required()
            ensure_case_access(self.db, case_id, user=user)
            active_only = request.args.get("activeOnly", "0").strip().lower() in {"1", "true", "yes"}
            return jsonify(self.db.list_case_alerts(case_id, active_only=active_only)), 200

        @bp.route("/alerts/<alert_id>/claim", methods=["PATCH"])
        def claim_alert(alert_id: str):
            user = current_user_required()
            alert = self.db.get_clinical_alert(alert_id)
            if not alert:
                return jsonify({"error": "alert_not_found"}), 404
            ensure_case_access(self.db, alert["case_id"], user=user)
            self._ensure_alert_assignment_allowed(user, alert, "claim")
            payload = validate_json_request(ClaimAlertPayload).model_dump()
            updated = self.db.update_clinical_alert(
                alert_id,
                {
                    "assigned_to_uid": user_uid(user),
                    "assigned_to_name": user_display_name(user),
                    "assigned_to_role": self._primary_role(user),
                    "claimed_by_uid": user_uid(user),
                    "claimed_by_name": user_display_name(user),
                    "claimed_by_role": self._primary_role(user),
                    "claimed_at": datetime.now().isoformat(),
                    "metadata": {"last_assignment_note": payload["notes"]},
                },
            )
            if not updated:
                return jsonify({"error": "alert_claim_failed"}), 500
            self._record_audit_event(
                patient_id=str(alert["patient_id"]),
                case_id=str(alert["case_id"]),
                entity_type="alert",
                entity_id=alert_id,
                action="alert_claimed",
                user=user,
                before=alert,
                after=updated,
                metadata=payload,
            )
            return jsonify(updated), 200

        @bp.route("/alerts/<alert_id>/handoff", methods=["PATCH"])
        def handoff_alert(alert_id: str):
            user = current_user_required()
            alert = self.db.get_clinical_alert(alert_id)
            if not alert:
                return jsonify({"error": "alert_not_found"}), 404
            ensure_case_access(self.db, alert["case_id"], user=user)
            self._ensure_alert_assignment_allowed(user, alert, "handoff")
            payload = validate_json_request(HandoffAlertPayload).model_dump()
            updated = self.db.update_clinical_alert(
                alert_id,
                {
                    "assigned_to_uid": payload["assigned_to_uid"],
                    "assigned_to_name": payload["assigned_to_name"],
                    "assigned_to_role": payload["assigned_to_role"],
                    "handoff_to_uid": payload["assigned_to_uid"],
                    "handoff_to_name": payload["assigned_to_name"],
                    "handoff_to_role": payload["assigned_to_role"],
                    "handoff_at": datetime.now().isoformat(),
                    "metadata": {
                        "last_assignment_note": payload["notes"],
                        "handoff_from_uid": user_uid(user),
                        "handoff_from_name": user_display_name(user),
                    },
                },
            )
            if not updated:
                return jsonify({"error": "alert_handoff_failed"}), 500
            self._record_audit_event(
                patient_id=str(alert["patient_id"]),
                case_id=str(alert["case_id"]),
                entity_type="alert",
                entity_id=alert_id,
                action="alert_handoff",
                user=user,
                before=alert,
                after=updated,
                metadata=payload,
            )
            return jsonify(updated), 200

        @bp.route("/alerts/<alert_id>/acknowledge", methods=["PATCH"])
        def acknowledge_alert(alert_id: str):
            user = current_user_required()
            alert = self.db.get_clinical_alert(alert_id)
            if not alert:
                return jsonify({"error": "alert_not_found"}), 404
            ensure_case_access(self.db, alert["case_id"], user=user)
            self._ensure_alert_action_allowed(user, alert, "acknowledge")
            payload = validate_json_request(AlertActionPayload).model_dump(exclude_none=True)
            updated = self.db.update_clinical_alert(
                alert_id,
                {
                    "status": "acknowledged",
                    "metadata": {
                        "acknowledged_by_uid": user_uid(user),
                        "acknowledged_by_name": user_display_name(user),
                        "acknowledged_by_role": self._primary_role(user),
                        "notes": payload.get("notes"),
                        "reason": payload.get("reason"),
                    },
                },
            )
            if not updated:
                return jsonify({"error": "alert_acknowledge_failed"}), 500
            self._record_audit_event(
                patient_id=str(alert["patient_id"]),
                case_id=str(alert["case_id"]),
                entity_type="alert",
                entity_id=alert_id,
                action="alert_acknowledged",
                user=user,
                before=alert,
                after=updated,
                metadata=payload,
            )
            return jsonify(updated), 200

        @bp.route("/alerts/<alert_id>/resolve", methods=["PATCH"])
        def resolve_alert(alert_id: str):
            user = current_user_required()
            alert = self.db.get_clinical_alert(alert_id)
            if not alert:
                return jsonify({"error": "alert_not_found"}), 404
            ensure_case_access(self.db, alert["case_id"], user=user)
            self._ensure_alert_action_allowed(user, alert, "resolve")
            payload = validate_json_request(AlertActionPayload).model_dump(exclude_none=True)
            updated = self.db.update_clinical_alert(
                alert_id,
                {
                    "status": "resolved",
                    "resolved_at": datetime.now().isoformat(),
                    "metadata": {
                        "resolved_by_uid": user_uid(user),
                        "resolved_by_name": user_display_name(user),
                        "resolved_by_role": self._primary_role(user),
                        "notes": payload.get("notes"),
                        "reason": payload.get("reason"),
                    },
                },
            )
            if not updated:
                return jsonify({"error": "alert_resolve_failed"}), 500
            self._record_audit_event(
                patient_id=str(alert["patient_id"]),
                case_id=str(alert["case_id"]),
                entity_type="alert",
                entity_id=alert_id,
                action="alert_resolved",
                user=user,
                before=alert,
                after=updated,
                metadata=payload,
            )
            return jsonify(updated), 200

        @bp.route("/lesions/<case_id>/audit", methods=["GET"])
        def list_lesion_audit(case_id: str):
            user = current_user_required()
            ensure_case_access(self.db, case_id, user=user)
            limit = max(1, min(int(request.args.get("limit", 50)), 200))
            return jsonify(self.db.list_case_audit_events(case_id, limit=limit)), 200

        @bp.route("/comparisons", methods=["GET"])
        def compare_evaluations():
            current_user_required()
            left_id = request.args.get("left")
            right_id = request.args.get("right")
            if not left_id or not right_id:
                return jsonify({"error": "left e right são obrigatórios"}), 400
            left = ensure_evaluation_access(self.db, left_id)
            right = ensure_evaluation_access(self.db, right_id)
            if str(left["patient_id"]) != str(right["patient_id"]):
                return jsonify({"error": "comparação entre pacientes diferentes não é permitida"}), 400
            return jsonify({"left": left, "right": right, "deltas": _calc_deltas(left, right)}), 200

        @bp.route("/reports/generate", methods=["POST"])
        def generate_report():
            user = ensure_clinical_write_access(action="generate reports")
            enforce_rate_limit("report", 10)
            started = time.time()
            payload = validate_json_request(GenerateReportPayload).model_dump()
            patient = ensure_patient_access(self.db, payload["patient_id"], user=user)
            patient_id = patient.id
            case_id = payload.get("lesion_id") or payload.get("case_id")
            if case_id:
                wound_case = self.db.get_wound_case(case_id)
                if not wound_case:
                    return jsonify({"error": "caso clínico não encontrado"}), 404
                if str(wound_case["patient_id"]) != str(patient_id):
                    return jsonify({"error": "case_id não pertence ao paciente informado"}), 400

            evals = self.db.list_patient_evaluations(patient_id, case_id=case_id)
            if not evals:
                return jsonify({"error": "nenhuma avaliação para gerar relatório"}), 400
            latest = evals[0]
            baseline = evals[-1]
            report_json = {
                "patient_id": patient_id,
                "generated_at": datetime.now().isoformat(),
                "type": payload.get("report_type", "evolution"),
                "professional": user_display_name(user),
                "baseline": baseline,
                "latest": latest,
                "deltas": _calc_deltas(baseline, latest),
                "recommendation": self._build_recommendation(latest),
            }

            report_name = f"report_{uuid.uuid4().hex}"
            json_path = self.report_dir / f"{report_name}.json"
            pdf_path = self.report_dir / f"{report_name}.pdf"
            docx_path = self.report_dir / f"{report_name}.docx"

            json_path.write_text(json.dumps(report_json, ensure_ascii=False, indent=2), encoding="utf-8")
            pdf_path.write_text(
                "Relatório clínico REDISUS\n\n" + json.dumps(report_json, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            docx_path.write_text(
                "Relatório clínico REDISUS\n\n" + json.dumps(report_json, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

            saved = self.db.create_structured_report(
                {
                    "patient_id": patient_id,
                    "case_id": case_id,
                    "evaluation_id": latest.get("id"),
                    "report_type": payload.get("report_type", "evolution"),
                    "report_json": report_json,
                    "pdf_path": str(pdf_path),
                    "docx_path": str(docx_path),
                    "generated_by": user_display_name(user),
                }
            )
            if not saved:
                return jsonify({"error": "falha ao salvar relatório"}), 500
            elapsed = int((time.time() - started) * 1000)
            self.metrics["report_generation_ms_sum"] += elapsed
            self.metrics["report_generation_total"] += 1
            logger.info(f"[reportId={saved['id']} patientId={patient_id}] relatório gerado em {elapsed}ms")
            return jsonify({"reportId": saved["id"], "report": report_json}), 201

        @bp.route("/reports/<report_id>/download", methods=["GET"])
        def download_report(report_id: str):
            current_user_required()
            fmt = (request.args.get("format") or "json").lower()
            if fmt not in {"json", "pdf", "docx"}:
                return jsonify({"error": "formato indisponível"}), 400
            report = ensure_report_access(self.db, report_id)

            if fmt == "json":
                path = self.report_dir / f"report_{report_id}.json"
                path.write_text(json.dumps(report["report_json"], ensure_ascii=False, indent=2), encoding="utf-8")
                return send_file(str(path), as_attachment=True, download_name=f"{report_id}.json")

            if fmt == "pdf" and report.get("pdf_path"):
                return send_file(report["pdf_path"], as_attachment=True)
            if fmt == "docx" and report.get("docx_path"):
                return send_file(report["docx_path"], as_attachment=True)
            return jsonify({"error": "formato indisponível"}), 400

    def _build_recommendation(self, evaluation: Dict[str, Any]) -> str:
        pain = _safe_float(evaluation.get("pain_score")) or 0
        area = _safe_float(evaluation.get("wound_area_cm2")) or 0
        if pain >= 7 or area >= 15:
            return "Intensificar monitoramento e revisar cobertura em até 72h."
        if pain >= 4 or area >= 8:
            return "Manter conduta e reavaliar em 7 dias."
        return "Evolução favorável. Seguir protocolo e reavaliar em 14 dias."

    def _process_ai_pipeline(self, run_id: str, evaluation_id: str, force_fallback: bool):
        start = time.time()
        self.metrics["jobs_total"] += 1
        try:
            evaluation = self.db.get_wound_evaluation(evaluation_id)
            if not evaluation:
                raise ValueError("evaluation not found for AI pipeline")
            case_id = evaluation.get("case_id")
            if not case_id:
                raise ValueError("evaluation is missing lesion/case association")

            self.db.update_ai_run(run_id, {"status": "running_stage1"})
            stage1_start = time.time()
            time.sleep(0.8)
            stage1_latency = int((time.time() - stage1_start) * 1000)
            self.metrics["stage1_latency_ms_sum"] += stage1_latency

            self.db.update_ai_run(run_id, {"status": "running_stage2", "stage1_latency_ms": stage1_latency})
            stage2_start = time.time()
            evaluation = {
                **evaluation,
                "images": self.db.list_evaluation_images(evaluation_id),
            }
            runtime_inference = (
                self.ml_service.run_inference(evaluation)
                if not force_fallback
                else {
                    "raw_output": {
                        "etiology": "venous_ulcer",
                        "confidence": 0.68,
                        "tissue_percentages": {"granulation": 55, "slough": 28, "necrosis": 17},
                        "wound_area_cm2": float(evaluation.get("wound_area_cm2") or 0.0),
                        "diagnosis_summary": "Fallback operacional ativado para manter continuidade assistencial.",
                        "recommendations": [
                            "Validar manualmente a inferência antes de decisão terapêutica.",
                            "Reavaliar a lesão em até 72h se houver piora clínica.",
                        ],
                        "fallback_used": True,
                        "needs_expert_review": True,
                        "confidence_level": "low",
                        "metadata": {"source": "forced-fallback"},
                    },
                    "model_version": os.getenv("REDISUS_MODEL_VERSION", DEFAULT_MODEL_VERSION),
                    "model_descriptor": {"id": "forced-fallback"},
                }
            )
            raw_output = dict(runtime_inference.get("raw_output") or {})
            time.sleep(0.8)
            stage2_latency = int((time.time() - stage2_start) * 1000)
            self.metrics["stage2_latency_ms_sum"] += stage2_latency

            result_payload = normalize_ai_output(
                raw_output,
                patient_id=str(evaluation["patient_id"]),
                lesion_id=str(case_id),
                evaluation=evaluation,
                fallback_used=bool(raw_output.get("fallback_used")),
                model_version=str(runtime_inference.get("model_version") or os.getenv("REDISUS_MODEL_VERSION", DEFAULT_MODEL_VERSION)),
            )
            if isinstance(runtime_inference.get("model_descriptor"), dict):
                result_payload.setdefault("metadata", {})["model_descriptor"] = dict(runtime_inference["model_descriptor"])
            saved_result = self.db.save_ai_result(run_id, result_payload)
            if not saved_result:
                raise ValueError("failed to persist AI result")
            self._record_audit_event(
                patient_id=str(evaluation["patient_id"]),
                case_id=str(case_id),
                entity_type="inference_result",
                entity_id=str(saved_result["id"]),
                action="inference_result_created",
                user={"uid": "ai-pipeline", "name": "ai-pipeline", "role": "admin"},
                after=saved_result,
                metadata={"run_id": run_id},
            )

            care_plan = self.db.create_care_plan(
                build_care_plan_payload(
                    patient_id=str(evaluation["patient_id"]),
                    lesion_id=str(case_id),
                    evaluation_id=evaluation_id,
                    result_id=str(saved_result["id"]),
                    inference_result=result_payload,
                    created_by="ai-pipeline",
                )
            )
            if care_plan:
                self._record_audit_event(
                    patient_id=str(evaluation["patient_id"]),
                    case_id=str(case_id),
                    entity_type="care_plan",
                    entity_id=str(care_plan["id"]),
                    action="care_plan_created_by_ai",
                    user={"uid": "ai-pipeline", "name": "ai-pipeline", "role": "admin"},
                    after=care_plan,
                    metadata={"run_id": run_id},
                )
                follow_up = self.db.create_follow_up(
                    build_follow_up_payload(
                        patient_id=str(evaluation["patient_id"]),
                        lesion_id=str(case_id),
                        evaluation_id=evaluation_id,
                        care_plan_id=str(care_plan["id"]),
                        inference_result=result_payload,
                        created_by="ai-pipeline",
                    )
                )
                if follow_up:
                    self._record_audit_event(
                        patient_id=str(evaluation["patient_id"]),
                        case_id=str(case_id),
                        entity_type="follow_up",
                        entity_id=str(follow_up["id"]),
                        action="follow_up_scheduled_by_ai",
                        user={"uid": "ai-pipeline", "name": "ai-pipeline", "role": "admin"},
                        after=follow_up,
                        metadata={"run_id": run_id},
                    )
                    for alert_payload in build_alert_payloads(
                        patient_id=str(evaluation["patient_id"]),
                        lesion_id=str(case_id),
                        care_plan_id=str(care_plan["id"]),
                        follow_up_id=str(follow_up["id"]),
                        inference_result=result_payload,
                    ):
                        created_alert = self.db.create_clinical_alert(alert_payload)
                        if created_alert:
                            self._record_audit_event(
                                patient_id=str(evaluation["patient_id"]),
                                case_id=str(case_id),
                                entity_type="alert",
                                entity_id=str(created_alert["id"]),
                                action="alert_created_by_ai",
                                user={"uid": "ai-pipeline", "name": "ai-pipeline", "role": "admin"},
                                after=created_alert,
                                metadata={"run_id": run_id},
                            )

            self.db.update_ai_run(
                run_id,
                {
                    "status": "completed",
                    "use_fallback": int(bool(result_payload["inference"].get("fallback_used"))),
                    "stage2_latency_ms": stage2_latency,
                },
            )
            total = int((time.time() - start) * 1000)
            logger.info(f"[jobId={run_id} evaluationId={evaluation_id}] IA concluida em {total}ms")
        except Exception as e:
            logger.exception(f"[jobId={run_id} evaluationId={evaluation_id}] erro no pipeline IA: {e}")
            self.metrics["jobs_failed"] += 1
            self.db.update_ai_run(run_id, {"status": "failed", "failure_reason": str(e)})

