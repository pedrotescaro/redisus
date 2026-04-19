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
- body site
- risk-derived severity
- AI confidence as extension

### DiagnosticReport

Mapped REDISUS concepts:

- assessment summary
- observation reference
- condition coding summary
- recommendations
- wound image attachments through `presentedForm`

### CarePlan

Mapped REDISUS concepts:

- task list
- schedule/frequency text
- goals and alert notes
- condition relationship

## Validation approach

This first version uses minimum structural validation by default:

- required fields per resource type
- resource references where mandatory
- non-empty bundle entries

Optional validation through `fhir.resources` remains available but is not the
default execution path because local environments may carry different package
versions or FHIR model expectations.

## Google Cloud Healthcare API boundary

The Google adapter targets a FHIR store endpoint with the following shape:

`https://healthcare.googleapis.com/v1/projects/{project}/locations/{location}/datasets/{dataset}/fhirStores/{store}/fhir`

Auth is intentionally externalized:

- direct bearer token via environment variable
- ADC via `GOOGLE_APPLICATION_CREDENTIALS` when `google-auth` is installed

This keeps transport concerns out of the mapper and makes it easier to add other
destinations later.

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
- Some REDISUS scores use local code systems instead of nationally adopted terminologies.
- Images are represented as attachments in `DiagnosticReport`; a richer `Media` strategy can be added later.
- Validation is structural-first, not full profile conformance validation.
- No write path is wired into the existing clinical API yet.
