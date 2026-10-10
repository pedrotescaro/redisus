# REDISUS Architecture Report

**Project:** HEAL+ / REDISUS (pedrotescaro/redisus)
**Description:** Portuguese wound diagnosis platform — medical image analysis, clinical workflow management, and FHIR interoperability.
**Date:** 2026-10-10
**Auditor:** Hermes autonomous code-explorer agent

---

## High-Level Overview

Redisus is a monolingual (Portuguese) healthcare platform for wound diagnosis and clinical management. It integrates computer vision (OpenCV, YOLO), deep learning (PyTorch, MedSAM, BioMedCLIP), rule-based clinical reasoning, and FHIR R4 interoperability for medical record exchange.

**Stack:** Python 3.11 (Flask backend), Next.js 14 (React frontend), SQLite (local DB), Firestore (cloud persistence), Firebase Auth, Google Gemini API, Docker (deployment).

---

## Entry Points

| File | Purpose |
|------|---------|
| `main.py` | Primary entrypoint — launches the app |
| `apps/api/app.py:29` | Flask app factory (`create_app()`) |
| `apps/api/run.py` | Thin runner: `from apps.api.app import app; app.run()` |
| `apps/api/routes/integration.py:279` | Integration API blueprint (`/api/v1/analyze`, `/ai-chat`, `/patients`) |
| `src/dashboard/clinical_api.py:87` | Clinical API class — EHR-style endpoints (`/evaluations`, `/care-plans`, `/alerts`) |
| `heal_platform.py` | Legacy monolithic platform (backup of older architecture) |
| `heal_model_standalone.py` | Standalone wound analysis model runner |

---

## Architecture Layers

### Layer 1: Presentation (API)
- **`apps/api/app.py`** — Flask app factory with CORS, security headers, request ID tracking, rate limiting, auth enforcement via `before_request` hooks.
- **`apps/api/routes/integration.py`** — Integration API blueprint (`/api/v1`). Handles AI image analysis (`/analyze`), image labeling (`/image-labels`), and AI chat (`/ai-chat/*`).
- **`src/dashboard/clinical_api.py`** — Clinical API blueprint (`/api/v1`). Handles wound evaluations, care plans, alerts, follow-ups, FHIR export, comparative reports.

### Layer 2: Domain (Clinical)
- **`packages/clinical_domain/`** — Core clinical domain models and workflows.
  - `api.py` — Wrapper importing `ClinicalAPI` and `ClinicalDashboard` from `src/`
  - `workflow.py:387` — `build_headless_analyzer_result()` — assembles AI inference results into a standardized contract
  - `validation.py` — Pydantic models for all request payloads (with `extra="forbid"`, field constraints)
  - `database.py` — Patient/evaluation/case persistence (SQLite)
  - `models.py` — Dataclass models for clinical entities

### Layer 3: Application Core (Processing)
- **`src/processing/`** — Image preprocessing, tissue analysis, ROI segmentation
  - `clinical_wound_analyzer_core.py` — Main pipeline orchestrator
  - `dl_tissue_pipeline.py` — Deep learning tissue segmentation
  - `image_processor.py`, `roi_segmentation.py` — Preprocessing
- **`src/diagnosis/`** — Wound classification and risk stratification
  - `clinical_ml.py` — ML service wrapper
  - `pressure_injury_stage_classifier.py`
  - `tissue_segmenter.py`, `two_stage_tissue_pipeline.py`
- **`src/ai_layer/`** — AI model integrations
  - `ensemble_orchestrator.py` — Multi-model ensemble (YOLO + ResNet + DL)
  - `biomedclip_analyzer.py` — CLIP-based zero-shot classification
  - `medsam_segmenter.py` — Segment Anything for medical images
- **`src/care_plans/`** — Care plan templates and lifecycle
- **`src/presentation/`** — HTML/terminal UI rendering

### Layer 4: Data Infrastructure
- **`src/data/`** — SQLite database management, caching, export
  - `database.py:87` — Core `Database` class (2,377 lines)
- **`src/interoperability/`** — FHIR R4 integration and external systems
  - `fhir_r4/` — Complete FHIR R4 model layer, mappers, validators, client
  - `datasus_integration.py`, `esus_integration.py` — Brazilian public health systems

### Layer 5: Infrastructure
- **`packages/shared/`** — Cross-cutting utilities
  - `security.py:319` — Auth (`enforce_request_auth`), rate limiting (`enforce_rate_limit`), RBAC (`ensure_admin_access`, `ensure_patient_access`), ABAC scoping
  - `runtime.py:20` — Environment loading (`.env` chain)
- **`src/risk/`** — Risk stratification scoring
- **`src/surveillance/`** — Epidemiological surveillance
- **`src/telemedicine/`** — Teleconsultation features

### Layer 6: Frontend
- **`web/redisus-frontend/src/app/`** — Next.js 14 app with Vite
  - React components with TypeScript
  - Firebase authentication
  - Firestore real-time database
  - AI services integration (`src/services/ai/`)

---

## Execution Flow

### Wound Analysis Flow (`/api/v1/analyze`)

1. Client POSTs image to `integration_api.analyze_image()` (`integration.py:279`)
2. Auth enforced via `current_user_required()` — Firebase Bearer token verified
3. Rate limit checked (`enforce_rate_limit("analyze", 20)`)
4. Image validated and sanitized (`packages/clinical_domain/validation.py:358`):
   - JPEG/PNG/WebP only
   - Max 10MB (configurable)
   - Max 12 megapixels (configurable)
   - MIME type ↔ file extension cross-check
5. Image decoded with PIL/OpenCV → BGR array
6. Optional manual ROI masks built from user-supplied polygon points
7. `ClinicalWoundAnalyzer.analyze()` runs:
   - Body part detection
   - Tissue segmentation (DL + classical CV)
   - Wound classification (ensemble: ResNet + YOLOv8)
   - Risk scoring → alerts + care plan generation
8. Result normalized via `normalize_ai_output()` (`workflow.py:153`)
9. Analysis persisted to Firestore; image + ROI mask uploaded to GCS bucket
10. JSON response returned with inference, interpretation, and visual overlays (base64)

### Clinical Workflow Flow (`/api/v1/evaluations`)

1. `ClinicalAPI.create_evaluation()` (`clinical_api.py:336`)
2. Auth + RBAC via `ensure_clinical_write_access()`
3. Patient access verified (`ensure_patient_access()`)
4. Wound case created if new lesion
5. Evaluation saved to SQLite
6. AI analysis triggered (`/analyze`) → async thread
7. Results → Firestore + SQLite audit trail

### AI Chat Flow (`/api/v1/ai-chat`)

1. Auth enforced, rate limited (60/min)
2. Pydantic-validated `AIChatPayload` (message ≤ 4000 chars)
3. Conversation history fetched from Firestore (scoped to owner)
4. Prompt assembled with conversation context
5. Gemini 2.0 Flash called (or rule-based fallback)
6. Response + conversation saved to Firestore

---

## Key Files Table

| File | Lines | Role |
|------|-------|------|
| `src/data/database.py` | 2,377 | SQLite schema, CRUD for patients/evaluations/cases/alerts/care-plans/follow-ups/audit |
| `src/dashboard/clinical_api.py` | 1,254 | Flask blueprint with 18+ clinical API routes |
| `apps/api/routes/integration.py` | 731 | Flask blueprint with 6 integration routes (AI analysis, labeling, chat) |
| `packages/clinical_domain/workflow.py` | 732 | Result normalization, risk scoring, alert/care-plan/follow-up generation |
| `packages/clinical_domain/validation.py` | 416 | Pydantic models — `extra="forbid"`, strict field constraints |
| `packages/shared/security.py` | 399 | Auth, RBAC, rate limiting, patient scoping |
| `apps/api/app.py` | 235 | Flask factory, CORS, security headers, error handlers |
| `src/diagnosis/clinical_ml.py` | — | ML service wrapper (YOLOv8, ResNet, ensemble) |
| `src/ai_layer/ensemble_orchestrator.py` | — | Multi-model ensemble orchestration |
| `src/interoperability/fhir_r4/` | 10 files | FHIR R4 models, mappers, client, validators, terminology |
| `tests/test_api_security.py` | 489 | Security contract tests (auth, RBAC, input validation) |

---

## External Dependencies

### Runtime
- **Flask + CORS** — web framework
- **PyTorch + OpenCV + Pillow** — computer vision / ML
- **YOLOv8** — wound detection
- **MedicalSAM** — lesion segmentation
- **BioMedCLIP** — zero-shot image-text classification
- **Firebase Admin SDK** — auth, Firestore, Cloud Storage
- **google-generativeai** — Gemini API for AI chat
- **FHIR R4 client** — medical record exchange
- **SQLite3** — local relational persistence

### Development (CI)
- `requirements-ci.txt` — minimal: ruff, mypy, pytest, coverage, numpy, opencv-python-headless, Pillow, Flask, loguru, requests, python-dotenv
- `ruff` — linter/formatter
- `mypy` — type checker (continue-on-error in CI)
- `vitest` — frontend test runner (TypeScript)

---

## Patterns & Conventions

- **Zero-trust backend**: Auth enforced at `before_request` hook for all `/api/v1/` routes. Public paths: `/`, `/health`, `/api/v1/health`.
- **Pydantic validation**: All API payloads validated with `extra="forbid"` (rejects unknown fields), strict type constraints, field length limits.
- **Defense in depth**: CORS + auth + RBAC + input validation + audit logging.
- **Audit trail**: All clinical mutations (create/update/claim/handoff/resolve) recorded via `_record_audit_event()`.
- **AI pipeline as thread**: Risk analysis runs in a daemon thread, with results persisted to Firestore.
- **Dual DB**: SQLite for local development (config via `REDISUS_DB_PATH`), Firestore for production cloud sync.

---

## Recommendations

1. **Migrate rate limiting to Redis-backed** — in-memory rate limiter doesn't work across worker processes in production.
2. **Add structured audit log export** — currently SQLite-only; consider exporting to a tamper-evident log store for LGPD compliance.
3. **Add `--with-nonce` to CodeQL queries** — enhance static analysis with nonce-based query configuration.
4. **Frontend: add CSP nonce to inline scripts** — the Next.js build may inject inline scripts that the new CSP would block.
