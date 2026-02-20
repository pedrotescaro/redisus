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
            return jsonify(self._get_dashboard_summary())

        @app.route("/api/patients")
        def api_patients():
            """Lista pacientes com indicadores"""
            return jsonify(self._get_patients_list())

        @app.route("/api/patients/<patient_id>")
        def api_patient_detail(patient_id):
            """Detalhe de um paciente"""
            return jsonify(self._get_patient_detail(patient_id))

        @app.route("/api/patients/<patient_id>/risk")
        def api_patient_risk(patient_id):
            """Score de risco de um paciente"""
            return jsonify(self._get_patient_risk(patient_id))

        @app.route("/api/indicators")
        def api_indicators():
            """Indicadores populacionais"""
            region = request.args.get("region", "")
            return jsonify(self._get_population_indicators(region))

        @app.route("/api/alerts")
        def api_alerts():
            """Alertas ativos"""
            return jsonify(self._get_active_alerts())

        @app.route("/api/surveillance/heatmap")
        def api_heatmap():
            """Dados de mapa de calor"""
            condition = request.args.get("condition")
            days = int(request.args.get("days", 30))
            return jsonify(self._get_heatmap_data(condition, days))

        @app.route("/api/surveillance/clusters")
        def api_clusters():
            """Clusters detectados"""
            return jsonify(self._get_clusters())

        @app.route("/api/reports/production")
        def api_production():
            """Relatório de produção"""
            period = request.args.get("period", "month")
            return jsonify(self._get_production_report(period))

        @app.route("/api/export/fhir/<patient_id>")
        def api_export_fhir(patient_id):
            """Exporta dados FHIR de um paciente"""
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
    <style>
        :root {
            --primary: #0066cc;
            --success: #28a745;
            --warning: #ffc107;
            --danger: #dc3545;
            --info: #17a2b8;
            --dark: #1a1a2e;
            --light: #f8f9fa;
            --bg: #0f0f23;
            --card-bg: #16213e;
            --text: #e8e8e8;
            --text-muted: #a0a0b0;
        }
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', system-ui, sans-serif;
            background: var(--bg);
            color: var(--text);
            min-height: 100vh;
        }
        .header {
            background: linear-gradient(135deg, var(--dark), #0a3d62);
            padding: 1rem 2rem;
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 2px solid var(--primary);
        }
        .header h1 { font-size: 1.5rem; color: #fff; }
        .header .subtitle { color: var(--text-muted); font-size: 0.85rem; }
        .nav {
            display: flex; gap: 1rem;
        }
        .nav a {
            color: var(--text-muted);
            text-decoration: none;
            padding: 0.5rem 1rem;
            border-radius: 6px;
            transition: all 0.3s;
        }
        .nav a:hover, .nav a.active {
            background: var(--primary);
            color: #fff;
        }
        .container { max-width: 1400px; margin: 0 auto; padding: 1.5rem; }
        .cards {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 1rem;
            margin-bottom: 2rem;
        }
        .card {
            background: var(--card-bg);
            border-radius: 12px;
            padding: 1.5rem;
            border: 1px solid rgba(255,255,255,0.05);
            transition: transform 0.2s;
        }
        .card:hover { transform: translateY(-2px); }
        .card .label { color: var(--text-muted); font-size: 0.85rem; margin-bottom: 0.5rem; }
        .card .value { font-size: 2rem; font-weight: 700; }
        .card .trend { font-size: 0.8rem; margin-top: 0.3rem; }
        .card.success .value { color: var(--success); }
        .card.warning .value { color: var(--warning); }
        .card.danger .value { color: var(--danger); }
        .card.info .value { color: var(--info); }
        .section { margin-bottom: 2rem; }
        .section h2 {
            font-size: 1.2rem;
            margin-bottom: 1rem;
            padding-bottom: 0.5rem;
            border-bottom: 1px solid rgba(255,255,255,0.1);
        }
        .table-container { overflow-x: auto; }
        table {
            width: 100%;
            border-collapse: collapse;
            background: var(--card-bg);
            border-radius: 8px;
            overflow: hidden;
        }
        th, td { padding: 0.75rem 1rem; text-align: left; }
        th {
            background: rgba(0,102,204,0.2);
            color: var(--primary);
            font-weight: 600;
            font-size: 0.85rem;
            text-transform: uppercase;
        }
        td { border-bottom: 1px solid rgba(255,255,255,0.05); font-size: 0.9rem; }
        tr:hover td { background: rgba(255,255,255,0.02); }
        .badge {
            display: inline-block;
            padding: 0.2rem 0.6rem;
            border-radius: 20px;
            font-size: 0.75rem;
            font-weight: 600;
        }
        .badge-baixo { background: rgba(40,167,69,0.2); color: var(--success); }
        .badge-moderado { background: rgba(255,193,7,0.2); color: var(--warning); }
        .badge-alto { background: rgba(255,128,0,0.2); color: #ff8000; }
        .badge-critico { background: rgba(220,53,69,0.2); color: var(--danger); }
        .alert-panel {
            background: rgba(220,53,69,0.1);
            border: 1px solid var(--danger);
            border-radius: 8px;
            padding: 1rem;
            margin-bottom: 1rem;
        }
        .alert-panel h3 { color: var(--danger); margin-bottom: 0.5rem; }
        .chart-placeholder {
            background: var(--card-bg);
            border-radius: 8px;
            padding: 2rem;
            text-align: center;
            color: var(--text-muted);
            border: 1px dashed rgba(255,255,255,0.1);
        }
        .grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; }
        .footer {
            text-align: center;
            padding: 1rem;
            color: var(--text-muted);
            font-size: 0.8rem;
            border-top: 1px solid rgba(255,255,255,0.05);
            margin-top: 2rem;
        }
        @media (max-width: 768px) {
            .grid-2 { grid-template-columns: 1fr; }
            .cards { grid-template-columns: 1fr 1fr; }
        }
    </style>
</head>
<body>
    <div class="header">
        <div>
            <h1>HEAL / REDISUS</h1>
            <div class="subtitle">Plataforma Nacional de Saude Digital Integrada</div>
        </div>
        <nav class="nav">
            <a href="/" class="active">Dashboard</a>
            <a href="/patients">Pacientes</a>
            <a href="/surveillance">Vigilancia</a>
            <a href="/alerts">Alertas</a>
        </nav>
    </div>

    <div class="container">
        <div class="cards" id="summary-cards">
            <div class="card info">
                <div class="label">Total de Pacientes</div>
                <div class="value" id="total-patients">--</div>
                <div class="trend">Monitorados atualmente</div>
            </div>
            <div class="card success">
                <div class="label">Analises Realizadas</div>
                <div class="value" id="total-analyses">--</div>
                <div class="trend">Avaliações de feridas</div>
            </div>
            <div class="card warning">
                <div class="label">Risco Alto/Critico</div>
                <div class="value" id="high-risk">--</div>
                <div class="trend">Necessitam atencao imediata</div>
            </div>
            <div class="card danger">
                <div class="label">Alertas Ativos</div>
                <div class="value" id="active-alerts">--</div>
                <div class="trend">Pendentes de reconhecimento</div>
            </div>
        </div>

        <div class="grid-2">
            <div class="section">
                <h2>Distribuicao por Etiologia</h2>
                <div class="chart-placeholder" id="etiology-chart">
                    Grafico de distribuicao por etiologia<br>
                    <small>Conecte ao banco de dados para visualizar</small>
                </div>
            </div>
            <div class="section">
                <h2>Estratificacao de Risco</h2>
                <div class="chart-placeholder" id="risk-chart">
                    Grafico de estratificacao de risco<br>
                    <small>Conecte ao modulo de risco para visualizar</small>
                </div>
            </div>
        </div>

        <div class="section">
            <h2>Pacientes em Acompanhamento</h2>
            <div class="table-container">
                <table id="patients-table">
                    <thead>
                        <tr>
                            <th>Paciente</th>
                            <th>Etiologia</th>
                            <th>Area (cm²)</th>
                            <th>Health Score</th>
                            <th>Risco</th>
                            <th>Ultima Avaliacao</th>
                        </tr>
                    </thead>
                    <tbody id="patients-tbody">
                        <tr><td colspan="6" style="text-align:center; color: var(--text-muted);">
                            Carregando dados...
                        </td></tr>
                    </tbody>
                </table>
            </div>
        </div>

        <div class="section">
            <h2>Eixos da Plataforma HEAL</h2>
            <div class="cards">
                <div class="card">
                    <div class="label">Eixo 1</div>
                    <div style="font-size:1.1rem; font-weight:600; margin-bottom:0.5rem;">
                        Diagnostico & Monitoramento
                    </div>
                    <div style="color:var(--text-muted); font-size:0.85rem;">
                        IA para imagens clinicas, sinais vitais, testes rapidos
                    </div>
                </div>
                <div class="card">
                    <div class="label">Eixo 2</div>
                    <div style="font-size:1.1rem; font-weight:600; margin-bottom:0.5rem;">
                        Gestao do Cuidado
                    </div>
                    <div style="color:var(--text-muted); font-size:0.85rem;">
                        Planos de cuidado, dashboards, estratificacao de risco
                    </div>
                </div>
                <div class="card">
                    <div class="label">Eixo 3</div>
                    <div style="font-size:1.1rem; font-weight:600; margin-bottom:0.5rem;">
                        Interoperabilidade SUS
                    </div>
                    <div style="color:var(--text-muted); font-size:0.85rem;">
                        HL7 FHIR, e-SUS/PEC, DATASUS, georreferenciamento
                    </div>
                </div>
                <div class="card">
                    <div class="label">Eixo 4</div>
                    <div style="font-size:1.1rem; font-weight:600; margin-bottom:0.5rem;">
                        Experiencia do Paciente
                    </div>
                    <div style="color:var(--text-muted); font-size:0.85rem;">
                        Digital Twin, interfaces acessiveis, educacao em saude
                    </div>
                </div>
                <div class="card">
                    <div class="label">Eixo 5</div>
                    <div style="font-size:1.1rem; font-weight:600; margin-bottom:0.5rem;">
                        Validacao & Escalabilidade
                    </div>
                    <div style="color:var(--text-muted); font-size:0.85rem;">
                        Pilotos em HUs, ESF, Telessaude, Rede RUTE
                    </div>
                </div>
            </div>
        </div>
    </div>

    <div class="footer">
        HEAL/REDISUS — Plataforma Nacional de Saude Digital Integrada | Cluster REDISUS - RNP/RUTE
    </div>

    <script>
        async function loadDashboard() {
            try {
                const resp = await fetch('/api/dashboard/summary');
                const data = await resp.json();
                document.getElementById('total-patients').textContent = data.total_patients || 0;
                document.getElementById('total-analyses').textContent = data.total_analyses || 0;
                document.getElementById('high-risk').textContent =
                    (data.risk_distribution?.alto || 0) + (data.risk_distribution?.critico || 0);
                document.getElementById('active-alerts').textContent = data.active_alerts || 0;
            } catch(e) {
                console.log('Dashboard data not available:', e);
            }
        }

        async function loadPatients() {
            try {
                const resp = await fetch('/api/patients');
                const patients = await resp.json();
                const tbody = document.getElementById('patients-tbody');
                if (patients.length === 0) {
                    tbody.innerHTML = '<tr><td colspan="6" style="text-align:center; color: var(--text-muted);">Nenhum paciente registrado</td></tr>';
                    return;
                }
                tbody.innerHTML = patients.map(p => `
                    <tr>
                        <td>${p.name || 'N/A'}</td>
                        <td>${p.metadata?.etiology || '--'}</td>
                        <td>${p.metadata?.area_cm2?.toFixed(1) || '--'}</td>
                        <td>${p.metadata?.health_score?.toFixed(1) || '--'}</td>
                        <td><span class="badge badge-${p.metadata?.risk_level || 'moderado'}">${p.metadata?.risk_level || 'N/A'}</span></td>
                        <td>${p.created_at?.split('T')[0] || '--'}</td>
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
    <title>HEAL — Pacientes</title>
    <style>
        body { font-family: 'Segoe UI', sans-serif; background: #0f0f23; color: #e8e8e8; padding: 2rem; }
        h1 { color: #0066cc; margin-bottom: 1rem; }
        a { color: #0066cc; }
        .back { margin-bottom: 1rem; display: inline-block; }
    </style>
</head>
<body>
    <a href="/" class="back">← Dashboard</a>
    <h1>Gestao de Pacientes</h1>
    <p>Pagina de gestao de pacientes — em integracao com o banco SQLite.</p>
    <p>Use a API <code>/api/patients</code> para consultar dados.</p>
</body>
</html>
"""

SURVEILLANCE_HTML = """
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <title>HEAL — Vigilancia Epidemiologica</title>
    <style>
        body { font-family: 'Segoe UI', sans-serif; background: #0f0f23; color: #e8e8e8; padding: 2rem; }
        h1 { color: #0066cc; margin-bottom: 1rem; }
        a { color: #0066cc; }
        .back { margin-bottom: 1rem; display: inline-block; }
    </style>
</head>
<body>
    <a href="/" class="back">← Dashboard</a>
    <h1>Vigilancia Epidemiologica Digital</h1>
    <p>Mapa de calor, clusters e indicadores epidemiologicos.</p>
    <p>APIs disponiveis:</p>
    <ul>
        <li><code>/api/surveillance/heatmap</code> — Dados do mapa de calor</li>
        <li><code>/api/surveillance/clusters</code> — Clusters detectados</li>
        <li><code>/api/alerts</code> — Alertas de surto</li>
    </ul>
</body>
</html>
"""

ALERTS_HTML = """
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <title>HEAL — Alertas</title>
    <style>
        body { font-family: 'Segoe UI', sans-serif; background: #0f0f23; color: #e8e8e8; padding: 2rem; }
        h1 { color: #dc3545; margin-bottom: 1rem; }
        a { color: #0066cc; }
        .back { margin-bottom: 1rem; display: inline-block; }
        .alert { background: rgba(220,53,69,0.1); border: 1px solid #dc3545; padding: 1rem; border-radius: 8px; margin-bottom: 1rem; }
    </style>
</head>
<body>
    <a href="/" class="back">← Dashboard</a>
    <h1>Alertas Clinicos e Epidemiologicos</h1>
    <div id="alerts-container">Carregando alertas...</div>
    <script>
        fetch('/api/alerts').then(r => r.json()).then(alerts => {
            const container = document.getElementById('alerts-container');
            if (alerts.length === 0) {
                container.innerHTML = '<p style="color:#28a745;">Nenhum alerta ativo.</p>';
                return;
            }
            container.innerHTML = alerts.map(a => `
                <div class="alert">
                    <strong>[${a.severity.toUpperCase()}]</strong> ${a.message}<br>
                    <small>${a.condition} — ${a.region} — ${a.timestamp}</small>
                </div>
            `).join('');
        }).catch(() => {
            document.getElementById('alerts-container').innerHTML = '<p>Erro ao carregar alertas.</p>';
        });
    </script>
</body>
</html>
"""
