# CareCompare

CareCompare is a healthcare transparency platform foundation for comparing facility cost
and quality information, beginning in New Hampshire. Phase 1 provides provenance-aware
CMS ingestion, a PostgreSQL data model, read-only facility APIs, and two Next.js shells.

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

API docs are at <http://localhost:8000/docs>. Run `npm run dev --workspace @carecompare/web`
for the public app or the corresponding `@carecompare/admin` command for admin.

## Architecture

- `apps/`: Next.js public and administrative interfaces.
- `services/api/`: FastAPI HTTP service.
- `collectors/`: source-specific ingestion jobs.
- `packages/database/`: SQLAlchemy models, sessions, and Alembic migrations.
- `packages/shared_types/` and `packages/validation/`: shared TypeScript contracts.
- `infrastructure/`: local and future cloud infrastructure definitions.
- `docs/`: architecture, provenance, security, and operating guides.

All imported data is tied to immutable source metadata and an import run. No PHI or patient
data belongs in this system. See [local development](docs/local-development.md) and
[data provenance](docs/data-provenance.md).
