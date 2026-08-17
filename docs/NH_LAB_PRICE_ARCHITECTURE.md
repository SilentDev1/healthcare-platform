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

## LabCorp OnDemand

Re-verification pending (do not reuse prior-researched values). Same architecture will
apply (national DTC bundled price + any required fee). Record a blocker if verification
is impossible; never substitute a third-party estimate.
