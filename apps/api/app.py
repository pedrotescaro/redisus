# -*- coding: utf-8 -*-
"""Official Flask app factory for HEAL+ / REDISUS."""

from __future__ import annotations

import os

from flask import Flask, jsonify, request
from flask_cors import CORS

from packages.clinical_domain import ClinicalAPI, ClinicalDashboard, Database
from packages.shared import load_project_env

from .routes.integration import get_integration_service_status, integration_api

load_project_env()


def create_app() -> Flask:
    app = Flask(__name__)
    app.config["JSON_AS_ASCII"] = False
    app.config["MAX_CONTENT_LENGTH"] = 20 * 1024 * 1024

    allowed_origin = os.getenv("CLINICAL_API_ALLOWED_ORIGIN", "http://localhost:3000")
    CORS(
        app,
        origins=[allowed_origin, "http://localhost:3000"],
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
    app.register_blueprint(clinical_api.blueprint)
    app.register_blueprint(integration_api)

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
        return jsonify(dashboard._get_dashboard_summary())

    @app.route("/api/patients", methods=["GET"])
    def dashboard_patients():
        return jsonify(dashboard._get_patients_list())

    @app.route("/api/patients/<patient_id>", methods=["GET"])
    def dashboard_patient_detail(patient_id: str):
        return jsonify(dashboard._get_patient_detail(patient_id))

    @app.route("/api/patients/<patient_id>/risk", methods=["GET"])
    def dashboard_patient_risk(patient_id: str):
        return jsonify(dashboard._get_patient_risk(patient_id))

    @app.route("/api/indicators", methods=["GET"])
    def dashboard_indicators():
        region = request.args.get("region", "")
        return jsonify(dashboard._get_population_indicators(region))

    @app.route("/api/alerts", methods=["GET"])
    def dashboard_alerts():
        return jsonify(dashboard._get_active_alerts())

    @app.route("/api/surveillance/heatmap", methods=["GET"])
    def dashboard_heatmap():
        condition = request.args.get("condition")
        days = int(request.args.get("days", 30))
        return jsonify(dashboard._get_heatmap_data(condition, days))

    @app.route("/api/surveillance/clusters", methods=["GET"])
    def dashboard_clusters():
        return jsonify(dashboard._get_clusters())

    @app.route("/api/reports/production", methods=["GET"])
    def dashboard_production_report():
        period = request.args.get("period", "month")
        return jsonify(dashboard._get_production_report(period))

    @app.route("/api/export/fhir/<patient_id>", methods=["GET"])
    def dashboard_export_fhir(patient_id: str):
        return jsonify(dashboard._export_fhir(patient_id))

    return app


app = create_app()


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    debug = os.getenv("FLASK_ENV", "development").lower() == "development"
    app.run(host="0.0.0.0", port=port, debug=debug)
