# Local development

For Phase 4, copy the `HOSPITAL_PRICE_*` settings from `.env.example`, migrate PostgreSQL, and run `make pricing-pipeline` for offline fixtures. Before a live download, run discovery and review source coverage and sizes. `make verify-phase-4` runs fixtures twice plus the complete validation suite.

After `make db-up` and `make migrate`, initialize Phase 3 with:

```bash
uv run python -m collectors.nppes_organizations --source-file data/fixtures/nppes_organizations.json
make seed-procedure-catalog
make rebuild-search-index
make evaluate-data-health
make api
```

Run `make web` on port 3000 and `make admin` on port 3001. A clean verification uses
`make verify-phase-3`. Live NPPES verification is optional and bounded; the offline fixture is
the reproducible default. PostgreSQL 17 is required for migration/search verification.

Install Docker, Python 3.12, uv, Node.js 22, and npm. Then:

```bash
cp .env.example .env
make setup
make db-up
make migrate
uv run python -m collectors.cms_hospitals --source-file data/fixtures/cms_hospitals.csv
make api
```

PostgreSQL listens on `localhost:5432`, the API on `localhost:8000`, the public app on 3000,
and admin on 3001. The default password is deliberately local-only. Override values in the
ignored `.env` file.

Use `make test`, `make lint`, `make typecheck`, and `make build` before submitting changes.
`make db-down` stops containers without deleting the persistent database volume. To inspect
generated API documentation, open <http://localhost:8000/docs> while the API is running.
