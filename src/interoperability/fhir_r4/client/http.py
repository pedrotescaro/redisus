from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

import requests

from ..models import compact_dict
from .base import AbstractFHIRClient


class SimpleFHIRHttpClient(AbstractFHIRClient):
    def __init__(
        self,
        server_url: str,
        *,
        strict_validation: bool = False,
        timeout: int = 30,
        session: requests.Session | None = None,
        extra_headers: Mapping[str, str] | None = None,
    ):
        super().__init__(strict_validation=strict_validation)
        self.server_url = server_url.rstrip("/")
        self.timeout = timeout
        self.session = session or requests.Session()
        self.headers = {
            "Accept": "application/fhir+json",
            "Content-Type": "application/fhir+json",
        }
        if extra_headers:
            self.headers.update(dict(extra_headers))

    def send_resource(self, resource: Mapping[str, Any]) -> dict[str, Any]:
        self.validate_resource_before_send(resource)
        resource_type = str(resource["resourceType"])
        resource_id = str(resource.get("id") or "").strip()
        if resource_id:
            response = self.session.put(
                f"{self.server_url}/{resource_type}/{resource_id}",
                json=dict(resource),
                headers=self.headers,
                timeout=self.timeout,
            )
        else:
            response = self.session.post(
                f"{self.server_url}/{resource_type}",
                json=dict(resource),
                headers=self.headers,
                timeout=self.timeout,
            )
        response.raise_for_status()
        return response.json()

    def send_bundle(self, bundle: Mapping[str, Any]) -> dict[str, Any]:
        self.validate_bundle_before_send(bundle)
        response = self.session.post(
            self.server_url,
            json=dict(bundle),
            headers=self.headers,
            timeout=self.timeout,
        )
        response.raise_for_status()
        return response.json()

    def read(self, resource_type: str, resource_id: str) -> dict[str, Any] | None:
        response = self.session.get(
            f"{self.server_url}/{resource_type}/{resource_id}",
            headers=self.headers,
            timeout=self.timeout,
        )
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return response.json()

    def search(self, resource_type: str, params: Mapping[str, Any] | None = None) -> dict[str, Any]:
        response = self.session.get(
            f"{self.server_url}/{resource_type}",
            params=compact_dict(dict(params or {})),
            headers=self.headers,
            timeout=self.timeout,
        )
        response.raise_for_status()
        return response.json()

    def export_to_file(self, payload: Mapping[str, Any], output_path: str) -> str:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(dict(payload), indent=2, ensure_ascii=False), encoding="utf-8")
        return str(path)
