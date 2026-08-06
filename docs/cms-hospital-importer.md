# CMS hospital importer

The importer consumes the official CMS Hospital General Information dataset (`xubh-q36u`), retains the raw
response and provenance, selects New Hampshire records, validates required identifiers and
address fields, and upserts by CMS Certification Number. Invalid rows are logged and saved to
`data/rejected/cms_hospitals/` without stopping valid rows.

Run offline validation:

```bash
uv run python -m collectors.cms_hospitals --source-file data/fixtures/cms_hospitals.csv
```

Local inputs record their absolute `file://` URI as the source URL. Supplying `--source-url`
overrides that value when a different canonical source identifier is required.

Run the configured source:

```bash
make import-cms-hospitals
```

Override a changed official endpoint with `CMS_HOSPITALS_SOURCE_URL` or `--source-url`. Tune
the bounded timeout, retry count, and maximum bytes using `.env.example`. A summary reports
read, inserted, updated, and rejected row counts. Re-running does not duplicate facilities,
though it intentionally creates a new source and import audit record.
