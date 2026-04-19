from __future__ import annotations

import os
from typing import Any, Mapping

import requests

from ...client.base import AbstractFHIRClient


class GoogleCloudHealthcareFHIRAdapter(AbstractFHIRClient):
    CLOUD_HEALTHCARE_SCOPE = "https://www.googleapis.com/auth/cloud-healthcare"
    DEFAULT_API_BASE = "https://healthcare.googleapis.com/v1"

    def __init__(
        self,
        *,
        project_id: str,
        location: str,
        dataset_id: str,
        fhir_store_id: str,
        strict_validation: bool = False,
        timeout: int = 30,
        session: requests.Session | None = None,
        api_base_url: str | None = None,
        bearer_token: str | None = None,
    ):
        super().__init__(strict_validation=strict_validation)
        self.project_id = project_id
        self.location = location
        self.dataset_id = dataset_id
        self.fhir_store_id = fhir_store_id
        self.timeout = timeout
        self.session = session or requests.Session()
        self.api_base_url = (api_base_url or self.DEFAULT_API_BASE).rstrip("/")
        self._bearer_token = bearer_token

    @classmethod
    def from_environment(cls, *, strict_validation: bool = False) -> "GoogleCloudHealthcareFHIRAdapter":
        required = {
            "project_id": os.getenv("REDISUS_FHIR_GCP_PROJECT_ID"),
            "location": os.getenv("REDISUS_FHIR_GCP_LOCATION"),
            "dataset_id": os.getenv("REDISUS_FHIR_GCP_DATASET_ID"),
            "fhir_store_id": os.getenv("REDISUS_FHIR_GCP_STORE_ID"),
        }
        missing = [name for name, value in required.items() if not str(value or "").strip()]
        if missing:
            raise RuntimeError(
                "Missing Google Cloud Healthcare configuration: "
                + ", ".join(f"REDISUS_FHIR_GCP_{name.upper()}" for name in missing)
            )

        return cls(
            project_id=str(required["project_id"]),
            location=str(required["location"]),
            dataset_id=str(required["dataset_id"]),
            fhir_store_id=str(required["fhir_store_id"]),
            strict_validation=strict_validation,
            api_base_url=os.getenv("REDISUS_FHIR_GCP_API_BASE_URL"),
            bearer_token=os.getenv("REDISUS_FHIR_GCP_BEARER_TOKEN") or os.getenv("GOOGLE_OAUTH_ACCESS_TOKEN"),
        )

    @property
    def fhir_store_url(self) -> str:
        return (
            f"{self.api_base_url}/projects/{self.project_id}/locations/{self.location}"
            f"/datasets/{self.dataset_id}/fhirStores/{self.fhir_store_id}/fhir"
        )

    def send_resource(self, resource: Mapping[str, Any]) -> dict[str, Any]:
        self.validate_resource_before_send(resource)
        resource_type = str(resource["resourceType"])
        resource_id = str(resource.get("id") or "").strip()
        if resource_id:
            response = self.session.put(
                f"{self.fhir_store_url}/{resource_type}/{resource_id}",
                json=dict(resource),
                headers=self._headers(),
                timeout=self.timeout,
            )
        else:
            response = self.session.post(
                f"{self.fhir_store_url}/{resource_type}",
                json=dict(resource),
                headers=self._headers(),
                timeout=self.timeout,
            )
        response.raise_for_status()
        return response.json()

    def send_bundle(self, bundle: Mapping[str, Any]) -> dict[str, Any]:
        self.validate_bundle_before_send(bundle)
        response = self.session.post(
            self.fhir_store_url,
            json=dict(bundle),
            headers=self._headers(),
            timeout=self.timeout,
        )
        response.raise_for_status()
        return response.json()

    def read(self, resource_type: str, resource_id: str) -> dict[str, Any] | None:
        response = self.session.get(
            f"{self.fhir_store_url}/{resource_type}/{resource_id}",
            headers=self._headers(),
            timeout=self.timeout,
        )
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return response.json()

    def search(self, resource_type: str, params: Mapping[str, Any] | None = None) -> dict[str, Any]:
        response = self.session.get(
            f"{self.fhir_store_url}/{resource_type}",
            params=dict(params or {}),
            headers=self._headers(),
            timeout=self.timeout,
        )
        response.raise_for_status()
        return response.json()

    def _headers(self) -> dict[str, str]:
        token = self._resolve_bearer_token()
        return {
            "Authorization": f"Bearer {token}",
            "Accept": "application/fhir+json",
            "Content-Type": "application/fhir+json; charset=utf-8",
        }

    def _resolve_bearer_token(self) -> str:
        if self._bearer_token:
            return self._bearer_token

        credentials_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        if credentials_path:
            try:
                from google.auth.transport.requests import Request
                import google.auth

                credentials, _ = google.auth.default(scopes=[self.CLOUD_HEALTHCARE_SCOPE])
                credentials.refresh(Request())
                if not credentials.token:
                    raise RuntimeError("Application Default Credentials did not return an access token")
                self._bearer_token = credentials.token
                return self._bearer_token
            except ModuleNotFoundError as exc:
                raise RuntimeError(
                    "GOOGLE_APPLICATION_CREDENTIALS is set, but google-auth is not installed. "
                    "Install google-auth or provide REDISUS_FHIR_GCP_BEARER_TOKEN."
                ) from exc

        raise RuntimeError(
            "Google Cloud Healthcare adapter requires REDISUS_FHIR_GCP_BEARER_TOKEN or "
            "GOOGLE_APPLICATION_CREDENTIALS with google-auth installed."
        )
