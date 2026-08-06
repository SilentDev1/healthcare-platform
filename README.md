# CareCompare

CareCompare is a healthcare transparency platform foundation beginning in New Hampshire.
Phase 3 adds deterministic facility identity, a consumer procedure catalog, unified
PostgreSQL search, and data-health operations to the provenance-aware CMS foundation.

## Quick start

Prerequisites: Docker, Python 3.12, [uv](https://docs.astral.sh/uv/), Node.js 22, and npm.

```bash
cp .env.example .env
make setup
make db-up
make migrate
make import-cms-hospitals
make api
```

API docs are at <http://localhost:8000/docs>. Run `make web` for the public directory on port
3000 or `make admin` for the operations dashboard on port 3001.

After importing facilities, load the focused CMS quality datasets with
`make import-cms-quality`. For a network-free run use:

```bash
uv run python -m collectors.cms_quality --fixtures-dir data/fixtures/cms_quality
```

`make verify-phase-2` runs migrations, the quality fixtures, tests, linting, type checking,
and production builds. Unchanged fixture/source checksums are skipped intentionally.

For Phase 3, run `make import-nppes-organizations`, `make seed-procedure-catalog`,
`make rebuild-search-index`, and `make evaluate-data-health`. `make verify-phase-3` runs
the offline reproducible workflow and complete check suite. No pricing data is ingested.

## Architecture

- `apps/`: Next.js public and administrative interfaces.
- `services/api/`: FastAPI HTTP service.
- `collectors/`: source-specific facility and CMS quality ingestion jobs.
- `packages/database/`: SQLAlchemy models, sessions, and Alembic migrations.
- `packages/identity/`, `packages/search/`, `packages/data_health/`: deterministic platform services.
- `packages/shared_types/` and `packages/validation/`: shared TypeScript contracts.
- `infrastructure/`: local and future cloud infrastructure definitions.
- `docs/`: architecture, provenance, security, and operating guides.

All imported data is tied to immutable source metadata and an import run. No PHI or patient
data belongs in this system. See [local development](docs/local-development.md) and
[data provenance](docs/data-provenance.md).
