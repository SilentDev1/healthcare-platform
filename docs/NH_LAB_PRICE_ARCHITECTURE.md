# NH DTC Lab Price Architecture (Quest / LabCorp OnDemand)

Status: **design + staged candidates (NON-PUBLIC)**. Nothing here is consumer-visible.
Last updated: 2026-08-17.

## The problem these prices are NOT the same as hospital lab prices

Direct-to-consumer (DTC) lab products (questhealth.com, ondemand.labcorp.com) are a
**different service model** from a hospital/clinic outpatient lab charge:

| Dimension | Hospital outpatient lab | Quest/LabCorp DTC |
|---|---|---|
| How you buy | provider orders → facility bills | consumer buys online, no doctor visit |
| Price basis | facility technical/prof component (CDM/MRF) | national fixed self-pay product price |
| Location | the specific facility | national — collect at ANY of 2000+ sites |
| Extra required cost | (in the charge) | flat **$6.00 physician service fee**, required |
| Code | CPT published in MRF | **no CPT/test code published** |

Because of this, a DTC lab price must **never** be min/maxed or "Save $X"-compared
against a hospital outpatient lab cash price as if they were the same billing scope.

## Smallest correct representation (additive, non-corrupting)

Each DTC product is stored as a `FacilityProcedurePriceSummary` with:

- `cash_price_* = TOTAL` the consumer actually pays = **test price + required $6 physician
  service fee** (e.g. CMP = $49 + $6 = **$55**). We never collapse to the test-only
  number — the fee is mandatory to obtain the result, so the honest price is the total.
- `included_component_scope` left at the sentinel **`unknown`** (the `component_scope`
  text begins with a non-scope token, so `normalize_component_scope` → `unknown`). This
  keeps DTC labs **out of directly-comparable ranking** even if ever published — they are
  a bundled DTC package, not a hospital facility charge.
- `notes` preserves the full breakdown: `test + physician_service_fee = total`, `sku`,
  per-product `product_url`, `retrieval_date`, `national_dtc=true`, and any mapping note.
- `publication_status = candidate_review` (**NON-PUBLIC**; consumer endpoints require
  `publishable`). The imaging-modality promotion gate excludes labs, so they cannot
  auto-publish.

The component fields (`test_price`, `physician_service_fee`, `total_price`, `sku`,
`product_url`) live in `data/nh_nonhospital_published_prices.json` and in the summary
`notes`. A dedicated additive component table is **not** built yet — the notes + JSON
are the smallest correct record until a lab-publish presentation is designed.

## Why not 14 NH location prices

The DTC price is national and org/product-level. Attaching it to all 14 NH Quest
locations as if each were a distinct location price would overstate coverage and imply
location specificity that does not exist. Staged candidates are org-wide **only** as a
non-public holding state; they must not be counted as 14 location prices in coverage
(see coverage reporting), and publication requires:

1. a decision on how to present a DTC product distinctly from walk-in facility billing,
2. per-location `LocationServiceAvailability` evidence that the collection site exists,
3. resolution of the mapping caveats below.

## Verified products (2026-08-17, in-browser)

| Product | Canonical | Test | +Fee | Total | SKU | Note |
|---|---|---|---|---|---|---|
| CMP | comprehensive-metabolic-panel | $49 | $6 | $55 | 10231M | clean |
| CBC | complete-blood-count | $29 | $6 | $35 | 6399M | clean |
| Lipid Panel | lipid-panel | $59 | $6 | $65 | 94355M | clean |
| TSH | thyroid-test | $49 | $6 | $55 | 36127M | product is TSH-only; canonical may be broader — review |
| Urinalysis (UTI) | urinalysis | $40 | $6 | $46 | 5463M | product is UTI-framed — review vs routine UA |
| HbA1c | — | $39 list ($35.10 promo) | $6 | $45 list | 496M | **no canonical** → gap, not ingested |

Promo caution: HbA1c showed a transient 10%-off promo ($35.10). Durable list = $39.00;
promotional prices are time-varying and must never be stored as a stable price.

## LabCorp OnDemand — verified 2026-08-18 (in-browser, official ondemand.labcorp.com)

| Product | Canonical | Price | Fee | Total | Source |
|---|---|---|---|---|---|
| CBC | complete-blood-count | $29 | included | **$29** | ondemand.labcorp.com/.../complete-blood-count |
| CMP | comprehensive-metabolic-panel | $49 | included | **$49** | .../comprehensive-metabolic-panel |
| Lipid | lipid-panel | $59 | included | **$59** | .../cholesterol-test-lipid-panel |
| TSH | thyroid-test | $49 | included | **$49** | .../thyroid-stimulating-hormone-tsh-test |
| HbA1c | — (canonical gap) | $39 | included | **$39** | .../diabetes-risk-hbA1c-test |

**Key finding — LabCorp OnDemand is all-inclusive.** Unlike Quest (test price + a separate
required $6 physician service fee), LabCorp OnDemand's displayed price already includes the
independent-provider order — there is no separate physician fee. So the honest self-pay total
is lower on every test:

| Test | Quest total | LabCorp total |
|---|---|---|
| CBC | $35 ($29 + $6) | **$29** |
| CMP | $55 ($49 + $6) | **$49** |
| Lipid | $65 ($59 + $6) | **$59** |
| TSH | $55 ($49 + $6) | **$49** |
| HbA1c | $45 ($39 + $6) | **$39** |

## PUBLICATION DECISION (2026-08-18): DTC labs stay NON-PUBLIC pending an org-level surface

Both Quest and LabCorp DTC prices are **national, organization/product-level** self-pay prices
(buy online → collect at any of that lab's Patient Service Centers). The current pricing model
(`FacilityProcedurePriceSummary`) is **per service location**. Publishing a single national DTC
price against each NH collection site would fabricate the exact "14 independent location-published
prices" the directive forbids — and would misrepresent a national product as location-specific.

Therefore the deliberate, safe disposition is: **verified, recorded, kept `candidate_review`
(NON-PUBLIC); NOT promoted as per-location prices.** Consumer publication uses a distinct
**org-level DTC price surface**, separate from the per-location hospital comparison.

**Backend LIVE (2026-08-18):** `GET /api/v1/procedures/{slug}/dtc-options` (API rev
`carevero-beta-api-00060-tir`) serves the verified org/product-level DTC options (read-only,
DB-free, from `data/nh_dtc_lab_options.json`) with an explicit disclaimer ("national online
purchase, collect at a provider location; not a personalized estimate; not location-specific").
Live: CBC → LabCorp $29 / Quest $35; CMP → $49 / $55; non-lab → empty; unknown → 404. It never
writes a `FacilityProcedurePriceSummary`, so it cannot create the forbidden 14 fake location prices.

**Remaining (frontend):** a "Direct-to-consumer self-pay option" card on the lab procedure /
comparison page that consumes `dtc-options`, shown distinctly from the per-location comparison
(owned by the frontend track). Optional: `LocationServiceAvailability` for collection sites
(service-offered, not price). The Quest `candidate_review` rows can then be retired in favor of
this surface. Until the card ships, DTC prices are served by the API but not yet rendered — no
fake location prices exist at any point.
