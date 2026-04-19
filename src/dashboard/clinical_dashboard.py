"""
HEAL/REDISUS - Dashboard Clínico Interativo Web
Painel web para equipes multiprofissionais (enfermagem, médicos, gestores).

Implementa:
- Dashboard de acompanhamento de pacientes
- Indicadores dinâmicos de saúde
- Visualização de estratificação de risco populacional
- Mapa epidemiológico interativo
- Painel de alertas e notificações
- Relatórios de produção e gestão
"""
import json
import os
from datetime import datetime, timedelta
from typing import Any, Dict, List, Mapping, Optional

from loguru import logger
from packages.shared.security import (
    current_user,
    current_user_required,
    enforce_request_auth,
    ensure_admin_access,
    ensure_case_access,
    ensure_patient_access,
    filter_patients_for_user,
    is_admin,
    user_roles,
    user_units,
)
from src.dashboard.clinical_api import ClinicalAPI


class ClinicalDashboard:
    """
    Dashboard clínico web baseado em Flask.
    Fornece API REST e views HTML para gestão de pacientes e indicadores.
    """

    def __init__(self, database=None, risk_engine=None, surveillance=None):
        """
        Args:
            database: Instância do Database (src.data.database)
            risk_engine: Instância do WoundRiskScoring (src.risk.stratification)
            surveillance: Instância do GeoSurveillance (src.surveillance.epidemiological)
        """
        self.db = database
        self.risk_engine = risk_engine
        self.surveillance = surveillance
        self.app = None
        logger.info("ClinicalDashboard inicializado")

    def create_app(self):
        """Cria aplicação Flask para o dashboard"""
        try:
            from flask import Flask, jsonify, render_template_string, request
        except ImportError:
            logger.error("Flask não instalado — instale com: pip install flask")
            return None

        app = Flask(__name__)
        app.config["JSON_AS_ASCII"] = False
        app.config["MAX_CONTENT_LENGTH"] = 20 * 1024 * 1024

        if self.db:
            clinical_api = ClinicalAPI(self.db)
            app.extensions["redisus_auth_verifier"] = clinical_api.firebase_auth
            app.register_blueprint(clinical_api.blueprint)

        @app.before_request
        def enforce_dashboard_auth():
            if request.method == "OPTIONS":
                return None
            if not request.path.startswith("/api/"):
                return None
            if request.path == "/api/v1/health":
                return None
            enforce_request_auth()
            return None

        @app.after_request
        def apply_dashboard_security_headers(response):
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["X-Frame-Options"] = "DENY"
            if request.path.startswith("/api/"):
                response.headers["Cache-Control"] = "no-store"
            return response

        # ---- Rotas HTML ----
        @app.route("/")
        def index():
            return render_template_string(DASHBOARD_HTML)

        @app.route("/patients")
        def patients_page():
            return render_template_string(PATIENTS_HTML)

        @app.route("/surveillance")
        def surveillance_page():
            return render_template_string(SURVEILLANCE_HTML)

        @app.route("/alerts")
        def alerts_page():
            return render_template_string(ALERTS_HTML)

        # ---- API REST ----
        @app.route("/api/dashboard/summary")
        def api_summary():
            """Resumo geral do dashboard"""
            user = current_user_required()
            role_view = request.args.get("roleView", "")
            unit = request.args.get("unit", "")
            team = request.args.get("team", "")
            return jsonify(self._get_dashboard_summary(user=user, role_view=role_view, unit=unit, team=team))

        @app.route("/api/dashboard/clinical-queue")
        def api_clinical_queue():
            """Fila clínica priorizada para decisão"""
            user = current_user_required()
            limit = int(request.args.get("limit", 20))
            view = request.args.get("view", "")
            role_view = request.args.get("roleView", "")
            unit = request.args.get("unit", "")
            team = request.args.get("team", "")
            return jsonify(self._get_clinical_queue(user=user, limit=limit, view=view, role_view=role_view, unit=unit, team=team))

        @app.route("/api/patients")
        def api_patients():
            """Lista pacientes com indicadores"""
            user = current_user_required()
            return jsonify(filter_patients_for_user(self._get_patients_list(), user=user))

        @app.route("/api/patients/<patient_id>")
        def api_patient_detail(patient_id):
            """Detalhe de um paciente"""
            if self.db:
                ensure_patient_access(self.db, patient_id)
            return jsonify(self._get_patient_detail(patient_id))

        @app.route("/api/dashboard/cases/<case_id>")
        def api_case_detail(case_id: str):
            user = current_user_required()
            if self.db:
                ensure_case_access(self.db, case_id, user=user)
            role_view = request.args.get("roleView", "")
            return jsonify(self._get_case_detail(case_id, user=user, role_view=role_view))

        @app.route("/api/patients/<patient_id>/risk")
        def api_patient_risk(patient_id):
            """Score de risco de um paciente"""
            if self.db:
                ensure_patient_access(self.db, patient_id)
            return jsonify(self._get_patient_risk(patient_id))

        @app.route("/api/indicators")
        def api_indicators():
            """Indicadores populacionais"""
            user = current_user_required()
            region = request.args.get("region", "")
            return jsonify(self._get_population_indicators(region, user=user))

        @app.route("/api/alerts")
        def api_alerts():
            """Alertas ativos"""
            user = current_user_required()
            role_view = request.args.get("roleView", "")
            return jsonify(self._get_active_alerts(user=user, role_view=role_view))

        @app.route("/api/surveillance/heatmap")
        def api_heatmap():
            """Dados de mapa de calor"""
            ensure_admin_access()
            condition = request.args.get("condition")
            days = int(request.args.get("days", 30))
            return jsonify(self._get_heatmap_data(condition, days))

        @app.route("/api/surveillance/clusters")
        def api_clusters():
            """Clusters detectados"""
            ensure_admin_access()
            return jsonify(self._get_clusters())

        @app.route("/api/reports/production")
        def api_production():
            """Relatório de produção"""
            user = current_user_required()
            period = request.args.get("period", "month")
            role_view = request.args.get("roleView", "")
            unit = request.args.get("unit", "")
            team = request.args.get("team", "")
            return jsonify(self._get_production_report(period, user=user, role_view=role_view, unit=unit, team=team))

        @app.route("/api/export/fhir/<patient_id>")
        def api_export_fhir(patient_id):
            """Exporta dados FHIR de um paciente"""
            if self.db:
                ensure_patient_access(self.db, patient_id)
            return jsonify(self._export_fhir(patient_id))

        self.app = app
        return app

    def run(self, host: str = "0.0.0.0", port: int = 5000, debug: bool = False):
        """Inicia o servidor do dashboard"""
        if self.app is None:
            self.create_app()
        if self.app:
            logger.info(f"Dashboard HEAL iniciando em http://{host}:{port}")
            self.app.run(host=host, port=port, debug=debug)

    # ---- Data methods ----
    def _get_dashboard_summary(self) -> Dict:
        """Gera resumo do dashboard"""
        summary = {
            "timestamp": datetime.now().isoformat(),
            "platform": "HEAL/REDISUS",
            "total_patients": 0,
            "total_analyses": 0,
            "risk_distribution": {"baixo": 0, "moderado": 0, "alto": 0, "critico": 0},
            "active_alerts": 0,
            "recent_analyses": [],
            "top_etiologies": [],
        }

        if self.db:
            try:
                stats = self.db.get_statistics()
                summary["total_patients"] = stats.get("total_patients", 0)
                summary["total_analyses"] = stats.get("total_analyses", 0)
                summary["top_etiologies"] = stats.get("top_etiologies", [])
            except Exception as e:
                logger.error(f"Erro ao obter estatísticas: {e}")

        if self.surveillance:
            summary["active_alerts"] = len([
                a for a in self.surveillance.alerts if not a.acknowledged
            ])

        return summary

    def _get_patients_list(self) -> List[Dict]:
        """Lista pacientes com dados resumidos"""
        if not self.db:
            return []
        try:
            patients = self.db.list_patients()
            return [p.to_dict() if hasattr(p, "to_dict") else p for p in patients]
        except Exception as e:
            logger.error(f"Erro ao listar pacientes: {e}")
            return []

    def _get_patient_detail(self, patient_id: str) -> Dict:
        """Detalhe completo de um paciente"""
        if not self.db:
            return {"error": "Database não configurado"}
        try:
            patient = self.db.get_patient(patient_id)
            if not patient:
                return {"error": "Paciente não encontrado"}
            analyses = self.db.get_patient_analyses(patient_id)
            return {
                "patient": patient.to_dict() if hasattr(patient, "to_dict") else patient,
                "analyses": [a.to_dict() if hasattr(a, "to_dict") else a for a in analyses],
                "total_analyses": len(analyses),
            }
        except Exception as e:
            logger.error(f"Erro ao buscar paciente {patient_id}: {e}")
            return {"error": str(e)}

    def _get_patient_risk(self, patient_id: str) -> Dict:
        """Calcula risco do paciente"""
        if not self.risk_engine:
            return {"error": "Motor de risco não configurado"}
        # Placeholder - em produção, busca dados reais do DB
        return {
            "patient_id": patient_id,
            "message": "Use o módulo risk.stratification para cálculo completo",
        }

    def _get_population_indicators(self, region: str) -> List[Dict]:
        """Indicadores populacionais"""
        return [{
            "name": "Indicadores populacionais",
            "region": region or "todas",
            "message": "Use o módulo risk.stratification.PopulationRiskAnalyzer",
        }]

    def _get_active_alerts(self) -> List[Dict]:
        """Alertas ativos do sistema"""
        alerts = []
        if self.surveillance:
            for a in self.surveillance.alerts:
                if not a.acknowledged:
                    alerts.append({
                        "id": a.alert_id,
                        "condition": a.condition,
                        "region": a.region,
                        "severity": a.severity,
                        "message": a.message,
                        "case_count": a.case_count,
                        "timestamp": a.timestamp,
                    })
        return alerts

    def _get_heatmap_data(self, condition: Optional[str], days: int) -> Dict:
        """Dados para mapa de calor"""
        if not self.surveillance:
            return {"points": [], "bounds": None}
        return self.surveillance.generate_heatmap_data(condition=condition, period_days=days)

    def _get_clusters(self) -> List[Dict]:
        """Clusters epidemiológicos"""
        if not self.surveillance:
            return []
        return self.surveillance.detect_clusters()

    def _get_production_report(self, period: str) -> Dict:
        """Relatório de produção"""
        return {
            "period": period,
            "generated_at": datetime.now().isoformat(),
            "generated_by": "HEAL/REDISUS",
            "message": "Relatório de produção — integre com DATASUSIntegration para dados reais",
        }

    @staticmethod
    def _to_dict(item: Any) -> Dict[str, Any]:
        if item is None:
            return {}
        if isinstance(item, dict):
            return dict(item)
        if isinstance(item, Mapping):
            return dict(item)
        if hasattr(item, "to_dict"):
            try:
                payload = item.to_dict()
                return dict(payload) if isinstance(payload, Mapping) else {}
            except Exception:
                return {}
        try:
            return dict(item)
        except Exception:
            return {}

    @staticmethod
    def _safe_float(value: Any) -> Optional[float]:
        if value in (None, ""):
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

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
    def _normalize_status(value: Any) -> str:
        mapping = {
            "completed": "concluido",
            "done": "concluido",
            "cancelled": "cancelado",
            "canceled": "cancelado",
            "scheduled": "agendado",
            "pending": "pendente",
            "open": "aberto",
            "acknowledged": "reconhecido",
            "closed": "fechado",
            "resolved": "resolvido",
            "active": "ativo",
        }
        normalized = str(value or "").strip().lower()
        return mapping.get(normalized, normalized)

    @staticmethod
    def _parse_datetime(value: Any) -> Optional[datetime]:
        if not value:
            return None
        text = str(value).strip()
        if not text:
            return None
        normalized = text.replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(normalized)
        except ValueError:
            try:
                parsed = datetime.fromisoformat(f"{text}T00:00:00")
            except ValueError:
                return None
        return parsed.replace(tzinfo=None) if parsed.tzinfo else parsed

    def _risk_rank(self, risk_level: Any) -> int:
        return {"baixo": 1, "moderado": 2, "alto": 3, "critico": 4}.get(self._normalize_risk(risk_level), 0)

    def _severity_rank(self, severity: Any) -> int:
        return self._risk_rank(severity)

    def _db_call(self, method_name: str, *args, default: Any = None, **kwargs) -> Any:
        if not self.db:
            return default
        method = getattr(self.db, method_name, None)
        if not callable(method):
            return default
        try:
            result = method(*args, **kwargs)
        except Exception as exc:
            logger.error(f"Erro ao executar {method_name}: {exc}")
            return default
        return default if result is None else result

    def _serialize_patient(self, patient: Any) -> Dict[str, Any]:
        payload = self._to_dict(patient)
        metadata = payload.get("metadata")
        payload["metadata"] = dict(metadata) if isinstance(metadata, Mapping) else {}
        payload.setdefault("unit_id", payload["metadata"].get("unit_id") or payload["metadata"].get("unit"))
        payload.setdefault("team_id", payload["metadata"].get("team_id") or payload["metadata"].get("team"))
        return payload

    def _patient_region(self, patient: Mapping[str, Any]) -> str:
        metadata = patient.get("metadata") if isinstance(patient.get("metadata"), Mapping) else {}
        for key in ("region", "unit", "unit_id", "facility", "city", "state"):
            value = metadata.get(key)
            if value:
                return str(value)
        return "nao_informada"

    def _patient_matches_region(self, patient: Mapping[str, Any], region: str) -> bool:
        if not region:
            return True
        target = region.strip().lower()
        patient_region = self._patient_region(patient).strip().lower()
        return target in patient_region or patient_region in target

    def _patient_unit(self, patient: Mapping[str, Any]) -> str:
        metadata = patient.get("metadata") if isinstance(patient.get("metadata"), Mapping) else {}
        for key in ("unit_id", "unit", "facility", "clinic", "health_unit"):
            value = patient.get(key)
            if value:
                return str(value)
            value = metadata.get(key)
            if value:
                return str(value)
        return "nao_informada"

    def _patient_team(self, patient: Mapping[str, Any]) -> str:
        metadata = patient.get("metadata") if isinstance(patient.get("metadata"), Mapping) else {}
        for key in ("team", "care_team", "team_id", "assigned_team"):
            value = patient.get(key)
            if value:
                return str(value)
            value = metadata.get(key)
            if value:
                return str(value)
        return "nao_informada"

    @staticmethod
    def _assignment_payload(record: Mapping[str, Any] | None) -> Dict[str, Any]:
        record = record or {}
        return {
            "uid": record.get("assigned_to_uid"),
            "name": record.get("assigned_to_name"),
            "role": record.get("assigned_to_role"),
            "claimed_at": record.get("claimed_at"),
            "handoff_to_uid": record.get("handoff_to_uid"),
            "handoff_to_name": record.get("handoff_to_name"),
            "handoff_to_role": record.get("handoff_to_role"),
            "handoff_at": record.get("handoff_at"),
        }

    @staticmethod
    def _primary_image(evaluation: Mapping[str, Any] | None) -> Dict[str, Any]:
        if not evaluation:
            return {}
        images = evaluation.get("images")
        if not isinstance(images, list):
            return {}
        preferred = [
            image
            for image in images
            if str((image or {}).get("image_role") or "clinical").strip().lower() in {"clinical", "frontal", "measurement"}
        ]
        selected = (preferred or images)[-1] if (preferred or images) else None
        return dict(selected) if isinstance(selected, Mapping) else {}

    @staticmethod
    def _image_url(image: Mapping[str, Any] | None) -> str | None:
        if not image:
            return None
        image_id = image.get("id")
        if not image_id:
            return None
        return f"/api/v1/images/{image_id}/content"

    def _normalize_role_view(self, role_view: str, user: Mapping[str, Any] | None = None) -> str:
        target = str(role_view or "").strip().lower()
        if target in {"nurse", "doctor", "admin"}:
            return target
        roles = user_roles(user) if user is not None else set()
        if "doctor" in roles:
            return "doctor"
        if is_admin(user):
            return "admin"
        if roles & {"nurse", "clinician", "estomaterapeuta"}:
            return "nurse"
        return "admin"

    def _patient_matches_unit(self, patient: Mapping[str, Any], unit: str) -> bool:
        if not unit:
            return True
        target = unit.strip().lower()
        patient_unit = self._patient_unit(patient).strip().lower()
        return target in patient_unit or patient_unit in target

    def _patient_matches_team(self, patient: Mapping[str, Any], team: str) -> bool:
        if not team:
            return True
        target = team.strip().lower()
        patient_team = self._patient_team(patient).strip().lower()
        return target in patient_team or patient_team in target

    def _sla_target_days(self, risk_level: Any) -> int:
        return {"critico": 1, "alto": 3, "moderado": 7, "baixo": 14}.get(self._normalize_risk(risk_level), 7)

    def _allowed_overdue_days(self, risk_level: Any) -> int:
        return {"critico": 0, "alto": 1, "moderado": 3, "baixo": 7}.get(self._normalize_risk(risk_level), 3)

    def _priority_bucket(self, priority_score: int, *, sla_status: str, requires_doctor_review: bool) -> str:
        if sla_status == "breached" or priority_score >= 110:
            return "imediata"
        if requires_doctor_review or priority_score >= 80:
            return "urgente"
        if priority_score >= 45:
            return "prioritaria"
        return "rotina"

    def _queue_actions_for_role(self, lesion_snapshot: Mapping[str, Any], role_view: str) -> List[str]:
        actions = ["open_case"]
        if role_view in {"nurse", "doctor", "admin"}:
            if not lesion_snapshot.get("assigned_to_uid"):
                actions.append("claim_case")
            else:
                actions.append("handoff_case")
        if lesion_snapshot.get("open_alerts"):
            primary_alert = (lesion_snapshot.get("open_alerts") or [{}])[0]
            if role_view in {"nurse", "doctor", "admin"}:
                if not primary_alert.get("assigned_to_uid"):
                    actions.append("claim_alert")
                else:
                    actions.append("handoff_alert")
            actions.append("acknowledge_alert")
            if role_view in {"doctor", "admin"} or self._severity_rank(primary_alert.get("severity")) <= 2:
                actions.append("resolve_alert")
        if lesion_snapshot.get("next_follow_up") and role_view in {"nurse", "doctor", "admin"}:
            actions.append("complete_follow_up")
        if role_view in {"doctor", "admin"} or (
            role_view == "nurse" and not lesion_snapshot.get("requires_doctor_review")
        ):
            actions.append("update_care_plan")
        return actions

    def _evaluation_sort_key(self, evaluation: Mapping[str, Any]) -> datetime:
        return (
            self._parse_datetime(evaluation.get("evaluation_date"))
            or self._parse_datetime(evaluation.get("created_at"))
            or datetime.min
        )

    def _calc_evaluation_delta(self, evaluations: List[Dict[str, Any]]) -> Dict[str, Any]:
        if len(evaluations) < 2:
            return {
                "area_delta_cm2": None,
                "area_change_pct": None,
                "push_delta": None,
                "bwat_delta": None,
                "pain_delta": None,
            }

        latest = evaluations[-1]
        previous = evaluations[-2]
        latest_area = self._safe_float(latest.get("wound_area_cm2"))
        previous_area = self._safe_float(previous.get("wound_area_cm2"))
        area_delta = None
        area_change_pct = None
        if latest_area is not None and previous_area is not None:
            area_delta = round(latest_area - previous_area, 2)
            if previous_area > 0:
                area_change_pct = round((area_delta / previous_area) * 100.0, 1)

        def metric_delta(field: str) -> Optional[float]:
            latest_value = self._safe_float(latest.get(field))
            previous_value = self._safe_float(previous.get(field))
            if latest_value is None or previous_value is None:
                return None
            return round(latest_value - previous_value, 2)

        return {
            "area_delta_cm2": area_delta,
            "area_change_pct": area_change_pct,
            "push_delta": metric_delta("push_score"),
            "bwat_delta": metric_delta("bwat_score"),
            "pain_delta": metric_delta("pain_score"),
        }

    def _build_lesion_snapshot(self, patient_id: str, lesion: Any) -> Dict[str, Any]:
        lesion_payload = self._to_dict(lesion)
        case_id = str(lesion_payload.get("id") or "")
        timeline = self._db_call("get_case_timeline", case_id, default=None) if case_id else None

        if timeline:
            lesion_payload = self._to_dict(timeline.get("lesion")) or lesion_payload
            evaluations = [self._to_dict(item) for item in timeline.get("evaluations", [])]
            care_plans = [self._to_dict(item) for item in timeline.get("care_plans", [])]
            follow_ups = [self._to_dict(item) for item in timeline.get("follow_ups", [])]
            alerts = [self._to_dict(item) for item in timeline.get("alerts", [])]
            audit_log = [self._to_dict(item) for item in timeline.get("audit_log", [])]
        else:
            evaluations = [
                self._to_dict(item)
                for item in self._db_call("list_patient_evaluations", patient_id, case_id=case_id, default=[])
            ]
            care_plans = [self._to_dict(item) for item in self._db_call("list_case_care_plans", case_id, default=[])]
            follow_ups = [self._to_dict(item) for item in self._db_call("list_case_follow_ups", case_id, default=[])]
            alerts = [self._to_dict(item) for item in self._db_call("list_case_alerts", case_id, default=[])]
            audit_log = [self._to_dict(item) for item in self._db_call("list_case_audit_events", case_id, default=[])]

        evaluations = sorted(evaluations, key=self._evaluation_sort_key)
        latest_evaluation = evaluations[-1] if evaluations else None
        previous_evaluation = evaluations[-2] if len(evaluations) > 1 else None
        latest_inference: Dict[str, Any] = {}
        for evaluation in reversed(evaluations):
            latest_inference = self._to_dict(evaluation.get("inference_result"))
            if latest_inference:
                break
        if not latest_inference and latest_evaluation and latest_evaluation.get("id"):
            latest_inference = self._to_dict(
                self._db_call("get_latest_ai_result_for_evaluation", latest_evaluation["id"], default=None)
            )

        interpretation = (
            dict(latest_inference.get("interpretation"))
            if isinstance(latest_inference.get("interpretation"), Mapping)
            else {}
        )
        active_care_plan = next(
            (plan for plan in care_plans if self._normalize_status(plan.get("status")) == "ativo"),
            care_plans[-1] if care_plans else None,
        )

        active_alerts = [
            alert
            for alert in alerts
            if self._normalize_status(alert.get("status") or "open") in {"aberto", "pendente", "reconhecido"}
        ]
        active_alerts.sort(
            key=lambda alert: (
                self._severity_rank(alert.get("severity")),
                self._parse_datetime(alert.get("created_at")) or datetime.min,
            ),
            reverse=True,
        )

        pending_follow_ups = [
            follow_up
            for follow_up in follow_ups
            if self._normalize_status(follow_up.get("status") or "scheduled") in {"agendado", "pendente", "aberto"}
        ]
        pending_follow_ups.sort(
            key=lambda follow_up: self._parse_datetime(follow_up.get("scheduled_for")) or datetime.max
        )
        next_follow_up = pending_follow_ups[0] if pending_follow_ups else None

        now = datetime.now()
        overdue_follow_up = None
        overdue_days = 0
        for follow_up in pending_follow_ups:
            scheduled_for = self._parse_datetime(follow_up.get("scheduled_for"))
            if scheduled_for and scheduled_for.date() < now.date():
                overdue_follow_up = follow_up
                overdue_days = max((now.date() - scheduled_for.date()).days, 0)
                break

        evaluation_delta = self._calc_evaluation_delta(evaluations)
        worsening = any(
            (
                evaluation_delta.get("area_change_pct") is not None and evaluation_delta["area_change_pct"] >= 15,
                evaluation_delta.get("area_delta_cm2") is not None and evaluation_delta["area_delta_cm2"] >= 1.0,
                evaluation_delta.get("push_delta") is not None and evaluation_delta["push_delta"] >= 1.0,
                evaluation_delta.get("bwat_delta") is not None and evaluation_delta["bwat_delta"] >= 1.0,
                evaluation_delta.get("pain_delta") is not None and evaluation_delta["pain_delta"] >= 2.0,
            )
        )

        lesion_metadata = lesion_payload.get("metadata") if isinstance(lesion_payload.get("metadata"), Mapping) else {}
        assignment = self._assignment_payload(lesion_payload)
        risk_level = self._normalize_risk(
            interpretation.get("risk_level")
            or latest_inference.get("risk_level")
            or (active_care_plan or {}).get("risk_level")
            or lesion_metadata.get("risk_level")
            or ("baixo" if self._normalize_status(lesion_payload.get("status")) in {"fechado", "resolvido"} else "moderado")
        )
        risk_rank = self._risk_rank(risk_level)
        latest_evaluation_date = (
            latest_evaluation.get("evaluation_date")
            if latest_evaluation
            else lesion_payload.get("opened_at")
            or lesion_payload.get("created_at")
        )
        latest_evaluation_dt = self._parse_datetime(latest_evaluation_date)
        days_since_evaluation = (now.date() - latest_evaluation_dt.date()).days if latest_evaluation_dt else None
        review_due_date = (active_care_plan or {}).get("review_due_date")
        review_due_dt = self._parse_datetime(review_due_date) if review_due_date else None
        if not review_due_dt and latest_evaluation_dt:
            review_due_dt = latest_evaluation_dt.replace(hour=0, minute=0, second=0, microsecond=0)
            review_due_dt = review_due_dt + timedelta(days=self._sla_target_days(risk_level))
        sla_target_days = self._sla_target_days(risk_level)
        overdue_limit_days = self._allowed_overdue_days(risk_level)
        sla_status = "sem_referencia"
        sla_days_remaining = None
        if review_due_dt:
            sla_days_remaining = (review_due_dt.date() - now.date()).days
            if sla_days_remaining < 0:
                sla_status = "breached"
            elif sla_days_remaining == 0:
                sla_status = "due_today"
            else:
                sla_status = "on_track"

        attention_reasons: List[str] = []
        if risk_rank >= 4:
            attention_reasons.append("risco critico")
        elif risk_rank >= 3:
            attention_reasons.append("risco alto")
        if worsening:
            attention_reasons.append("piora clinica na ultima comparacao")
        if overdue_follow_up:
            attention_reasons.append(f"follow-up atrasado ha {overdue_days} dia(s)")
        if sla_status == "breached":
            attention_reasons.append("sla clinico vencido")
        elif sla_status == "due_today":
            attention_reasons.append("sla clinico vence hoje")
        if active_alerts:
            attention_reasons.append(f"{len(active_alerts)} alerta(s) clinico(s) aberto(s)")
            if not active_alerts[0].get("assigned_to_uid"):
                attention_reasons.append("alerta clinico sem responsavel atribuido")
        if not active_care_plan:
            attention_reasons.append("sem plano de cuidado ativo")
        if not assignment.get("uid") and (
            active_alerts or overdue_follow_up or worsening or risk_rank >= 3 or sla_status in {"breached", "due_today"}
        ):
            attention_reasons.append("caso sem responsavel atribuido")
        if latest_inference.get("fallback_used"):
            attention_reasons.append("resultado de IA em fallback requer revisao")
        if latest_inference.get("needs_expert_review"):
            attention_reasons.append("IA requer revisao especialista")
        if days_since_evaluation is not None and days_since_evaluation >= 14:
            attention_reasons.append(f"sem nova avaliacao ha {days_since_evaluation} dia(s)")
        if not evaluations:
            attention_reasons.append("lesao sem avaliacao registrada")

        needs_attention = bool(attention_reasons)
        highest_alert_severity = max(
            (self._severity_rank(alert.get("severity")) for alert in active_alerts),
            default=0,
        )
        unresolved_alert_count = len(active_alerts)
        requires_doctor_review = bool(
            risk_rank >= 3
            or highest_alert_severity >= 3
            or worsening
            or (next_follow_up or {}).get("assigned_role") == "doctor"
        )
        priority_score = 10
        priority_score += {1: 10, 2: 24, 3: 46, 4: 70}.get(risk_rank, 0)
        priority_score += unresolved_alert_count * 8
        priority_score += highest_alert_severity * 4
        priority_score += min(overdue_days * 2, 24)
        priority_score += 18 if worsening else 0
        priority_score += 10 if not active_care_plan else 0
        priority_score += 8 if latest_inference.get("fallback_used") else 0
        priority_score += 10 if latest_inference.get("needs_expert_review") else 0
        priority_score += 12 if not evaluations else 0
        priority_score += 20 if sla_status == "breached" else 8 if sla_status == "due_today" else 0
        priority_score += 12 if requires_doctor_review else 0
        priority_score += 10 if not assignment.get("uid") and needs_attention else 0
        priority_score += 6 if active_alerts and not active_alerts[0].get("assigned_to_uid") else 0
        if days_since_evaluation is not None and days_since_evaluation > 14:
            priority_score += min(days_since_evaluation - 14, 14)
        if self._normalize_status(lesion_payload.get("status")) in {"fechado", "resolvido"}:
            priority_score = max(priority_score - 30, 0)

        if risk_rank >= 4 or highest_alert_severity >= 4 or overdue_days > overdue_limit_days or sla_status == "breached":
            lesion_status = "atencao_imediata"
        elif overdue_follow_up:
            lesion_status = "atrasado"
        elif needs_attention:
            lesion_status = "prioritario"
        elif self._normalize_status(lesion_payload.get("status")) in {"fechado", "resolvido"}:
            lesion_status = "resolvido"
        else:
            lesion_status = "em_acompanhamento"
        priority_bucket = self._priority_bucket(
            int(priority_score),
            sla_status=sla_status,
            requires_doctor_review=requires_doctor_review,
        )

        return {
            "lesion": lesion_payload,
            "timeline": timeline,
            "audit_log": audit_log,
            "latest_evaluation": latest_evaluation,
            "previous_evaluation": previous_evaluation,
            "latest_inference": latest_inference,
            "active_care_plan": active_care_plan,
            "care_plan_count": len(care_plans),
            "follow_ups": follow_ups,
            "next_follow_up": next_follow_up,
            "overdue_follow_up": overdue_follow_up,
            "overdue_follow_up_flag": overdue_follow_up is not None,
            "overdue_days": overdue_days,
            "alerts": alerts,
            "open_alerts": active_alerts,
            "open_alert_count": len(active_alerts),
            "audit_event_count": len(audit_log),
            "assigned_to_uid": assignment.get("uid"),
            "assigned_to_name": assignment.get("name"),
            "assigned_to_role": assignment.get("role"),
            "claimed_at": assignment.get("claimed_at"),
            "ownership": assignment,
            "risk_level": risk_level,
            "risk_rank": risk_rank,
            "worsening": worsening,
            "needs_attention": needs_attention,
            "attention_reasons": attention_reasons,
            "priority_score": int(priority_score),
            "priority_bucket": priority_bucket,
            "status": lesion_status,
            "evaluation_delta": evaluation_delta,
            "latest_evaluation_date": latest_evaluation_date,
            "days_since_evaluation": days_since_evaluation,
            "review_due_date": review_due_dt.date().isoformat() if review_due_dt else review_due_date,
            "sla_target_days": sla_target_days,
            "sla_status": sla_status,
            "sla_days_remaining": sla_days_remaining,
            "overdue_limit_days": overdue_limit_days,
            "requires_doctor_review": requires_doctor_review,
            "recommended_owner_role": "doctor" if requires_doctor_review else "nurse",
            "available_actions": [],
            "decision_rule_version": "2026-04-07-clinical-queue-v2",
        }

    def _build_patient_snapshot(self, patient: Any) -> Dict[str, Any]:
        patient_payload = self._serialize_patient(patient)
        patient_id = str(patient_payload.get("id") or "")
        lesions = [
            self._build_lesion_snapshot(patient_id, lesion)
            for lesion in self._db_call("list_wound_cases", patient_id, default=[])
        ]
        lesions.sort(
            key=lambda item: (
                item.get("priority_score", 0),
                self._risk_rank(item.get("risk_level")),
                item.get("overdue_days", 0),
                (self._parse_datetime(item.get("latest_evaluation_date")) or datetime.min).isoformat(),
            ),
            reverse=True,
        )

        top_lesion = lesions[0] if lesions else None
        risk_level = top_lesion["risk_level"] if top_lesion else "baixo"

        pending_follow_ups = [lesion["next_follow_up"] for lesion in lesions if lesion.get("next_follow_up")]
        next_follow_up = None
        if pending_follow_ups:
            pending_follow_ups.sort(
                key=lambda follow_up: self._parse_datetime(follow_up.get("scheduled_for")) or datetime.max
            )
            next_follow_up = pending_follow_ups[0]

        latest_evaluation_date = None
        evaluation_dates = [lesion.get("latest_evaluation_date") for lesion in lesions if lesion.get("latest_evaluation_date")]
        if evaluation_dates:
            evaluation_dates.sort(key=lambda value: self._parse_datetime(value) or datetime.min, reverse=True)
            latest_evaluation_date = evaluation_dates[0]

        attention_reasons: List[str] = []
        for lesion in lesions:
            for reason in lesion.get("attention_reasons", []):
                if reason not in attention_reasons:
                    attention_reasons.append(reason)

        scheduled_follow_ups = sum(
            1
            for lesion in lesions
            for follow_up in lesion.get("follow_ups", [])
            if self._normalize_status(follow_up.get("status") or "scheduled") in {"agendado", "pendente", "aberto"}
        )
        active_care_plans = sum(1 for lesion in lesions if lesion.get("active_care_plan"))
        open_alert_count = sum(int(lesion.get("open_alert_count") or 0) for lesion in lesions)
        overdue_follow_ups = sum(1 for lesion in lesions if lesion.get("overdue_follow_up_flag"))
        sla_breaches = sum(1 for lesion in lesions if lesion.get("sla_status") == "breached")
        doctor_review_cases = sum(1 for lesion in lesions if lesion.get("requires_doctor_review"))
        audit_event_count = sum(int(lesion.get("audit_event_count") or 0) for lesion in lesions)
        needs_attention = any(lesion.get("needs_attention") for lesion in lesions)
        worsening = any(lesion.get("worsening") for lesion in lesions)
        priority_score = (top_lesion or {}).get("priority_score", 0)
        if len(lesions) > 1:
            priority_score += min(len(lesions) - 1, 3) * 3

        if top_lesion and top_lesion.get("status") == "atencao_imediata":
            patient_status = "atencao_imediata"
        elif overdue_follow_ups:
            patient_status = "atrasado"
        elif needs_attention:
            patient_status = "prioritario"
        elif lesions:
            patient_status = "em_acompanhamento"
        else:
            patient_status = "sem_lesoes_ativas"

        return {
            "patient": patient_payload,
            "lesions": lesions,
            "lesion_count": len(lesions),
            "unit": self._patient_unit(patient_payload),
            "team": self._patient_team(patient_payload),
            "risk_level": risk_level,
            "status": patient_status,
            "priority_score": int(priority_score),
            "needs_attention": needs_attention,
            "worsening": worsening,
            "overdue_follow_ups": overdue_follow_ups,
            "sla_breaches": sla_breaches,
            "doctor_review_cases": doctor_review_cases,
            "open_alert_count": open_alert_count,
            "active_care_plans": active_care_plans,
            "scheduled_follow_ups": scheduled_follow_ups,
            "next_follow_up": next_follow_up,
            "latest_evaluation_date": latest_evaluation_date,
            "attention_reasons": attention_reasons,
            "audit_event_count": audit_event_count,
            "priority_lesion": top_lesion,
        }

    def _get_all_patient_snapshots(
        self,
        region: str = "",
        *,
        user: Mapping[str, Any] | None = None,
        unit: str = "",
        team: str = "",
    ) -> List[Dict[str, Any]]:
        patients = [self._serialize_patient(item) for item in self._db_call("list_patients", default=[])]
        if user is not None:
            patients = [self._serialize_patient(item) for item in filter_patients_for_user(patients, user=user)]
            if unit or (not is_admin(user) and user_units(user)):
                requested_units = {unit.strip()} if unit else set()
                allowed_units = {item.strip() for item in user_units(user)}
                if requested_units:
                    allowed_units = requested_units & allowed_units if not is_admin(user) else requested_units
                patients = [patient for patient in patients if self._patient_unit(patient) in allowed_units] if allowed_units else []
        snapshots = [self._build_patient_snapshot(patient) for patient in patients]
        return [
            snapshot
            for snapshot in snapshots
            if self._patient_matches_region(snapshot.get("patient", {}), region)
            and self._patient_matches_unit(snapshot.get("patient", {}), unit)
            and self._patient_matches_team(snapshot.get("patient", {}), team)
        ]

    def _build_clinical_queue_from_snapshots(
        self,
        snapshots: List[Dict[str, Any]],
        *,
        limit: int = 20,
        view: str = "",
        role_view: str = "",
    ) -> Dict[str, Any]:
        items: List[Dict[str, Any]] = []
        normalized_role_view = self._normalize_role_view(role_view)
        for snapshot in snapshots:
            patient = snapshot.get("patient", {})
            priority_lesion = snapshot.get("priority_lesion") or {}
            lesion_payload = priority_lesion.get("lesion", {}) if isinstance(priority_lesion, Mapping) else {}
            available_actions = self._queue_actions_for_role(priority_lesion, normalized_role_view)
            items.append(
                {
                    "patient_id": patient.get("id"),
                    "patient_name": patient.get("name"),
                    "region": self._patient_region(patient),
                    "unit": snapshot.get("unit") or self._patient_unit(patient),
                    "team": snapshot.get("team") or self._patient_team(patient),
                    "role_view": normalized_role_view,
                    "risk_level": snapshot.get("risk_level"),
                    "status": snapshot.get("status"),
                    "priority_score": snapshot.get("priority_score", 0),
                    "needs_attention": snapshot.get("needs_attention", False),
                    "worsening": snapshot.get("worsening", False),
                    "overdue_follow_up": snapshot.get("overdue_follow_ups", 0) > 0,
                    "overdue_follow_ups": snapshot.get("overdue_follow_ups", 0),
                    "overdue_days": priority_lesion.get("overdue_days", 0),
                    "open_alert_count": snapshot.get("open_alert_count", 0),
                    "active_care_plans": snapshot.get("active_care_plans", 0),
                    "scheduled_follow_ups": snapshot.get("scheduled_follow_ups", 0),
                    "latest_evaluation_date": snapshot.get("latest_evaluation_date"),
                    "next_follow_up": snapshot.get("next_follow_up"),
                    "next_follow_up_id": (snapshot.get("next_follow_up") or {}).get("id"),
                    "review_due_date": priority_lesion.get("review_due_date"),
                    "sla_status": priority_lesion.get("sla_status"),
                    "sla_target_days": priority_lesion.get("sla_target_days"),
                    "sla_days_remaining": priority_lesion.get("sla_days_remaining"),
                    "priority_bucket": priority_lesion.get("priority_bucket"),
                    "requires_doctor_review": priority_lesion.get("requires_doctor_review", False),
                    "recommended_owner_role": priority_lesion.get("recommended_owner_role"),
                    "assigned_to_uid": priority_lesion.get("assigned_to_uid"),
                    "assigned_to_name": priority_lesion.get("assigned_to_name"),
                    "assigned_to_role": priority_lesion.get("assigned_to_role"),
                    "claimed_at": priority_lesion.get("claimed_at"),
                    "audit_event_count": priority_lesion.get("audit_event_count", 0),
                    "attention_reasons": snapshot.get("attention_reasons", []),
                    "lesion_id": lesion_payload.get("id"),
                    "lesion_title": lesion_payload.get("title") or lesion_payload.get("location") or lesion_payload.get("wound_type"),
                    "lesion_status": lesion_payload.get("status"),
                    "lesion_location": lesion_payload.get("location"),
                    "evaluation_delta": priority_lesion.get("evaluation_delta", {}),
                    "open_alerts": priority_lesion.get("open_alerts", []),
                    "open_alert_id": ((priority_lesion.get("open_alerts") or [{}])[0]).get("id"),
                    "open_alert_owner_uid": ((priority_lesion.get("open_alerts") or [{}])[0]).get("assigned_to_uid"),
                    "open_alert_owner_name": ((priority_lesion.get("open_alerts") or [{}])[0]).get("assigned_to_name"),
                    "open_alert_owner_role": ((priority_lesion.get("open_alerts") or [{}])[0]).get("assigned_to_role"),
                    "active_care_plan": priority_lesion.get("active_care_plan"),
                    "active_care_plan_id": (priority_lesion.get("active_care_plan") or {}).get("id"),
                    "available_actions": available_actions,
                }
            )

        normalized_view = str(view or "").strip().lower()
        if normalized_view in {"attention", "needs-attention", "needs_attention"}:
            items = [item for item in items if item["needs_attention"]]
        elif normalized_view == "worsening":
            items = [item for item in items if item["worsening"]]
        elif normalized_view == "overdue":
            items = [item for item in items if item["overdue_follow_up"]]
        elif normalized_view in {"high-risk", "high_risk"}:
            items = [item for item in items if self._risk_rank(item["risk_level"]) >= 3]
        elif normalized_view == "alerts":
            items = [item for item in items if item["open_alert_count"] > 0]

        if normalized_role_view == "nurse":
            items.sort(
                key=lambda item: (
                    item.get("overdue_follow_up", False),
                    item.get("open_alert_count", 0),
                    item.get("priority_score", 0),
                ),
                reverse=True,
            )
        elif normalized_role_view == "doctor":
            items.sort(
                key=lambda item: (
                    item.get("requires_doctor_review", False),
                    self._risk_rank(item.get("risk_level")),
                    item.get("priority_score", 0),
                ),
                reverse=True,
            )
        else:
            items.sort(
                key=lambda item: (
                    item.get("sla_status") == "breached",
                    item.get("priority_score", 0),
                    item.get("open_alert_count", 0),
                ),
                reverse=True,
            )

        return {
            "generated_at": datetime.now().isoformat(),
            "view": normalized_view or "all",
            "role_view": normalized_role_view,
            "limit": max(limit, 1),
            "total_items": len(items),
            "counts": {
                "all": len(snapshots),
                "needs_attention": sum(1 for snapshot in snapshots if snapshot.get("needs_attention")),
                "worsening": sum(1 for snapshot in snapshots if snapshot.get("worsening")),
                "overdue": sum(1 for snapshot in snapshots if snapshot.get("overdue_follow_ups", 0) > 0),
                "high_risk": sum(1 for snapshot in snapshots if self._risk_rank(snapshot.get("risk_level")) >= 3),
                "sla_breached": sum(1 for snapshot in snapshots if snapshot.get("sla_breaches", 0) > 0),
                "doctor_review": sum(1 for snapshot in snapshots if snapshot.get("doctor_review_cases", 0) > 0),
            },
            "items": items[: max(limit, 1)],
        }

    def _get_dashboard_summary(
        self,
        *,
        user: Mapping[str, Any] | None = None,
        role_view: str = "",
        unit: str = "",
        team: str = "",
    ) -> Dict:
        """Gera resumo clÃ­nico decisÃ³rio do dashboard."""
        summary = {
            "timestamp": datetime.now().isoformat(),
            "platform": "HEAL/REDISUS",
            "role_view": self._normalize_role_view(role_view, user),
            "unit": unit or None,
            "team": team or None,
            "total_patients": 0,
            "total_analyses": 0,
            "risk_distribution": {"baixo": 0, "moderado": 0, "alto": 0, "critico": 0},
            "active_alerts": 0,
            "recent_analyses": [],
            "top_etiologies": [],
            "clinical_queue": [],
            "patients_needing_attention": 0,
            "patients_worsening": 0,
            "patients_overdue": 0,
            "active_care_plans": 0,
            "scheduled_follow_ups": 0,
            "open_clinical_alerts": 0,
            "patients_sla_breached": 0,
            "patients_requiring_doctor_review": 0,
        }

        stats = self._db_call("get_statistics", default={}) or {}
        summary["total_patients"] = int(stats.get("total_patients", 0) or 0)
        summary["total_analyses"] = int(stats.get("total_analyses", 0) or 0)
        summary["top_etiologies"] = list(stats.get("top_etiologies", []) or [])

        snapshots = self._get_all_patient_snapshots(user=user, unit=unit, team=team)
        if not summary["total_patients"]:
            summary["total_patients"] = len(snapshots)

        for snapshot in snapshots:
            risk_level = self._normalize_risk(snapshot.get("risk_level"))
            if risk_level in summary["risk_distribution"]:
                summary["risk_distribution"][risk_level] += 1
            summary["patients_needing_attention"] += int(bool(snapshot.get("needs_attention")))
            summary["patients_worsening"] += int(bool(snapshot.get("worsening")))
            summary["patients_overdue"] += int(snapshot.get("overdue_follow_ups", 0) > 0)
            summary["active_care_plans"] += int(snapshot.get("active_care_plans", 0))
            summary["scheduled_follow_ups"] += int(snapshot.get("scheduled_follow_ups", 0))
            summary["open_clinical_alerts"] += int(snapshot.get("open_alert_count", 0))
            summary["patients_sla_breached"] += int(snapshot.get("sla_breaches", 0) > 0)
            summary["patients_requiring_doctor_review"] += int(snapshot.get("doctor_review_cases", 0) > 0)

        recent_analyses: List[Dict[str, Any]] = []
        for snapshot in snapshots:
            patient = snapshot.get("patient", {})
            priority_lesion = snapshot.get("priority_lesion") or {}
            latest_evaluation = priority_lesion.get("latest_evaluation")
            if not latest_evaluation:
                continue
            recent_analyses.append(
                {
                    "patient_id": patient.get("id"),
                    "patient_name": patient.get("name"),
                    "lesion_id": (priority_lesion.get("lesion") or {}).get("id"),
                    "evaluation_id": latest_evaluation.get("id"),
                    "evaluation_date": latest_evaluation.get("evaluation_date"),
                    "risk_level": priority_lesion.get("risk_level"),
                    "priority_score": priority_lesion.get("priority_score"),
                }
            )
        recent_analyses.sort(
            key=lambda item: self._parse_datetime(item.get("evaluation_date")) or datetime.min,
            reverse=True,
        )
        summary["recent_analyses"] = recent_analyses[:5]
        summary["clinical_queue"] = self._build_clinical_queue_from_snapshots(
            snapshots,
            limit=5,
            role_view=summary["role_view"],
        )["items"]

        surveillance_alerts = 0
        if self.surveillance:
            surveillance_alerts = len([alert for alert in self.surveillance.alerts if not alert.acknowledged])
        summary["active_alerts"] = summary["open_clinical_alerts"] + surveillance_alerts
        return summary

    def _get_clinical_queue(
        self,
        *,
        user: Mapping[str, Any] | None = None,
        limit: int = 20,
        view: str = "",
        role_view: str = "",
        unit: str = "",
        team: str = "",
    ) -> Dict:
        return self._build_clinical_queue_from_snapshots(
            self._get_all_patient_snapshots(user=user, unit=unit, team=team),
            limit=limit,
            view=view,
            role_view=self._normalize_role_view(role_view, user),
        )

    def _get_patients_list(self) -> List[Dict]:
        """Lista pacientes com status clÃ­nico resumido."""
        snapshots = {snapshot["patient"].get("id"): snapshot for snapshot in self._get_all_patient_snapshots()}
        patients = [self._serialize_patient(item) for item in self._db_call("list_patients", default=[])]
        enriched_patients: List[Dict[str, Any]] = []

        for patient in patients:
            snapshot = snapshots.get(patient.get("id"))
            metadata = dict(patient.get("metadata") or {})
            if snapshot:
                metadata.update(
                    {
                        "risk_level": snapshot.get("risk_level"),
                        "status": snapshot.get("status"),
                        "needs_attention": snapshot.get("needs_attention"),
                        "worsening": snapshot.get("worsening"),
                        "priority_score": snapshot.get("priority_score"),
                        "open_alerts": snapshot.get("open_alert_count"),
                        "overdue_follow_ups": snapshot.get("overdue_follow_ups"),
                        "lesion_count": snapshot.get("lesion_count"),
                        "latest_evaluation_date": snapshot.get("latest_evaluation_date"),
                        "next_follow_up": snapshot.get("next_follow_up"),
                    }
                )
            patient["metadata"] = metadata
            enriched_patients.append(patient)
        return enriched_patients

    def _get_patient_detail(self, patient_id: str) -> Dict:
        """Detalhe completo de um paciente com linha do tempo clÃ­nica."""
        if not self.db:
            return {"error": "Database nÃ£o configurado"}

        patient = self._db_call("get_patient", patient_id, default=None)
        if not patient:
            return {"error": "Paciente nÃ£o encontrado"}

        try:
            analyses = [self._to_dict(item) for item in self._db_call("get_patient_analyses", patient_id, default=[])]
            snapshot = self._build_patient_snapshot(patient)
            lesion_timelines = [
                lesion_snapshot.get("timeline")
                or {
                    "lesion": lesion_snapshot.get("lesion"),
                    "summary": {
                        "latest_risk_level": lesion_snapshot.get("risk_level"),
                        "open_alert_count": lesion_snapshot.get("open_alert_count"),
                        "next_follow_up": lesion_snapshot.get("next_follow_up"),
                    },
                }
                for lesion_snapshot in snapshot.get("lesions", [])
            ]
            return {
                "patient": self._serialize_patient(patient),
                "analyses": analyses,
                "total_analyses": len(analyses),
                "clinical_summary": {
                    "risk_level": snapshot.get("risk_level"),
                    "status": snapshot.get("status"),
                    "needs_attention": snapshot.get("needs_attention"),
                    "worsening": snapshot.get("worsening"),
                    "priority_score": snapshot.get("priority_score"),
                    "sla_breaches": snapshot.get("sla_breaches"),
                    "doctor_review_cases": snapshot.get("doctor_review_cases"),
                    "open_alert_count": snapshot.get("open_alert_count"),
                    "overdue_follow_ups": snapshot.get("overdue_follow_ups"),
                    "latest_evaluation_date": snapshot.get("latest_evaluation_date"),
                    "next_follow_up": snapshot.get("next_follow_up"),
                    "attention_reasons": snapshot.get("attention_reasons"),
                },
                "lesions": snapshot.get("lesions", []),
                "lesion_timelines": lesion_timelines,
            }
        except Exception as e:
            logger.error(f"Erro ao buscar paciente {patient_id}: {e}")
            return {"error": str(e)}

    def _get_case_detail(
        self,
        case_id: str,
        *,
        user: Mapping[str, Any] | None = None,
        role_view: str = "",
    ) -> Dict[str, Any]:
        if not self.db:
            return {"error": "Database nÃ£o configurado"}

        raw_timeline = self._db_call("get_case_timeline", case_id, default=None)
        if not raw_timeline:
            return {"error": "Lesao nÃ£o encontrada"}

        timeline = raw_timeline.get("timeline")
        if not timeline:
            from packages.clinical_domain.workflow import build_case_timeline

            timeline = build_case_timeline(
                patient=raw_timeline["patient"],
                lesion=raw_timeline["lesion"],
                evaluations=raw_timeline["evaluations"],
                care_plans=raw_timeline["care_plans"],
                follow_ups=raw_timeline["follow_ups"],
                alerts=raw_timeline["alerts"],
                audit_log=raw_timeline.get("audit_log", []),
            )

        patient_payload = self._serialize_patient(raw_timeline["patient"])
        lesion_snapshot = self._build_lesion_snapshot(str(patient_payload.get("id") or ""), raw_timeline["lesion"])
        evaluations = [self._to_dict(item) for item in raw_timeline.get("evaluations", [])]
        latest = lesion_snapshot.get("latest_evaluation")
        previous = lesion_snapshot.get("previous_evaluation")
        latest_image = self._primary_image(latest)
        previous_image = self._primary_image(previous)
        primary_alert = ((lesion_snapshot.get("open_alerts") or [{}])[0]) if lesion_snapshot.get("open_alerts") else {}
        before_vs_after = {
            "latest": latest,
            "previous": previous,
            "deltas": lesion_snapshot.get("evaluation_delta", {}),
            "latest_image": latest_image,
            "previous_image": previous_image,
            "latest_image_url": self._image_url(latest_image),
            "previous_image_url": self._image_url(previous_image),
        }

        return {
            "patient": patient_payload,
            "lesion": self._to_dict(raw_timeline.get("lesion")),
            "clinical_summary": {
                "risk_level": lesion_snapshot.get("risk_level"),
                "status": lesion_snapshot.get("status"),
                "priority_score": lesion_snapshot.get("priority_score"),
                "priority_bucket": lesion_snapshot.get("priority_bucket"),
                "sla_status": lesion_snapshot.get("sla_status"),
                "sla_target_days": lesion_snapshot.get("sla_target_days"),
                "sla_days_remaining": lesion_snapshot.get("sla_days_remaining"),
                "review_due_date": lesion_snapshot.get("review_due_date"),
                "needs_attention": lesion_snapshot.get("needs_attention"),
                "worsening": lesion_snapshot.get("worsening"),
                "requires_doctor_review": lesion_snapshot.get("requires_doctor_review"),
                "recommended_owner_role": lesion_snapshot.get("recommended_owner_role"),
                "attention_reasons": lesion_snapshot.get("attention_reasons"),
                "available_actions": self._queue_actions_for_role(
                    lesion_snapshot,
                    self._normalize_role_view(role_view, user),
                ),
            },
            "timeline": timeline,
            "before_vs_after": before_vs_after,
            "ownership": {
                "case": lesion_snapshot.get("ownership"),
                "primary_alert": self._assignment_payload(primary_alert),
            },
            "active_care_plan": lesion_snapshot.get("active_care_plan"),
            "follow_ups": lesion_snapshot.get("follow_ups"),
            "alerts": lesion_snapshot.get("alerts"),
            "audit_log": lesion_snapshot.get("audit_log"),
            "metrics": {
                "evaluation_count": len(evaluations),
                "open_alert_count": lesion_snapshot.get("open_alert_count"),
                "audit_event_count": lesion_snapshot.get("audit_event_count"),
                "follow_up_count": len(lesion_snapshot.get("follow_ups") or []),
            },
        }

    def _get_patient_risk(self, patient_id: str) -> Dict:
        """Resumo de risco orientado a decisÃ£o clÃ­nica."""
        if not self.db:
            return {"error": "Database nÃ£o configurado"}

        patient = self._db_call("get_patient", patient_id, default=None)
        if not patient:
            return {"error": "Paciente nÃ£o encontrado"}

        snapshot = self._build_patient_snapshot(patient)
        lesion_risks = [
            {
                "lesion_id": (lesion.get("lesion") or {}).get("id"),
                "title": (lesion.get("lesion") or {}).get("title"),
                "risk_level": lesion.get("risk_level"),
                "status": lesion.get("status"),
                "priority_score": lesion.get("priority_score"),
                "worsening": lesion.get("worsening"),
                "overdue_follow_up": lesion.get("overdue_follow_up_flag"),
                "open_alert_count": lesion.get("open_alert_count"),
                "attention_reasons": lesion.get("attention_reasons"),
            }
            for lesion in snapshot.get("lesions", [])
        ]
        return {
            "patient_id": patient_id,
            "risk_level": snapshot.get("risk_level"),
            "status": snapshot.get("status"),
            "priority_score": snapshot.get("priority_score"),
            "needs_attention": snapshot.get("needs_attention"),
            "worsening": snapshot.get("worsening"),
            "overdue_follow_ups": snapshot.get("overdue_follow_ups"),
            "open_alert_count": snapshot.get("open_alert_count"),
            "active_care_plans": snapshot.get("active_care_plans"),
            "latest_evaluation_date": snapshot.get("latest_evaluation_date"),
            "next_follow_up": snapshot.get("next_follow_up"),
            "attention_reasons": snapshot.get("attention_reasons"),
            "lesions": lesion_risks,
        }

    def _get_population_indicators(self, region: str, *, user: Mapping[str, Any] | None = None) -> List[Dict]:
        """Indicadores populacionais orientados Ã  operaÃ§Ã£o clÃ­nica."""
        snapshots = self._get_all_patient_snapshots(region=region, user=user)
        region_label = region or "todas"
        return [
            {"name": "Pacientes em acompanhamento", "value": len(snapshots), "region": region_label},
            {
                "name": "Pacientes que precisam de atencao",
                "value": sum(1 for snapshot in snapshots if snapshot.get("needs_attention")),
                "region": region_label,
            },
            {
                "name": "Pacientes com piora recente",
                "value": sum(1 for snapshot in snapshots if snapshot.get("worsening")),
                "region": region_label,
            },
            {
                "name": "Follow-ups atrasados",
                "value": sum(snapshot.get("overdue_follow_ups", 0) for snapshot in snapshots),
                "region": region_label,
            },
            {
                "name": "Alertas clinicos abertos",
                "value": sum(snapshot.get("open_alert_count", 0) for snapshot in snapshots),
                "region": region_label,
            },
        ]

    def _get_active_alerts(
        self,
        *,
        user: Mapping[str, Any] | None = None,
        role_view: str = "",
    ) -> List[Dict]:
        """Alertas ativos do sistema, combinando vigilÃ¢ncia e alertas clÃ­nicos."""
        alerts: List[Dict[str, Any]] = []
        normalized_role_view = self._normalize_role_view(role_view, user)
        if self.surveillance:
            for alert in self.surveillance.alerts:
                if alert.acknowledged:
                    continue
                alerts.append(
                    {
                        "id": alert.alert_id,
                        "source": "surveillance",
                        "condition": alert.condition,
                        "region": alert.region,
                        "severity": self._normalize_risk(alert.severity),
                        "message": alert.message,
                        "case_count": alert.case_count,
                        "timestamp": alert.timestamp,
                    }
                )

        for snapshot in self._get_all_patient_snapshots(user=user):
            patient = snapshot.get("patient", {})
            for lesion in snapshot.get("lesions", []):
                lesion_payload = lesion.get("lesion") or {}
                for alert in lesion.get("open_alerts", []):
                    severity = self._normalize_risk(alert.get("severity"))
                    if normalized_role_view == "doctor" and self._risk_rank(severity) < 3:
                        continue
                    alerts.append(
                        {
                            "id": alert.get("id"),
                            "source": "clinical",
                            "condition": lesion_payload.get("wound_type") or lesion_payload.get("title") or "lesao",
                            "region": self._patient_region(patient),
                            "severity": severity,
                            "message": alert.get("message") or alert.get("title"),
                            "case_count": 1,
                            "timestamp": alert.get("created_at"),
                            "patient_id": patient.get("id"),
                            "patient_name": patient.get("name"),
                            "lesion_id": lesion_payload.get("id"),
                            "lesion_title": lesion_payload.get("title"),
                            "alert_type": alert.get("alert_type"),
                        }
                    )

        alerts.sort(
            key=lambda alert: (
                self._severity_rank(alert.get("severity")),
                self._parse_datetime(alert.get("timestamp")) or datetime.min,
            ),
            reverse=True,
        )
        return alerts

    def _get_production_report(
        self,
        period: str,
        *,
        user: Mapping[str, Any] | None = None,
        role_view: str = "",
        unit: str = "",
        team: str = "",
    ) -> Dict:
        """RelatÃ³rio operacional com foco no fluxo clÃ­nico principal."""
        normalized_role_view = self._normalize_role_view(role_view, user)
        snapshots = self._get_all_patient_snapshots(user=user, unit=unit, team=team)
        queue = self._build_clinical_queue_from_snapshots(snapshots, limit=10, role_view=normalized_role_view)
        return {
            "period": period,
            "generated_at": datetime.now().isoformat(),
            "generated_by": "HEAL/REDISUS",
            "role_view": normalized_role_view,
            "unit": unit or None,
            "team": team or None,
            "message": "Relatorio operacional do fluxo paciente -> lesao -> imagem -> IA -> avaliacao -> evolucao -> plano -> acompanhamento",
            "patients_in_follow_up": len(snapshots),
            "patients_needing_attention": queue["counts"]["needs_attention"],
            "patients_worsening": queue["counts"]["worsening"],
            "follow_ups_overdue": queue["counts"]["overdue"],
            "high_risk_patients": queue["counts"]["high_risk"],
            "patients_sla_breached": queue["counts"]["sla_breached"],
            "patients_requiring_doctor_review": queue["counts"]["doctor_review"],
            "open_clinical_alerts": sum(snapshot.get("open_alert_count", 0) for snapshot in snapshots),
            "active_care_plans": sum(snapshot.get("active_care_plans", 0) for snapshot in snapshots),
            "scheduled_follow_ups": sum(snapshot.get("scheduled_follow_ups", 0) for snapshot in snapshots),
            "top_queue": queue["items"],
        }

    def _export_fhir(self, patient_id: str) -> Dict:
        """Exporta dados FHIR"""
        return {
            "patient_id": patient_id,
            "message": "Use GET /api/v1/lesions/<case_id>/fhir para exportação FHIR R4 sob demanda por caso clínico.",
        }


# ============================================================================
# Templates HTML para o Dashboard
# ============================================================================

DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>HEAL/REDISUS — Dashboard Clínico</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
    <style>
        :root {
            --primary: #6366f1;
            --primary-light: #818cf8;
            --primary-dark: #4f46e5;
            --success: #10b981;
            --success-light: #34d399;
            --warning: #f59e0b;
            --warning-light: #fbbf24;
            --danger: #ef4444;
            --danger-light: #f87171;
            --info: #06b6d4;
            --info-light: #22d3ee;
            --bg: #0b0e14;
            --bg-secondary: #111827;
            --card-bg: rgba(17, 24, 39, 0.7);
            --card-border: rgba(255, 255, 255, 0.06);
            --card-hover: rgba(255, 255, 255, 0.03);
            --text: #f1f5f9;
            --text-secondary: #94a3b8;
            --text-muted: #64748b;
            --glow-primary: rgba(99, 102, 241, 0.15);
            --glow-success: rgba(16, 185, 129, 0.15);
            --glow-warning: rgba(245, 158, 11, 0.15);
            --glow-danger: rgba(239, 68, 68, 0.15);
            --glow-info: rgba(6, 182, 212, 0.15);
            --radius: 16px;
            --radius-sm: 10px;
            --shadow: 0 4px 24px rgba(0, 0, 0, 0.3);
        }

        * { margin: 0; padding: 0; box-sizing: border-box; }

        body {
            font-family: 'Inter', 'Segoe UI', system-ui, -apple-system, sans-serif;
            background: var(--bg);
            color: var(--text);
            min-height: 100vh;
            overflow-x: hidden;
        }

        /* Animated background mesh */
        body::before {
            content: '';
            position: fixed;
            top: 0; left: 0; right: 0; bottom: 0;
            background:
                radial-gradient(ellipse 600px 400px at 10% 20%, rgba(99,102,241,0.08), transparent),
                radial-gradient(ellipse 500px 350px at 85% 60%, rgba(6,182,212,0.06), transparent),
                radial-gradient(ellipse 400px 300px at 50% 90%, rgba(16,185,129,0.05), transparent);
            pointer-events: none;
            z-index: 0;
        }

        /* ---- HEADER ---- */
        .header {
            position: sticky;
            top: 0;
            z-index: 100;
            background: rgba(11, 14, 20, 0.85);
            backdrop-filter: blur(20px) saturate(1.4);
            -webkit-backdrop-filter: blur(20px) saturate(1.4);
            padding: 0 2rem;
            display: flex;
            justify-content: space-between;
            align-items: center;
            height: 64px;
            border-bottom: 1px solid var(--card-border);
        }
        .header-brand {
            display: flex;
            align-items: center;
            gap: 12px;
        }
        .header-logo {
            width: 36px; height: 36px;
            background: linear-gradient(135deg, var(--primary), var(--info));
            border-radius: 10px;
            display: flex; align-items: center; justify-content: center;
            font-weight: 800; font-size: 14px; color: #fff;
            box-shadow: 0 2px 12px rgba(99,102,241,0.3);
        }
        .header h1 {
            font-size: 1.15rem;
            font-weight: 700;
            color: #fff;
            letter-spacing: -0.02em;
        }
        .header h1 span { color: var(--primary-light); }
        .header .subtitle {
            color: var(--text-muted);
            font-size: 0.7rem;
            font-weight: 400;
            letter-spacing: 0.04em;
            text-transform: uppercase;
        }

        .nav { display: flex; gap: 4px; }
        .nav a {
            color: var(--text-secondary);
            text-decoration: none;
            padding: 8px 16px;
            border-radius: 8px;
            font-size: 0.85rem;
            font-weight: 500;
            transition: all 0.2s ease;
            position: relative;
        }
        .nav a:hover {
            color: var(--text);
            background: rgba(255,255,255,0.06);
        }
        .nav a.active {
            color: #fff;
            background: var(--primary);
            box-shadow: 0 2px 12px rgba(99,102,241,0.35);
        }
        .nav a .nav-icon { margin-right: 6px; font-size: 1rem; }

        /* ---- STATUS BAR ---- */
        .status-bar {
            background: rgba(16, 185, 129, 0.08);
            border-bottom: 1px solid rgba(16, 185, 129, 0.15);
            padding: 6px 2rem;
            display: flex;
            align-items: center;
            gap: 1.5rem;
            font-size: 0.75rem;
            color: var(--text-secondary);
            position: relative;
            z-index: 1;
        }
        .status-dot {
            width: 7px; height: 7px;
            background: var(--success);
            border-radius: 50%;
            display: inline-block;
            margin-right: 6px;
            animation: pulse-dot 2s ease-in-out infinite;
            box-shadow: 0 0 6px var(--success);
        }
        @keyframes pulse-dot {
            0%, 100% { opacity: 1; transform: scale(1); }
            50% { opacity: 0.6; transform: scale(0.85); }
        }

        /* ---- CONTAINER ---- */
        .container {
            max-width: 1440px;
            margin: 0 auto;
            padding: 1.5rem 2rem;
            position: relative;
            z-index: 1;
        }

        /* ---- KPI CARDS ---- */
        .kpi-grid {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 1rem;
            margin-bottom: 2rem;
        }
        .kpi-card {
            background: var(--card-bg);
            backdrop-filter: blur(12px);
            border: 1px solid var(--card-border);
            border-radius: var(--radius);
            padding: 1.5rem;
            position: relative;
            overflow: hidden;
            transition: transform 0.25s ease, box-shadow 0.25s ease, border-color 0.25s ease;
        }
        .kpi-card:hover {
            transform: translateY(-3px);
            box-shadow: var(--shadow);
        }
        .kpi-card::before {
            content: '';
            position: absolute;
            top: 0; left: 0; right: 0;
            height: 3px;
            border-radius: 3px 3px 0 0;
        }
        .kpi-card.info::before { background: linear-gradient(90deg, var(--info), var(--info-light)); }
        .kpi-card.success::before { background: linear-gradient(90deg, var(--success), var(--success-light)); }
        .kpi-card.warning::before { background: linear-gradient(90deg, var(--warning), var(--warning-light)); }
        .kpi-card.danger::before { background: linear-gradient(90deg, var(--danger), var(--danger-light)); }
        .kpi-card.info:hover { border-color: rgba(6,182,212,0.25); box-shadow: 0 4px 30px var(--glow-info); }
        .kpi-card.success:hover { border-color: rgba(16,185,129,0.25); box-shadow: 0 4px 30px var(--glow-success); }
        .kpi-card.warning:hover { border-color: rgba(245,158,11,0.25); box-shadow: 0 4px 30px var(--glow-warning); }
        .kpi-card.danger:hover { border-color: rgba(239,68,68,0.25); box-shadow: 0 4px 30px var(--glow-danger); }

        .kpi-header {
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            margin-bottom: 1rem;
        }
        .kpi-label {
            color: var(--text-secondary);
            font-size: 0.78rem;
            font-weight: 500;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }
        .kpi-icon {
            width: 40px; height: 40px;
            border-radius: 12px;
            display: flex; align-items: center; justify-content: center;
            font-size: 1.2rem;
        }
        .kpi-card.info .kpi-icon { background: var(--glow-info); }
        .kpi-card.success .kpi-icon { background: var(--glow-success); }
        .kpi-card.warning .kpi-icon { background: var(--glow-warning); }
        .kpi-card.danger .kpi-icon { background: var(--glow-danger); }

        .kpi-value {
            font-size: 2.2rem;
            font-weight: 800;
            letter-spacing: -0.03em;
            line-height: 1;
            margin-bottom: 6px;
        }
        .kpi-card.info .kpi-value { color: var(--info-light); }
        .kpi-card.success .kpi-value { color: var(--success-light); }
        .kpi-card.warning .kpi-value { color: var(--warning-light); }
        .kpi-card.danger .kpi-value { color: var(--danger-light); }

        .kpi-sub {
            font-size: 0.75rem;
            color: var(--text-muted);
            font-weight: 400;
        }

        /* ---- SECTIONS ---- */
        .section {
            margin-bottom: 2rem;
        }
        .section-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 1rem;
        }
        .section-header h2 {
            font-size: 1.05rem;
            font-weight: 600;
            color: var(--text);
            letter-spacing: -0.01em;
        }
        .section-header h2 .sec-icon { margin-right: 8px; opacity: 0.7; }

        /* ---- GRID LAYOUTS ---- */
        .grid-2 {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 1.25rem;
        }

        /* ---- CHART PLACEHOLDERS ---- */
        .chart-card {
            background: var(--card-bg);
            backdrop-filter: blur(12px);
            border: 1px solid var(--card-border);
            border-radius: var(--radius);
            padding: 1.5rem;
            transition: border-color 0.25s ease;
            min-height: 240px;
            display: flex;
            flex-direction: column;
        }
        .chart-card:hover {
            border-color: rgba(255,255,255,0.1);
        }
        .chart-card h3 {
            font-size: 0.9rem;
            font-weight: 600;
            margin-bottom: 1rem;
            color: var(--text);
        }
        .chart-body {
            flex: 1;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            color: var(--text-muted);
            font-size: 0.85rem;
        }
        .chart-body .chart-icon {
            font-size: 2.5rem;
            margin-bottom: 0.75rem;
            opacity: 0.4;
        }
        .chart-body small {
            margin-top: 0.4rem;
            font-size: 0.75rem;
            opacity: 0.6;
        }

        /* Bar chart simulation */
        .mini-bars {
            display: flex;
            align-items: flex-end;
            gap: 6px;
            height: 100px;
            width: 100%;
            padding: 0 1rem;
            margin-top: auto;
        }
        .mini-bar {
            flex: 1;
            border-radius: 4px 4px 0 0;
            min-height: 8px;
            transition: height 0.6s ease;
            position: relative;
        }
        .mini-bar.b1 { background: linear-gradient(to top, var(--primary-dark), var(--primary-light)); }
        .mini-bar.b2 { background: linear-gradient(to top, #0e7490, var(--info-light)); }
        .mini-bar.b3 { background: linear-gradient(to top, #b45309, var(--warning-light)); }
        .mini-bar.b4 { background: linear-gradient(to top, #047857, var(--success-light)); }

        /* Donut placeholder */
        .donut-placeholder {
            width: 120px; height: 120px;
            border-radius: 50%;
            background: conic-gradient(
                var(--success) 0% 40%,
                var(--warning) 40% 60%,
                var(--danger) 60% 75%,
                var(--info) 75% 100%
            );
            position: relative;
            margin: 0.5rem auto;
        }
        .donut-placeholder::after {
            content: '';
            position: absolute;
            top: 50%; left: 50%;
            transform: translate(-50%, -50%);
            width: 70px; height: 70px;
            border-radius: 50%;
            background: var(--bg-secondary);
        }

        /* ---- TABLE ---- */
        .table-card {
            background: var(--card-bg);
            backdrop-filter: blur(12px);
            border: 1px solid var(--card-border);
            border-radius: var(--radius);
            overflow: hidden;
        }
        table {
            width: 100%;
            border-collapse: collapse;
        }
        thead { background: rgba(99, 102, 241, 0.08); }
        th {
            padding: 12px 16px;
            text-align: left;
            font-size: 0.72rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.06em;
            color: var(--text-secondary);
            border-bottom: 1px solid var(--card-border);
        }
        td {
            padding: 12px 16px;
            font-size: 0.88rem;
            border-bottom: 1px solid rgba(255,255,255,0.03);
            color: var(--text);
        }
        tr { transition: background 0.15s ease; }
        tr:hover td { background: var(--card-hover); }
        tr:last-child td { border-bottom: none; }

        .badge {
            display: inline-flex;
            align-items: center;
            gap: 5px;
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 0.72rem;
            font-weight: 600;
            letter-spacing: 0.02em;
        }
        .badge::before {
            content: '';
            width: 6px; height: 6px;
            border-radius: 50%;
        }
        .badge-baixo { background: rgba(16,185,129,0.12); color: var(--success-light); }
        .badge-baixo::before { background: var(--success); }
        .badge-moderado { background: rgba(245,158,11,0.12); color: var(--warning-light); }
        .badge-moderado::before { background: var(--warning); }
        .badge-alto { background: rgba(249,115,22,0.12); color: #fb923c; }
        .badge-alto::before { background: #f97316; }
        .badge-critico { background: rgba(239,68,68,0.12); color: var(--danger-light); }
        .badge-critico::before { background: var(--danger); }

        .queue-toolbar {
            display: flex;
            gap: 0.6rem;
            flex-wrap: wrap;
            margin-bottom: 1rem;
        }
        .queue-filter {
            background: rgba(255,255,255,0.04);
            color: var(--text-secondary);
            border: 1px solid var(--card-border);
            border-radius: 999px;
            padding: 0.5rem 0.9rem;
            font-size: 0.78rem;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s ease;
        }
        .queue-filter:hover {
            color: var(--text);
            border-color: rgba(99,102,241,0.25);
        }
        .queue-filter.active {
            color: #fff;
            background: rgba(99,102,241,0.18);
            border-color: rgba(129,140,248,0.35);
            box-shadow: 0 4px 18px rgba(99,102,241,0.14);
        }
        .queue-list {
            display: flex;
            flex-direction: column;
            gap: 0.9rem;
        }
        .queue-item {
            border: 1px solid var(--card-border);
            border-left: 4px solid transparent;
            border-radius: 14px;
            padding: 1rem 1.1rem;
            background: rgba(255,255,255,0.02);
            transition: transform 0.2s ease, border-color 0.2s ease, background 0.2s ease;
        }
        .queue-item:hover {
            transform: translateX(2px);
            background: rgba(255,255,255,0.03);
        }
        .queue-item.risk-critico { border-left-color: var(--danger); }
        .queue-item.risk-alto { border-left-color: var(--warning); }
        .queue-item.risk-moderado { border-left-color: var(--info); }
        .queue-item.risk-baixo { border-left-color: var(--success); }
        .queue-top {
            display: flex;
            align-items: flex-start;
            justify-content: space-between;
            gap: 1rem;
            flex-wrap: wrap;
        }
        .queue-title {
            font-size: 0.96rem;
            font-weight: 600;
            color: var(--text);
            margin-bottom: 0.25rem;
        }
        .queue-score {
            display: inline-flex;
            align-items: center;
            gap: 0.35rem;
            padding: 0.35rem 0.7rem;
            border-radius: 999px;
            background: rgba(239,68,68,0.12);
            color: var(--danger-light);
            font-size: 0.78rem;
            font-weight: 700;
        }
        .queue-meta {
            display: flex;
            flex-wrap: wrap;
            gap: 0.75rem;
            color: var(--text-muted);
            font-size: 0.78rem;
        }
        .queue-reasons {
            margin-top: 0.75rem;
            display: flex;
            flex-wrap: wrap;
            gap: 0.5rem;
        }
        .reason-chip {
            display: inline-flex;
            align-items: center;
            padding: 0.32rem 0.65rem;
            border-radius: 999px;
            background: rgba(255,255,255,0.05);
            color: var(--text-secondary);
            font-size: 0.73rem;
        }
        .queue-empty {
            text-align: center;
            color: var(--text-muted);
            padding: 1.5rem 0.75rem;
            font-size: 0.85rem;
        }
        .queue-context {
            display: flex;
            gap: 0.6rem;
            flex-wrap: wrap;
            margin-bottom: 1rem;
        }
        .queue-context select,
        .queue-context input {
            background: rgba(255,255,255,0.04);
            color: var(--text);
            border: 1px solid var(--card-border);
            border-radius: 10px;
            padding: 0.55rem 0.75rem;
            font-size: 0.8rem;
            min-width: 150px;
        }
        .queue-context button,
        .queue-action-btn,
        .case-action-btn {
            background: rgba(99,102,241,0.18);
            color: #fff;
            border: 1px solid rgba(129,140,248,0.35);
            border-radius: 10px;
            padding: 0.55rem 0.8rem;
            font-size: 0.78rem;
            font-weight: 600;
            cursor: pointer;
        }
        .queue-actions,
        .case-actions {
            display: flex;
            gap: 0.5rem;
            flex-wrap: wrap;
            margin-top: 0.85rem;
        }
        .case-panel {
            margin-top: 1rem;
            border: 1px solid var(--card-border);
            border-radius: 14px;
            padding: 1rem 1.1rem;
            background: rgba(255,255,255,0.02);
        }
        .case-grid {
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 1rem;
            margin-top: 0.75rem;
        }
        .case-block {
            border: 1px solid rgba(255,255,255,0.05);
            border-radius: 12px;
            padding: 0.9rem;
            background: rgba(255,255,255,0.02);
        }
        .case-block h4 {
            font-size: 0.82rem;
            text-transform: uppercase;
            letter-spacing: 0.06em;
            color: var(--text-secondary);
            margin-bottom: 0.75rem;
        }
        .case-stat {
            display: flex;
            justify-content: space-between;
            gap: 0.75rem;
            color: var(--text-secondary);
            font-size: 0.82rem;
            margin-bottom: 0.45rem;
        }
        .case-timeline {
            display: flex;
            flex-direction: column;
            gap: 0.55rem;
            max-height: 280px;
            overflow-y: auto;
        }
        .case-event {
            border-left: 2px solid rgba(99,102,241,0.35);
            padding-left: 0.75rem;
            color: var(--text-secondary);
            font-size: 0.8rem;
        }
        .case-event strong {
            display: block;
            color: var(--text);
            font-size: 0.82rem;
            margin-bottom: 0.15rem;
        }
        .case-inline-form {
            display: flex;
            gap: 0.5rem;
            flex-wrap: wrap;
            margin-top: 0.75rem;
        }
        .case-inline-form input,
        .case-inline-form select,
        .case-inline-form textarea {
            background: rgba(255,255,255,0.04);
            color: var(--text);
            border: 1px solid var(--card-border);
            border-radius: 10px;
            padding: 0.5rem 0.7rem;
            font-size: 0.8rem;
        }
        .case-inline-form textarea {
            min-height: 88px;
            width: 100%;
            resize: vertical;
        }
        .case-compare {
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 0.85rem;
            margin-top: 0.85rem;
        }
        .case-compare-card {
            border: 1px solid rgba(255,255,255,0.06);
            border-radius: 12px;
            padding: 0.75rem;
            background: rgba(255,255,255,0.02);
        }
        .case-compare-card img {
            width: 100%;
            height: 180px;
            object-fit: cover;
            border-radius: 10px;
            margin-top: 0.55rem;
            border: 1px solid rgba(255,255,255,0.08);
        }
        .case-owner {
            display: flex;
            flex-direction: column;
            gap: 0.4rem;
            color: var(--text-secondary);
            font-size: 0.8rem;
        }

        /* ---- EIXOS / FEATURE CARDS ---- */
        .features-grid {
            display: grid;
            grid-template-columns: repeat(5, 1fr);
            gap: 1rem;
        }
        .feature-card {
            background: var(--card-bg);
            backdrop-filter: blur(12px);
            border: 1px solid var(--card-border);
            border-radius: var(--radius);
            padding: 1.5rem 1.25rem;
            transition: all 0.3s ease;
            position: relative;
            overflow: hidden;
        }
        .feature-card:hover {
            transform: translateY(-2px);
            border-color: rgba(99,102,241,0.2);
            box-shadow: 0 8px 30px rgba(99,102,241,0.1);
        }
        .feature-card::after {
            content: '';
            position: absolute;
            bottom: 0; left: 0; right: 0;
            height: 2px;
            background: linear-gradient(90deg, var(--primary), var(--info));
            opacity: 0;
            transition: opacity 0.3s ease;
        }
        .feature-card:hover::after { opacity: 1; }
        .feature-num {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            width: 28px; height: 28px;
            border-radius: 8px;
            background: var(--glow-primary);
            color: var(--primary-light);
            font-size: 0.75rem;
            font-weight: 700;
            margin-bottom: 12px;
        }
        .feature-title {
            font-size: 0.92rem;
            font-weight: 600;
            color: var(--text);
            margin-bottom: 8px;
            line-height: 1.3;
        }
        .feature-desc {
            font-size: 0.78rem;
            color: var(--text-muted);
            line-height: 1.5;
        }

        /* ---- FOOTER ---- */
        .footer {
            text-align: center;
            padding: 1.5rem 2rem;
            color: var(--text-muted);
            font-size: 0.75rem;
            border-top: 1px solid var(--card-border);
            margin-top: 1rem;
            letter-spacing: 0.02em;
        }
        .footer strong { color: var(--text-secondary); font-weight: 600; }

        /* ---- ANIMATIONS ---- */
        @keyframes fadeInUp {
            from { opacity: 0; transform: translateY(16px); }
            to { opacity: 1; transform: translateY(0); }
        }
        .kpi-card, .chart-card, .table-card, .feature-card {
            animation: fadeInUp 0.5s ease both;
        }
        .kpi-card:nth-child(1) { animation-delay: 0.05s; }
        .kpi-card:nth-child(2) { animation-delay: 0.1s; }
        .kpi-card:nth-child(3) { animation-delay: 0.15s; }
        .kpi-card:nth-child(4) { animation-delay: 0.2s; }
        .feature-card:nth-child(1) { animation-delay: 0.1s; }
        .feature-card:nth-child(2) { animation-delay: 0.15s; }
        .feature-card:nth-child(3) { animation-delay: 0.2s; }
        .feature-card:nth-child(4) { animation-delay: 0.25s; }
        .feature-card:nth-child(5) { animation-delay: 0.3s; }

        /* ---- SCROLLBAR ---- */
        ::-webkit-scrollbar { width: 6px; }
        ::-webkit-scrollbar-track { background: transparent; }
        ::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.1); border-radius: 3px; }
        ::-webkit-scrollbar-thumb:hover { background: rgba(255,255,255,0.2); }

        /* ---- RESPONSIVE ---- */
        @media (max-width: 1200px) {
            .features-grid { grid-template-columns: repeat(3, 1fr); }
        }
        @media (max-width: 900px) {
            .kpi-grid { grid-template-columns: repeat(2, 1fr); }
            .grid-2 { grid-template-columns: 1fr; }
            .features-grid { grid-template-columns: repeat(2, 1fr); }
            .header { padding: 0 1rem; }
            .container { padding: 1rem; }
        }
        @media (max-width: 600px) {
            .kpi-grid { grid-template-columns: 1fr; }
            .features-grid { grid-template-columns: 1fr; }
            .nav a span { display: none; }
            .header h1 { font-size: 1rem; }
        }
    </style>
</head>
<body>
    <div class="header">
        <div class="header-brand">
            <div class="header-logo">H+</div>
            <div>
                <h1>HEAL <span>/</span> REDISUS</h1>
                <div class="subtitle">Plataforma Nacional de Saúde Digital Integrada</div>
            </div>
        </div>
        <nav class="nav">
            <a href="/" class="active"><span class="nav-icon">📊</span><span>Dashboard</span></a>
            <a href="/patients"><span class="nav-icon">🩺</span><span>Pacientes</span></a>
            <a href="/surveillance"><span class="nav-icon">🗺️</span><span>Vigilância</span></a>
            <a href="/alerts"><span class="nav-icon">🔔</span><span>Alertas</span></a>
        </nav>
    </div>

    <div class="status-bar">
        <div><span class="status-dot"></span>Sistema operacional</div>
        <div>🕐 Última atualização: <span id="last-update">--</span></div>
        <div style="margin-left:auto;">v2.0 · Cluster REDISUS</div>
    </div>

    <div class="container">
        <!-- KPI Cards -->
        <div class="kpi-grid" id="summary-cards">
            <div class="kpi-card info">
                <div class="kpi-header">
                    <div class="kpi-label">Total de Pacientes</div>
                    <div class="kpi-icon">👥</div>
                </div>
                <div class="kpi-value" id="total-patients">--</div>
                <div class="kpi-sub">Monitorados atualmente</div>
            </div>
            <div class="kpi-card success">
                <div class="kpi-header">
                    <div class="kpi-label">Análises Realizadas</div>
                    <div class="kpi-icon">🔬</div>
                </div>
                <div class="kpi-value" id="total-analyses">--</div>
                <div class="kpi-sub">Avaliações de feridas</div>
            </div>
            <div class="kpi-card warning">
                <div class="kpi-header">
                    <div class="kpi-label">Risco Alto / Crítico</div>
                    <div class="kpi-icon">⚠️</div>
                </div>
                <div class="kpi-value" id="high-risk">--</div>
                <div class="kpi-sub">Necessitam atenção imediata</div>
            </div>
            <div class="kpi-card danger">
                <div class="kpi-header">
                    <div class="kpi-label">Alertas Ativos</div>
                    <div class="kpi-icon">🚨</div>
                </div>
                <div class="kpi-value" id="active-alerts">--</div>
                <div class="kpi-sub">Pendentes de reconhecimento</div>
            </div>
        </div>

        <!-- Charts Row -->
        <div class="grid-2">
            <div class="chart-card">
                <h3><span class="sec-icon">📈</span> Distribuição por Etiologia</h3>
                <div class="mini-bars" id="etiology-chart">
                    <div class="mini-bar b1" style="height:70%;" title="Úlcera venosa"></div>
                    <div class="mini-bar b2" style="height:45%;" title="Pé diabético"></div>
                    <div class="mini-bar b3" style="height:55%;" title="Úlcera pressão"></div>
                    <div class="mini-bar b4" style="height:30%;" title="Queimaduras"></div>
                    <div class="mini-bar b1" style="height:20%;" title="Outras"></div>
                </div>
                <div class="chart-body" style="flex:0; padding-top:0.75rem;">
                    <small>Conecte ao banco de dados para dados reais</small>
                </div>
            </div>
            <div class="chart-card">
                <h3><span class="sec-icon">🎯</span> Estratificação de Risco</h3>
                <div class="chart-body">
                    <div class="donut-placeholder"></div>
                    <small>Conecte ao módulo de risco para dados reais</small>
                </div>
            </div>
        </div>

        <div class="section" style="margin-top:1.25rem;">
            <div class="section-header">
                <h2><span class="sec-icon">ðŸ©º</span> Fila ClÃ­nica DecisÃ³ria</h2>
                <div style="color:var(--text-muted); font-size:0.8rem;" id="queue-summary">Carregando fila...</div>
            </div>
            <div class="table-card" style="padding:1rem 1.25rem;">
                <div class="queue-context">
                    <select id="queue-role-view">
                        <option value="admin">Visão admin</option>
                        <option value="doctor">Visão médico</option>
                        <option value="nurse">Visão enfermagem</option>
                    </select>
                    <input id="queue-unit-filter" type="text" placeholder="Filtrar por unidade">
                    <input id="queue-team-filter" type="text" placeholder="Filtrar por equipe">
                    <button id="queue-context-apply" type="button">Aplicar contexto</button>
                </div>
                <div class="queue-toolbar" id="queue-filters">
                    <button class="queue-filter active" data-view="all">Tudo</button>
                    <button class="queue-filter" data-view="attention">Precisam de atenÃ§Ã£o</button>
                    <button class="queue-filter" data-view="worsening">Piora recente</button>
                    <button class="queue-filter" data-view="overdue">Atrasados</button>
                    <button class="queue-filter" data-view="high-risk">Alto risco</button>
                </div>
                <div class="queue-list" id="clinical-queue-list">
                    <div class="queue-empty">Carregando fila clÃ­nica...</div>
                </div>
            </div>
        </div>

        <div class="case-panel" id="case-panel">
            <div class="queue-empty">Abra um caso da fila para ver timeline, comparação e ações clínicas.</div>
        </div>

        <!-- Patients Table -->
        <div class="section" style="margin-top:1.25rem;">
            <div class="section-header">
                <h2><span class="sec-icon">🩻</span> Pacientes em Acompanhamento</h2>
            </div>
            <div class="table-card">
                <table id="patients-table">
                    <thead>
                        <tr>
                            <th>Paciente</th>
                            <th>Status</th>
                            <th>Área (cm²)</th>
                            <th>PrÃ³ximo follow-up</th>
                            <th>Risco</th>
                            <th>Última Avaliação</th>
                        </tr>
                    </thead>
                    <tbody id="patients-tbody">
                        <tr><td colspan="6" style="text-align:center; padding:2rem; color: var(--text-muted);">
                            Carregando dados...
                        </td></tr>
                    </tbody>
                </table>
            </div>
        </div>

        <!-- Platform Axes -->
        <div class="section" style="margin-top:1.25rem;">
            <div class="section-header">
                <h2><span class="sec-icon">🏗️</span> Eixos da Plataforma HEAL</h2>
            </div>
            <div class="features-grid">
                <div class="feature-card">
                    <div class="feature-num">01</div>
                    <div class="feature-title">Diagnóstico &amp; Monitoramento</div>
                    <div class="feature-desc">IA para imagens clínicas, sinais vitais e testes rápidos</div>
                </div>
                <div class="feature-card">
                    <div class="feature-num">02</div>
                    <div class="feature-title">Gestão do Cuidado</div>
                    <div class="feature-desc">Planos de cuidado, dashboards e estratificação de risco</div>
                </div>
                <div class="feature-card">
                    <div class="feature-num">03</div>
                    <div class="feature-title">Interoperabilidade SUS</div>
                    <div class="feature-desc">HL7 FHIR, e-SUS/PEC, DATASUS e georreferenciamento</div>
                </div>
                <div class="feature-card">
                    <div class="feature-num">04</div>
                    <div class="feature-title">Experiência do Paciente</div>
                    <div class="feature-desc">Digital Twin, interfaces acessíveis e educação em saúde</div>
                </div>
                <div class="feature-card">
                    <div class="feature-num">05</div>
                    <div class="feature-title">Validação &amp; Escalabilidade</div>
                    <div class="feature-desc">Pilotos em HUs, ESF, Telessaúde e Rede RUTE</div>
                </div>
            </div>
        </div>
    </div>

    <div class="footer">
        <strong>HEAL / REDISUS</strong> — Plataforma Nacional de Saúde Digital Integrada · Cluster REDISUS · RNP / RUTE
    </div>

    <script>
        function updateClock() {
            const el = document.getElementById('last-update');
            if (el) el.textContent = new Date().toLocaleTimeString('pt-BR', {hour:'2-digit', minute:'2-digit'});
        }
        updateClock();

        async function loadDashboard() {
            try {
                const resp = await fetch('/api/dashboard/summary');
                const data = await resp.json();
                animateValue('total-patients', data.total_patients || 0);
                animateValue('total-analyses', data.total_analyses || 0);
                animateValue('high-risk', (data.risk_distribution?.alto || 0) + (data.risk_distribution?.critico || 0));
                animateValue('active-alerts', data.active_alerts || 0);
                updateClock();
            } catch(e) {
                console.log('Dashboard data not available:', e);
            }
        }

        function animateValue(id, end) {
            const el = document.getElementById(id);
            if (!el) return;
            const start = parseInt(el.textContent) || 0;
            if (start === end) { el.textContent = end; return; }
            const duration = 600;
            const startTime = performance.now();
            function step(now) {
                const progress = Math.min((now - startTime) / duration, 1);
                const ease = 1 - Math.pow(1 - progress, 3);
                el.textContent = Math.round(start + (end - start) * ease);
                if (progress < 1) requestAnimationFrame(step);
            }
            requestAnimationFrame(step);
        }

        async function loadPatients() {
            try {
                const resp = await fetch('/api/patients');
                const patients = await resp.json();
                const tbody = document.getElementById('patients-tbody');
                if (patients.length === 0) {
                    tbody.innerHTML = '<tr><td colspan="6" style="text-align:center; padding:2.5rem; color: var(--text-muted);">Nenhum paciente registrado</td></tr>';
                    return;
                }
                tbody.innerHTML = patients.map(p => `
                    <tr>
                        <td style="font-weight:500;">${p.name || 'N/A'}</td>
                        <td>${p.metadata?.etiology || '—'}</td>
                        <td>${p.metadata?.area_cm2?.toFixed(1) || '—'}</td>
                        <td>${p.metadata?.health_score?.toFixed(1) || '—'}</td>
                        <td><span class="badge badge-${p.metadata?.risk_level || 'moderado'}">${p.metadata?.risk_level || 'N/A'}</span></td>
                        <td style="color:var(--text-secondary);">${p.created_at?.split('T')[0] || '—'}</td>
                    </tr>
                `).join('');
            } catch(e) {
                console.log('Patient data not available:', e);
            }
        }

        let activeQueueView = 'all';

        function formatDate(value) {
            if (!value) return '—';
            if (typeof value === 'object' && value.scheduled_for) return String(value.scheduled_for).split('T')[0];
            if (typeof value === 'object' && value.evaluation_date) return String(value.evaluation_date).split('T')[0];
            return String(value).split('T')[0];
        }

        function escapeHtml(value) {
            return String(value || '')
                .replaceAll('&', '&amp;')
                .replaceAll('<', '&lt;')
                .replaceAll('>', '&gt;')
                .replaceAll('"', '&quot;')
                .replaceAll("'", '&#39;');
        }

        function renderQueueItems(items) {
            const container = document.getElementById('clinical-queue-list');
            if (!container) return;
            if (!items.length) {
                container.innerHTML = '<div class="queue-empty">Nenhum paciente nesta visao agora.</div>';
                return;
            }
            container.innerHTML = items.map(item => {
                const reasons = (item.attention_reasons || []).slice(0, 4).map(reason => (
                    `<span class="reason-chip">${escapeHtml(reason)}</span>`
                )).join('');
                const risk = item.risk_level || 'moderado';
                return `
                    <div class="queue-item risk-${risk}">
                        <div class="queue-top">
                            <div>
                                <div class="queue-title">${escapeHtml(item.patient_name || 'Paciente sem nome')}</div>
                                <div class="queue-meta">
                                    <span>${escapeHtml(item.lesion_title || 'Lesao sem titulo')}</span>
                                    <span>Status: ${escapeHtml(item.status || 'em_acompanhamento')}</span>
                                    <span>Risco: ${escapeHtml(risk)}</span>
                                    <span>Alertas: ${item.open_alert_count || 0}</span>
                                    <span>Follow-up: ${formatDate(item.next_follow_up)}</span>
                                </div>
                            </div>
                            <div class="queue-score">Prioridade ${item.priority_score || 0}</div>
                        </div>
                        <div class="queue-reasons">${reasons || '<span class="reason-chip">Acompanhamento regular</span>'}</div>
                    </div>
                `;
            }).join('');
        }

        function hydratePatientHeaders() {
            const headers = document.querySelectorAll('#patients-table thead th');
            if (headers.length < 6) return;
            headers[1].textContent = 'Status';
            headers[2].textContent = 'Alertas';
            headers[3].textContent = 'Proximo follow-up';
            headers[4].textContent = 'Risco';
            headers[5].textContent = 'Ultima avaliacao';
        }

        function bindQueueFilters() {
            const filters = document.querySelectorAll('.queue-filter');
            filters.forEach(button => {
                button.addEventListener('click', () => {
                    activeQueueView = button.dataset.view || 'all';
                    filters.forEach(item => item.classList.toggle('active', item === button));
                    loadClinicalQueue();
                });
            });
        }

        async function loadDashboard() {
            try {
                const resp = await fetch('/api/dashboard/summary');
                const data = await resp.json();
                animateValue('total-patients', data.total_patients || 0);
                animateValue('total-analyses', data.total_analyses || 0);
                animateValue('high-risk', (data.risk_distribution?.alto || 0) + (data.risk_distribution?.critico || 0));
                animateValue('active-alerts', data.active_alerts || 0);
                const queueSummary = document.getElementById('queue-summary');
                if (queueSummary) {
                    queueSummary.textContent = `${data.patients_needing_attention || 0} precisam de atencao · ${data.patients_overdue || 0} atrasados · ${data.patients_worsening || 0} pioraram`;
                }
                updateClock();
            } catch(e) {
                console.log('Dashboard data not available:', e);
            }
        }

        async function loadClinicalQueue() {
            try {
                const resp = await fetch(`/api/dashboard/clinical-queue?limit=6&view=${encodeURIComponent(activeQueueView)}`);
                const payload = await resp.json();
                renderQueueItems(payload.items || []);
            } catch(e) {
                const container = document.getElementById('clinical-queue-list');
                if (container) {
                    container.innerHTML = '<div class="queue-empty">Nao foi possivel carregar a fila clinica.</div>';
                }
                console.log('Clinical queue not available:', e);
            }
        }

        async function loadPatients() {
            try {
                const resp = await fetch('/api/patients');
                const patients = await resp.json();
                const tbody = document.getElementById('patients-tbody');
                if (patients.length === 0) {
                    tbody.innerHTML = '<tr><td colspan="6" style="text-align:center; padding:2.5rem; color: var(--text-muted);">Nenhum paciente registrado</td></tr>';
                    return;
                }
                tbody.innerHTML = patients.map(p => `
                    <tr>
                        <td style="font-weight:500;">${escapeHtml(p.name || 'N/A')}</td>
                        <td>${escapeHtml(p.metadata?.status || 'em_acompanhamento')}</td>
                        <td><span class="badge badge-${p.metadata?.risk_level || 'moderado'}">${escapeHtml(p.metadata?.risk_level || 'N/A')}</span></td>
                        <td>${p.metadata?.open_alerts ?? 0}</td>
                        <td>${formatDate(p.metadata?.next_follow_up)}</td>
                        <td style="color:var(--text-secondary);">${formatDate(p.metadata?.latest_evaluation_date || p.created_at)}</td>
                    </tr>
                `).join('');
            } catch(e) {
                console.log('Patient data not available:', e);
            }
        }

        let activeCaseId = null;
        const queueContext = { roleView: 'admin', unit: '', team: '' };

        function buildContextQuery(extra = {}) {
            const params = new URLSearchParams();
            params.set('roleView', queueContext.roleView || 'admin');
            if (queueContext.unit) params.set('unit', queueContext.unit);
            if (queueContext.team) params.set('team', queueContext.team);
            Object.entries(extra).forEach(([key, value]) => {
                if (value !== undefined && value !== null && value !== '') params.set(key, String(value));
            });
            return params.toString();
        }

        function renderCaseDetail(detail) {
            const panel = document.getElementById('case-panel');
            if (!panel) return;
            if (!detail || detail.error) {
                panel.innerHTML = '<div class="queue-empty">Nao foi possivel carregar o caso clinico.</div>';
                return;
            }

            const summary = detail.clinical_summary || {};
            const alerts = detail.alerts || [];
            const unresolvedAlerts = alerts.filter(alert => !['resolved', 'resolvido'].includes(String(alert.status || '').toLowerCase()));
            const followUps = detail.follow_ups || [];
            const pendingFollowUp = followUps.find(item => !['completed', 'cancelled', 'missed', 'concluido', 'cancelado'].includes(String(item.status || '').toLowerCase()));
            const carePlan = detail.active_care_plan || {};
            const events = (detail.timeline?.events || []).slice(-8).reverse();
            const deltas = detail.before_vs_after?.deltas || {};
            const ownership = detail.ownership || {};
            const caseOwner = ownership.case || {};
            const alertOwner = ownership.primary_alert || {};
            const latestImageUrl = detail.before_vs_after?.latest_image_url || '';
            const previousImageUrl = detail.before_vs_after?.previous_image_url || '';

            panel.innerHTML = `
                <div class="queue-top">
                    <div>
                        <div class="queue-title">${escapeHtml(detail.patient?.name || 'Paciente sem nome')} · ${escapeHtml(detail.lesion?.title || detail.lesion?.location || 'Lesao')}</div>
                        <div class="queue-meta">
                            <span>Risco: ${escapeHtml(summary.risk_level || 'moderado')}</span>
                            <span>Status: ${escapeHtml(summary.status || 'em_acompanhamento')}</span>
                            <span>SLA: ${escapeHtml(summary.sla_status || 'sem_referencia')}</span>
                            <span>Plano: ${escapeHtml(carePlan.title || 'sem plano ativo')}</span>
                            <span>Unidade: ${escapeHtml(detail.patient?.unit_id || detail.patient?.metadata?.unit_id || '—')}</span>
                            <span>Equipe: ${escapeHtml(detail.patient?.team_id || detail.patient?.metadata?.team_id || '—')}</span>
                        </div>
                    </div>
                    <div class="queue-score">${escapeHtml(summary.priority_bucket || 'rotina')}</div>
                </div>
                <div class="queue-reasons">${(summary.attention_reasons || []).map(reason => `<span class="reason-chip">${escapeHtml(reason)}</span>`).join('') || '<span class="reason-chip">Acompanhamento regular</span>'}</div>
                <div class="case-inline-form" style="margin-top:0.85rem;">
                    <textarea id="case-action-note" placeholder="Nota clinica obrigatoria para claim, handoff, alerta, follow-up e plano."></textarea>
                </div>
                <div class="case-actions">
                    ${!caseOwner.uid ? `<button class="case-action-btn" data-action="claim-case" data-id="${escapeHtml(detail.lesion?.id || '')}">Assumir caso</button>` : ''}
                    <button class="case-action-btn" data-action="handoff-case" data-id="${escapeHtml(detail.lesion?.id || '')}">Passar caso</button>
                    ${unresolvedAlerts[0] && !alertOwner.uid ? `<button class="case-action-btn" data-action="claim-alert" data-id="${escapeHtml(unresolvedAlerts[0].id)}">Assumir alerta</button>` : ''}
                    ${unresolvedAlerts[0] ? `<button class="case-action-btn" data-action="handoff-alert" data-id="${escapeHtml(unresolvedAlerts[0].id)}">Passar alerta</button>` : ''}
                    ${unresolvedAlerts[0] ? `<button class="case-action-btn" data-action="ack-alert" data-id="${escapeHtml(unresolvedAlerts[0].id)}">Reconhecer alerta</button>` : ''}
                    ${unresolvedAlerts[0] ? `<button class="case-action-btn" data-action="resolve-alert" data-id="${escapeHtml(unresolvedAlerts[0].id)}">Resolver alerta</button>` : ''}
                    ${pendingFollowUp ? `<button class="case-action-btn" data-action="complete-follow-up" data-id="${escapeHtml(pendingFollowUp.id)}">Concluir follow-up</button>` : ''}
                </div>
                <div class="case-grid">
                    <div class="case-block">
                        <h4>Comparação clínica</h4>
                        <div class="case-stat"><span>Área</span><strong>${escapeHtml(deltas.area_delta_cm2 ?? '—')}</strong></div>
                        <div class="case-stat"><span>% área</span><strong>${escapeHtml(deltas.area_change_pct ?? '—')}</strong></div>
                        <div class="case-stat"><span>PUSH</span><strong>${escapeHtml(deltas.push_delta ?? '—')}</strong></div>
                        <div class="case-stat"><span>Dor</span><strong>${escapeHtml(deltas.pain_delta ?? '—')}</strong></div>
                        <div class="case-compare">
                            <div class="case-compare-card">
                                <div class="case-owner"><strong>Anterior</strong><span>${escapeHtml(formatDate(detail.before_vs_after?.previous))}</span></div>
                                ${previousImageUrl ? `<img src="${escapeHtml(previousImageUrl)}" alt="Imagem anterior">` : '<div class="queue-empty">Sem imagem anterior.</div>'}
                            </div>
                            <div class="case-compare-card">
                                <div class="case-owner"><strong>Atual</strong><span>${escapeHtml(formatDate(detail.before_vs_after?.latest))}</span></div>
                                ${latestImageUrl ? `<img src="${escapeHtml(latestImageUrl)}" alt="Imagem atual">` : '<div class="queue-empty">Sem imagem atual.</div>'}
                            </div>
                        </div>
                    </div>
                    <div class="case-block">
                        <h4>Plano de cuidado</h4>
                        <div class="case-stat"><span>Título</span><strong>${escapeHtml(carePlan.title || 'Sem plano ativo')}</strong></div>
                        <div class="case-stat"><span>Revisão</span><strong>${escapeHtml(summary.review_due_date || carePlan.review_due_date || '—')}</strong></div>
                        <div class="case-inline-form">
                            <input id="care-plan-review-date" type="date" value="${escapeHtml(summary.review_due_date || carePlan.review_due_date || '')}">
                            <select id="care-plan-risk-level">
                                <option value="baixo" ${summary.risk_level === 'baixo' ? 'selected' : ''}>baixo</option>
                                <option value="moderado" ${summary.risk_level === 'moderado' ? 'selected' : ''}>moderado</option>
                                <option value="alto" ${summary.risk_level === 'alto' ? 'selected' : ''}>alto</option>
                                <option value="critico" ${summary.risk_level === 'critico' ? 'selected' : ''}>critico</option>
                            </select>
                            <button class="case-action-btn" data-action="update-care-plan" data-id="${escapeHtml(carePlan.id || '')}">Atualizar plano</button>
                        </div>
                    </div>
                    <div class="case-block">
                        <h4>Alertas e follow-ups</h4>
                        <div class="case-stat"><span>Alertas abertos</span><strong>${unresolvedAlerts.length}</strong></div>
                        <div class="case-stat"><span>Próximo follow-up</span><strong>${escapeHtml(formatDate(pendingFollowUp || summary.next_follow_up))}</strong></div>
                        <div class="case-stat"><span>Requer médico</span><strong>${summary.requires_doctor_review ? 'sim' : 'não'}</strong></div>
                        <div class="case-owner">
                            <span><strong>Caso:</strong> ${escapeHtml(caseOwner.name || 'Sem responsável')}</span>
                            <span><strong>Role do caso:</strong> ${escapeHtml(caseOwner.role || '—')}</span>
                            <span><strong>Claim:</strong> ${escapeHtml(formatDate(caseOwner.claimed_at))}</span>
                            <span><strong>Alerta principal:</strong> ${escapeHtml(alertOwner.name || 'Sem responsável')}</span>
                        </div>
                        <div class="case-inline-form">
                            <input id="handoff-uid" type="text" placeholder="uid destino">
                            <input id="handoff-name" type="text" placeholder="nome destino">
                            <select id="handoff-role">
                                <option value="nurse">nurse</option>
                                <option value="doctor">doctor</option>
                                <option value="admin">admin</option>
                            </select>
                            <input id="handoff-unit" type="text" placeholder="unidade destino">
                            <input id="handoff-team" type="text" placeholder="equipe destino">
                        </div>
                    </div>
                    <div class="case-block">
                        <h4>Timeline</h4>
                        <div class="case-timeline">
                            ${events.map(event => `
                                <div class="case-event">
                                    <strong>${escapeHtml(event.title || event.type || 'Evento')}</strong>
                                    <span>${escapeHtml(formatDate(event.timestamp))} · ${escapeHtml(event.status || 'registrado')}</span>
                                </div>
                            `).join('') || '<div class="queue-empty">Sem eventos ainda.</div>'}
                        </div>
                    </div>
                </div>
            `;

            panel.querySelectorAll('[data-action]').forEach(button => {
                button.addEventListener('click', async () => {
                    const action = button.dataset.action;
                    const id = button.dataset.id;
                    const note = document.getElementById('case-action-note')?.value?.trim() || '';
                    const target = {
                        assigned_to_uid: document.getElementById('handoff-uid')?.value?.trim() || '',
                        assigned_to_name: document.getElementById('handoff-name')?.value?.trim() || '',
                        assigned_to_role: document.getElementById('handoff-role')?.value || 'nurse',
                        unit_id: document.getElementById('handoff-unit')?.value?.trim() || '',
                        team_id: document.getElementById('handoff-team')?.value?.trim() || '',
                    };
                    if (!note) {
                        window.alert('Informe uma nota clínica antes de executar a ação.');
                        return;
                    }
                    if (!id && action !== 'update-care-plan') return;
                    if (action === 'claim-case') {
                        await fetch(`/api/v1/lesions/${encodeURIComponent(id)}/claim`, {
                            method: 'PATCH',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ notes: note })
                        });
                    } else if (action === 'handoff-case') {
                        if (!target.assigned_to_uid || !target.assigned_to_name) {
                            window.alert('Preencha uid e nome do destino para o handoff.');
                            return;
                        }
                        await fetch(`/api/v1/lesions/${encodeURIComponent(id)}/handoff`, {
                            method: 'PATCH',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ ...target, notes: note })
                        });
                    } else if (action === 'claim-alert') {
                        await fetch(`/api/v1/alerts/${encodeURIComponent(id)}/claim`, {
                            method: 'PATCH',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ notes: note })
                        });
                    } else if (action === 'handoff-alert') {
                        if (!target.assigned_to_uid || !target.assigned_to_name) {
                            window.alert('Preencha uid e nome do destino para o handoff.');
                            return;
                        }
                        await fetch(`/api/v1/alerts/${encodeURIComponent(id)}/handoff`, {
                            method: 'PATCH',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({
                                assigned_to_uid: target.assigned_to_uid,
                                assigned_to_name: target.assigned_to_name,
                                assigned_to_role: target.assigned_to_role,
                                notes: note
                            })
                        });
                    } else if (action === 'ack-alert') {
                        await fetch(`/api/v1/alerts/${encodeURIComponent(id)}/acknowledge`, {
                            method: 'PATCH',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ notes: note })
                        });
                    } else if (action === 'resolve-alert') {
                        await fetch(`/api/v1/alerts/${encodeURIComponent(id)}/resolve`, {
                            method: 'PATCH',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ notes: note })
                        });
                    } else if (action === 'complete-follow-up') {
                        await fetch(`/api/v1/follow-ups/${encodeURIComponent(id)}/complete`, {
                            method: 'PATCH',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ status: 'completed', notes: note })
                        });
                    } else if (action === 'update-care-plan') {
                        const reviewDate = document.getElementById('care-plan-review-date')?.value;
                        const riskLevel = document.getElementById('care-plan-risk-level')?.value;
                        await fetch(`/api/v1/care-plans/${encodeURIComponent(id)}`, {
                            method: 'PATCH',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({
                                review_due_date: reviewDate || undefined,
                                risk_level: riskLevel || undefined,
                                notes: note
                            })
                        });
                    }
                    if (activeCaseId) await openCase(activeCaseId);
                    await loadDashboard();
                    await loadClinicalQueue();
                    await loadPatients();
                });
            });
        }

        async function openCase(caseId) {
            activeCaseId = caseId;
            const panel = document.getElementById('case-panel');
            if (panel) panel.innerHTML = '<div class="queue-empty">Carregando caso clínico...</div>';
            try {
                const resp = await fetch(`/api/dashboard/cases/${encodeURIComponent(caseId)}?${buildContextQuery()}`);
                const detail = await resp.json();
                renderCaseDetail(detail);
            } catch (e) {
                renderCaseDetail({ error: true });
                console.log('Case detail not available:', e);
            }
        }

        function renderQueueItems(items) {
            const container = document.getElementById('clinical-queue-list');
            if (!container) return;
            if (!items.length) {
                container.innerHTML = '<div class="queue-empty">Nenhum paciente nesta visao agora.</div>';
                return;
            }
            container.innerHTML = items.map(item => {
                const reasons = (item.attention_reasons || []).slice(0, 4).map(reason => (
                    `<span class="reason-chip">${escapeHtml(reason)}</span>`
                )).join('');
                const risk = item.risk_level || 'moderado';
                return `
                    <div class="queue-item risk-${risk}">
                        <div class="queue-top">
                            <div>
                                <div class="queue-title">${escapeHtml(item.patient_name || 'Paciente sem nome')}</div>
                                <div class="queue-meta">
                                    <span>${escapeHtml(item.lesion_title || 'Lesao sem titulo')}</span>
                                    <span>Status: ${escapeHtml(item.status || 'em_acompanhamento')}</span>
                                    <span>Bucket: ${escapeHtml(item.priority_bucket || 'rotina')}</span>
                                    <span>Risco: ${escapeHtml(risk)}</span>
                                    <span>Alertas: ${item.open_alert_count || 0}</span>
                                    <span>Unidade: ${escapeHtml(item.unit || '—')}</span>
                                    <span>Follow-up: ${formatDate(item.next_follow_up)}</span>
                                </div>
                            </div>
                            <div class="queue-score">Prioridade ${item.priority_score || 0}</div>
                        </div>
                        <div class="queue-reasons">${reasons || '<span class="reason-chip">Acompanhamento regular</span>'}</div>
                        <div class="queue-actions">
                            <button class="queue-action-btn" data-case-id="${escapeHtml(item.lesion_id || '')}">Abrir caso</button>
                        </div>
                    </div>
                `;
            }).join('');
            container.querySelectorAll('[data-case-id]').forEach(button => {
                button.addEventListener('click', () => openCase(button.dataset.caseId));
            });
        }

        function bindQueueContext() {
            const applyButton = document.getElementById('queue-context-apply');
            if (!applyButton) return;
            applyButton.addEventListener('click', async () => {
                queueContext.roleView = document.getElementById('queue-role-view')?.value || 'admin';
                queueContext.unit = document.getElementById('queue-unit-filter')?.value?.trim() || '';
                queueContext.team = document.getElementById('queue-team-filter')?.value?.trim() || '';
                await loadDashboard();
                await loadClinicalQueue();
                await loadPatients();
                if (activeCaseId) await openCase(activeCaseId);
            });
        }

        function bindQueueFilters() {
            const filters = document.querySelectorAll('.queue-filter');
            filters.forEach(button => {
                button.addEventListener('click', async () => {
                    activeQueueView = button.dataset.view || 'all';
                    filters.forEach(item => item.classList.toggle('active', item === button));
                    await loadClinicalQueue();
                });
            });
        }

        async function loadDashboard() {
            try {
                const resp = await fetch(`/api/dashboard/summary?${buildContextQuery()}`);
                const data = await resp.json();
                animateValue('total-patients', data.total_patients || 0);
                animateValue('total-analyses', data.total_analyses || 0);
                animateValue('high-risk', (data.risk_distribution?.alto || 0) + (data.risk_distribution?.critico || 0));
                animateValue('active-alerts', data.active_alerts || 0);
                const queueSummary = document.getElementById('queue-summary');
                if (queueSummary) {
                    queueSummary.textContent = `${data.patients_needing_attention || 0} precisam de atencao · ${data.patients_overdue || 0} atrasados · ${data.patients_sla_breached || 0} com SLA vencido`;
                }
                updateClock();
            } catch(e) {
                console.log('Dashboard data not available:', e);
            }
        }

        async function loadClinicalQueue() {
            try {
                const resp = await fetch(`/api/dashboard/clinical-queue?${buildContextQuery({ limit: 6, view: activeQueueView })}`);
                const payload = await resp.json();
                renderQueueItems(payload.items || []);
            } catch(e) {
                const container = document.getElementById('clinical-queue-list');
                if (container) {
                    container.innerHTML = '<div class="queue-empty">Nao foi possivel carregar a fila clinica.</div>';
                }
                console.log('Clinical queue not available:', e);
            }
        }

        async function loadPatients() {
            try {
                const resp = await fetch('/api/patients');
                const patients = await resp.json();
                const tbody = document.getElementById('patients-tbody');
                if (patients.length === 0) {
                    tbody.innerHTML = '<tr><td colspan="6" style="text-align:center; padding:2.5rem; color: var(--text-muted);">Nenhum paciente registrado</td></tr>';
                    return;
                }
                tbody.innerHTML = patients.map(p => `
                    <tr>
                        <td style="font-weight:500;">${escapeHtml(p.name || 'N/A')}</td>
                        <td>${escapeHtml(p.metadata?.status || 'em_acompanhamento')}</td>
                        <td><span class="badge badge-${p.metadata?.risk_level || 'moderado'}">${escapeHtml(p.metadata?.risk_level || 'N/A')}</span></td>
                        <td>${p.metadata?.open_alerts ?? 0}</td>
                        <td>${formatDate(p.metadata?.next_follow_up)}</td>
                        <td style="color:var(--text-secondary);">${formatDate(p.metadata?.latest_evaluation_date || p.created_at)}</td>
                    </tr>
                `).join('');
            } catch(e) {
                console.log('Patient data not available:', e);
            }
        }

        hydratePatientHeaders();
        bindQueueContext();
        bindQueueFilters();
        loadDashboard();
        loadClinicalQueue();
        loadPatients();
        setInterval(() => {
            loadDashboard();
            loadClinicalQueue();
        }, 30000);
    </script>
</body>
</html>
"""

PATIENTS_HTML = """
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>HEAL — Pacientes</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
    <style>
        :root { --primary:#6366f1; --bg:#0b0e14; --card-bg:rgba(17,24,39,0.7); --card-border:rgba(255,255,255,0.06); --text:#f1f5f9; --text-sec:#94a3b8; --text-muted:#64748b; --radius:16px; }
        * { margin:0; padding:0; box-sizing:border-box; }
        body { font-family:'Inter','Segoe UI',system-ui,sans-serif; background:var(--bg); color:var(--text); min-height:100vh; }
        body::before { content:''; position:fixed; inset:0; background:radial-gradient(ellipse 600px 400px at 10% 20%,rgba(99,102,241,0.08),transparent),radial-gradient(ellipse 500px 350px at 85% 60%,rgba(6,182,212,0.06),transparent); pointer-events:none; z-index:0; }
        .header { position:sticky; top:0; z-index:100; background:rgba(11,14,20,0.85); backdrop-filter:blur(20px) saturate(1.4); padding:0 2rem; display:flex; justify-content:space-between; align-items:center; height:64px; border-bottom:1px solid var(--card-border); }
        .header-brand { display:flex; align-items:center; gap:12px; }
        .header-logo { width:36px; height:36px; background:linear-gradient(135deg,var(--primary),#06b6d4); border-radius:10px; display:flex; align-items:center; justify-content:center; font-weight:800; font-size:14px; color:#fff; box-shadow:0 2px 12px rgba(99,102,241,0.3); }
        .header h1 { font-size:1.15rem; font-weight:700; color:#fff; letter-spacing:-0.02em; }
        .header h1 span { color:#818cf8; }
        .nav { display:flex; gap:4px; }
        .nav a { color:var(--text-sec); text-decoration:none; padding:8px 16px; border-radius:8px; font-size:0.85rem; font-weight:500; transition:all 0.2s ease; }
        .nav a:hover { color:var(--text); background:rgba(255,255,255,0.06); }
        .nav a.active { color:#fff; background:var(--primary); box-shadow:0 2px 12px rgba(99,102,241,0.35); }
        .container { max-width:1440px; margin:0 auto; padding:2rem; position:relative; z-index:1; }
        .page-title { font-size:1.6rem; font-weight:700; margin-bottom:0.5rem; letter-spacing:-0.02em; }
        .page-desc { color:var(--text-muted); font-size:0.9rem; margin-bottom:2rem; }
        .card { background:var(--card-bg); backdrop-filter:blur(12px); border:1px solid var(--card-border); border-radius:var(--radius); padding:1.5rem; }
        .card h3 { font-size:0.95rem; font-weight:600; margin-bottom:0.75rem; }
        .card p { color:var(--text-sec); font-size:0.88rem; line-height:1.6; margin-bottom:0.5rem; }
        code { background:rgba(99,102,241,0.15); color:#818cf8; padding:2px 8px; border-radius:6px; font-size:0.82rem; font-family:'Fira Code',monospace; }
        .table-card { background:var(--card-bg); backdrop-filter:blur(12px); border:1px solid var(--card-border); border-radius:var(--radius); overflow:hidden; margin-top:1.5rem; }
        table { width:100%; border-collapse:collapse; }
        thead { background:rgba(99,102,241,0.08); }
        th { padding:12px 16px; text-align:left; font-size:0.72rem; font-weight:600; text-transform:uppercase; letter-spacing:0.06em; color:var(--text-sec); border-bottom:1px solid var(--card-border); }
        td { padding:12px 16px; font-size:0.88rem; border-bottom:1px solid rgba(255,255,255,0.03); }
        tr:hover td { background:rgba(255,255,255,0.03); }
        @keyframes fadeInUp { from{opacity:0;transform:translateY(16px);} to{opacity:1;transform:translateY(0);} }
        .card,.table-card { animation:fadeInUp 0.5s ease both; }
    </style>
</head>
<body>
    <div class="header">
        <div class="header-brand">
            <div class="header-logo">H+</div>
            <div><h1>HEAL <span>/</span> REDISUS</h1></div>
        </div>
        <nav class="nav">
            <a href="/">📊 Dashboard</a>
            <a href="/patients" class="active">🩺 Pacientes</a>
            <a href="/surveillance">🗺️ Vigilância</a>
            <a href="/alerts">🔔 Alertas</a>
        </nav>
    </div>
    <div class="container">
        <h2 class="page-title">🩺 Gestão de Pacientes</h2>
        <p class="page-desc">Acompanhamento individual e histórico de avaliações de feridas.</p>
        <div class="card">
            <h3>Integração com Banco de Dados</h3>
            <p>O sistema de pacientes está integrado com o banco SQLite local para armazenamento persistente.</p>
            <p>Consulte dados via API: <code>/api/patients</code></p>
            <p>Detalhe individual: <code>/api/patients/&lt;id&gt;</code></p>
        </div>
        <div class="table-card">
            <table>
                <thead><tr><th>Paciente</th><th>Etiologia</th><th>Risco</th><th>Última Avaliação</th></tr></thead>
                <tbody id="p-tbody"><tr><td colspan="4" style="text-align:center;padding:2rem;color:var(--text-muted);">Carregando...</td></tr></tbody>
            </table>
        </div>
    </div>
    <script>
        fetch('/api/patients').then(r=>r.json()).then(ps=>{
            const t=document.getElementById('p-tbody');
            if(!ps.length){t.innerHTML='<tr><td colspan="4" style="text-align:center;padding:2rem;color:var(--text-muted);">Nenhum paciente registrado</td></tr>';return;}
            t.innerHTML=ps.map(p=>`<tr><td style="font-weight:500">${p.name||'N/A'}</td><td>${p.metadata?.etiology||'—'}</td><td>${p.metadata?.risk_level||'—'}</td><td style="color:var(--text-sec)">${p.created_at?.split('T')[0]||'—'}</td></tr>`).join('');
        }).catch(()=>{});
    </script>
</body>
</html>
"""

SURVEILLANCE_HTML = """
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>HEAL — Vigilância Epidemiológica</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
    <style>
        :root { --primary:#6366f1; --bg:#0b0e14; --card-bg:rgba(17,24,39,0.7); --card-border:rgba(255,255,255,0.06); --text:#f1f5f9; --text-sec:#94a3b8; --text-muted:#64748b; --success:#10b981; --radius:16px; }
        * { margin:0; padding:0; box-sizing:border-box; }
        body { font-family:'Inter','Segoe UI',system-ui,sans-serif; background:var(--bg); color:var(--text); min-height:100vh; }
        body::before { content:''; position:fixed; inset:0; background:radial-gradient(ellipse 600px 400px at 10% 20%,rgba(99,102,241,0.08),transparent),radial-gradient(ellipse 500px 350px at 85% 60%,rgba(6,182,212,0.06),transparent); pointer-events:none; z-index:0; }
        .header { position:sticky; top:0; z-index:100; background:rgba(11,14,20,0.85); backdrop-filter:blur(20px) saturate(1.4); padding:0 2rem; display:flex; justify-content:space-between; align-items:center; height:64px; border-bottom:1px solid var(--card-border); }
        .header-brand { display:flex; align-items:center; gap:12px; }
        .header-logo { width:36px; height:36px; background:linear-gradient(135deg,var(--primary),#06b6d4); border-radius:10px; display:flex; align-items:center; justify-content:center; font-weight:800; font-size:14px; color:#fff; box-shadow:0 2px 12px rgba(99,102,241,0.3); }
        .header h1 { font-size:1.15rem; font-weight:700; color:#fff; letter-spacing:-0.02em; }
        .header h1 span { color:#818cf8; }
        .nav { display:flex; gap:4px; }
        .nav a { color:var(--text-sec); text-decoration:none; padding:8px 16px; border-radius:8px; font-size:0.85rem; font-weight:500; transition:all 0.2s ease; }
        .nav a:hover { color:var(--text); background:rgba(255,255,255,0.06); }
        .nav a.active { color:#fff; background:var(--primary); box-shadow:0 2px 12px rgba(99,102,241,0.35); }
        .container { max-width:1440px; margin:0 auto; padding:2rem; position:relative; z-index:1; }
        .page-title { font-size:1.6rem; font-weight:700; margin-bottom:0.5rem; letter-spacing:-0.02em; }
        .page-desc { color:var(--text-muted); font-size:0.9rem; margin-bottom:2rem; }
        .cards-grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(300px,1fr)); gap:1rem; }
        .card { background:var(--card-bg); backdrop-filter:blur(12px); border:1px solid var(--card-border); border-radius:var(--radius); padding:1.5rem; transition:all 0.25s ease; }
        .card:hover { transform:translateY(-2px); border-color:rgba(99,102,241,0.2); box-shadow:0 8px 30px rgba(99,102,241,0.1); }
        .card h3 { font-size:0.95rem; font-weight:600; margin-bottom:0.75rem; display:flex; align-items:center; gap:8px; }
        .card p { color:var(--text-sec); font-size:0.85rem; line-height:1.6; margin-bottom:0.5rem; }
        code { background:rgba(99,102,241,0.15); color:#818cf8; padding:2px 8px; border-radius:6px; font-size:0.82rem; font-family:'Fira Code',monospace; }
        .endpoint { display:flex; align-items:center; gap:8px; padding:8px 12px; background:rgba(255,255,255,0.03); border-radius:8px; margin-bottom:6px; }
        .method { background:rgba(16,185,129,0.15); color:var(--success); padding:2px 8px; border-radius:4px; font-size:0.7rem; font-weight:700; font-family:monospace; }
        .endpoint-path { color:var(--text-sec); font-size:0.83rem; }
        @keyframes fadeInUp { from{opacity:0;transform:translateY(16px);} to{opacity:1;transform:translateY(0);} }
        .card { animation:fadeInUp 0.5s ease both; }
        .card:nth-child(1){animation-delay:0.05s;} .card:nth-child(2){animation-delay:0.1s;} .card:nth-child(3){animation-delay:0.15s;}
    </style>
</head>
<body>
    <div class="header">
        <div class="header-brand">
            <div class="header-logo">H+</div>
            <div><h1>HEAL <span>/</span> REDISUS</h1></div>
        </div>
        <nav class="nav">
            <a href="/">📊 Dashboard</a>
            <a href="/patients">🩺 Pacientes</a>
            <a href="/surveillance" class="active">🗺️ Vigilância</a>
            <a href="/alerts">🔔 Alertas</a>
        </nav>
    </div>
    <div class="container">
        <h2 class="page-title">🗺️ Vigilância Epidemiológica Digital</h2>
        <p class="page-desc">Mapa de calor, detecção de clusters e indicadores epidemiológicos em tempo real.</p>
        <div class="cards-grid">
            <div class="card">
                <h3>🌡️ Mapa de Calor</h3>
                <p>Visualização georreferenciada da incidência de feridas por região.</p>
                <div class="endpoint"><span class="method">GET</span><code class="endpoint-path">/api/surveillance/heatmap</code></div>
            </div>
            <div class="card">
                <h3>📍 Clusters Detectados</h3>
                <p>Identificação automática de agrupamentos geográficos de casos.</p>
                <div class="endpoint"><span class="method">GET</span><code class="endpoint-path">/api/surveillance/clusters</code></div>
            </div>
            <div class="card">
                <h3>🚨 Alertas de Surto</h3>
                <p>Notificações quando padrões incomuns são detectados na população.</p>
                <div class="endpoint"><span class="method">GET</span><code class="endpoint-path">/api/alerts</code></div>
            </div>
        </div>
    </div>
</body>
</html>
"""

ALERTS_HTML = """
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>HEAL — Alertas</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
    <style>
        :root { --primary:#6366f1; --bg:#0b0e14; --card-bg:rgba(17,24,39,0.7); --card-border:rgba(255,255,255,0.06); --text:#f1f5f9; --text-sec:#94a3b8; --text-muted:#64748b; --danger:#ef4444; --danger-light:#f87171; --warning:#f59e0b; --success:#10b981; --radius:16px; }
        * { margin:0; padding:0; box-sizing:border-box; }
        body { font-family:'Inter','Segoe UI',system-ui,sans-serif; background:var(--bg); color:var(--text); min-height:100vh; }
        body::before { content:''; position:fixed; inset:0; background:radial-gradient(ellipse 600px 400px at 10% 20%,rgba(239,68,68,0.06),transparent),radial-gradient(ellipse 500px 350px at 85% 60%,rgba(245,158,11,0.05),transparent); pointer-events:none; z-index:0; }
        .header { position:sticky; top:0; z-index:100; background:rgba(11,14,20,0.85); backdrop-filter:blur(20px) saturate(1.4); padding:0 2rem; display:flex; justify-content:space-between; align-items:center; height:64px; border-bottom:1px solid var(--card-border); }
        .header-brand { display:flex; align-items:center; gap:12px; }
        .header-logo { width:36px; height:36px; background:linear-gradient(135deg,var(--primary),#06b6d4); border-radius:10px; display:flex; align-items:center; justify-content:center; font-weight:800; font-size:14px; color:#fff; box-shadow:0 2px 12px rgba(99,102,241,0.3); }
        .header h1 { font-size:1.15rem; font-weight:700; color:#fff; letter-spacing:-0.02em; }
        .header h1 span { color:#818cf8; }
        .nav { display:flex; gap:4px; }
        .nav a { color:var(--text-sec); text-decoration:none; padding:8px 16px; border-radius:8px; font-size:0.85rem; font-weight:500; transition:all 0.2s ease; }
        .nav a:hover { color:var(--text); background:rgba(255,255,255,0.06); }
        .nav a.active { color:#fff; background:var(--primary); box-shadow:0 2px 12px rgba(99,102,241,0.35); }
        .container { max-width:1440px; margin:0 auto; padding:2rem; position:relative; z-index:1; }
        .page-title { font-size:1.6rem; font-weight:700; margin-bottom:0.5rem; letter-spacing:-0.02em; }
        .page-desc { color:var(--text-muted); font-size:0.9rem; margin-bottom:2rem; }
        .empty-state { text-align:center; padding:3rem; color:var(--success); font-size:0.95rem; }
        .empty-state .empty-icon { font-size:2.5rem; margin-bottom:0.75rem; opacity:0.7; }
        .alert-card { background:var(--card-bg); backdrop-filter:blur(12px); border-radius:var(--radius); padding:1.25rem 1.5rem; margin-bottom:0.75rem; display:flex; gap:1rem; align-items:flex-start; transition:all 0.25s ease; animation:fadeInUp 0.4s ease both; border-left:4px solid transparent; border-right:1px solid var(--card-border); border-top:1px solid var(--card-border); border-bottom:1px solid var(--card-border); }
        .alert-card:hover { transform:translateX(4px); }
        .alert-card.sev-critico,.alert-card.sev-alto { border-left-color:var(--danger); }
        .alert-card.sev-moderado { border-left-color:var(--warning); }
        .alert-card.sev-baixo { border-left-color:var(--success); }
        .alert-icon { font-size:1.5rem; flex-shrink:0; padding-top:2px; }
        .alert-body { flex:1; }
        .alert-sev { display:inline-flex; align-items:center; gap:5px; padding:3px 10px; border-radius:20px; font-size:0.68rem; font-weight:700; text-transform:uppercase; letter-spacing:0.05em; margin-bottom:6px; }
        .alert-sev::before { content:''; width:6px; height:6px; border-radius:50%; }
        .sev-critico .alert-sev,.sev-alto .alert-sev { background:rgba(239,68,68,0.12); color:var(--danger-light); }
        .sev-critico .alert-sev::before,.sev-alto .alert-sev::before { background:var(--danger); }
        .sev-moderado .alert-sev { background:rgba(245,158,11,0.12); color:#fbbf24; }
        .sev-moderado .alert-sev::before { background:var(--warning); }
        .sev-baixo .alert-sev { background:rgba(16,185,129,0.12); color:#34d399; }
        .sev-baixo .alert-sev::before { background:var(--success); }
        .alert-msg { font-size:0.92rem; font-weight:500; margin-bottom:4px; line-height:1.4; }
        .alert-meta { font-size:0.78rem; color:var(--text-muted); display:flex; gap:1rem; flex-wrap:wrap; }
        .alert-meta span { display:flex; align-items:center; gap:4px; }
        @keyframes fadeInUp { from{opacity:0;transform:translateY(16px);} to{opacity:1;transform:translateY(0);} }
        .alert-card:nth-child(1){animation-delay:0.05s;} .alert-card:nth-child(2){animation-delay:0.1s;} .alert-card:nth-child(3){animation-delay:0.15s;} .alert-card:nth-child(4){animation-delay:0.2s;}
    </style>
</head>
<body>
    <div class="header">
        <div class="header-brand">
            <div class="header-logo">H+</div>
            <div><h1>HEAL <span>/</span> REDISUS</h1></div>
        </div>
        <nav class="nav">
            <a href="/">📊 Dashboard</a>
            <a href="/patients">🩺 Pacientes</a>
            <a href="/surveillance">🗺️ Vigilância</a>
            <a href="/alerts" class="active">🔔 Alertas</a>
        </nav>
    </div>
    <div class="container">
        <h2 class="page-title">🔔 Alertas Clínicos e Epidemiológicos</h2>
        <p class="page-desc">Notificações em tempo real sobre situações que requerem atenção.</p>
        <div id="alerts-container"><div style="text-align:center;padding:2rem;color:var(--text-muted);">Carregando alertas...</div></div>
    </div>
    <script>
        const sevIcon = {critico:'🔴',alto:'🟠',moderado:'🟡',baixo:'🟢'};
        fetch('/api/alerts').then(r=>r.json()).then(alerts=>{
            const c=document.getElementById('alerts-container');
            if(!alerts.length){
                c.innerHTML='<div class="empty-state"><div class="empty-icon">✅</div>Nenhum alerta ativo no momento.</div>';
                return;
            }
            c.innerHTML=alerts.map((a,i)=>`
                <div class="alert-card sev-${a.severity}" style="animation-delay:${i*0.06}s">
                    <div class="alert-icon">${sevIcon[a.severity]||'⚪'}</div>
                    <div class="alert-body">
                        <div class="alert-sev">${a.severity}</div>
                        <div class="alert-msg">${a.message}</div>
                        <div class="alert-meta">
                            <span>🏥 ${a.condition}</span>
                            <span>📍 ${a.region}</span>
                            <span>👥 ${a.case_count} casos</span>
                            <span>🕐 ${a.timestamp}</span>
                        </div>
                    </div>
                </div>
            `).join('');
        }).catch(()=>{
            document.getElementById('alerts-container').innerHTML='<div style="text-align:center;padding:2rem;color:var(--danger);">Erro ao carregar alertas.</div>';
        });
    </script>
</body>
</html>
"""
