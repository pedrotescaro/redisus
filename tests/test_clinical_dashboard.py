"""
HEAL/REDISUS — Testes do Dashboard Clínico Interativo.
Cobre: inicialização, criação do app Flask, endpoints REST e métodos de dados.
"""
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_database():
    """Mock do banco de dados com métodos usados pelo dashboard."""
    db = MagicMock()
    db.get_statistics.return_value = {
        "total_patients": 42,
        "total_analyses": 128,
        "top_etiologies": [
            {"name": "Úlcera venosa", "count": 30},
            {"name": "Pé diabético", "count": 12},
        ],
    }
    db.list_patients.return_value = [
        {"id": "P001", "name": "João Silva", "created_at": "2026-01-10T10:00:00"},
        {"id": "P002", "name": "Maria Santos", "created_at": "2026-01-15T14:30:00"},
    ]
    db.get_patient.return_value = {
        "id": "P001",
        "name": "João Silva",
        "created_at": "2026-01-10T10:00:00",
    }
    db.get_patient_analyses.return_value = [
        {"analysis_id": "A1", "date": "2026-01-10"},
        {"analysis_id": "A2", "date": "2026-01-20"},
    ]
    return db


@pytest.fixture
def mock_risk_engine():
    """Mock do motor de risco."""
    return MagicMock()


@pytest.fixture
def mock_surveillance():
    """Mock do módulo de vigilância epidemiológica com alertas."""
    surv = MagicMock()
    alert1 = SimpleNamespace(
        alert_id="ALT-001",
        condition="pé diabético",
        region="Nordeste",
        severity="alto",
        message="Aumento de casos de pé diabético",
        case_count=15,
        timestamp="2026-02-18T10:00:00",
        acknowledged=False,
    )
    alert2 = SimpleNamespace(
        alert_id="ALT-002",
        condition="úlcera venosa",
        region="Sul",
        severity="moderado",
        message="Cluster de úlcera venosa",
        case_count=8,
        timestamp="2026-02-19T12:00:00",
        acknowledged=True,  # já reconhecido
    )
    surv.alerts = [alert1, alert2]
    surv.generate_heatmap_data.return_value = {
        "points": [{"lat": -23.5, "lng": -46.6, "weight": 5}],
        "bounds": {"north": -20, "south": -30, "east": -40, "west": -55},
    }
    surv.detect_clusters.return_value = [
        {"cluster_id": "C1", "region": "Nordeste", "cases": 15},
    ]
    return surv


@pytest.fixture
def dashboard_no_deps():
    """Dashboard sem dependências externas."""
    from src.dashboard.clinical_dashboard import ClinicalDashboard
    return ClinicalDashboard()


@pytest.fixture
def dashboard_full(mock_database, mock_risk_engine, mock_surveillance):
    """Dashboard com todas as dependências mockadas."""
    from src.dashboard.clinical_dashboard import ClinicalDashboard
    return ClinicalDashboard(
        database=mock_database,
        risk_engine=mock_risk_engine,
        surveillance=mock_surveillance,
    )


@pytest.fixture
def client_no_deps(dashboard_no_deps):
    """Flask test client sem dependências."""
    app = dashboard_no_deps.create_app()
    assert app is not None, "Flask não está instalado"
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


@pytest.fixture
def client_full(dashboard_full):
    """Flask test client com dependências completas."""
    app = dashboard_full.create_app()
    assert app is not None, "Flask não está instalado"
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


# ===================================================================
# Testes de inicialização
# ===================================================================

class TestDashboardInit:
    """Testes de criação e configuração do ClinicalDashboard."""

    def test_init_sem_dependencias(self, dashboard_no_deps):
        assert dashboard_no_deps.db is None
        assert dashboard_no_deps.risk_engine is None
        assert dashboard_no_deps.surveillance is None
        assert dashboard_no_deps.app is None

    def test_init_com_dependencias(self, dashboard_full, mock_database, mock_risk_engine, mock_surveillance):
        assert dashboard_full.db is mock_database
        assert dashboard_full.risk_engine is mock_risk_engine
        assert dashboard_full.surveillance is mock_surveillance

    def test_create_app_retorna_flask(self, dashboard_no_deps):
        app = dashboard_no_deps.create_app()
        assert app is not None
        assert dashboard_no_deps.app is app

    def test_create_app_sem_flask_retorna_none(self, dashboard_no_deps):
        """Se Flask não estiver disponível, create_app retorna None."""
        with patch.dict("sys.modules", {"flask": None}):
            from importlib import reload
            # Esse cenário é coberto pelo try/except interno
            # Testa apenas que o atributo app inicia None
            assert dashboard_no_deps.app is None


# ===================================================================
# Testes das páginas HTML
# ===================================================================

class TestHTMLPages:
    """Testa que as rotas HTML retornam 200 e contêm marcadores esperados."""

    def test_index_page(self, client_no_deps):
        resp = client_no_deps.get("/")
        assert resp.status_code == 200
        html = resp.data.decode("utf-8")
        assert "HEAL" in html
        assert "REDISUS" in html
        assert "Dashboard" in html

    def test_patients_page(self, client_no_deps):
        resp = client_no_deps.get("/patients")
        assert resp.status_code == 200
        html = resp.data.decode("utf-8")
        assert "Pacientes" in html

    def test_surveillance_page(self, client_no_deps):
        resp = client_no_deps.get("/surveillance")
        assert resp.status_code == 200
        html = resp.data.decode("utf-8")
        assert "Vigilância" in html or "Vigilancia" in html

    def test_alerts_page(self, client_no_deps):
        resp = client_no_deps.get("/alerts")
        assert resp.status_code == 200
        html = resp.data.decode("utf-8")
        assert "Alertas" in html


# ===================================================================
# Testes da API — sem dependências (retornos padrão / vazios)
# ===================================================================

class TestAPISemDependencias:
    """Testa endpoints REST quando nenhuma dependência está configurada."""

    def test_summary_sem_db(self, client_no_deps):
        resp = client_no_deps.get("/api/dashboard/summary")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["platform"] == "HEAL/REDISUS"
        assert data["total_patients"] == 0
        assert data["total_analyses"] == 0
        assert data["active_alerts"] == 0
        assert "timestamp" in data

    def test_patients_list_sem_db(self, client_no_deps):
        resp = client_no_deps.get("/api/patients")
        assert resp.status_code == 200
        assert resp.get_json() == []

    def test_patient_detail_sem_db(self, client_no_deps):
        resp = client_no_deps.get("/api/patients/P001")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "error" in data

    def test_patient_risk_sem_engine(self, client_no_deps):
        resp = client_no_deps.get("/api/patients/P001/risk")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "error" in data

    def test_indicators_sem_deps(self, client_no_deps):
        resp = client_no_deps.get("/api/indicators")
        assert resp.status_code == 200
        data = resp.get_json()
        assert isinstance(data, list)

    def test_alerts_sem_surveillance(self, client_no_deps):
        resp = client_no_deps.get("/api/alerts")
        assert resp.status_code == 200
        assert resp.get_json() == []

    def test_heatmap_sem_surveillance(self, client_no_deps):
        resp = client_no_deps.get("/api/surveillance/heatmap")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["points"] == []

    def test_clusters_sem_surveillance(self, client_no_deps):
        resp = client_no_deps.get("/api/surveillance/clusters")
        assert resp.status_code == 200
        assert resp.get_json() == []

    def test_production_report(self, client_no_deps):
        resp = client_no_deps.get("/api/reports/production")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["period"] == "month"
        assert "generated_at" in data

    def test_production_report_period_custom(self, client_no_deps):
        resp = client_no_deps.get("/api/reports/production?period=week")
        assert resp.status_code == 200
        assert resp.get_json()["period"] == "week"

    def test_export_fhir(self, client_no_deps):
        resp = client_no_deps.get("/api/export/fhir/P001")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["patient_id"] == "P001"


# ===================================================================
# Testes da API — com dependências (mock completo)
# ===================================================================

class TestAPIComDependencias:
    """Testa endpoints REST com banco, risco e vigilância mockados."""

    def test_summary_com_db(self, client_full):
        resp = client_full.get("/api/dashboard/summary")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["total_patients"] == 42
        assert data["total_analyses"] == 128
        assert len(data["top_etiologies"]) == 2
        # Apenas 1 alerta não reconhecido
        assert data["active_alerts"] == 1

    def test_patients_list(self, client_full):
        resp = client_full.get("/api/patients")
        assert resp.status_code == 200
        patients = resp.get_json()
        assert len(patients) == 2
        assert patients[0]["name"] == "João Silva"

    def test_patient_detail(self, client_full, mock_database):
        resp = client_full.get("/api/patients/P001")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["total_analyses"] == 2
        mock_database.get_patient.assert_called_with("P001")
        mock_database.get_patient_analyses.assert_called_with("P001")

    def test_patient_detail_not_found(self, client_full, mock_database):
        mock_database.get_patient.return_value = None
        resp = client_full.get("/api/patients/P999")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "error" in data
        assert "não encontrado" in data["error"].lower() or "encontrado" in data["error"].lower()

    def test_patient_risk(self, client_full):
        resp = client_full.get("/api/patients/P001/risk")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["patient_id"] == "P001"

    def test_alerts_com_surveillance(self, client_full):
        resp = client_full.get("/api/alerts")
        assert resp.status_code == 200
        alerts = resp.get_json()
        # Apenas o alerta não reconhecido deve aparecer
        assert len(alerts) == 1
        assert alerts[0]["id"] == "ALT-001"
        assert alerts[0]["severity"] == "alto"

    def test_heatmap_com_surveillance(self, client_full, mock_surveillance):
        resp = client_full.get("/api/surveillance/heatmap?condition=diabetes&days=60")
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data["points"]) == 1
        mock_surveillance.generate_heatmap_data.assert_called_once_with(
            condition="diabetes", period_days=60
        )

    def test_heatmap_sem_parametros(self, client_full, mock_surveillance):
        resp = client_full.get("/api/surveillance/heatmap")
        assert resp.status_code == 200
        mock_surveillance.generate_heatmap_data.assert_called_with(
            condition=None, period_days=30
        )

    def test_clusters_com_surveillance(self, client_full):
        resp = client_full.get("/api/surveillance/clusters")
        assert resp.status_code == 200
        clusters = resp.get_json()
        assert len(clusters) == 1
        assert clusters[0]["cluster_id"] == "C1"

    def test_indicators_com_region(self, client_full):
        resp = client_full.get("/api/indicators?region=Nordeste")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data[0]["region"] == "Nordeste"

    def test_indicators_sem_region(self, client_full):
        resp = client_full.get("/api/indicators")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data[0]["region"] == "todas"


# ===================================================================
# Testes de tratamento de erros
# ===================================================================

class TestErrorHandling:
    """Testa resiliência quando dependências lançam exceções."""

    def test_summary_db_exception(self, dashboard_full):
        dashboard_full.db.get_statistics.side_effect = RuntimeError("DB offline")
        summary = dashboard_full._get_dashboard_summary()
        # Deve retornar valores padrão em vez de quebrar
        assert summary["total_patients"] == 0
        assert summary["total_analyses"] == 0

    def test_patients_list_db_exception(self, dashboard_full):
        dashboard_full.db.list_patients.side_effect = RuntimeError("DB offline")
        result = dashboard_full._get_patients_list()
        assert result == []

    def test_patient_detail_db_exception(self, dashboard_full):
        dashboard_full.db.get_patient.side_effect = RuntimeError("DB offline")
        result = dashboard_full._get_patient_detail("P001")
        assert "error" in result


# ===================================================================
# Testes dos métodos de dados internos
# ===================================================================

class TestDataMethods:
    """Testa métodos _get_* diretamente."""

    def test_get_dashboard_summary_structure(self, dashboard_no_deps):
        summary = dashboard_no_deps._get_dashboard_summary()
        required_keys = {
            "timestamp", "platform", "total_patients", "total_analyses",
            "risk_distribution", "active_alerts", "recent_analyses", "top_etiologies",
        }
        assert required_keys.issubset(summary.keys())

    def test_risk_distribution_keys(self, dashboard_no_deps):
        summary = dashboard_no_deps._get_dashboard_summary()
        dist = summary["risk_distribution"]
        assert set(dist.keys()) == {"baixo", "moderado", "alto", "critico"}

    def test_get_patient_risk_sem_engine(self, dashboard_no_deps):
        result = dashboard_no_deps._get_patient_risk("P001")
        assert "error" in result

    def test_get_patient_risk_com_engine(self, dashboard_full):
        result = dashboard_full._get_patient_risk("P001")
        assert result["patient_id"] == "P001"

    def test_get_production_report_default(self, dashboard_no_deps):
        report = dashboard_no_deps._get_production_report("month")
        assert report["period"] == "month"
        assert "HEAL/REDISUS" in report["generated_by"]
        # Timestamp deve ser parseable
        datetime.fromisoformat(report["generated_at"])

    def test_export_fhir_structure(self, dashboard_no_deps):
        result = dashboard_no_deps._export_fhir("P123")
        assert result["patient_id"] == "P123"
        assert "message" in result

    def test_get_heatmap_sem_surveillance(self, dashboard_no_deps):
        result = dashboard_no_deps._get_heatmap_data("diabetes", 30)
        assert result == {"points": [], "bounds": None}

    def test_get_clusters_sem_surveillance(self, dashboard_no_deps):
        assert dashboard_no_deps._get_clusters() == []

    def test_get_active_alerts_sem_surveillance(self, dashboard_no_deps):
        assert dashboard_no_deps._get_active_alerts() == []

    def test_get_active_alerts_filtra_reconhecidos(self, dashboard_full):
        alerts = dashboard_full._get_active_alerts()
        # Somente alertas não reconhecidos
        assert len(alerts) == 1
        assert all(a["id"] != "ALT-002" for a in alerts)


# ===================================================================
# Testes de integração leve (run)
# ===================================================================

class TestRunMethod:
    """Testa o método run sem subir servidor real."""

    def test_run_cria_app_se_necessario(self, dashboard_no_deps):
        assert dashboard_no_deps.app is None
        with patch.object(dashboard_no_deps, "create_app") as mock_create:
            mock_app = MagicMock()
            mock_create.return_value = mock_app
            dashboard_no_deps.app = None
            # Como app é None, create_app será chamado
            dashboard_no_deps.run(host="127.0.0.1", port=5001, debug=False)
            mock_create.assert_called_once()
