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
from datetime import datetime
from typing import Any, Dict, List, Optional

from loguru import logger
from packages.shared.security import (
    current_user_required,
    enforce_request_auth,
    ensure_admin_access,
    ensure_patient_access,
    filter_patients_for_user,
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
            ensure_admin_access()
            return jsonify(self._get_dashboard_summary())

        @app.route("/api/patients")
        def api_patients():
            """Lista pacientes com indicadores"""
            user = current_user_required()
            return jsonify(filter_patients_for_user(self._get_patients_list(), user=user))

        @app.route("/api/patients/<patient_id>")
        def api_patient_detail(patient_id):
            """Detalhe de um paciente"""
            ensure_patient_access(self.db, patient_id)
            return jsonify(self._get_patient_detail(patient_id))

        @app.route("/api/patients/<patient_id>/risk")
        def api_patient_risk(patient_id):
            """Score de risco de um paciente"""
            ensure_patient_access(self.db, patient_id)
            return jsonify(self._get_patient_risk(patient_id))

        @app.route("/api/indicators")
        def api_indicators():
            """Indicadores populacionais"""
            ensure_admin_access()
            region = request.args.get("region", "")
            return jsonify(self._get_population_indicators(region))

        @app.route("/api/alerts")
        def api_alerts():
            """Alertas ativos"""
            ensure_admin_access()
            return jsonify(self._get_active_alerts())

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
            ensure_admin_access()
            period = request.args.get("period", "month")
            return jsonify(self._get_production_report(period))

        @app.route("/api/export/fhir/<patient_id>")
        def api_export_fhir(patient_id):
            """Exporta dados FHIR de um paciente"""
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

    def _export_fhir(self, patient_id: str) -> Dict:
        """Exporta dados FHIR"""
        return {
            "patient_id": patient_id,
            "message": "Use FHIRClient.export_analysis_as_fhir() para exportação completa",
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
                            <th>Etiologia</th>
                            <th>Área (cm²)</th>
                            <th>Health Score</th>
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

        loadDashboard();
        loadPatients();
        setInterval(loadDashboard, 30000);
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
