import io

from PIL import Image

from src.data.database import PatientRecord


def _png_bytes(color: tuple[int, int, int] = (0, 120, 180)) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (32, 32), color=color).save(buffer, format="PNG")
    return buffer.getvalue()


def _build_headers(token: str = "valid-user-1") -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _build_user(uid: str, *, role: str = "clinician") -> dict[str, str]:
    return {
        "uid": uid,
        "email": f"{uid}@example.test",
        "name": f"User {uid}",
        "role": role,
    }


def test_protected_routes_fail_closed_without_auth_backend(tmp_path, monkeypatch):
    monkeypatch.setenv("REDISUS_DB_PATH", str(tmp_path / "security.db"))
    monkeypatch.setenv("CLINICAL_API_REQUIRE_AUTH", "1")

    from apps.api.app import create_app

    app = create_app()
    app.config["TESTING"] = True

    with app.test_client() as client:
        response = client.get("/api/dashboard/summary")

    assert response.status_code == 503
    assert response.get_json()["detail"] == "authentication backend unavailable"


def test_missing_token_is_rejected(tmp_path, monkeypatch):
    monkeypatch.setenv("REDISUS_DB_PATH", str(tmp_path / "security.db"))
    monkeypatch.setenv("CLINICAL_API_REQUIRE_AUTH", "1")

    from apps.api.app import create_app

    app = create_app()
    app.config["TESTING"] = True
    app.config["REDISUS_AUTH_VERIFIER"] = lambda token: _build_user("user-1", role="admin")

    with app.test_client() as client:
        response = client.get("/api/dashboard/summary")

    assert response.status_code == 401
    assert response.get_json()["detail"] == "missing bearer token"


def test_patient_listing_is_scoped_to_owner(tmp_path, monkeypatch):
    monkeypatch.setenv("REDISUS_DB_PATH", str(tmp_path / "security.db"))
    monkeypatch.setenv("CLINICAL_API_REQUIRE_AUTH", "1")

    from apps.api.app import create_app

    app = create_app()
    app.config["TESTING"] = True
    app.config["REDISUS_AUTH_VERIFIER"] = lambda token: _build_user("user-1")
    db = app.extensions["redisus_db"]
    db.save_patient(PatientRecord(id="p001", name="Paciente 1", metadata={"owner_uid": "user-1"}))
    db.save_patient(PatientRecord(id="p002", name="Paciente 2", metadata={"owner_uid": "user-2"}))

    with app.test_client() as client:
        response = client.get("/api/patients", headers=_build_headers())

    assert response.status_code == 200
    payload = response.get_json()
    assert [item["id"] for item in payload] == ["p001"]


def test_client_supplied_ids_are_rejected(tmp_path, monkeypatch):
    monkeypatch.setenv("REDISUS_DB_PATH", str(tmp_path / "security.db"))
    monkeypatch.setenv("CLINICAL_API_REQUIRE_AUTH", "1")

    from apps.api.app import create_app

    app = create_app()
    app.config["TESTING"] = True
    app.config["REDISUS_AUTH_VERIFIER"] = lambda token: _build_user("user-1")
    db = app.extensions["redisus_db"]
    db.save_patient(PatientRecord(id="p001", name="Paciente 1", metadata={"owner_uid": "user-1"}))

    with app.test_client() as client:
        response = client.post(
            "/api/v1/evaluations",
            headers={**_build_headers(), "Content-Type": "application/json"},
            json={
                "id": "eval-malicioso",
                "patient_id": "p001",
                "evaluation_date": "2026-04-07",
                "wound_area_cm2": 10.0,
            },
        )

    assert response.status_code == 400
    assert "Extra inputs are not permitted" in response.get_json()["detail"]


def test_upload_rejects_unexpected_form_fields(tmp_path, monkeypatch):
    monkeypatch.setenv("REDISUS_DB_PATH", str(tmp_path / "security.db"))
    monkeypatch.setenv("CLINICAL_API_REQUIRE_AUTH", "1")

    from apps.api.app import create_app

    app = create_app()
    app.config["TESTING"] = True
    app.config["REDISUS_AUTH_VERIFIER"] = lambda token: _build_user("user-1")
    db = app.extensions["redisus_db"]
    db.save_patient(PatientRecord(id="p001", name="Paciente 1", metadata={"owner_uid": "user-1"}))

    with app.test_client() as client:
        create_response = client.post(
            "/api/v1/evaluations",
            headers={**_build_headers(), "Content-Type": "application/json"},
            json={
                "patient_id": "p001",
                "evaluation_date": "2026-04-07",
                "wound_area_cm2": 8.0,
            },
        )
        evaluation_id = create_response.get_json()["id"]

        upload_response = client.post(
            f"/api/v1/evaluations/{evaluation_id}/images",
            headers=_build_headers(),
            data={
                "imageRole": "clinical",
                "tamperedField": "1",
                "image": (io.BytesIO(_png_bytes()), "ferida.png"),
            },
            content_type="multipart/form-data",
        )

    assert upload_response.status_code == 400
    assert "unexpected form fields" in upload_response.get_json()["detail"]


def test_report_generation_ignores_professional_from_client(tmp_path, monkeypatch):
    monkeypatch.setenv("REDISUS_DB_PATH", str(tmp_path / "security.db"))
    monkeypatch.setenv("CLINICAL_API_REQUIRE_AUTH", "1")

    from apps.api.app import create_app

    app = create_app()
    app.config["TESTING"] = True
    app.config["REDISUS_AUTH_VERIFIER"] = lambda token: _build_user("user-1")
    db = app.extensions["redisus_db"]
    db.save_patient(PatientRecord(id="p001", name="Paciente 1", metadata={"owner_uid": "user-1"}))

    with app.test_client() as client:
        first = client.post(
            "/api/v1/evaluations",
            headers={**_build_headers(), "Content-Type": "application/json"},
            json={
                "patient_id": "p001",
                "evaluation_date": "2026-04-01",
                "wound_area_cm2": 8.0,
                "pain_score": 5,
            },
        ).get_json()
        client.post(
            "/api/v1/evaluations",
            headers={**_build_headers(), "Content-Type": "application/json"},
            json={
                "patient_id": "p001",
                "case_id": first["case_id"],
                "evaluation_date": "2026-04-07",
                "wound_area_cm2": 6.0,
                "pain_score": 3,
            },
        )

        report_response = client.post(
            "/api/v1/reports/generate",
            headers={**_build_headers(), "Content-Type": "application/json"},
            json={
                "patient_id": "p001",
                "case_id": first["case_id"],
                "report_type": "evolution",
                "professional": "frontend-spoof",
            },
        )

    assert report_response.status_code == 400
    assert "Extra inputs are not permitted" in report_response.get_json()["detail"]
