# NHCHIS Data Request Plan (owner-ready)

**Track A deliverable.** Prepared from official NHCHIS/NHID documentation. **Nothing has been
submitted.** This is the package for the owner to file the request. `CostEstimate` production
migration is intentionally NOT built yet — the final schema will be validated against the actual
fields + permitted uses in the approved dataset (see `docs/COST_DATA_ARCHITECTURE.md`).

## 1. What Carevero should request

**Recommended: the NHCHIS _Commercial Claims Public Use Data Set_** — the least-restrictive tier.
NHCHIS offers three commercial claims releases:
1. **Commercial Claims Public Use Data Set** ← recommended first (most openly available; de-identified/aggregated).
2. **Commercial Limited Use Data Set** — requires an application justifying each requested element + a data-use agreement.
3. **Confidential Health Care Claims Research Data Set** — most restricted (IRB-style).

If the Public Use tier lacks provider-level `allowed_amount` at the granularity Carevero needs,
the fallback is the **Limited Use Data Set** (fuller fields, but a formal DUA + element
justification). Decide after reading the Public Use data dictionary (URL below).

## 2. Datasets / files to request (confirm exact availability against the data dictionary)

| Dataset | Why Carevero needs it |
|---|---|
| **Medical Claims** (core) | the cost figures — links to procedure codes via the **CPT** element; contains amount fields (charge / allowed / paid — confirm which are in Public Use) |
| **Provider reference** | provider identity (**NPI** / provider id) to match to Carevero's roster deterministically |
| **Reference code tables** (CPT/HCPCS) | map claim lines to Carevero canonical procedures by exact code |
| **Geography fields** (on claims/provider) | service location / county / ZIP to attach at the correct granularity |

**Years:** request the **most recent 2–3 complete measurement years** available (claims data is
historical; recency matters for consumer relevance). Confirm available years on the DataSets page.

## 3. Exact official URLs the owner needs (nhchis.com — has a TLS cert quirk in tooling; open in a browser)
- Public Use Data Set **data dictionary (v1):** https://nhchis.com/DocumentDelivery/GetFile/15
- Limited Use Data Set data dictionary (v5): https://nhchis.com/DocumentDelivery/GetFile/25
- NHCHIS overview doc: https://nhchis.com/DocumentDelivery/GetFile/17
- DataSets catalog: https://nhchis.com/DataAndReport/DataSets
- Public-Use request log / process: https://nhchis.com/DataAndReport/PublicUseDataRequests
- Limited-Use request log: https://nhchis.com/DataAndReport/LimitedUseDataRequests
- Governing rule **INS 4000** (uniform reporting of health-care claims): https://www.insurance.nh.gov/sites/g/files/ehbemt861/files/inline-documents/sonh/ins-4000-chis-adopted.pdf
- NHID transparency program: https://www.insurance.nh.gov/about-us/transparency-efforts

## 4. Items to confirm on those pages before/at submission (I could not fetch nhchis.com through tooling — TLS cert)
- Exact **amount fields** present in the **Public Use** tier: is provider-specific `allowed_amount` included, or only aggregated/statewide? (Data dictionary GetFile/15.)
- **Provider granularity**: entity/organization vs specific service-location vs NPI.
- **Suppression / minimum-cell** rules in Public Use (NH HealthCost drops <4-patient cells; the dataset likely mirrors this).
- **Fees** (if any) and turnaround.
- **Exact request form** and **data-use-agreement** text (Public Use may be download-on-agreement; Limited Use is a formal application).
- **Commercial-use / redistribution** conditions and **required attribution** wording.

## 5. Draft "purpose of use" (for the request form)

> Carevero operates a consumer healthcare price-transparency website for New Hampshire residents.
> We intend to use the NHCHIS Commercial Claims Public Use Data Set to display **historical,
> claims-derived cost information** (e.g. median allowed amounts by procedure and provider),
> clearly labelled as claims-based historical estimates and kept **separate from** provider-
> published cash prices and hospital standard-charge data. The data will be presented with its
> measurement period, methodology, and NHCHIS attribution, will respect all suppression rules,
> and will never be represented as a personalized quote or as the patient's final cost. Purpose:
> to help NH consumers understand and compare the cost of shoppable health-care services.

## 6. Intended handling once approved (matches `docs/COST_DATA_ARCHITECTURE.md`)
- Land in the additive `CostEstimate` table as `source_class=CLAIMS_DERIVED`, `metric_type` set
  from the dataset's own definition (e.g. `median_allowed_amount`), with payer context,
  measurement period, component scope, suppression state, and full provenance + NHCHIS attribution.
- **Never** serialized/displayed as a provider-published price; comparability guard prevents
  cross-class "savings" claims.
- Deterministic **CPT → canonical-procedure** mapping (exact code); false-positive detector after
  each batch; provider match by NPI/id, not name.
- Validate the final `CostEstimate` schema against the **actual approved fields** before building
  the production migration.

## 7. Owner action required
Only the owner/organization can file the NHCHIS request and sign any DUA. This plan does not
submit anything. Once the dataset (and its exact fields/terms) is in hand, the claims layer is a
bounded additive build.
