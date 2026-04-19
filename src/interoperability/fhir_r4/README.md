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
- `Observation`
- `Condition`
- `DiagnosticReport`
- `CarePlan`
- `Bundle` for case packaging and transaction submission

## Mapping scope

The mapper is intentionally focused on the REDISUS domain already present in the
repository:

- wound analysis values
- tissue distribution
- wound area and depth
- PUSH and BWAT scores
- AI classification and confidence
- risk level and recommendations
- clinical images attached to `DiagnosticReport.presentedForm`

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

## External dependency boundaries

This package does not implement a real RNDS integration. It only prepares the
architecture for future connectors by keeping the following pieces isolated:

- FHIR resource construction
- transport client abstraction
- cloud adapter boundary
- validation boundary

Future RNDS work should plug into the client/adapter layer instead of changing
the domain mapper directly.
