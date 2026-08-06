# Architecture

## Scope

Phase 1 is a modular monorepo with two Next.js clients, a FastAPI service, source-specific
Python collectors, and PostgreSQL 17. Components remain independently containerizable for
eventual Cloud Run deployment, but Phase 1 creates no cloud resources.

## Data flow

1. A collector downloads an official file through bounded, retrying HTTP.
2. The unmodified file is saved and hashed with SHA-256.
3. `source_files` stores its URL, dates, checksum, parser version, and local/cloud path.
4. `import_runs` records counts and status for one parsing attempt.
5. Valid NH rows are normalized without altering source prices and upserted by CMS CCN.
6. The API exposes active facilities through validated, paginated read endpoints.

Phase 2 quality collectors resolve official CMS CSV distributions, select an explicit measure
allowlist, and match only by exact CCN. Immutable `facility_source_observations` retain raw
records; typed `facility_quality_measure_observations` reference measure definitions, source
files, and import runs. Unknown CCNs enter a separate review queue. Public and admin Next.js
applications consume versioned FastAPI endpoints with server-side fetching.

The collector/API boundary is the database. This keeps collection failures out of request
paths and permits independent scheduling. SQLAlchemy models are the application schema;
Alembic migrations are the deployment record. Future collectors must preserve the same
provenance contract.

## Expansion

State filtering is data-driven; geographic expansion does not require new facility tables.
Pricing domains should receive separate source-bound fact tables in later phases.
The empty orchestrator and collector directories document planned boundaries, not incomplete
Phase 1 features.
