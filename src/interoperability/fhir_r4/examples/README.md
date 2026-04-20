# Example artifacts

This directory contains static example JSON files generated from
`example_payloads.py`.

Files included:

- `patient_example.json`
- `organization_example.json`
- `practitioner_example.json`
- `practitioner_role_example.json`
- `encounter_example.json`
- `media_example.json`
- `observation_example.json`
- `condition_example.json`
- `diagnostic_report_example.json`
- `care_plan_example.json`
- `provenance_example.json`
- `wound_case_bundle.json`

These examples show a venous ulcer case with:

- one patient
- one health unit organization plus one care team organization inside the bundle
- one practitioner responsible for the evaluation
- one practitioner role linked to the team context
- one ambulatory encounter for the wound reassessment
- one clinical `Media` resource for the wound image
- one wound assessment observation
- one wound condition
- one diagnostic report with `Media` linkage and attachment fallback
- one care plan
- one provenance resource for human authorship plus AI-derived generation
- one bundle that groups the full case

They are intentionally synthetic and should be treated as development fixtures,
not production-ready clinical content.
