import io
import time

from PIL import Image

from src.data.database import PatientRecord


def _png_bytes(color: tuple[int, int, int] = (0, 120, 180)) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (32, 32), color=color).save(buffer, format="PNG")
    return buffer.getvalue()


def _build_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _build_user(uid: str, *, name: str, role: str, unit_id: str, team_id: str) -> dict[str, str]:
    return {
        "uid": uid,
        "email": f"{uid}@example.test",
        "name": name,
        "role": role,
        "unit_id": unit_id,
        "team_id": team_id,
    }


def _wait_for_job_completion(client, job_id: str, token: str) -> None:
    for _ in range(20):
        payload = client.get(f"/api/v1/analysis-jobs/{job_id}", headers=_build_headers(token)).get_json()
        if payload["job"]["status"] == "completed":
            return
        time.sleep(0.2)
    raise AssertionError("AI pipeline did not complete in time")


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
            "wound_type": "pe_diabetico",
            "wound_location": "pe direito",
        },
    )
    assert create_response.status_code == 201
    evaluation = create_response.get_json()

    upload_response = client.post(
        f"/api/v1/evaluations/{evaluation['id']}/images",
        headers=_build_headers(token),
        data={"imageRole": "clinical", "image": (io.BytesIO(_png_bytes((0, 120, 180))), "ferida-1.png")},
        content_type="multipart/form-data",
    )
    assert upload_response.status_code == 201

    analyze_response = client.post(
        f"/api/v1/evaluations/{evaluation['id']}/analyze",
        headers={**_build_headers(token), "Content-Type": "application/json"},
        json={},
    )
    assert analyze_response.status_code == 202
    _wait_for_job_completion(client, analyze_response.get_json()["jobId"], token)

    timeline_response = client.get(
        f"/api/v1/lesions/{evaluation['case_id']}/timeline",
        headers=_build_headers(token),
    )
    assert timeline_response.status_code == 200
    return {"evaluation": evaluation, "timeline": timeline_response.get_json()}


def _create_follow_up_evaluation(client, *, case_id: str, token: str = "nurse-token") -> dict:
    create_response = client.post(
        "/api/v1/evaluations",
        headers={**_build_headers(token), "Content-Type": "application/json"},
        json={
            "patient_id": "p001",
            "case_id": case_id,
            "evaluation_date": "2026-04-10",
            "wound_area_cm2": 6.5,
            "pain_score": 3,
            "depth_mm": 5.0,
            "wound_type": "pe_diabetico",
            "wound_location": "pe direito",
        },
    )
    assert create_response.status_code == 201
    evaluation = create_response.get_json()

    upload_response = client.post(
        f"/api/v1/evaluations/{evaluation['id']}/images",
        headers=_build_headers(token),
        data={"imageRole": "clinical", "image": (io.BytesIO(_png_bytes((160, 40, 40))), "ferida-2.png")},
        content_type="multipart/form-data",
    )
    assert upload_response.status_code == 201
    return {"evaluation": evaluation, "image": upload_response.get_json()}


def test_authenticated_dashboard_e2e_supports_claim_handoff_and_image_compare(tmp_path, monkeypatch):
    monkeypatch.setenv("REDISUS_DB_PATH", str(tmp_path / "dashboard-e2e.db"))
    monkeypatch.setenv("CLINICAL_API_REQUIRE_AUTH", "1")

    from apps.api.app import create_app

    def verifier(token: str):
        if token == "doctor-token":
            return _build_user("user-2", name="Dr Bruno", role="doctor", unit_id="UBS-01", team_id="Equipe-A")
        return _build_user("user-1", name="Enf Ana", role="nurse", unit_id="UBS-01", team_id="Equipe-A")

    app = create_app()
    app.config["TESTING"] = True
    app.config["REDISUS_AUTH_VERIFIER"] = verifier
    db = app.extensions["redisus_db"]
    db.save_patient(
        PatientRecord(
            id="p001",
            name="Paciente 1",
            unit_id="UBS-01",
            team_id="Equipe-A",
            metadata={"owner_uid": "user-1"},
        )
    )

    with app.test_client() as client:
        payload = _create_case_with_pipeline(client, token="nurse-token")
        evaluation = payload["evaluation"]
        timeline = payload["timeline"]
        case_id = evaluation["case_id"]
        high_alert = next(
            alert for alert in timeline["alerts"] if str(alert.get("severity")).lower() in {"alto", "critico", "high", "critical"}
        )

        second_eval = _create_follow_up_evaluation(client, case_id=case_id, token="nurse-token")

        claim_case = client.patch(
            f"/api/v1/lesions/{case_id}/claim",
            headers={**_build_headers("nurse-token"), "Content-Type": "application/json"},
            json={"notes": "Assumindo o caso para triagem inicial"},
        )
        handoff_case = client.patch(
            f"/api/v1/lesions/{case_id}/handoff",
            headers={**_build_headers("nurse-token"), "Content-Type": "application/json"},
            json={
                "assigned_to_uid": "user-2",
                "assigned_to_name": "Dr Bruno",
                "assigned_to_role": "doctor",
                "unit_id": "UBS-01",
                "team_id": "Equipe-A",
                "notes": "Escalonando para avaliação médica",
            },
        )
        claim_alert = client.patch(
            f"/api/v1/alerts/{high_alert['id']}/claim",
            headers={**_build_headers("nurse-token"), "Content-Type": "application/json"},
            json={"notes": "Assumindo o alerta para triagem"},
        )
        handoff_alert = client.patch(
            f"/api/v1/alerts/{high_alert['id']}/handoff",
            headers={**_build_headers("nurse-token"), "Content-Type": "application/json"},
            json={
                "assigned_to_uid": "user-2",
                "assigned_to_name": "Dr Bruno",
                "assigned_to_role": "doctor",
                "notes": "Alerta precisa de decisão médica",
            },
        )

        queue_response = client.get(
            "/api/dashboard/clinical-queue?roleView=doctor",
            headers=_build_headers("doctor-token"),
        )
        case_detail_response = client.get(
            f"/api/dashboard/cases/{case_id}?roleView=doctor",
            headers=_build_headers("doctor-token"),
        )
        image_content_response = client.get(
            f"/api/v1/images/{second_eval['image']['id']}/content",
            headers=_build_headers("doctor-token"),
        )

    assert claim_case.status_code == 200
    assert handoff_case.status_code == 200
    assert claim_alert.status_code == 200
    assert handoff_alert.status_code == 200

    queue_payload = queue_response.get_json()
    assert queue_response.status_code == 200
    assert queue_payload["items"][0]["assigned_to_uid"] == "user-2"
    assert queue_payload["items"][0]["assigned_to_name"] == "Dr Bruno"
    assert queue_payload["items"][0]["unit"] == "UBS-01"
    assert queue_payload["items"][0]["team"] == "Equipe-A"

    case_payload = case_detail_response.get_json()
    assert case_detail_response.status_code == 200
    assert case_payload["ownership"]["case"]["uid"] == "user-2"
    assert case_payload["ownership"]["case"]["name"] == "Dr Bruno"
    assert case_payload["ownership"]["primary_alert"]["uid"] == "user-2"
    assert case_payload["before_vs_after"]["latest_image_url"]
    assert case_payload["before_vs_after"]["previous_image_url"]

    assert image_content_response.status_code == 200
    assert image_content_response.mimetype == "image/png"


def test_authenticated_actions_require_notes(tmp_path, monkeypatch):
    monkeypatch.setenv("REDISUS_DB_PATH", str(tmp_path / "dashboard-notes.db"))
    monkeypatch.setenv("CLINICAL_API_REQUIRE_AUTH", "1")

    from apps.api.app import create_app

    def verifier(token: str):
        if token == "doctor-token":
            return _build_user("user-2", name="Dr Bruno", role="doctor", unit_id="UBS-01", team_id="Equipe-A")
        return _build_user("user-1", name="Enf Ana", role="nurse", unit_id="UBS-01", team_id="Equipe-A")

    app = create_app()
    app.config["TESTING"] = True
    app.config["REDISUS_AUTH_VERIFIER"] = verifier
    db = app.extensions["redisus_db"]
    db.save_patient(
        PatientRecord(
            id="p001",
            name="Paciente 1",
            unit_id="UBS-01",
            team_id="Equipe-A",
            metadata={"owner_uid": "user-1"},
        )
    )

    with app.test_client() as client:
        payload = _create_case_with_pipeline(client, token="nurse-token")
        case_id = payload["evaluation"]["case_id"]
        timeline = payload["timeline"]
        alert_id = timeline["alerts"][0]["id"]
        follow_up_id = timeline["follow_ups"][0]["id"]
        care_plan_id = timeline["care_plans"][0]["id"]

        claim_case = client.patch(
            f"/api/v1/lesions/{case_id}/claim",
            headers={**_build_headers("nurse-token"), "Content-Type": "application/json"},
            json={},
        )
        ack_alert = client.patch(
            f"/api/v1/alerts/{alert_id}/acknowledge",
            headers={**_build_headers("doctor-token"), "Content-Type": "application/json"},
            json={},
        )
        complete_follow_up = client.patch(
            f"/api/v1/follow-ups/{follow_up_id}/complete",
            headers={**_build_headers("doctor-token"), "Content-Type": "application/json"},
            json={"status": "completed"},
        )
        update_plan = client.patch(
            f"/api/v1/care-plans/{care_plan_id}",
            headers={**_build_headers("doctor-token"), "Content-Type": "application/json"},
            json={"risk_level": "alto"},
        )

    assert claim_case.status_code == 400
    assert "notes" in claim_case.get_json()["detail"]
    assert ack_alert.status_code == 400
    assert "notes" in ack_alert.get_json()["detail"]
    assert complete_follow_up.status_code == 400
    assert "notes" in complete_follow_up.get_json()["detail"]
    assert update_plan.status_code == 400
    assert "notes" in update_plan.get_json()["detail"]
