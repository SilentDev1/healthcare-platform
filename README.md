# Carevero

Carevero is a consumer-first healthcare price-transparency and hospital-comparison
platform. It ingests public hospital machine-readable files and official CMS data,
normalizes the records into a provenance-preserving PostgreSQL model, applies publication
safety gates, and exposes the reviewed data through a FastAPI service and a Next.js public
site.

The product is currently a New Hampshire private beta. Its core search, price browsing,
facility detail, and comparison flows are anonymous and free—an account is not required.

## Local development

Prerequisites: Docker Desktop, Python 3.12+, [`uv`](https://docs.astral.sh/uv/), Node.js
22+, and npm.

```bash
cp .env.example .env
make setup
make db-up
docker compose ps
make migrate
```

Run each application in a separate terminal:

```bash
make api     # FastAPI on http://localhost:8000
make web     # public Next.js app on http://localhost:3000
make admin   # local-only admin app on http://localhost:3001
```

API documentation is available locally at <http://localhost:8000/docs>. The configured
local database is PostgreSQL 17 from [`compose.yaml`](compose.yaml).

## Verification

The primary release gate is:

```bash
make beta-gate
```

It runs Python and TypeScript tests, Ruff formatting/lint, strict MyPy, ESLint, Prettier,
TypeScript checks, production builds, the secret scan, and `npm audit`. Useful individual
commands are:

```bash
make test
make lint
make typecheck
make build
make secret-scan
make beta-data-smoke
```

The Phase 4.7 pre-commit verification (prior session) passed 116 Python tests, 22 workspace
tests, strict MyPy, Ruff, ESLint, Prettier, TypeScript, both Next.js production builds, the
secret scan, and npm audit with zero vulnerabilities. Re-run the suite after changes;
historical results are not a substitute for current verification.

To smoke-test a deployed beta, use the checked-in command rather than ad hoc fixture
fallbacks:

```bash
uv run python -m scripts.beta_smoke \
  --web-url "$PUBLIC_APP_URL" \
  --api-url "$API_PUBLIC_URL" \
  --facility-id "$KNOWN_PRICED_FACILITY_ID" \
  --missing-price-facility-id "$KNOWN_UNPRICED_FACILITY_ID"
```

## Architecture

```text
apps/web/                    Next.js consumer search, prices, compare, facilities, map
apps/admin/                  Local/internal Next.js operational dashboard
services/api/                FastAPI public and internal API boundaries
collectors/                  CMS and hospital-price acquisition/parsing
packages/database/           SQLAlchemy models and Alembic migrations (head: 0011)
packages/search/             Consumer search index and synonyms
packages/identity/           Deterministic facility and location identity resolution
packages/shared_types/       Shared TypeScript contracts
packages/validation/         Shared validation
scripts/                     Pipeline, verification, migration, and deployment tooling
infrastructure/cloudbuild/   Remote image build definitions
infrastructure/docker/       Container definitions used by Cloud Build
infrastructure/terraform/    Existing Google Cloud beta infrastructure
docs/                        Architecture, provenance, API, operations, and runbooks
```

Important domain boundaries:

- Canonical facilities and physical service locations are separate entities.
- Price sources may be associated with verified physical locations.
- Raw source data, normalized Carevero data, consumer representations, and future
  commercial analytics are conceptually separate.
- Organic price results and ranking must never be changed by future paid placement.
- Provider-supplied information must eventually remain distinguishable from independently
  collected transparency and government data.

Do not introduce speculative tables or services for future accounts, billing, RBAC,
commercial APIs, or provider products. Document extension points until a current feature
naturally needs an abstraction.

## Pricing and publication pipeline

The pipeline is:

```text
discover -> download -> parse -> normalize -> map -> review -> publish
```

Key safety properties:

- discovery is bounded to official hospital sources;
- downloads preserve checksums, source URLs, and immutable source-file metadata;
- parsing is deterministic and supports CMS HPT CSV/JSON plus approved legacy formats;
- procedure mapping uses reviewed codes/crosswalks rather than fuzzy inference;
- unresolved critical anomalies block publication;
- public APIs return only publication-gated summaries; and
- overlapping schedules retain provenance while public identities remain deduplicated.

`make pricing-pipeline` uses fixtures. Live statewide commands such as
`pipeline-discover-nh`, `pipeline-download-nh`, `pipeline-import-nh`, and
`pipeline-full-nh` affect real pipeline state and require deliberate operational review.
See [`docs/hospital-price-transparency.md`](docs/hospital-price-transparency.md),
[`docs/phase-4-2-operations.md`](docs/phase-4-2-operations.md), and
[`docs/statewide-coverage.md`](docs/statewide-coverage.md).

## Deployment

The existing private-beta architecture is:

- Cloud Run: public web and FastAPI services
- Cloud Run Jobs: hospital pricing refresh/import
- Cloud SQL: private PostgreSQL 17 with deletion protection and automated backups
- Cloud Storage: private, versioned source/provenance storage
- Cloud Scheduler: bounded refresh schedules
- Secret Manager: runtime secrets
- Artifact Registry and Cloud Build: immutable application images
- Cloud Logging/Monitoring and budget alerts: operations and cost visibility

Build images remotely from the checked-in files under `infrastructure/cloudbuild/`, tag
them with the Git SHA, and deploy immutable digests. Terraform uses the existing remote
state and project resources. A safe plan must not recreate the project, create duplicate
resources, expose Cloud SQL/storage publicly, or alter unrelated resources.

The temporary Cloud Run hostname must remain `noindex` while
`SEO_INDEXING_ENABLED=false`. A future permanent domain should require configuration
changes to `PUBLIC_APP_URL`, `API_PUBLIC_URL`, `CANONICAL_SITE_URL`, CORS/trusted hosts,
and SEO settings—not an application redesign.

## Product direction

The primary anonymous journey is:

```text
Search -> Results -> Compare -> Facility -> Understand Price -> Take Action
```

Near-term work should improve this real-data consumer experience without weakening trust.
Future consumer accounts, provider products, employer tools, analytics, and commercial
APIs are valid extension paths, but they are not permission to create unused identity,
billing, authorization, advertising, or microservice infrastructure today.

When handing off work, report exactly what changed, what was verified, whether production
or data state changed, the deployed URLs/revisions if applicable, Git status, and commit
hashes.
