# Massachusetts Pricing Coverage Dashboard — Phase 2

Live coverage of MA hospital pricing. Updated after each ingestion wave. **NH is untouched throughout.**
The goal is **53/53 accounted for** (a precise disposition each), *not* 53/53 priced.

## Denominator

**53** operating general acute + critical-access hospitals (CMS-reconciled; see `MA_FOUNDATION_DENOMINATOR.md`).

## Directory (identity) — DONE

- **53/53 seeded + live** at `GET /api/v1/facilities/directory?state=MA` — all 10 regions, honest
  `pricing_not_available_yet` until each hospital has verified prices. Public state dropdown gated
  (`markets.py` MA `consumer_visible=False`) until MA activation.

## MRF acquisition — DONE (53/53 accounted)

| Status | Count |
|---|---:|
| MRF_FOUND (verified URL) | 51 |
| SOURCE_BLOCKED (WAF 403 — Sturdy, Holyoke) | 2 |

Formats: csv 19, zip 15, json 14, unknown 3. Detail: `MA_MRF_ACQUISITION.md`.

## Pricing ingestion — IN PROGRESS (5 published, scale-out ongoing)

| Hospital | CCN | Region | Published procedures | Status |
|---|---|---|---:|---|
| Massachusetts General Hospital | 220071 | Greater Boston | 49 / 52 | **PUBLISHED** |
| Boston Medical Center | 220031 | Greater Boston | 48 | **PUBLISHED** |
| Fairview Hospital | 221302 | Berkshires | 44 | **PUBLISHED** |
| North Adams Regional Hospital | 221304 | Berkshires | 44 | **PUBLISHED** |
| Martha's Vineyard Hospital | 221300 | Cape Cod & Islands | 38 | **PUBLISHED** |
| *(remaining 46)* | | | 0 | small-wave ingestion in progress |

**Live examples** (verified on the production API): MGH MRI-brain-without-contrast **$3,858**,
Martha's Vineyard **$2,116.50**, honest `facility` billing scope; cash vs negotiated preserved.

### Ingestion operational rules (learned)

- **Import time dominates** (~2 min per 10 MB, from the rate-detail fan-out). A single 489 MB MRF ≈ 90 min.
- **Large hospitals (>~150 MB) run SOLO**; small ones batch 3/job. Never batch two large files.
- **Per-wave rebuild is deferred** (`--no-rebuild`) — one final rebuild surfaces all summaries; MA is not
  consumer-activated during scale-out, so deferral is invisible.
- **Never cancel a running ingest** — cancellation leaves a stuck ImportRun (fails the safety gate) and
  partial records (which a rebuild would surface). Recover with `reset_ma_pricing --fast --keep-ccns <priced>`.
- Task timeout raised to 3 hr for large-hospital headroom.

### Ingestion status legend (fail-forward)

`PUBLISHED` · `INGESTED_NOT_PUBLISHED` · `MRF_FOUND_PARSER_NEEDED` · `SOURCE_BLOCKED` ·
`MRF_NOT_FOUND` · `FORMAT_UNSUPPORTED` · `NO_MAPPABLE_CANONICAL_PROCEDURES` · `FAILED_VALIDATION`.

### Pipeline hardening (from the pilot)

The diverse pilot surfaced and fixed 4 recurring ingest issues (size cap 750 MB→3 GB, TLS legacy
renegotiation, code-column overflow, `binary/octet-stream`) and one operational lesson (batching many
large MRFs per Cloud Run job hits the 2 hr task timeout → **small waves, large hospitals isolated**).
Reuses the NH pipeline + shared national code catalog — no new parsers, no new MA procedure mappings.

## Safety (every wave)

NH must stay: `active_consumer_hospitals=26`, `official_public_summaries≥16,893`, all zero-invariants 0,
**ai_modified_prices=0**; MA fp-detector 0 suspects. Verified green through the pilot + recovery.

## Regional coverage (priced hospitals per region — updates per wave)

| Region | Hospitals | Priced |
|---|---:|---:|
| Greater Boston | 14 | 2 |
| Pioneer Valley | 7 | 0 |
| Central Massachusetts | 6 | 0 |
| North Shore | 4 | 0 |
| MetroWest | 4 | 0 |
| South Shore | 4 | 0 |
| Southeastern MA / South Coast | 4 | 0 |
| Cape Cod & Islands | 4 | 1 |
| Merrimack Valley | 3 | 0 |
| Berkshires | 3 | 2 |
| **Total** | **53** | **5** |
