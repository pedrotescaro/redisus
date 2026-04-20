from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping

from .client import AbstractFHIRClient
from .models import compact_dict, fhir_now


class FHIRPublicationError(RuntimeError):
    pass


@dataclass(slots=True)
class FHIRPublicationResult:
    status: str
    publication_id: str
    idempotency_key: str
    bundle_hash: str
    attempts: int
    target: str
    published_at: str
    audit_log_path: str
    state_path: str
    response: dict[str, Any] | None = None
    metadata: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return compact_dict(
            {
                "status": self.status,
                "publication_id": self.publication_id,
                "idempotency_key": self.idempotency_key,
                "bundle_hash": self.bundle_hash,
                "attempts": self.attempts,
                "target": self.target,
                "published_at": self.published_at,
                "audit_log_path": self.audit_log_path,
                "state_path": self.state_path,
                "response": self.response,
                "metadata": self.metadata,
            }
        )


class FHIRPublicationService:
    def __init__(
        self,
        client: AbstractFHIRClient,
        *,
        audit_dir: str | Path = "artifacts/fhir_publication",
        max_retries: int = 2,
        retry_delay_seconds: float = 0.5,
        sleep_func: Callable[[float], None] | None = None,
    ):
        self.client = client
        self.audit_dir = Path(audit_dir)
        self.audit_dir.mkdir(parents=True, exist_ok=True)
        self.max_retries = max(0, int(max_retries))
        self.retry_delay_seconds = max(0.0, float(retry_delay_seconds))
        self.sleep_func = sleep_func or time.sleep
        self.audit_log_path = self.audit_dir / "publication_audit.jsonl"
        self.state_path = self.audit_dir / "publication_index.json"

    def publish_export(
        self,
        export_payload: Mapping[str, Any],
        *,
        publication_key: str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> FHIRPublicationResult:
        bundle = export_payload.get("bundle")
        if not isinstance(bundle, Mapping):
            raise FHIRPublicationError("export payload must contain a FHIR bundle in export_payload['bundle']")

        export_metadata = {
            "case_id": export_payload.get("case_id"),
            "patient_id": export_payload.get("patient_id"),
            "evaluation_id": export_payload.get("evaluation_id"),
            "care_plan_id": export_payload.get("care_plan_id"),
            "bundle_type": export_payload.get("bundle_type"),
            "resource_count": export_payload.get("resource_count"),
        }
        merged_metadata = dict(metadata or {})
        merged_metadata.update({key: value for key, value in export_metadata.items() if value not in (None, "", [], {})})
        return self.publish_bundle(
            bundle,
            case_id=str(export_payload.get("case_id") or "").strip() or None,
            evaluation_id=str(export_payload.get("evaluation_id") or "").strip() or None,
            publication_key=publication_key,
            metadata=merged_metadata,
        )

    def publish_bundle(
        self,
        bundle: Mapping[str, Any],
        *,
        case_id: str | None = None,
        evaluation_id: str | None = None,
        publication_key: str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> FHIRPublicationResult:
        payload = dict(bundle)
        self.client.validate_bundle_before_send(payload)

        target = self._resolve_target()
        bundle_hash = self._hash_payload(payload)
        resolved_metadata = dict(metadata or {})
        if case_id:
            resolved_metadata.setdefault("case_id", case_id)
        if evaluation_id:
            resolved_metadata.setdefault("evaluation_id", evaluation_id)

        idempotency_key = publication_key or self._build_idempotency_key(
            target=target,
            bundle_hash=bundle_hash,
            case_id=case_id,
            evaluation_id=evaluation_id,
        )
        publication_id = f"publication-{idempotency_key[:16]}"

        state = self._load_state()
        existing = state.get(idempotency_key)
        if existing and existing.get("status") == "published" and existing.get("bundle_hash") == bundle_hash:
            published_at = str(existing.get("published_at") or fhir_now())
            self._append_audit_event(
                event_type="idempotent_skip",
                publication_id=publication_id,
                idempotency_key=idempotency_key,
                bundle_hash=bundle_hash,
                target=target,
                attempts=int(existing.get("attempts") or 1),
                metadata=resolved_metadata,
            )
            return FHIRPublicationResult(
                status="skipped",
                publication_id=publication_id,
                idempotency_key=idempotency_key,
                bundle_hash=bundle_hash,
                attempts=int(existing.get("attempts") or 1),
                target=target,
                published_at=published_at,
                audit_log_path=str(self.audit_log_path),
                state_path=str(self.state_path),
                response=dict(existing.get("response") or {}),
                metadata=resolved_metadata or None,
            )

        total_attempts = self.max_retries + 1
        last_error: Exception | None = None
        for attempt in range(1, total_attempts + 1):
            self._append_audit_event(
                event_type="attempt_started",
                publication_id=publication_id,
                idempotency_key=idempotency_key,
                bundle_hash=bundle_hash,
                target=target,
                attempts=attempt,
                metadata=resolved_metadata,
            )
            try:
                response = self.client.send_bundle(payload)
                published_at = fhir_now()
                record = {
                    "status": "published",
                    "publication_id": publication_id,
                    "idempotency_key": idempotency_key,
                    "bundle_hash": bundle_hash,
                    "attempts": attempt,
                    "target": target,
                    "published_at": published_at,
                    "response": dict(response or {}),
                    "metadata": resolved_metadata,
                }
                state[idempotency_key] = record
                self._save_state(state)
                self._append_audit_event(
                    event_type="published",
                    publication_id=publication_id,
                    idempotency_key=idempotency_key,
                    bundle_hash=bundle_hash,
                    target=target,
                    attempts=attempt,
                    metadata=resolved_metadata,
                    response=response,
                )
                return FHIRPublicationResult(
                    status="published",
                    publication_id=publication_id,
                    idempotency_key=idempotency_key,
                    bundle_hash=bundle_hash,
                    attempts=attempt,
                    target=target,
                    published_at=published_at,
                    audit_log_path=str(self.audit_log_path),
                    state_path=str(self.state_path),
                    response=dict(response or {}),
                    metadata=resolved_metadata or None,
                )
            except Exception as exc:  # pragma: no cover - exercised via tests with fake clients
                last_error = exc
                self._append_audit_event(
                    event_type="attempt_failed",
                    publication_id=publication_id,
                    idempotency_key=idempotency_key,
                    bundle_hash=bundle_hash,
                    target=target,
                    attempts=attempt,
                    metadata=resolved_metadata,
                    error=str(exc),
                )
                if attempt < total_attempts and self.retry_delay_seconds:
                    self.sleep_func(self.retry_delay_seconds)

        raise FHIRPublicationError(
            f"Failed to publish FHIR bundle after {total_attempts} attempts to {target}"
        ) from last_error

    def _build_idempotency_key(
        self,
        *,
        target: str,
        bundle_hash: str,
        case_id: str | None = None,
        evaluation_id: str | None = None,
    ) -> str:
        fingerprint = {
            "target": target,
            "case_id": case_id,
            "evaluation_id": evaluation_id,
            "bundle_hash": bundle_hash,
        }
        return hashlib.sha256(self._canonical_json(fingerprint).encode("utf-8")).hexdigest()

    def _hash_payload(self, bundle: Mapping[str, Any]) -> str:
        normalized = self._normalize_for_hash(bundle)
        return hashlib.sha256(self._canonical_json(normalized).encode("utf-8")).hexdigest()

    def _normalize_for_hash(self, value: Any) -> Any:
        if isinstance(value, Mapping):
            normalized: dict[str, Any] = {}
            for key in sorted(value.keys()):
                if key in {"lastUpdated", "timestamp"}:
                    continue
                normalized[key] = self._normalize_for_hash(value[key])
            return normalized
        if isinstance(value, list):
            return [self._normalize_for_hash(item) for item in value]
        return value

    def _canonical_json(self, payload: Any) -> str:
        return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)

    def _resolve_target(self) -> str:
        return str(
            getattr(self.client, "fhir_store_url", None)
            or getattr(self.client, "server_url", None)
            or self.client.__class__.__name__
        )

    def _load_state(self) -> dict[str, Any]:
        if not self.state_path.exists():
            return {}
        try:
            payload = json.loads(self.state_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
        return payload if isinstance(payload, dict) else {}

    def _save_state(self, state: Mapping[str, Any]) -> None:
        self.state_path.write_text(
            json.dumps(dict(state), indent=2, ensure_ascii=False, sort_keys=True),
            encoding="utf-8",
        )

    def _append_audit_event(
        self,
        *,
        event_type: str,
        publication_id: str,
        idempotency_key: str,
        bundle_hash: str,
        target: str,
        attempts: int,
        metadata: Mapping[str, Any] | None = None,
        response: Mapping[str, Any] | None = None,
        error: str | None = None,
    ) -> None:
        event = compact_dict(
            {
                "event_type": event_type,
                "recorded_at": fhir_now(),
                "publication_id": publication_id,
                "idempotency_key": idempotency_key,
                "bundle_hash": bundle_hash,
                "target": target,
                "attempts": attempts,
                "metadata": dict(metadata or {}),
                "response": dict(response or {}),
                "error": error,
            }
        )
        with self.audit_log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False) + "\n")
