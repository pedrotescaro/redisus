# Example artifacts

This directory contains static example JSON files generated from
`example_payloads.py`.

Files included:

- `patient_example.json`
- `practitioner_example.json`
- `encounter_example.json`
- `observation_example.json`
- `condition_example.json`
- `diagnostic_report_example.json`
- `care_plan_example.json`
- `wound_case_bundle.json`

These examples show a venous ulcer case with:

- one patient
- one practitioner responsible for the evaluation
- one ambulatory encounter for the wound reassessment
- one wound assessment observation
- one wound condition
- one diagnostic report with image attachment metadata
- one care plan
- one bundle that groups the full case

They are intentionally synthetic and should be treated as development fixtures,
not production-ready clinical content.
