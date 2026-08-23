# Massachusetts Pricing Coverage Dashboard — Phase 2 (FINAL)

**53/53 hospitals accounted for. 45 published with verified prices; 8 precisely dispositioned.**
NH untouched throughout. MA consumer-visibility (public state dropdown) remains owner-gated (`markets.py` `consumer_visible=False`).

## Headline

| Metric | Value |
|---|---:|
| Denominator (operating acute + CAH) | **53** |
| **Hospitals published (live, verified prices)** | **45** |
| Accounted-for but unpriced (disposition below) | 8 |
| MA public price summaries | **7,751** (of 24,644 total incl. NH) |
| MA price observations | ~368K (of 702,485 total) |
| MA raw price records | ~13.8M |
| Safety gate | **PASS** (NH 26 hospitals intact; ai_modified_prices 0; all zero-invariants 0) |
| MA false-positive suspects | **0** (fp-detector 53/53 CLEAN) |

## Directory + MRF acquisition — DONE

- **53/53 seeded + live** at `GET /api/v1/facilities/directory?state=MA` (all 10 regions).
- MRF sources located for 53/53 (`docs/MA_MRF_ACQUISITION.md`); pipeline reused NH collectors (no new parsers); shared national code catalog (no new MA procedure mappings).

## Regional coverage (priced / total)

| Region | Priced | Total |
|---|---:|---:|
| Berkshires | 3 | 3 |
| Cape Cod & Islands | 4 | 4 |
| Central Massachusetts | 6 | 6 |
| North Shore | 4 | 4 |
| South Shore | 4 | 4 |
| Greater Boston | 12 | 14 |
| Pioneer Valley | 5 | 7 |
| MetroWest | 3 | 4 |
| Southeastern MA / South Coast | 3 | 4 |
| Merrimack Valley | 1 | 3 |
| **Total** | **45** | **53** |

Every region has priced hospitals. **MA is genuinely useful to a consumer.**

## High-demand procedures (MA-wide price points, live)

MRI brain w/o contrast **173** · colonoscopy **176** · A1C **178** — plus CT, X-ray, ultrasound, mammogram,
CBC, CMP, lipid, TSH, Vitamin D, PSA, knee/hip replacement across the 45 hospitals. Prices carry honest
billing scope (facility/global) and preserve cash vs negotiated distinctions; **no AI-authored prices**.

## The 8 accounted-for, unpriced — precise disposition

| CCN | Hospital | Disposition | Why |
|---|---|---|---|
| 220008 | Sturdy Memorial | SOURCE_BLOCKED | sturdyhealth.org WAF 403 |
| 220024 | Holyoke Medical Center | SOURCE_BLOCKED | holyokehealth.com WAF 403 |
| 220063 | Lowell General | SOURCE_BLOCKED | tuftsmedicine.org WAF 403 |
| 220070 | MelroseWakefield | SOURCE_BLOCKED | tuftsmedicine.org WAF 403 |
| 220116 | Tufts Medical Center | SOURCE_BLOCKED | tuftsmedicine.org WAF 403 |
| 220049 | Marlborough Hospital | MERGED_INTO_UMMC | charges inside the UMass Memorial file (imported under 220163) |
| 220010 | Lawrence General | SHARED_SYSTEM_MRF | Merrimack Health system file (EIN 042103586) published under Holy Family 220080 |
| 220066 | Mercy Medical Center | TOO_LARGE | Trinity Health all-payer MRF >3.5M records; exceeds single-job import |

**Retryable:** the 5 WAF-blocked hospitals with a browser user-agent; Mercy with a resumable/streaming import.

## Pipeline hardening (this phase)

Reused the NH pipeline end-to-end. Fixes shipped: download size cap 750 MB→3 GB; TLS legacy renegotiation;
`PriceServiceCode.code` varchar(100) cap; robust content-type (accept data-like, reject markup); MGB moved-URL
refresh; **rebuild IN-list chunked to psycopg's 65535-param cap** (unblocked the MA-scale final rebuild).
Operational lessons: import time tracks record count (not download size) → large hospitals solo under a 12 hr
timeout, 32 GB job memory; never cancel a running ingest (leaves a stuck run + partial); targeted `--reset-ccns`
cleanup + retry for transient Cloud SQL connection drops.

## Production

API `carevero-beta-api-*` (MA served via `?state=MA`); job `carevero-beta-price-audit` image `ma-scale11`
(32Gi/8CPU, 12 hr timeout). Rollback: NH is independent and untouched; MA prices are additive summaries.
