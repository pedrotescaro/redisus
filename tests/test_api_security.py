import io
import time

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


def test_researcher_is_read_only_for_clinical_writes(tmp_path, monkeypatch):
    monkeypatch.setenv("REDISUS_DB_PATH", str(tmp_path / "security.db"))
    monkeypatch.setenv("CLINICAL_API_REQUIRE_AUTH", "1")

    from apps.api.app import create_app

    app = create_app()
    app.config["TESTING"] = True
    app.config["REDISUS_AUTH_VERIFIER"] = lambda token: _build_user("user-1", role="researcher")
    db = app.extensions["redisus_db"]
    db.save_patient(PatientRecord(id="p001", name="Paciente 1", metadata={"owner_uid": "user-1"}))

    with app.test_client() as client:
        list_response = client.get("/api/patients", headers=_build_headers())
        create_response = client.post(
            "/api/v1/evaluations",
            headers={**_build_headers(), "Content-Type": "application/json"},
            json={
                "patient_id": "p001",
                "evaluation_date": "2026-04-07",
                "wound_area_cm2": 8.0,
            },
        )

    assert list_response.status_code == 200
    assert create_response.status_code == 403
    assert "requires nurse, doctor, or admin role" in create_response.get_json()["detail"]


def test_researcher_can_read_timeline_when_scoped(tmp_path, monkeypatch):
    monkeypatch.setenv("REDISUS_DB_PATH", str(tmp_path / "security.db"))
    monkeypatch.setenv("CLINICAL_API_REQUIRE_AUTH", "1")

    from apps.api.app import create_app

    def verifier(token: str):
        if token == "nurse-token":
            return _build_user("user-1", role="nurse")
        return _build_user("user-1", role="researcher")

    app = create_app()
    app.config["TESTING"] = True
    app.config["REDISUS_AUTH_VERIFIER"] = verifier
    db = app.extensions["redisus_db"]
    db.save_patient(PatientRecord(id="p001", name="Paciente 1", metadata={"owner_uid": "user-1"}))

    with app.test_client() as client:
        create_response = client.post(
            "/api/v1/evaluations",
            headers={**_build_headers("nurse-token"), "Content-Type": "application/json"},
            json={
                "patient_id": "p001",
                "evaluation_date": "2026-04-07",
                "wound_area_cm2": 8.0,
                "pain_score": 5,
            },
        )
        assert create_response.status_code == 201
        evaluation = create_response.get_json()
        upload_response = client.post(
            f"/api/v1/evaluations/{evaluation['id']}/images",
            headers=_build_headers("nurse-token"),
            data={"imageRole": "clinical", "image": (io.BytesIO(_png_bytes()), "ferida.png")},
            content_type="multipart/form-data",
        )
        assert upload_response.status_code == 201
        analyze_response = client.post(
            f"/api/v1/evaluations/{evaluation['id']}/analyze",
            headers={**_build_headers("nurse-token"), "Content-Type": "application/json"},
            json={},
        )
        assert analyze_response.status_code == 202
        job_id = analyze_response.get_json()["jobId"]

        for _ in range(15):
            job_payload = client.get(f"/api/v1/analysis-jobs/{job_id}", headers=_build_headers("nurse-token")).get_json()
            if job_payload["job"]["status"] == "completed":
                break
            time.sleep(0.2)
        else:
            raise AssertionError("Care plan was not created in time")

        timeline_response = client.get(
            f"/api/v1/lesions/{evaluation['case_id']}/timeline",
            headers=_build_headers("researcher-token"),
        )

    assert timeline_response.status_code == 200
    timeline = timeline_response.get_json()
    assert timeline["lesion"]["id"] == evaluation["case_id"]


def _create_case_with_pipeline(client, *, token: str = "nurse-token") -> dict:
    create_response = client.post(
        "/api/v1/evaluations",
        headers={**_build_headers(token), "Content-Type": "application/json"},
        json={
            "patient_id": "p001",
            "evaluation_date": "2026-04-07",
            "wound_area_cm2": 8.0,
            "pain_score": 5,
            "depth_mm": 7.0,
        },
    )
    assert create_response.status_code == 201
    evaluation = create_response.get_json()
    upload_response = client.post(
        f"/api/v1/evaluations/{evaluation['id']}/images",
        headers=_build_headers(token),
        data={"imageRole": "clinical", "image": (io.BytesIO(_png_bytes()), "ferida.png")},
        content_type="multipart/form-data",
    )
    assert upload_response.status_code == 201
    analyze_response = client.post(
        f"/api/v1/evaluations/{evaluation['id']}/analyze",
        headers={**_build_headers(token), "Content-Type": "application/json"},
        json={},
    )
    assert analyze_response.status_code == 202
    job_id = analyze_response.get_json()["jobId"]

    for _ in range(15):
        job_payload = client.get(f"/api/v1/analysis-jobs/{job_id}", headers=_build_headers(token)).get_json()
        if job_payload["job"]["status"] == "completed":
            break
        time.sleep(0.2)
    else:
        raise AssertionError("AI pipeline did not complete in time")

    timeline_response = client.get(
        f"/api/v1/lesions/{evaluation['case_id']}/timeline",
        headers=_build_headers(token),
    )
    assert timeline_response.status_code == 200
    timeline = timeline_response.get_json()
    return {"evaluation": evaluation, "timeline": timeline}


def test_nurse_can_acknowledge_alert_and_complete_nurse_follow_up(tmp_path, monkeypatch):
    monkeypatch.setenv("REDISUS_DB_PATH", str(tmp_path / "queue-actions.db"))
    monkeypatch.setenv("CLINICAL_API_REQUIRE_AUTH", "1")

    from apps.api.app import create_app

    def verifier(token: str):
        if token == "doctor-token":
            return _build_user("user-1", role="doctor")
        return _build_user("user-1", role="nurse")

    app = create_app()
    app.config["TESTING"] = True
    app.config["REDISUS_AUTH_VERIFIER"] = verifier
    db = app.extensions["redisus_db"]
    db.save_patient(PatientRecord(id="p001", name="Paciente 1", metadata={"owner_uid": "user-1"}))

    with app.test_client() as client:
        payload = _create_case_with_pipeline(client, token="nurse-token")
        evaluation = payload["evaluation"]
        timeline = payload["timeline"]
        high_alert = next(
            alert for alert in timeline["alerts"] if str(alert.get("severity")).lower() in {"alto", "critico", "high", "critical"}
        )
        alert_id = high_alert["id"]
        care_plan_id = timeline["care_plans"][0]["id"]

        create_follow_up = client.post(
            "/api/v1/follow-ups",
            headers={**_build_headers("nurse-token"), "Content-Type": "application/json"},
            json={
                "patient_id": "p001",
                "lesion_id": evaluation["case_id"],
                "care_plan_id": care_plan_id,
                "scheduled_for": "2026-04-08",
                "assigned_role": "nurse",
                "reason": "curativo",
            },
        )
        assert create_follow_up.status_code == 201
        follow_up_id = create_follow_up.get_json()["id"]

        ack_response = client.patch(
            f"/api/v1/alerts/{alert_id}/acknowledge",
            headers={**_build_headers("nurse-token"), "Content-Type": "application/json"},
            json={"notes": "Alerta recebido"},
        )
        complete_response = client.patch(
            f"/api/v1/follow-ups/{follow_up_id}/complete",
            headers={**_build_headers("nurse-token"), "Content-Type": "application/json"},
            json={"status": "completed", "notes": "Follow-up realizado"},
        )
        audit_response = client.get(
            f"/api/v1/lesions/{evaluation['case_id']}/audit",
            headers=_build_headers("nurse-token"),
        )

    assert ack_response.status_code == 200
    assert ack_response.get_json()["status"] == "acknowledged"
    assert complete_response.status_code == 200
    assert complete_response.get_json()["status"] == "completed"
    assert audit_response.status_code == 200
    actions = {item["action"] for item in audit_response.get_json()}
    assert "alert_acknowledged" in actions
    assert "follow_up_completed" in actions


def test_doctor_can_resolve_alert_and_update_care_plan(tmp_path, monkeypatch):
    monkeypatch.setenv("REDISUS_DB_PATH", str(tmp_path / "queue-doctor.db"))
    monkeypatch.setenv("CLINICAL_API_REQUIRE_AUTH", "1")

    from apps.api.app import create_app

    def verifier(token: str):
        if token == "doctor-token":
            return _build_user("user-1", role="doctor")
        return _build_user("user-1", role="nurse")

    app = create_app()
    app.config["TESTING"] = True
    app.config["REDISUS_AUTH_VERIFIER"] = verifier
    db = app.extensions["redisus_db"]
    db.save_patient(PatientRecord(id="p001", name="Paciente 1", metadata={"owner_uid": "user-1"}))

    with app.test_client() as client:
        payload = _create_case_with_pipeline(client, token="nurse-token")
        evaluation = payload["evaluation"]
        timeline = payload["timeline"]
        high_alert = next(
            alert for alert in timeline["alerts"] if str(alert.get("severity")).lower() in {"alto", "critico", "high", "critical"}
        )
        alert_id = high_alert["id"]
        care_plan_id = timeline["care_plans"][0]["id"]

        resolve_response = client.patch(
            f"/api/v1/alerts/{alert_id}/resolve",
            headers={**_build_headers("doctor-token"), "Content-Type": "application/json"},
            json={"notes": "Revisado pelo médico"},
        )
        update_plan_response = client.patch(
            f"/api/v1/care-plans/{care_plan_id}",
            headers={**_build_headers("doctor-token"), "Content-Type": "application/json"},
            json={"risk_level": "alto", "review_due_date": "2026-04-09", "notes": "Plano ajustado"},
        )
        case_detail_response = client.get(
            f"/api/dashboard/cases/{evaluation['case_id']}?roleView=doctor",
            headers=_build_headers("doctor-token"),
        )

    assert resolve_response.status_code == 200
    assert resolve_response.get_json()["status"] == "resolved"
    assert update_plan_response.status_code == 200
    assert update_plan_response.get_json()["review_due_date"] == "2026-04-09"
    assert case_detail_response.status_code == 200
    assert case_detail_response.get_json()["clinical_summary"]["available_actions"]


def test_nurse_cannot_resolve_high_alert_or_update_high_risk_plan(tmp_path, monkeypatch):
    monkeypatch.setenv("REDISUS_DB_PATH", str(tmp_path / "queue-blocks.db"))
    monkeypatch.setenv("CLINICAL_API_REQUIRE_AUTH", "1")

    from apps.api.app import create_app

    app = create_app()
    app.config["TESTING"] = True
    app.config["REDISUS_AUTH_VERIFIER"] = lambda token: _build_user("user-1", role="nurse")
    db = app.extensions["redisus_db"]
    db.save_patient(PatientRecord(id="p001", name="Paciente 1", metadata={"owner_uid": "user-1"}))

    with app.test_client() as client:
        payload = _create_case_with_pipeline(client, token="valid-user-1")
        timeline = payload["timeline"]
        high_alert = next(
            alert for alert in timeline["alerts"] if str(alert.get("severity")).lower() in {"alto", "critico", "high", "critical"}
        )
        alert_id = high_alert["id"]
        care_plan_id = timeline["care_plans"][0]["id"]

        resolve_response = client.patch(
            f"/api/v1/alerts/{alert_id}/resolve",
            headers={**_build_headers("valid-user-1"), "Content-Type": "application/json"},
            json={"notes": "Tentativa de resolução"},
        )
        update_plan_response = client.patch(
            f"/api/v1/care-plans/{care_plan_id}",
            headers={**_build_headers("valid-user-1"), "Content-Type": "application/json"},
            json={"risk_level": "critico", "notes": "Tentativa de edição"},
        )

    assert resolve_response.status_code == 403
    assert "requires doctor/admin" in resolve_response.get_json()["detail"]
    assert update_plan_response.status_code == 403
    assert "requires doctor or admin" in update_plan_response.get_json()["detail"]
