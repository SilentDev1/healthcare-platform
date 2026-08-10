# CareCompare

CareCompare is a healthcare price transparency platform for New Hampshire. It ingests
public hospital machine-readable files, maps them to a consumer procedure catalog, enforces
publication safety gates, and serves reviewed pricing through a Next.js public site, admin
dashboard, and FastAPI backend — all backed by PostgreSQL 17 and Alembic migrations.

## Current status (Phase 4.2.2)

| Metric                                 | Value     |
| -------------------------------------- | --------- |
| NH facilities in database              | 28        |
| Facilities with discovered MRF sources | 22 (79%)  |
| Facilities with downloaded files       | 13 (46%)  |
| Facilities with parsed records         | 13 (46%)  |
| Facilities with publishable pricing    | 12 (43%)  |
| Consumer procedures in catalog         | 50        |
| Total price records                    | 1,197,796 |
| Publishable summaries                  | 4,173     |
| Average pricing health score           | 49.07     |
| Safety invariants                      | All clear |

Phase 4.2.2 achieved a major coverage recovery: from 6 publishable facilities (21%) to
12 (43%), with total records growing from 361K to 1.2M. Key unlocks included CMS HPT JSON
3.0 parsing for large files (246–437 MB), streaming downloads with .part atomic rename and
HTTP Range resume, expanded CDM crosswalk (54 patterns), and a conditional publication
pathway for legacy parsers with approved-code mappings.

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
packages/database/ SQLAlchemy models, Alembic migrations (0001–0007)
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
- **Parsing**: Deterministic CMS HPT CSV/JSON parsers (including 3.0 nested format), chargemaster
  wide CSV, XML standard charges — with header-alias extensions (24 description synonyms, 27 code synonyms)
- **Mapping**: Code-based procedure mapping (87 CPT/HCPCS/DRG mappings, 54 CDM crosswalk patterns) — no fuzzy matching
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

### Phase 4.2.2 — Coverage recovery

- **Large file streaming** — 750 MB download ceiling, .part atomic rename, HTTP Range resume, streaming SHA-256
- **CMS HPT JSON 3.0** — nested `code_information` and `standard_charges`/`payers_information` extraction
- **Expanded parsers** — 24 description synonyms, 27 code synonyms, space-variant header detection, chargemaster wide CSV preamble skip
- **CDM crosswalk** — 54 deterministic patterns (ED visits, deliveries, imaging, urgent care, labs)
- **Health system propagation** — Dartmouth Health, SolutionHealth, North Country Healthcare sibling source sharing
- **Publication pathway** — legacy parsers publishable when records have exact approved-code mappings
- **Diagnostics** — `scripts/publication_blockers.py`, `scripts/analyze_unmapped_codes.py`, `scripts/final_classification.py`

### Verified status

All checks pass as of the latest commit:

| Check              | Result                 |
| ------------------ | ---------------------- |
| mypy (strict)      | 0 errors, 109 files    |
| pytest             | 78 passed              |
| Ruff format + lint | Clean                  |
| Safety invariants  | 0 AI / 0 fuzzy / 0 PHI |

### Remaining gaps

1. 9 facilities have discovered sources but download failed (stale URLs, 404s, HTML error pages)
2. 6 facilities have no discovered MRF source (Cottage, Exeter, Hampstead, Monadnock, NH Hospital, Valley Regional)
3. Littleton Regional parsed (20K records) but not publishable — CDM codes unresolved, legacy parser
4. 2 excluded facilities (Hampstead psychiatric, NH Hospital state-run)

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
