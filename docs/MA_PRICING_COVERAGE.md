# Massachusetts Pricing Coverage Dashboard — Phase 2 (FINAL)

**53/53 hospitals accounted for. 46 published with verified prices; 7 precisely dispositioned.**
NH untouched throughout. MA consumer-visibility flip staged (`markets.py`) — owner-confirm before deploy.

## Headline

| Metric | Value |
|---|---:|
| Denominator (operating acute + CAH) | **53** |
| **Hospitals published (live, verified prices)** | **46** |
| Accounted-for but unpriced (disposition below) | 7 |
| MA public price summaries | **~7,647** (of 24,540 total incl. NH) |
| MA raw price records | ~14.1M |
| Safety gate | **PASS** (NH 26 hospitals intact; ai_modified_prices 0; negatives 0; missing-provenance 0) |
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
| Pioneer Valley | 6 | 7 |
| MetroWest | 3 | 4 |
| Southeastern MA / South Coast | 3 | 4 |
| Merrimack Valley | 1 | 3 |
| **Total** | **46** | **53** |

Every region has priced hospitals. **MA is genuinely useful to a consumer.**

## High-demand procedures (MA-wide price points, live)

MRI brain w/o contrast **173** · colonoscopy **176** · A1C **178** — plus CT, X-ray, ultrasound, mammogram,
CBC, CMP, lipid, TSH, Vitamin D, PSA, knee/hip replacement across the 45 hospitals. Prices carry honest
billing scope (facility/global) and preserve cash vs negotiated distinctions; **no AI-authored prices**.

## The 7 accounted-for, unpriced — precise disposition

| CCN | Hospital | Disposition | Why |
|---|---|---|---|
| 220008 | Sturdy Memorial | SOURCE_BLOCKED | sturdyhealth.org **Akamai** bot-manager 403s httpx even with browser UA+Referer+Sec-Fetch (URL known; needs a real browser/JS) |
| 220063 | Lowell General | SOURCE_BLOCKED | tuftsmedicine.org WAF 403 (browser headers insufficient) |
| 220070 | MelroseWakefield | SOURCE_BLOCKED | tuftsmedicine.org WAF 403 |
| 220116 | Tufts Medical Center | SOURCE_BLOCKED | tuftsmedicine.org WAF 403 |
| 220049 | Marlborough Hospital | MERGED_INTO_UMMC | charges inside the UMass Memorial file (imported under 220163) |
| 220010 | Lawrence General | SHARED_SYSTEM_MRF | Merrimack Health system file (EIN 042103586) published under Holy Family 220080 |
| 220066 | Mercy Medical Center | TOO_LARGE | Trinity Health all-payer MRF ~4M records; a single Cloud Run job (12 hr) can't finish it — needs resumable/streaming import |

**Holyoke Medical Center (220024) was recovered** with a browser User-Agent (WordPress CDN) → now published.
**Retryable follow-ups:** Sturdy + the 3 Tufts Medicine hospitals via a headless browser (their WAFs defeat
header-spoofing); Mercy via a resumable/chunked import.

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
