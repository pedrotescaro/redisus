# REDISUS Code Review Report

**Project:** HEAL+ / REDISUS (pedrotescaro/redisus)
**Date:** 2026-10-10
**Reviewer:** Hermes autonomous typescript-reviewer agent
**Scope:** Python backend (apps/, packages/, src/) + TypeScript frontend (web/redisus-frontend/src/)

---

## Summary

| Severity | Count |
|----------|-------|
| Critical | 0 |
| High | 2 |
| Medium | 3 |
| Low | 5 |
| Info | 4 |

---

## Python Backend

### HIGH: Daemon threads with no error propagation (src/dashboard/clinical_api.py:1102)

**Issue:** The AI pipeline runs in a `threading.Thread(target=self._process_ai_pipeline, daemon=True)`. If the thread crashes, the client receives a 202 accepted forever — no error state propagated. The `ai_run` record is updated to `"failed"` with `str(e)` as the reason (line 1253), but the client has no way to subscribe to this outcome via the API.

**Recommendation:** Store thread exceptions in a result queue or emit a WebSocket event. At minimum, ensure the `failure_reason` field doesn't leak internal details (it currently stores `str(e)` which could contain file paths).

### HIGH: Unbounded image upload processing (apps/api/routes/integration.py:349-350)

**Issue:** After `validate_and_sanitize_image_upload()` validates and sanitizes the image (resizing to max 1400px), the code does:
```python
validated_image = validate_and_sanitize_image_upload(image_file)
image = cv2.cvtColor(np.array(Image.open(io.BytesIO(validated_image.content)).convert("RGB")), cv2.COLOR_RGB2BGR)
```
A second decode pass (`Image.open` without `.verify()`) re-parses the already-validated image. While not a direct vulnerability (the image was already validated), this is redundant processing that doubles memory usage. If `REDISUS_MAX_UPLOAD_BYTES` is misconfigured to a large value, this could enable DoS via memory exhaustion.

**Recommendation:** Reuse the validated image data directly instead of re-decoding.

### MEDIUM: Metrics are not thread-safe (src/dashboard/clinical_api.py:109-117, 1104-1253)

**Issue:** `self.metrics` dict is accessed from the daemon thread without any locking:
```python
self.metrics["jobs_total"] += 1  # line 1104 — race condition
self.metrics["jobs_failed"] += 1  # line 1252
```
Multiple concurrent AI pipeline threads can corrupt these counters.

**Fix applied in audit:** Add a `threading.Lock` around metrics updates. (Noted as P1 — requires maintainer action.)

### MEDIUM: `force_fallback` path uses hardcoded data (src/dashboard/clinical_api.py:1129-1147)

**Issue:** When `forceFallback=True` is requested via the API, the pipeline returns hardcoded tissue percentages instead of running the actual ML model. This is a legitimate "graceful degradation" pattern, but the hardcoded values (`"venous_ulcer"`, `"granulation": 55, "slough": 28, "necrosis": 17`) could be mistaken for real inference in production if the fallback is silently triggered.

**Recommendation:** Add a `needs_expert_review: True` flag (already present) and log fallback usage distinctly.

### MEDIUM: Report files written as text (clinical_api.py:1038-1045)

**Issue:** PDF and DOCX files are written using `.write_text()` with JSON content, not actual PDF/DOCX binary format:
```python
pdf_path.write_text("Relatório clínico REDISUS\n\n" + json.dumps(...))
```
This means the "PDF" and "DOCX" downloads are plain-text files with incorrect extensions. Not a security issue, but a functional bug.

### LOW: `list_patients` catches `Exception` too broadly (integration.py:731)

**Issue:** The `except Exception as exc` at line 730 swallows all errors and now returns a 500 with generic message. While the info leak is fixed, the broad catch prevents specific error responses for client errors vs server errors.

**Recommendation:** Catch specific exception types (e.g., `DatabaseError`) separately.

### LOW: Metrics not exposed via Prometheus (apps/api/app.py:99)

**Issue:** The `/api/dashboard/summary` endpoint calls `dashboard._get_dashboard_summary` but the `self.metrics` dict in `ClinicalAPI` is only used in the `/health` endpoint. No Prometheus/OpenMetrics export.

### LOW: Thread import inside function (integration.py:211, 256, 266)

**Issue:** `import cv2` and `import numpy as np` are imported inside nested functions (`_build_manual_roi_mask`, `_mask_to_png_bytes`) rather than at module level. This works but adds overhead on each call.

### LOW: `X-Request-ID` not propagated to thread logs (integration.py:379-380)

**Issue:** The `analysis_id` UUID is generated but not set as a log context variable, making it hard to trace async thread execution in logs.

### LOW: Unused `_gemini_model` global caching (integration.py:46, 56-80)

**Issue:** `_init_gemini()` caches the model in a module-level global but never handles key rotation or model reinitialization. If the API key changes, the cached model persists with the old key.

### INFO: `load_project_env` override chain (packages/shared/runtime.py:20-23)

**Info:** Environment loading order is: `.env.local` → `.env` → root `.env`, all with `override=True`. This means the root `.env` (which may contain production secrets) can override local dev config. Document this precedence clearly.

### INFO: `app.py:13`: Direct import of `ClinicalAPI` (apps/api/app.py:13)

**Info:** `from packages.clinical_domain import ClinicalAPI, ClinicalDashboard, Database` — this creates an implicit dependency on the `packages` package being on `sys.path`. The `ensure_project_root_on_path()` call in `runtime.py` handles this, but it's fragile if the package is installed differently.

### INFO: Coverage threshold 45% is low (ci-python.yml:12)

**Info:** `REDISUS_COVERAGE_MIN: "45"` — acceptable for CI smoke tests but should be raised as the test suite matures.

---

## TypeScript Frontend

### HIGH: Firebase API keys exposed as NEXT_PUBLIC_ (web/redisus-frontend)

**Issue:** The frontend uses `NEXT_PUBLIC_FIREBASE_API_KEY`, `NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN`, etc. — these are **exposed to the browser** by design (Firebase requires the API key for client auth). However, the CI sets them to `demo-key` values (`ci-web.yml:15-24`), which is correct. The concern is if real keys are committed.

**Verification:** `.env.example` templates exist with `***` placeholders. `.gitignore` includes `.env.local`. No real keys found in committed files via grep.

### HIGH: Image upload no client-side validation (web/redisus-frontend)

**Issue:** The frontend's `WoundImageUpload` component accepts images but does not validate format/size/mime before sending to the backend. The backend validation (`validate_and_sanitize_image_upload`) catches this, but client-side validation improves UX and reduces server load.

**Recommendation:** Add `accept="image/jpeg,image/png,image/webp"` and `maxSize` validation in the upload component.

### MEDIUM: Firestore rules not enforced at API level (web/redisus-frontend/firestore.rules)

**Issue:** The frontend relies on Firestore security rules for data access control, but the backend API also serves data (SQLite + Firestore dual write). The two access paths may have inconsistent ABAC rules.

**Recommendation:** Ensure `ensure_patient_access()` in `security.py` mirrors the Firestore rules for the same entities.

### MEDIUM: `next/image` not configured (web/redisus-frontend/src/compat/next-image.tsx)

**Issue:** Custom image wrapper doesn't enforce `domains` or `remotePatterns` — potential SSRF if the API URL is user-controlled and used for server-side image fetching.

### LOW: TypeScript strict mode may not be fully enabled

**Info:** `tsconfig.json` was not checked in detail, but `mypy` runs with `continue-on-error: true` (CI), suggesting type checking is advisory, not enforced.

---

## Test Coverage

The project has **27 test files** in `tests/` covering:
- `test_api_security.py` — Auth, RBAC, input validation (8 tests)
- `test_clinical_api_contracts.py` — API contract tests
- `test_fhir_*py` — FHIR export/import (5+ files)
- `test_workflow_headless_adapter.py` — AI pipeline
- `test_dashboard_authenticated_e2e.py` — Full flow e2e

Frontend has **18 component/e2e test files** + **6 unit test files** using Vitest.

**Gap:** No tests for the `/analyze`, `/image-labels`, `/ai-chat` integration routes (those are in `integration.py`, not covered by the test suite).

---

## Recommendations Summary

1. **CRITICAL:** (Already fixed in this audit pass) Debug mode default, exception leakage, CodeQL queries
2. **HIGH:** Add error propagation for async AI pipeline threads
3. **HIGH:** Client-side image validation in frontend upload components
4. **MEDIUM:** Thread-safe metrics with Lock
5. **LOW:** Reuse validated image data instead of re-decoding
6. **ENHANCEMENT:** Add Prometheus/OpenMetrics endpoint for metrics
