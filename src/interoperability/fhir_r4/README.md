# REDISUS FHIR R4 Layer

This package is the first functional FHIR R4 interoperability layer for REDISUS.
It lives under `src/interoperability/fhir_r4` so the new implementation stays close
to the existing interoperability package without spreading FHIR-specific logic
through the rest of the codebase.

## Package layout

- `models/`: lightweight Python structures for the main FHIR resources used here.
- `mappers/`: conversion logic from REDISUS wound assessment payloads to FHIR R4.
- `validators/`: minimum structural validation before a resource or bundle is sent.
- `client/`: abstract client plus a generic HTTP FHIR client.
- `adapters/google_cloud/`: Google Cloud Healthcare API FHIR store adapter.
- `examples/`: reusable example payloads and checked-in example JSON files.

## Supported resources

- `Patient`
- `Organization`
- `Practitioner`
- `PractitionerRole`
- `Encounter`
- `Media`
- `Observation`
- `Condition`
- `DiagnosticReport`
- `CarePlan`
- `Provenance`
- `Bundle` for case packaging and transaction submission

## Mapping scope

The mapper is intentionally focused on the REDISUS domain already present in the
repository:

- wound analysis values
- responsible practitioner and encounter context
- health unit and care-team scope derived from `unit_id` and `team_id`
- tissue distribution
- wound area and depth
- PUSH and BWAT scores
- AI classification and confidence
- risk level and recommendations
- clinical images represented as `Media` and linked from `DiagnosticReport.media`
- provenance for human evaluator and AI pipeline generation
- care-plan and report references linked back to the encounter when available

## Typical usage

```python
from src.interoperability.fhir_r4 import RedisusFHIRMapper

mapper = RedisusFHIRMapper()
bundle = mapper.map_case_to_bundle(
    patient_data=patient_data,
    evaluation_data=evaluation_data,
    inference_result=inference_result,
    care_plan_data=care_plan_data,
    bundle_type="transaction",
)
```

## Backend endpoint

The clinical API now exposes on-demand case export at:

- `GET /api/v1/lesions/<case_id>/fhir`

Supported query parameters:

- `bundleType=collection|transaction`
- `evaluationId=<evaluation_id>` to export a specific evaluation from the case
- `download=1` to return the generated FHIR bundle as a file

For backward compatibility, `src.interoperability.fhir_client.FHIRResourceBuilder`
now delegates to this package instead of maintaining a second FHIR implementation.

## Validation strategy

This first version performs minimum structural validation by default:

- required top-level fields per resource
- subject/reference presence where applicable
- bundle entry integrity

There is also optional model-based validation through `fhir.resources`, but it is
not the default because the installed package version may not match the exact R4
shape needed by this repository in every environment.

## Google Cloud adapter

`GoogleCloudHealthcareFHIRAdapter` supports two auth paths:

1. `REDISUS_FHIR_GCP_BEARER_TOKEN`
2. `GOOGLE_APPLICATION_CREDENTIALS` with `google-auth` installed

Required environment variables:

- `REDISUS_FHIR_GCP_PROJECT_ID`
- `REDISUS_FHIR_GCP_LOCATION`
- `REDISUS_FHIR_GCP_DATASET_ID`
- `REDISUS_FHIR_GCP_STORE_ID`

Optional:

- `REDISUS_FHIR_GCP_API_BASE_URL`
- `GOOGLE_OAUTH_ACCESS_TOKEN`

## Controlled publication

`FHIRPublicationService` prepares the write path to a FHIR store without coupling
the mapper to transport concerns. The service currently provides:

- bundle validation before send
- stable bundle hashing that ignores volatile timestamps
- idempotent skip for an already published logical bundle
- retry with bounded attempts
- JSON audit trail plus local publication index

Typical usage:

```python
from src.interoperability.fhir_r4 import (
    FHIRPublicationService,
    GoogleCloudHealthcareFHIRAdapter,
)

client = GoogleCloudHealthcareFHIRAdapter.from_environment()
publisher = FHIRPublicationService(client)
result = publisher.publish_bundle(bundle, case_id="case-001", evaluation_id="eval-001")
```

## External dependency boundaries

This package does not implement a real RNDS integration. It only prepares the
architecture for future connectors by keeping the following pieces isolated:

- FHIR resource construction
- transport client abstraction
- cloud adapter boundary
- controlled publication boundary with idempotency and audit
- validation boundary

Future RNDS work should plug into the client/adapter layer instead of changing
the domain mapper directly.
