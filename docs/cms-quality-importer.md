# CMS quality importer

Phase 2 imports a focused MVP from five official CMS Provider Data Catalog datasets:

- Hospital General Information (`xubh-q36u`): overall hospital rating.
- Patient survey/HCAHPS Hospital (`dgck-syfz`): overall patient-experience star rating.
- Unplanned Hospital Visits (`632h-zaca`): heart-failure 30-day readmission measure.
- Complications and Deaths (`ynj2-r877`): heart-attack mortality and PSI-90 safety.
- Timely and Effective Care (`yv7e-xc69`): emergency-department timeliness.

Dataset identifiers and direct URLs are independently overridable through `.env.example`.
Without a URL override, the importer resolves the current CSV distribution from CMS metadata,
streams it with bounded size/time/retries, archives the original, and computes SHA-256.

Only exact CMS Certification Number matches create facility observations. Each selected row
retains its raw value, numeric/text interpretation, footnote, reporting period, raw payload,
payload hash, source file, and import run. A malformed row is rejected without stopping the
source. An unknown CCN creates a pending unmatched record. Identical completed source
checksums with the same parser version are skipped, so repeated imports create no duplicates.

To add a dataset, add a `QualityDataset` configuration, its deterministic field mapping and
measure allowlist, an offline fixture, matching/import tests, and documentation for unit and
directionality. Never infer a value that CMS did not publish.
