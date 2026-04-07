# -*- coding: utf-8 -*-
"""Official Flask app factory for HEAL+ / REDISUS."""

from __future__ import annotations

import os
import uuid

from flask import Flask, g, jsonify, request
from flask_cors import CORS
from werkzeug.exceptions import HTTPException

from packages.clinical_domain import ClinicalAPI, ClinicalDashboard, Database
from packages.shared import load_project_env
from packages.shared.security import (
    current_user_required,
    enforce_request_auth,
    ensure_admin_access,
    ensure_patient_access,
    filter_patients_for_user,
)

from .routes.integration import get_integration_service_status, integration_api

load_project_env()


def create_app() -> Flask:
    app = Flask(__name__)
    app.config["JSON_AS_ASCII"] = False
    app.config["MAX_CONTENT_LENGTH"] = 20 * 1024 * 1024
    app.config["REDISUS_MAX_UPLOAD_BYTES"] = int(os.getenv("REDISUS_MAX_UPLOAD_BYTES", str(10 * 1024 * 1024)))
    app.config["REDISUS_MAX_IMAGE_MEGAPIXELS"] = int(os.getenv("REDISUS_MAX_IMAGE_MEGAPIXELS", "12"))

    allowed_origin = os.getenv("CLINICAL_API_ALLOWED_ORIGIN", "http://localhost:3000")
    CORS(
        app,
        origins=[allowed_origin],
        allow_headers=["Content-Type", "Authorization"],
        methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        supports_credentials=True,
    )

    db_path = os.getenv("REDISUS_DB_PATH", "data/redisus.db")
    database = Database(db_path)
    dashboard = ClinicalDashboard(database=database)
    app.extensions["redisus_db"] = database
    app.extensions["redisus_dashboard"] = dashboard

    clinical_api = ClinicalAPI(database=database, service_status_provider=get_integration_service_status)
    app.extensions["redisus_auth_verifier"] = clinical_api.firebase_auth
    app.register_blueprint(clinical_api.blueprint)
    app.register_blueprint(integration_api)

    def _request_id() -> str:
        request_id = getattr(g, "redisus_request_id", None)
        if request_id:
            return request_id
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        g.redisus_request_id = request_id
        return request_id

    def _parse_positive_int(name: str, default: int, *, minimum: int = 1, maximum: int = 365) -> int:
        raw = request.args.get(name, str(default))
        try:
            value = int(raw)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{name} must be an integer") from exc
        if value < minimum or value > maximum:
            raise ValueError(f"{name} must stay between {minimum} and {maximum}")
        return value

    @app.before_request
    def enforce_api_security():
        _request_id()
        public_paths = {"/", "/health", "/api/v1/health"}
        if request.method == "OPTIONS" or request.path in public_paths:
            return None
        if request.path.startswith("/api/"):
            enforce_request_auth()
        return None

    @app.after_request
    def apply_security_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["X-Request-ID"] = _request_id()
        if request.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.errorhandler(HTTPException)
    def handle_http_exception(exc: HTTPException):
        if request.path.startswith("/api/") or request.path in {"/health", "/"}:
            return (
                jsonify(
                    {
                        "error": exc.name.lower().replace(" ", "_"),
                        "detail": exc.description,
                        "request_id": _request_id(),
                    }
                ),
                exc.code,
            )
        return exc

    @app.errorhandler(Exception)
    def handle_unexpected_exception(exc: Exception):
        if request.path.startswith("/api/") or request.path in {"/health", "/"}:
            return (
                jsonify(
                    {
                        "error": "internal_server_error",
                        "detail": "unexpected backend error",
                        "request_id": _request_id(),
                    }
                ),
                500,
            )
        raise exc

    @app.route("/", methods=["GET"])
    def index():
        return jsonify(
            {
                "name": "heal-redisus-official-api",
                "status": "ok",
                "version": "2.0.0",
                "message": "Use /api/v1/health para o healthcheck oficial.",
            }
        )

    @app.route("/health", methods=["GET"])
    def root_health():
        return jsonify(
            {
                "status": "ok",
                "api": "official",
                "healthcheck": "/api/v1/health",
            }
        )

    @app.route("/api/dashboard/summary", methods=["GET"])
    def dashboard_summary():
        ensure_admin_access()
        return jsonify(dashboard._get_dashboard_summary())

    @app.route("/api/dashboard/clinical-queue", methods=["GET"])
    def dashboard_clinical_queue():
        ensure_admin_access()
        limit = _parse_positive_int("limit", 20, minimum=1, maximum=100)
        view = request.args.get("view", "")
        return jsonify(dashboard._get_clinical_queue(limit=limit, view=view))

    @app.route("/api/patients", methods=["GET"])
    def dashboard_patients():
        user = current_user_required()
        return jsonify(filter_patients_for_user(dashboard._get_patients_list(), user=user))

    @app.route("/api/patients/<patient_id>", methods=["GET"])
    def dashboard_patient_detail(patient_id: str):
        ensure_patient_access(database, patient_id)
        return jsonify(dashboard._get_patient_detail(patient_id))

    @app.route("/api/patients/<patient_id>/risk", methods=["GET"])
    def dashboard_patient_risk(patient_id: str):
        ensure_patient_access(database, patient_id)
        return jsonify(dashboard._get_patient_risk(patient_id))

    @app.route("/api/indicators", methods=["GET"])
    def dashboard_indicators():
        ensure_admin_access()
        region = request.args.get("region", "")
        return jsonify(dashboard._get_population_indicators(region))

    @app.route("/api/alerts", methods=["GET"])
    def dashboard_alerts():
        ensure_admin_access()
        return jsonify(dashboard._get_active_alerts())

    @app.route("/api/surveillance/heatmap", methods=["GET"])
    def dashboard_heatmap():
        ensure_admin_access()
        condition = request.args.get("condition")
        days = _parse_positive_int("days", 30)
        return jsonify(dashboard._get_heatmap_data(condition, days))

    @app.route("/api/surveillance/clusters", methods=["GET"])
    def dashboard_clusters():
        ensure_admin_access()
        return jsonify(dashboard._get_clusters())

    @app.route("/api/reports/production", methods=["GET"])
    def dashboard_production_report():
        ensure_admin_access()
        period = request.args.get("period", "month")
        return jsonify(dashboard._get_production_report(period))

    @app.route("/api/export/fhir/<patient_id>", methods=["GET"])
    def dashboard_export_fhir(patient_id: str):
        ensure_patient_access(database, patient_id)
        return jsonify(dashboard._export_fhir(patient_id))

    return app


app = create_app()


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    debug = os.getenv("FLASK_ENV", "development").lower() == "development"
    app.run(host="0.0.0.0", port=port, debug=debug)
