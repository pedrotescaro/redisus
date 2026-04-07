import pytest

from packages.clinical_domain import PatientRecord


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("REDISUS_DB_PATH", str(tmp_path / "official-api.db"))
    monkeypatch.setenv("CLINICAL_API_REQUIRE_AUTH", "0")

    from apps.api.app import create_app

    app = create_app()
    db = app.extensions["redisus_db"]
    db.save_patient(PatientRecord(id="p001", name="Paciente Oficial"))
    app.config["TESTING"] = True
    with app.test_client() as test_client:
        yield test_client


def test_official_root_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["status"] == "ok"
    assert payload["api"] == "official"


def test_official_api_health(client):
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["status"] == "ok"
    assert "components" in payload
    assert "metrics" in payload


def test_dashboard_summary_route(client):
    response = client.get("/api/dashboard/summary")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["platform"] == "HEAL/REDISUS"
