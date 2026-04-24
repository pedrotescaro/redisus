# Clinical data policy

Redisus/Heal+ must be treated as health software from the first commit. The repository must never become storage for real patient data, identifiable wound images, database dumps, operational exports, or clinical reports with personal data.

## Data classes

| Class | Examples | Git policy |
| --- | --- | --- |
| Public synthetic data | generated fixtures, tiny synthetic images, mocked payloads | allowed when documented |
| Public reference data | open terminology, public protocol tables, public schemas | allowed when license and source are documented |
| Restricted research data | curated wound datasets, benchmark splits, derived annotations | metadata only; store artifacts outside Git |
| Sensitive clinical data | patient images, identifiers, reports, timelines, FHIR exports | forbidden in Git |
| Secrets and operational data | tokens, service accounts, local databases, logs | forbidden in Git |

## Rules for clinical data

- Do not commit real patient images, even when faces are not visible.
- Do not commit CPF, CNS, phone, address, exact birth date, free-text clinical notes, or timestamps from real care events.
- Do not commit FHIR Bundles exported from real cases.
- Do not commit local SQLite databases or generated reports.
- Use synthetic identifiers and synthetic examples in tests and docs.
- Keep screenshots free of patient-identifiable data.
- Redact logs before attaching them to issues or PRs.

## Accepted examples

Examples are acceptable only when they are one of:

- fully synthetic fixtures created for tests;
- small static assets needed by the UI;
- public data with license and source documented;
- metadata manifests without the raw clinical artifact.

## External artifact storage

Raw datasets, model weights, training runs, generated reports, and validation artifacts must live outside Git. The repository should keep only:

- dataset cards in `docs/data/`;
- manifests in `data/manifests/`;
- model cards in `ml/model_cards/`;
- registry entries in `ml/registry/models.yaml`;
- checksums, provenance, license, intended use, and limitations.

## Review checklist

Before merging a PR that touches data, ML, FHIR, API payloads, reports, or frontend screenshots:

- confirm that no real clinical data is present;
- confirm that artifacts are ignored by `.gitignore`;
- confirm that Artifact Guard passes;
- confirm that model and dataset metadata were updated;
- document any exception in the PR body.

