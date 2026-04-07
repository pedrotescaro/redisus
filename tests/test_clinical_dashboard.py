"""Tests for the clinical dashboard and decisional queue."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def disable_auth(monkeypatch):
    monkeypatch.setenv("CLINICAL_API_REQUIRE_AUTH", "0")


@pytest.fixture
def mock_database():
    db = MagicMock()

    patients = [
        {
            "id": "P001",
            "name": "Joao Silva",
            "created_at": "2026-01-10T10:00:00",
            "metadata": {"region": "Nordeste"},
        },
        {
            "id": "P002",
            "name": "Maria Santos",
            "created_at": "2026-01-15T14:30:00",
            "metadata": {"region": "Sul"},
        },
    ]
    patient_map = {patient["id"]: patient for patient in patients}

    lesions = {
        "P001": [
            {
                "id": "L001",
                "patient_id": "P001",
                "title": "Lesao plantar",
                "wound_type": "pe_diabetico",
                "location": "pe direito",
                "status": "active",
                "opened_at": "2026-03-01",
                "metadata": {},
            }
        ],
        "P002": [
            {
                "id": "L002",
                "patient_id": "P002",
                "title": "Ulcera venosa",
                "wound_type": "ulcera_venosa",
                "location": "membro inferior esquerdo",
                "status": "active",
                "opened_at": "2026-03-15",
                "metadata": {},
            }
        ],
    }

    timelines = {
        "L001": {
            "lesion": lesions["P001"][0],
            "evaluations": [
                {
                    "id": "E100",
                    "patient_id": "P001",
                    "case_id": "L001",
                    "evaluation_date": "2026-03-28",
                    "wound_area_cm2": 4.0,
                    "push_score": 8,
                    "bwat_score": 10,
                    "pain_score": 3,
                },
                {
                    "id": "E101",
                    "patient_id": "P001",
                    "case_id": "L001",
                    "evaluation_date": "2026-04-05",
                    "wound_area_cm2": 5.2,
                    "push_score": 10,
                    "bwat_score": 12,
                    "pain_score": 6,
                    "inference_result": {
                        "id": "IR1",
                        "evaluation_id": "E101",
                        "risk_level": "critico",
                        "fallback_used": False,
                        "interpretation": {"risk_level": "critico"},
                    },
                },
            ],
            "care_plans": [
                {
                    "id": "CP1",
                    "case_id": "L001",
                    "status": "active",
                    "risk_level": "critico",
                    "created_at": "2026-04-05T10:00:00",
                }
            ],
            "follow_ups": [
                {
                    "id": "FU1",
                    "case_id": "L001",
                    "scheduled_for": "2026-04-04",
                    "status": "scheduled",
                }
            ],
            "alerts": [
                {
                    "id": "AL1",
                    "case_id": "L001",
                    "alert_type": "clinical_deterioration",
                    "severity": "alto",
                    "status": "open",
                    "title": "Piora clinica",
                    "message": "Aumento de area e dor",
                    "created_at": "2026-04-05T12:00:00",
                }
            ],
        },
        "L002": {
            "lesion": lesions["P002"][0],
            "evaluations": [
                {
                    "id": "E200",
                    "patient_id": "P002",
                    "case_id": "L002",
                    "evaluation_date": "2026-03-30",
                    "wound_area_cm2": 3.2,
                    "push_score": 7,
                    "bwat_score": 9,
                    "pain_score": 3,
                },
                {
                    "id": "E201",
                    "patient_id": "P002",
                    "case_id": "L002",
                    "evaluation_date": "2026-04-06",
                    "wound_area_cm2": 2.4,
                    "push_score": 6,
                    "bwat_score": 8,
                    "pain_score": 2,
                    "inference_result": {
                        "id": "IR2",
                        "evaluation_id": "E201",
                        "risk_level": "baixo",
                        "fallback_used": False,
                        "interpretation": {"risk_level": "baixo"},
                    },
                },
            ],
            "care_plans": [
                {
                    "id": "CP2",
                    "case_id": "L002",
                    "status": "active",
                    "risk_level": "baixo",
                    "created_at": "2026-04-06T10:00:00",
                }
            ],
            "follow_ups": [
                {
                    "id": "FU2",
                    "case_id": "L002",
                    "scheduled_for": "2026-04-10",
                    "status": "scheduled",
                }
            ],
            "alerts": [],
        },
    }

    db.get_statistics.return_value = {
        "total_patients": 2,
        "total_analyses": 4,
        "top_etiologies": [
            {"name": "Pe diabetico", "count": 1},
            {"name": "Ulcera venosa", "count": 1},
        ],
    }
    db.list_patients.return_value = patients
    db.get_patient.side_effect = lambda patient_id: patient_map.get(patient_id)
    db.get_patient_analyses.side_effect = lambda patient_id: [
        {"analysis_id": f"{patient_id}-A1", "date": "2026-04-01"},
        {"analysis_id": f"{patient_id}-A2", "date": "2026-04-05"},
    ]
    db.list_wound_cases.side_effect = lambda patient_id: lesions.get(patient_id, [])
    db.get_case_timeline.side_effect = lambda case_id: timelines.get(case_id)
    db.list_patient_evaluations.return_value = []
    db.list_case_care_plans.return_value = []
    db.list_case_follow_ups.return_value = []
    db.list_case_alerts.return_value = []
    db.get_latest_ai_result_for_evaluation.return_value = None
    return db


@pytest.fixture
def mock_surveillance():
    surv = MagicMock()
    surv.alerts = [
        SimpleNamespace(
            alert_id="SURV-001",
            condition="pe diabetico",
            region="Nordeste",
            severity="alto",
            message="Aumento regional de casos",
            case_count=12,
            timestamp="2026-04-05T08:00:00",
            acknowledged=False,
        ),
        SimpleNamespace(
            alert_id="SURV-002",
            condition="ulcera venosa",
            region="Sul",
            severity="moderado",
            message="Cluster monitorado",
            case_count=4,
            timestamp="2026-04-04T08:00:00",
            acknowledged=True,
        ),
    ]
    surv.generate_heatmap_data.return_value = {
        "points": [{"lat": -23.5, "lng": -46.6, "weight": 5}],
        "bounds": {"north": -20, "south": -30, "east": -40, "west": -55},
    }
    surv.detect_clusters.return_value = [{"cluster_id": "C1", "region": "Nordeste", "cases": 15}]
    return surv


@pytest.fixture
def dashboard_no_deps():
    from src.dashboard.clinical_dashboard import ClinicalDashboard

    return ClinicalDashboard()


@pytest.fixture
def dashboard_full(mock_database, mock_surveillance):
    from src.dashboard.clinical_dashboard import ClinicalDashboard

    return ClinicalDashboard(database=mock_database, surveillance=mock_surveillance)


@pytest.fixture
def client_no_deps(dashboard_no_deps):
    app = dashboard_no_deps.create_app()
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


@pytest.fixture
def client_full(dashboard_full):
    app = dashboard_full.create_app()
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


class TestHTMLPages:
    def test_index_page(self, client_no_deps):
        response = client_no_deps.get("/")
        assert response.status_code == 200
        assert "Dashboard" in response.data.decode("utf-8")

    def test_patients_page(self, client_no_deps):
        response = client_no_deps.get("/patients")
        assert response.status_code == 200
        assert "Pacientes" in response.data.decode("utf-8")


class TestDashboardWithoutDeps:
    def test_summary_without_db(self, client_no_deps):
        response = client_no_deps.get("/api/dashboard/summary")
        payload = response.get_json()
        assert response.status_code == 200
        assert payload["total_patients"] == 0
        assert payload["clinical_queue"] == []

    def test_clinical_queue_without_db(self, client_no_deps):
        response = client_no_deps.get("/api/dashboard/clinical-queue")
        payload = response.get_json()
        assert response.status_code == 200
        assert payload["total_items"] == 0
        assert payload["items"] == []

    def test_patient_risk_without_db(self, client_no_deps):
        response = client_no_deps.get("/api/patients/P001/risk")
        payload = response.get_json()
        assert response.status_code == 200
        assert "error" in payload


class TestDashboardWithClinicalQueue:
    def test_summary_exposes_decisional_metrics(self, client_full):
        response = client_full.get("/api/dashboard/summary")
        payload = response.get_json()
        assert response.status_code == 200
        assert payload["total_patients"] == 2
        assert payload["risk_distribution"]["critico"] == 1
        assert payload["risk_distribution"]["baixo"] == 1
        assert payload["patients_needing_attention"] == 1
        assert payload["patients_worsening"] == 1
        assert payload["patients_overdue"] == 1
        assert payload["open_clinical_alerts"] == 1
        assert payload["active_alerts"] == 2
        assert payload["clinical_queue"][0]["patient_id"] == "P001"

    def test_clinical_queue_prioritizes_worsening_case(self, client_full):
        response = client_full.get("/api/dashboard/clinical-queue?view=attention")
        payload = response.get_json()
        assert response.status_code == 200
        assert payload["view"] == "attention"
        assert payload["total_items"] == 1
        assert payload["items"][0]["patient_id"] == "P001"
        assert payload["items"][0]["worsening"] is True
        assert payload["items"][0]["overdue_follow_up"] is True
        assert payload["items"][0]["open_alert_count"] == 1

    def test_patients_list_is_enriched(self, client_full):
        response = client_full.get("/api/patients")
        patients = response.get_json()
        assert response.status_code == 200
        assert len(patients) == 2
        assert patients[0]["metadata"]["priority_score"] >= patients[1]["metadata"]["priority_score"]
        assert patients[0]["metadata"]["needs_attention"] is True

    def test_patient_detail_includes_clinical_summary(self, client_full):
        response = client_full.get("/api/patients/P001")
        payload = response.get_json()
        assert response.status_code == 200
        assert payload["clinical_summary"]["risk_level"] == "critico"
        assert payload["clinical_summary"]["worsening"] is True
        assert payload["lesions"][0]["open_alert_count"] == 1
        assert payload["total_analyses"] == 2

    def test_patient_risk_uses_timeline(self, client_full):
        response = client_full.get("/api/patients/P001/risk")
        payload = response.get_json()
        assert response.status_code == 200
        assert payload["patient_id"] == "P001"
        assert payload["risk_level"] == "critico"
        assert payload["needs_attention"] is True
        assert payload["overdue_follow_ups"] == 1
        assert payload["lesions"][0]["worsening"] is True

    def test_active_alerts_merge_surveillance_and_clinical(self, client_full):
        response = client_full.get("/api/alerts")
        payload = response.get_json()
        assert response.status_code == 200
        assert len(payload) == 2
        assert {item["source"] for item in payload} == {"surveillance", "clinical"}

    def test_population_indicators_support_region_filter(self, client_full):
        response = client_full.get("/api/indicators?region=Nordeste")
        payload = response.get_json()
        assert response.status_code == 200
        assert payload[0]["region"] == "Nordeste"
        assert payload[0]["value"] == 1
        assert payload[1]["value"] == 1

    def test_production_report_surfaces_operational_queue(self, client_full):
        response = client_full.get("/api/reports/production?period=week")
        payload = response.get_json()
        assert response.status_code == 200
        assert payload["period"] == "week"
        assert payload["patients_needing_attention"] == 1
        assert payload["follow_ups_overdue"] == 1
        assert payload["top_queue"][0]["patient_id"] == "P001"


class TestInternalMethods:
    def test_heatmap_without_surveillance(self, dashboard_no_deps):
        assert dashboard_no_deps._get_heatmap_data("diabetes", 30) == {"points": [], "bounds": None}

    def test_alerts_filter_acknowledged_surveillance(self, dashboard_full):
        alerts = dashboard_full._get_active_alerts()
        assert len(alerts) == 2
        assert all(alert["id"] != "SURV-002" for alert in alerts)


class TestRunMethod:
    def test_run_creates_app_if_needed(self, dashboard_no_deps):
        with patch.object(dashboard_no_deps, "create_app") as mock_create:
            mock_app = MagicMock()
            mock_create.return_value = mock_app
            dashboard_no_deps.app = None
            dashboard_no_deps.run(host="127.0.0.1", port=5001, debug=False)
            mock_create.assert_called_once()
