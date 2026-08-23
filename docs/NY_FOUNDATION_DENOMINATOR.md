# New York Foundation — Authoritative Hospital Denominator (Phase 1)

**Date:** 2026-08-23 · **Scope:** identity + regional taxonomy only — **no pricing, no DB writes, no
consumer surface.** NH and MA baselines are untouched. This is the reconciled denominator that later
phases (identity seed → directory → MRF acquisition → pricing) build on.

**Verification:** `python -m scripts.verify_ny_foundation` → **PASS** (regression gate:
`scripts/tests/test_verify_ny_foundation.py`, 6 tests).

---

## Headline

| Metric | Value |
|---|---:|
| CMS Hospital General Information — NY rows (all types) | **192** |
| CMS consumer-type (Acute + Critical Access + Rural Emergency) | **152** |
| — dispositioned (closed / merged / superseded / specialty / rehab-LTAC) | **8** |
| — operating, from CMS | **144** |
| + operating hospitals CMS Care Compare **omits** (NYSDOH-confirmed) | **13** |
| **Operating consumer denominator** | **157** |
| Consumer regions (NYC split into 5 boroughs) | **14** (10 roll-up groups) |
| Counties with a hospital → all resolve to exactly one region | **57 / 57** |
| Unresolved / null / multi-region hospitals | **0** |

Artifacts: [`data/ny_cms_hospital_snapshot.json`](../data/ny_cms_hospital_snapshot.json) (CMS cache),
[`data/ny_hospitals_seed.json`](../data/ny_hospitals_seed.json) (the 157 + full disposition metadata),
[`data/ny_region_taxonomy.json`](../data/ny_region_taxonomy.json).

---

## Sources reconciled

1. **CMS Hospital General Information** — `data.cms.gov` dataset `xubh-q36u`, `state=NY`, retrieved
   2026-08-23 (192 rows). The CCN/price spine, but **incomplete**: Care Compare omits hospitals that
   don't report its quality measures.
2. **NYSDOH Health Facility General Information** — `health.data.ny.gov` dataset `vn5v-hh5r`
   (`description="Hospital" / "Primary Care Hospital - Critical Access Hospital" / "Rural Emergency
   Hospital"`). The authoritative **operating-status** source; used to (a) catch operating hospitals
   CMS omits and (b) confirm closures are truly gone.
3. **Health-system membership research** (sourced, 2025–2026) — resolved multi-campus-single-CCN
   cases, closures, mergers, and CCNs for the CMS-omitted hospitals.

> The directive's warning held: **do not treat every CMS "Acute Care" row as the denominator, and do
> not treat CMS as complete.** Both a subtraction (stale/closed/specialty rows) and an addition
> (Care-Compare-omitted operating hospitals) were required.

---

## Why the denominator is **not** just "CMS acute rows"

### Excluded by CMS type (never part of the consumer denominator)
| Type | Count | Why |
|---|---:|---|
| Acute Care – Veterans Administration | 9 | Federal VA; not consumer-shoppable, no MRF |
| Acute Care – Department of Defense | 1 | Federal military |
| Psychiatric | 29 | Psychiatric-only specialty |
| Childrens | 1 | Blythedale Children's (Valhalla) — pediatric-rehab specialty |

### Dispositioned out of the 152 CMS consumer-type rows (8)
| CCN | Hospital | Disposition | Reason |
|---|---|---|---|
| 330169 | Mount Sinai Beth Israel (Manhattan) | **CLOSED** | Closed 2025-04-09 after NYSDOH-approved plan + litigation; CMS acute tag lags; absent from NYSDOH operating |
| 330246 | St Charles Hospital (Port Jefferson) | **MERGED** | Into Good Samaritan University Hospital **330286** (2026-07-01) as its St. Charles Campus; shared license/TIN/CCN — priced under 330286, never separately |
| 330166 | Westfield Memorial (acute) | **SUPERSEDED** | Converted to a Rural Emergency Hospital; live CCN is REH **330801** (same hospital) |
| 330100 | NY Eye & Ear Infirmary of Mount Sinai | **SPECIALTY** | Ophthalmology/ENT specialty acute — bucketed (candidate for later consumer visibility) |
| 330270 | Hospital for Special Surgery (Manhattan) | **SPECIALTY** | Orthopedic specialty acute — bucketed (high-value for hip/knee; candidate for later visibility) |
| 330405 | Helen Hayes Hospital (West Haverstraw) | **REHAB** | Physical-rehab specialty hospital, not general acute |
| 330406 | Sunnyview Hospital & Rehab (Schenectady) | **REHAB** | Rehabilitation specialty hospital |
| 330411 | Unity Specialty Hospital (Rochester) | **LTAC** | Long-term acute care / specialty unit |

**Identity check:** 144 operating (CMS) + 8 dispositioned = **152** = CMS consumer-type rows. ✔

### Added back — operating general-acute hospitals CMS Care Compare **omits** (13)
Each is confirmed **operating** in NYSDOH `vn5v-hh5r` and absent from the entire `xubh-q36u` dataset.
| CCN | Hospital | City | Region | System |
|---|---|---|---|---|
| 330061 | NewYork-Presbyterian Westchester (ex-Lawrence) | Bronxville | Hudson Valley | NYP † |
| 330064 | NewYork-Presbyterian Lower Manhattan | New York | Manhattan | NYP † |
| 330072 | Montefiore Wakefield Campus | Bronx | Bronx | Montefiore |
| 330088 | Stony Brook Eastern Long Island | Greenport | Long Island | Stony Brook |
| 330108 | St Joseph's Hospital (Elmira) | Elmira | Southern Tier | Arnot Health |
| 330167 | NYU Langone Hospital – Long Island (ex-Winthrop) | Mineola | Long Island | NYU Langone |
| 330236 | NYP Brooklyn Methodist | Brooklyn | Brooklyn | NYP |
| 330306 | NYU Langone Hospital – Brooklyn (ex-Lutheran) | Brooklyn | Brooklyn | NYU Langone |
| 330340 | Stony Brook Southampton | Southampton | Long Island | Stony Brook |
| 330353 | Long Island Jewish Forest Hills | Forest Hills | Queens | Northwell |
| 330372 | Long Island Jewish Valley Stream (ex-Franklin) | Valley Stream | Long Island | Northwell |
| 330397 | Interfaith Medical Center | Brooklyn | Brooklyn | One Brooklyn Health |
| 330398 | Syosset Hospital | Syosset | Long Island | Northwell |

† CCNs 330064 / 330061 carry **moderate** confidence (330060/330061 legacy-Lawrence ambiguity) — flagged
in the seed for direct CMS re-verification at MRF-acquisition time.

---

## Duplicates & multi-campus / single-CCN handling

- **Duplicate CCNs in CMS:** none (each of the 192 rows is a distinct CCN).
- **Sequential CCN reuse:** MVHS **Wynn Hospital 330044** inherited the closed Faxton–St. Luke's CCN;
  St. Elizabeth's CCN was retired (both absent from the snapshot — already resolved by CMS).
- **`330223` (old Massena)** is **not** added — Massena operates in CMS as CAH **331322**.
- **North Central Bronx** and **Lockport Memorial** are **campuses of existing CCNs**, not separate
  hospitals: NCB shares Jacobi's NYS opcert 7000002H (no separate CCN); Lockport Memorial operates as a
  campus of Mount St. Mary's **330188** (it replaced the closed Eastern Niagara Hospital).
- **16 multi-campus single-CCN hospitals** are recorded in the seed's `multi_campus_single_ccn` list
  (e.g. NYP 330101 = Weill Cornell + Columbia + Allen + Morgan Stanley Children's; NYU Langone 330214;
  Montefiore 330059 = Moses + Weiler + CHAM; Staten Island Univ 330160 = North + South; Kaleida 330005 =
  Buffalo General + Gates Vascular + Millard Fillmore Suburban + Oishei). **Consequence for pricing:**
  each surfaces as **one** priced facility (its MRF is filed once per CCN); the same CCN's price must not
  be duplicated across campus addresses without campus-specific evidence in the MRF.

---

## Regional taxonomy

14 consumer regions derived from New York State's **10 REDC regions**, with **New York City split into
its five boroughs** (first-class regions that roll up to "New York City" via `region_groups`, so a
query like "MRI in NYC" spans all five) and **Long Island = Nassau + Suffolk**. Region is derived
**purely from county** — no municipality subdivision needed (unlike MA). Consumer-friendly naming:
"Hudson Valley" for the REDC "Mid-Hudson" 7 counties; **Mohawk Valley kept** (a real Utica–Rome hospital
market). Full 62-county partition in [`data/ny_region_taxonomy.json`](../data/ny_region_taxonomy.json).

| Region | Hospitals | | Region | Hospitals |
|---|---:|---|---|---:|
| Manhattan | 9 | | Mohawk Valley | 8 |
| Brooklyn | 12 | | Central New York | 8 |
| Queens | 7 | | North Country | 13 |
| Bronx | 6 | | Southern Tier | 13 |
| Staten Island | 2 | | Finger Lakes | 13 |
| Long Island | 22 | | Western New York | 14 |
| Hudson Valley | 23 | | Capital Region | 7 |

Every region has real hospitals; coverage is **not** NYC-concentrated (NYC boroughs = 36 of 157;
upstate + Long Island + Hudson Valley = 121).

---

## What Phase 1 did **not** do (next phases)

Identity seed into the DB (price-unavailable) → directory QA → MRF source discovery (organization-first)
→ acquisition ledger → pilot → ingestion waves → validation → consumer QA → activation. Standing safety
rules from NH/MA apply throughout: `ai_modified_prices = 0`; never fabricate/estimate prices; preserve
provenance, billing scope, cash-vs-negotiated; never damage NH or MA.
