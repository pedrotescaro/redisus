import json
import os
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from flask import Blueprint, jsonify, request, send_file
from loguru import logger

from packages.clinical_domain.validation import (
    AIChatPayload,
    AnalyzeEvaluationPayload,
    CreateEvaluationPayload,
    GenerateReportPayload,
    assert_allowed_form_fields,
    normalize_image_role,
    validate_and_sanitize_image_upload,
    validate_json_request,
)
from packages.shared.security import (
    current_user_required,
    enforce_rate_limit,
    enforce_request_auth,
    ensure_evaluation_access,
    ensure_job_access,
    ensure_patient_access,
    ensure_report_access,
    user_display_name,
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
        self.upload_dir = Path("output/uploads")
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        self.report_dir = Path("output/reports")
        self.report_dir.mkdir(parents=True, exist_ok=True)
        self.service_status_provider = service_status_provider
        self.require_auth = os.getenv("CLINICAL_API_REQUIRE_AUTH", "1") != "0"
        self.allowed_origin = os.getenv("CLINICAL_API_ALLOWED_ORIGIN", "http://localhost:3000")
        self.firebase_auth = self._init_firebase_auth()
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
            user = current_user_required()
            payload = validate_json_request(CreateEvaluationPayload).model_dump()
            patient = ensure_patient_access(self.db, payload["patient_id"], user=user)

            case_id = payload.get("case_id")
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
            user = current_user_required()
            enforce_rate_limit("upload", 30)
            ensure_evaluation_access(self.db, evaluation_id, user=user)

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
                    },
                },
            )
            if not saved:
                return jsonify({"error": "falha ao persistir imagem"}), 500
            return jsonify(saved), 201

        @bp.route("/evaluations/<evaluation_id>/analyze", methods=["POST"])
        def analyze_evaluation(evaluation_id: str):
            user = current_user_required()
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
            user = current_user_required()
            enforce_rate_limit("report", 10)
            started = time.time()
            payload = validate_json_request(GenerateReportPayload).model_dump()
            patient = ensure_patient_access(self.db, payload["patient_id"], user=user)
            patient_id = patient.id
            case_id = payload.get("case_id")
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
            self.db.update_ai_run(run_id, {"status": "running_stage1"})
            stage1_start = time.time()
            time.sleep(0.8)
            stage1_latency = int((time.time() - stage1_start) * 1000)
            self.metrics["stage1_latency_ms_sum"] += stage1_latency

            self.db.update_ai_run(run_id, {"status": "running_stage2", "stage1_latency_ms": stage1_latency})
            stage2_start = time.time()

            # Fallback clínico consistente para ausência de modelo em runtime.
            output = {
                "etiology": "ulcera_venosa",
                "confidence": 0.74,
                "tissue_percentages": {"granulation": 62, "slough": 30, "necrosis": 8},
                "wound_area_cm2": 9.8,
                "diagnosis_summary": "Leito com granulação predominante e redução de necrose.",
                "recommendations": [
                    "Manter cobertura absorvente.",
                    "Controle de exsudato e proteção perilesional.",
                    "Reavaliação clínica em 7 dias.",
                ],
                "fallback_used": bool(force_fallback or True),
            }
            time.sleep(0.8)
            stage2_latency = int((time.time() - stage2_start) * 1000)
            self.metrics["stage2_latency_ms_sum"] += stage2_latency
            self.db.save_ai_result(run_id, output)
            self.db.update_ai_run(
                run_id,
                {
                    "status": "completed",
                    "use_fallback": int(output["fallback_used"]),
                    "stage2_latency_ms": stage2_latency,
                },
            )
            total = int((time.time() - start) * 1000)
            logger.info(f"[jobId={run_id} evaluationId={evaluation_id}] IA concluída em {total}ms")
        except Exception as e:
            logger.exception(f"[jobId={run_id} evaluationId={evaluation_id}] erro no pipeline IA: {e}")
            self.metrics["jobs_failed"] += 1
            self.db.update_ai_run(run_id, {"status": "failed", "failure_reason": str(e)})

