# CareCompare

CareCompare is a healthcare price transparency platform for New Hampshire. It ingests
public hospital machine-readable files, maps them to a consumer procedure catalog, enforces
publication safety gates, and serves reviewed pricing through a Next.js public site, admin
dashboard, and FastAPI backend — all backed by PostgreSQL 17 and Alembic migrations.

## Current status (Phase 4.2)

| Metric                                 | Value          |
| -------------------------------------- | -------------- |
| NH facilities in database              | 28             |
| Facilities with discovered MRF sources | 13 (46%)       |
| Facilities with publishable pricing    | 2 (7%)         |
| Consumer procedures in catalog         | 50             |
| Procedures with publishable prices     | 6 (12%)        |
| Import throughput                      | 1,305 rows/sec |
| Statewide readiness score              | 34.4%          |
| Safety invariants                      | All clear      |

The engineering infrastructure — pipeline, API, UI, quality system, and operational tooling —
is complete and fully verified. The primary gap is data coverage: 15 facilities lack
discovered sources, and most raw hospital data uses internal charge codes that require
crosswalk mapping to standard CPT/HCPCS/DRG codes.

## Quick start

Prerequisites: Docker, Python 3.12+, Node.js 22+, and npm.

```bash
cp .env.example .env
make setup
make db-up
make migrate
make import-cms-hospitals
make api
```

API docs: <http://localhost:8000/docs>. Public site: `make web` (port 3000).
Admin dashboard: `make admin` (port 3001).

### Phase-specific workflows

```bash
# Phase 2: CMS quality data
make import-cms-quality
make verify-phase-2

# Phase 3: Identity, search, data health
make import-nppes-organizations
make seed-procedure-catalog
make rebuild-search-index
make evaluate-data-health
make verify-phase-3

# Phase 4: Hospital pricing pipeline (fixture-only)
make pricing-pipeline
make verify-phase-4

# Phase 4.2: Statewide coverage
make pipeline-full-nh
make statewide-scorecard
make verify-phase-4-2
```

## Architecture

```
apps/web/          Next.js public interface (facilities, procedures, prices, map, search)
apps/admin/        Next.js admin dashboard (scorecard, pipeline status, quality review)
services/api/      FastAPI backend (28 endpoints, publication-gated pricing)
collectors/        Hospital price discovery, download, parsing, normalization
packages/database/ SQLAlchemy models, Alembic migrations (0001–0006)
packages/search/   Search index with 40+ consumer synonym mappings
packages/identity/ Deterministic facility identity resolution
scripts/           Pipeline CLI, benchmarks, reports, verification
docs/              Operations, API, coverage methodology, provenance
```

All imported data is tied to immutable source metadata and an import run. No PHI or patient
data belongs in this system.

## Hospital pricing pipeline

The pipeline follows a strict sequence: discover → download → parse → normalize → map →
review → publish. Each stage has safety gates:

- **Discovery**: Bounded to official hospital domains via `robots.txt`-compliant crawling
- **Parsing**: Deterministic CMS HPT CSV/JSON parsers with header-alias extensions
- **Mapping**: Code-based procedure mapping (51 CPT/HCPCS/DRG mappings) — no fuzzy matching
- **Quality**: Auto-triage rules suppress known false positives; unresolved critical/error
  anomalies block publication
- **Publication**: Only `publishable` summaries with reviewed mappings and acceptable
  source confidence reach the public API

`make pricing-pipeline` runs fixtures only. Live discovery and downloads are separate
reviewable commands. See [hospital price transparency](docs/hospital-price-transparency.md).

## Statewide coverage (Phase 4.2)

Phase 4.2 extends the pricing pipeline to all 28 NH acute-care hospitals:

- **Statewide pipeline** — `make pipeline-full-nh` runs the full discover → postprocess sequence
- **Quality system** — auto-triage rules, freshness scoring (30/60/90/180-day tiers), historical price change tracking via `PriceChangeSnapshot`
- **Statewide scorecard** — 6-component readiness score (discovery, parsing, mapping, quality, freshness, coverage)
- **Search synonyms** — 40+ consumer-friendly term mappings (e.g., "knee replacement" → "total knee arthroplasty")
- **Interactive map** — Leaflet/OpenStreetMap NH hospital map with pricing-status color coding
- **Admin dashboard** — readiness gauge, component score bars, per-facility quality table
- **API endpoints** — scorecard, freshness, facility scores, map data, pricing health, price filtering

### Verified status

All checks pass as of the final Phase 4.2 commit:

| Check                  | Result                  |
| ---------------------- | ----------------------- |
| mypy (strict)          | 0 errors, 99 files      |
| pytest                 | 64 passed, 71% coverage |
| Ruff format + lint     | Clean                   |
| ESLint                 | 0 errors                |
| Prettier               | Clean                   |
| TypeScript             | 0 errors                |
| Vitest                 | 3 passed                |
| Web production build   | Success                 |
| Admin production build | Success                 |
| npm audit              | 0 vulnerabilities       |
| Phase 4.2 verification | 7/7 checks passed       |

### Top remaining gaps

1. 15 NH facilities have no discovered MRF source (including Dartmouth-Hitchcock, Elliot, Southern NH)
2. Concord Hospital-Franklin has 97,817 records using CDM codes — needs CPT crosswalk
3. 26 discovered source URLs have not been downloaded
4. 44 of 50 procedures have zero publishable prices
5. 34 procedures lack CPT/HCPCS code mappings

See [pipeline operations](docs/phase-4-2-operations.md), [API endpoints](docs/api-pricing-endpoints.md),
and [coverage methodology](docs/statewide-coverage.md).

## Safety invariants

These invariants are enforced and verified on every commit:

- 0 AI-modified prices
- 0 fuzzy auto-merges of facility identity
- 0 public unreviewed procedure mappings
- 0 accepted negative prices in public output
- 0 PHI stored
- 0 insurer Transparency in Coverage files ingested
- 0 cloud deployments

Public pricing pages include disclaimers that published prices may not equal the final bill
and that additional professional, anesthesia, pathology, imaging, laboratory, medication,
implant, or other charges may apply.
