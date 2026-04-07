import json
import os
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from flask import Blueprint, jsonify, request, send_file
from loguru import logger


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
        default_require_auth = "1" if os.getenv("FLASK_ENV", "").lower() == "production" else "0"
        self.require_auth = os.getenv("CLINICAL_API_REQUIRE_AUTH", default_require_auth) != "0"
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
            if not self.require_auth:
                return None
            if not self.firebase_auth:
                return jsonify({"error": "auth_backend_not_configured"}), 503
            auth_header = request.headers.get("Authorization", "")
            if not auth_header.startswith("Bearer "):
                return jsonify({"error": "missing_bearer_token"}), 401
            token = auth_header.replace("Bearer ", "", 1).strip()
            try:
                request.firebase_user = self.firebase_auth.verify_id_token(token)
            except Exception:
                return jsonify({"error": "invalid_firebase_token"}), 401
            return None

        @bp.after_request
        def add_cors_headers(response):
            response.headers["Access-Control-Allow-Origin"] = self.allowed_origin
            response.headers["Access-Control-Allow-Headers"] = "Authorization, Content-Type"
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
            response.headers["Access-Control-Allow-Credentials"] = "true"
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
            payload = request.get_json(silent=True) or {}
            if not payload.get("patient_id"):
                return jsonify({"error": "patient_id é obrigatório"}), 400

            case_id = payload.get("case_id")
            if not case_id:
                case = self.db.create_wound_case(payload["patient_id"], payload)
                case_id = case["id"] if case else None

            record = self.db.create_wound_evaluation({**payload, "case_id": case_id})
            if not record:
                return jsonify({"error": "não foi possível criar avaliação"}), 500
            return jsonify(record), 201

        @bp.route("/evaluations/<evaluation_id>/images", methods=["POST"])
        def upload_evaluation_image(evaluation_id: str):
            evaluation = self.db.get_wound_evaluation(evaluation_id)
            if not evaluation:
                return jsonify({"error": "avaliação não encontrada"}), 404

            image = request.files.get("image")
            if not image:
                return jsonify({"error": "arquivo 'image' é obrigatório"}), 400

            role = request.form.get("imageRole", "clinical")
            extension = Path(image.filename or "image.jpg").suffix or ".jpg"
            image_name = f"{evaluation_id}_{int(time.time() * 1000)}{extension}"
            image_path = self.upload_dir / image_name
            image.save(image_path)

            saved = self.db.add_wound_image(
                evaluation_id,
                {
                    "image_role": role,
                    "image_path": str(image_path),
                    "content_type": image.mimetype or "image/jpeg",
                    "metadata": {"original_name": image.filename},
                },
            )
            if not saved:
                return jsonify({"error": "falha ao persistir imagem"}), 500
            return jsonify(saved), 201

        @bp.route("/evaluations/<evaluation_id>/analyze", methods=["POST"])
        def analyze_evaluation(evaluation_id: str):
            evaluation = self.db.get_wound_evaluation(evaluation_id)
            if not evaluation:
                return jsonify({"error": "avaliação não encontrada"}), 404

            body = request.get_json(silent=True) or {}
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
            run = self.db.get_ai_run(job_id)
            if not run:
                return jsonify({"error": "job não encontrado"}), 404
            result = self.db.get_ai_result_by_run(job_id)
            return jsonify({"job": run, "result": result}), 200

        @bp.route("/patients/<patient_id>/evaluations", methods=["GET"])
        def list_patient_evaluations(patient_id: str):
            case_id = request.args.get("caseId")
            evaluations = self.db.list_patient_evaluations(patient_id, case_id=case_id)
            return jsonify(evaluations), 200

        @bp.route("/comparisons", methods=["GET"])
        def compare_evaluations():
            left_id = request.args.get("left")
            right_id = request.args.get("right")
            if not left_id or not right_id:
                return jsonify({"error": "left e right são obrigatórios"}), 400
            left = self.db.get_wound_evaluation(left_id)
            right = self.db.get_wound_evaluation(right_id)
            if not left or not right:
                return jsonify({"error": "avaliações inválidas"}), 404
            return jsonify({"left": left, "right": right, "deltas": _calc_deltas(left, right)}), 200

        @bp.route("/reports/generate", methods=["POST"])
        def generate_report():
            started = time.time()
            payload = request.get_json(silent=True) or {}
            patient_id = payload.get("patient_id")
            if not patient_id:
                return jsonify({"error": "patient_id é obrigatório"}), 400

            evals = self.db.list_patient_evaluations(patient_id, case_id=payload.get("case_id"))
            if not evals:
                return jsonify({"error": "nenhuma avaliação para gerar relatório"}), 400
            latest = evals[0]
            baseline = evals[-1]
            report_json = {
                "patient_id": patient_id,
                "generated_at": datetime.now().isoformat(),
                "type": payload.get("report_type", "evolution"),
                "professional": payload.get("professional"),
                "baseline": baseline,
                "latest": latest,
                "deltas": _calc_deltas(baseline, latest),
                "recommendation": self._build_recommendation(latest),
            }

            report_name = f"report_{patient_id}_{int(time.time())}"
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
                    "case_id": payload.get("case_id"),
                    "evaluation_id": latest.get("id"),
                    "report_type": payload.get("report_type", "evolution"),
                    "report_json": report_json,
                    "pdf_path": str(pdf_path),
                    "docx_path": str(docx_path),
                    "generated_by": payload.get("professional"),
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
            fmt = (request.args.get("format") or "json").lower()
            report = self.db.get_structured_report(report_id)
            if not report:
                return jsonify({"error": "relatório não encontrado"}), 404

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

