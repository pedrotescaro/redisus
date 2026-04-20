# FHIR R4 Interoperability Architecture

## Placement decision

The repository already had an interoperability package at `src/interoperability`.
Instead of introducing a parallel package elsewhere, the new FHIR layer was added
as `src/interoperability/fhir_r4`.

This keeps the structure clean for three reasons:

1. Existing code already groups interoperability concerns under `src/interoperability`.
2. Legacy entry points such as `src.interoperability.fhir_client` can stay stable.
3. New FHIR-specific logic remains isolated from dashboard, ML, and care-plan code.

## Folder structure

```text
src/interoperability/fhir_r4/
  models/
  mappers/
  validators/
  client/
  adapters/google_cloud/
  examples/
```

## Data flow

The implementation follows this flow:

1. REDISUS payloads arrive from:
   - wound evaluations
   - normalized inference results from `packages/clinical_domain/workflow.py`
   - care plan payloads
   - image metadata
2. `RedisusFHIRMapper` normalizes those payloads.
3. Resource models build the FHIR JSON structure.
4. Validators perform minimum structural checks.
5. A generic client or cloud adapter sends the payload.

## Backend integration

The first backend integration point is now available in the clinical API:

- `GET /api/v1/lesions/<case_id>/fhir`

This route assembles the FHIR export from the real persisted clinical case:

- patient record
- selected evaluation, defaulting to the latest one in the lesion timeline
- stored clinical images
- latest inference result linked to the evaluation
- active or matching care plan

Supported query parameters:

- `bundleType=collection|transaction`
- `evaluationId=<evaluation_id>`
- `download=1`

## Resource mapping

### Patient

Source inputs:

- internal patient id
- CPF / CNS
- demographics
- contact and address data

### Practitioner

Mapped REDISUS concepts:

- `professional_name` from the stored evaluation
- local professional identifier when available
- professional role represented in `PractitionerRole`

### Encounter

Mapped REDISUS concepts:

- evaluation as an ambulatory encounter
- patient subject and practitioner participant
- service provider link to the mapped unit organization when available
- condition link through encounter diagnosis
- local case/evaluation identifiers for traceability
- period, reason text, wound location, and service type coding

### Observation

Mapped REDISUS concepts:

- tissue percentages
- wound area
- wound depth
- pain score
- PUSH score
- BWAT score
- REDISUS health score
- AI confidence
- risk level

### Condition

Mapped REDISUS concepts:

- wound etiology classification
- dual-use coding strategy with local REDISUS coding plus standard wound codings where already known
- body site
- risk-derived severity
- AI confidence as extension
- optional links to `Encounter` and recorder `Practitioner`

### DiagnosticReport

Mapped REDISUS concepts:

- assessment summary
- observation reference
- condition coding summary
- recommendations
- wound image linkage through `Media`
- attachment fallback through `presentedForm`
- encounter and performer linkage when available

### CarePlan

Mapped REDISUS concepts:

- task list
- schedule/frequency text
- goals and alert notes
- condition relationship
- author and encounter linkage when available

### Organization

Mapped REDISUS concepts:

- `unit_id` and `unit_name` as the primary service organization
- `team_id` and `team_name` as the care-team organization
- hierarchical relation between team and unit through `partOf`

### PractitionerRole

Mapped REDISUS concepts:

- clinical role derived from practitioner/evaluation context
- organization allocation derived from team or unit scope
- wound-care specialty placeholder prepared for future target value sets

### Media

Mapped REDISUS concepts:

- stored wound images as reusable clinical resources
- patient, encounter, operator, reason, and body-site linkage
- attachment preservation for URL, inline data, or local image path

### Provenance

Mapped REDISUS concepts:

- human authorship from the evaluating professional
- derived AI generation with model/contract version traceability
- explicit linkage between exported resources and the originating evaluation/images

## Validation approach

This first version uses minimum structural validation by default:

- required fields per resource type
- resource references where mandatory
- non-empty bundle entries

Optional validation through `fhir.resources` remains available but is not the
default execution path because local environments may carry different package
versions or target-profile expectations.

## Google Cloud Healthcare API boundary

The Google adapter targets a FHIR store endpoint with the following shape:

`https://healthcare.googleapis.com/v1/projects/{project}/locations/{location}/datasets/{dataset}/fhirStores/{store}/fhir`

Auth is intentionally externalized:

- direct bearer token via environment variable
- ADC via `GOOGLE_APPLICATION_CREDENTIALS` when `google-auth` is installed

This keeps transport concerns out of the mapper and makes it easier to add other
destinations later.

## Publication flow

The package now includes `FHIRPublicationService` as the controlled write path.
It is intentionally separate from the mapper and the API route.

Current responsibilities:

- validate bundle structure before send
- compute a stable hash ignoring volatile export timestamps
- skip duplicate publication of the same logical bundle
- retry transient failures with bounded attempts
- persist a local audit log and publication index

What is intentionally not hard-wired yet:

- asynchronous job orchestration
- persistent DB-backed publication ledger
- distributed locking
- target-specific retry policies
- operator-facing dashboards for publication status

## RNDS and other external dependencies

No real RNDS integration was created in this iteration.

Prepared dependency points:

- client abstraction for future transport adapters
- cloud adapter namespace for infrastructure-specific implementations
- local code-system namespace for REDISUS-only concepts
- clear separation between FHIR payload generation and transport

What still depends on external definition before RNDS work starts:

- official endpoint topology and authentication contract
- profile/package requirements adopted by RNDS
- required Brazilian national implementation guides
- document/media exchange rules
- consent and provenance obligations

## Known limitations of this first version

- The mapper covers the main wound case flow only.
- Several score/service/reason codings still depend on local REDISUS value sets until the external target profile is fixed.
- Validation is structural-first, not full conformance against a Brazilian production IG package.
- Publication audit is currently file-based, not yet persisted in the application database.
- No automatic publication route is wired into the existing clinical API yet.
