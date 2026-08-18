# Massachusetts Foundation — Phase 1: Provider/Facility Denominator + Regional Taxonomy

**Status:** COMPLETE & VERIFIED · **Nothing published** · Identity/geography only, **no pricing**, no
DB writes, no deploy, no consumer surface. NH baseline untouched.
**Date:** 2026-08-18. **Authoritative source:** CMS Hospital General Information (dataset `xubh-q36u`).

Phase 1 establishes *who the MA hospitals are* and *how MA is divided into regions* — the denominator
every later coverage metric (e.g. "X/53 hospitals priced") will be measured against — and proves it
reconciles to an authoritative external source. It publishes nothing.

## The denominator (verified against CMS)

| Bucket | Count | Notes |
|---|---:|---|
| **Operating general acute + critical-access** (the consumer denominator) | **53** | `data/ma_hospitals_seed.json` |
| Specialty acute (bucketed separately) | 3 | Mass Eye & Ear `220075`, New England Baptist `220088`, AdCare Worcester `220062` |
| Closed (excluded; CMS-lagged) | 3 | Carney `220017`, Nashoba Valley `220098` (both closed 2024-08-31, Steward), Norwood `220126` (closed 2020) |
| **= CMS acute + critical-access total** | **59** | 53 + 3 + 3 — exact identity |

CMS's full MA hospital file returns **84** rows (55 Acute Care, 19 Psychiatric, 4 Critical Access,
3 VA, 3 Children's). The price-transparency denominator is the **acute + critical-access** subset (59),
which reconciles exactly to `53 operating + 3 specialty + 3 closed`.

**Key integrity finding:** CMS still lists all three closed hospitals (Carney, Nashoba, Norwood) as
"Acute Care Hospitals." A naive CMS pull would therefore over-count the operating denominator by 3.
The curated seed's closure exclusions — cross-checked against Mass.gov (Steward transitions) and the
Massachusetts Health & Hospital Association — are the essential correction and are what makes **53** the
right number rather than 56.

## Regional taxonomy (10 regions, all 14 counties covered)

`data/ma_region_taxonomy.json`. Every one of the 53 hospitals resolves to exactly one region, and the
region is **derivable from (county, city)** — no hand-label is unverifiable.

| Region | Hospitals | County basis |
|---|---:|---|
| Greater Boston | 14 | Suffolk + inner Middlesex/Norfolk |
| Pioneer Valley | 7 | Hampden + Hampshire + Franklin |
| Central Massachusetts | 6 | Worcester |
| North Shore | 4 | Essex (coastal) + Burlington |
| MetroWest | 4 | western Middlesex + Milford |
| South Shore | 4 | Plymouth (N) + southern Norfolk |
| Southeastern MA / South Coast | 4 | Bristol |
| Cape Cod & Islands | 4 | Barnstable + Dukes + Nantucket |
| Merrimack Valley | 3 | Lawrence/Methuen/Lowell |
| Berkshires | 3 | Berkshire |

**Resolution rules** (checked in order): (1) named **municipal overrides** for cross-boundary towns
(e.g. Milford — Worcester County but MetroWest belt); (2) **9 counties** map 1:1 to a region; (3) the
**5 eastern metro counties** (Suffolk, Middlesex, Essex, Norfolk, Plymouth) resolve by a per-county
default + a municipality gazetteer. The gazetteer is authoritative for every hospital in the denominator
and is extended per-municipality as non-hospital facilities are added later (never guessed at publish time).

## Verification (reproducible, offline)

`scripts/verify_ma_foundation.py` (READ-ONLY) reconciles the seed against the cached CMS snapshot and
validates the taxonomy. **RESULT: PASS.** Five checks: (1) CMS↔seed reconciliation; (2) no missing/unknown
CCNs; (3) no orphan region labels; (4) taxonomy covers every county with a hospital; (5) every hospital's
region is derivable from (county, city). Regression-guarded by `scripts/tests/test_verify_ma_foundation.py`
(4 tests, pass). Ruff clean.

```bash
python -m scripts.verify_ma_foundation
```

## Artifacts (this phase)

- `data/ma_hospitals_seed.json` — 53 operating hospitals (CCN, name, city, zip, type, system, region) + closed/specialty meta.
- `data/ma_cms_hospital_snapshot.json` — cached CMS `xubh-q36u` MA rows (84), trimmed, with provenance + retrieval date, for reproducible verification.
- `data/ma_region_taxonomy.json` — 10 regions; municipal overrides + county map + eastern-metro gazetteer.
- `scripts/verify_ma_foundation.py` + `scripts/tests/test_verify_ma_foundation.py` — verifier + regression gate.

## Explicitly NOT done in Phase 1 (by design)

- **No pricing.** No MRF ingestion, no price summaries, no `$` anywhere. (Standing rule: never fabricate/estimate prices; missing stays "not available.")
- **No DB writes / no consumer surface.** Hospitals are not seeded into `Organization`/`Facility`/`FacilityLocation`; nothing appears in the `/providers` directory; nothing deployed. "Without publishing anything yet."
- **No non-hospital roster yet.** Labs, urgent care, imaging, ASCs, PT, chiropractic, EDs — the broader denominator — are Phase 2 research waves (the taxonomy is already built to absorb them via county+city → region).

## Next (Phase 2 candidates — not started, await go)

1. Seed the 53 hospitals into the DB as **price-unavailable identity** (directory only, no prices) — first consumer-visible step; still no pricing.
2. Begin MA hospital **MRF acquisition** hospital-by-hospital (the NH pattern: exact code mappings, safety gates, fp-detector, `ai_modified_prices=0`).
3. Extend the denominator to non-hospital provider types via research waves, assigning regions through the taxonomy gazetteer.
