# New York MRF Acquisition — Phase 7–9

**Date:** 2026-08-23 · **Scope:** locate + register WHERE to fetch each operating NY hospital's
machine-readable standard-charges file (MRF). Registering a source is **not** price availability —
download / import / publish are separate gated steps. Machine-readable ledger:
[`data/ny_pricing_acquisition_ledger.json`](../data/ny_pricing_acquisition_ledger.json).

## Headline

| Metric | Value |
|---|---:|
| Denominator (operating hospitals) | **157** |
| **MRF sources FOUND** (direct file/endpoint URL) | **154** |
| Registered into `FacilityPriceSource` (prod) | **154** |
| SOURCE_BLOCKED (WAF) | 2 |
| INDEX_ONLY (vendor portal, no direct file) | 1 |
| **Total accounted** | **157 / 157** |

## Method — organization-first via `/cms-hpt.txt`

Nearly every NY hospital/system publishes the CMS-required machine-readable index at
`https://<domain>/cms-hpt.txt`, which names the direct MRF URL. Discovery grouped the 157 hospitals
by health system and resolved each system's index once, then verified per-hospital file URLs. This
resolved 154/157 to direct URLs — no scraping, only the official CMS-mandated public index.

## Format & vendor profile (FOUND)

| Format | n | | Vendor | n |
|---|---:|---|---|---:|
| CSV | 66 | | self-hosted | 88 |
| JSON | 38 | | Panacea | 29 |
| ZIP (csv/json inside) | 31 | | Craneware | 10 |
| vendor endpoint (unknown ext) | 19 | | ElevatePFS | 8 |
| | | | hospitalpricedisclosure | 6 |
| | | | Hyve / Trinity / others | 13 |

The pipeline reuses the NH/MA collectors (ZIP member extraction, CSV/JSON parsers) + the shared
national code catalog — **no new NY-specific parsers or procedure mappings**.

## Shared system files (import once, attribute per-CCN — never duplicate campus prices)

| File (EIN) | CCNs it covers |
|---|---|
| NYP `133957095` | 330101, 330236 (Brooklyn Methodist), 330064 (Lower Manhattan), 330061 (Westchester) |
| Montefiore `131740114` | 330059 (Moses/Weiler/CHAM), 330072 (Wakefield) |
| Mount Sinai `132997301` | 330046 (West + Morningside) |
| Garnet Catskills `146049030` | 330386 (Harris), 331303 (Callicoon) |

These plus the 16 multi-campus single-CCN hospitals recorded in the seed's `multi_campus_single_ccn`
govern ingestion: a shared/multi-campus file is imported once per CCN it legitimately covers, and the
same CCN's prices are never rendered under multiple campus addresses without campus-level evidence.

## Regional coverage of sources

All **14 regions** have MRF sources (Hudson Valley 23, Long Island 22, Western NY 14, Southern Tier /
Finger Lakes / North Country 13 each, Brooklyn 12, Manhattan 9, Mohawk Valley / Central NY 8, Capital
7, Queens 7, Bronx 6, Staten Island 2). No regional source desert.

## Precise dispositions (the 3 not-FOUND)

| CCN | Hospital | Region | Disposition | Evidence / retry |
|---|---|---|---|---|
| 330218 | Oswego Hospital | Central NY | **SOURCE_BLOCKED** | oswegohealth.org returns 403 (WAF) to `/cms-hpt.txt` + transparency page; media on res.cloudinary.com. Retry with browser-UA during ingestion. |
| 330241 | SUNY Upstate University Hospital | Central NY | **SOURCE_BLOCKED** | upstate.edu returns 403 (WAF) to all file paths. A pricing `.xlsx` is known to exist; standard-charges file URL unverified. Retry browser-UA. |
| 330221 | Wyckoff Heights Medical Center | Brooklyn | **INDEX_ONLY** | Only an interactive CDMPricing/Craneware portal found; no direct file URL exposed; domain `cms-hpt.txt` 404s. Resolve official vendor download during the campaign. |

None blocks NY activation on its own — 154/157 hospitals are ingestion-ready.

## Notable identity/vendor findings during discovery

- **NYU Langone** self-hosts on AWS S3 (`standard-charges-prod.s3.amazonaws.com`), one file per campus CCN.
- **NYC Health + Hospitals** — one Panacea MRF per hospital, indexed at `nychealthandhospitals.org/cms-hpt.txt`.
- **Mount Sinai** + **White Plains** + **Montefiore Nyack** host-WAF the automated index read but the direct
  file URLs are documented; attempt browser-UA download (as MA's Holyoke recovered).
- Corrections vs assumptions: Our Lady of Lourdes (330011) is now **Guthrie** (not Ascension); Westfield REH
  (330801) is served by **Allegheny Health Network**; Claxton-Hepburn (331324, Ogdensburg) has its **own** EIN
  (not shared with Carthage 331318).

## Status

Sources registered; **ingestion (download → import → map → publish) is the next phase** — bounded waves,
large MRFs solo, safety gate + false-positive detector after each wave, `ai_modified_prices = 0`. See
`docs/NY_PRICING_COVERAGE.md` for live coverage as waves complete.
