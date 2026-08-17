# Carevero Multi-Source Cost Data Architecture (design)

Phase 8–10 of the multi-source cost directive. **Design only — not implemented** (per the directive:
"Do NOT blindly implement"; build the model when there is licensed data to populate it). Goal:
represent published prices, negotiated rates, and claims-derived costs **together but never
collapsed**, with complete provenance, comparability safety, and multi-state readiness.

## 1. The question every stored amount must answer
WHAT is this number · WHO produced it · from WHAT data · WHAT period · WHICH provider/location ·
WHICH service · quote-or-historical · cash/negotiated/claims · facility/professional/combined.

## 2. Semantic taxonomy (source-neutral, additive)

Three orthogonal axes rather than one enum, so new sources/states slot in without rework:

**A. `source_class`** — provenance family
`PROVIDER_PUBLISHED` (hospital MRF, provider cash/fee schedule) · `CLAIMS_DERIVED` (all-payer claims,
e.g. NHCHIS) · `STATE_AGGREGATE` (statewide/region/market statistics) · `PROVIDER_ESTIMATOR`.

**B. `metric_type`** — what the dollar figure *is* (use the source's own definition)
`cash_price` · `standard_charge` · `negotiated_rate` · `charge_minus_uninsured_discount` ·
`median_allowed_amount` · `median_paid_amount` · `episode_estimate`. (NH HealthCost insured →
`median_allowed_amount`; NHHC uninsured → `charge_minus_uninsured_discount`.)

**C. modifiers** — `billing_component` (facility / professional / combined), `scope`
(single_service / bundled / episode), `payer_category` + `payer_name`, `is_quote` (true for
provider quotes, false for historical claims).

The **existing hospital-MRF pricing keeps its current model** — it maps onto this taxonomy as
`source_class=PROVIDER_PUBLISHED`, `metric_type ∈ {standard_charge, negotiated_rate, cash_price}`.
No migration of existing data; the taxonomy is a superset.

## 3. Additive storage — a new `CostEstimate` sibling (NOT hospital_price_records)

Non-MRF cost data lands in a **new additive table**, never shoehorned into hospital price records:

```
CostEstimate(
  id, organization_id, service_location_id NULL,  # NULL when source is provider-level only
  procedure_id, source_id,                         # FK -> CostSource registry
  source_class, metric_type,
  amount, amount_low NULL, amount_high NULL, currency,
  billing_component, scope, payer_category, payer_name NULL, is_quote,
  measurement_period_start NULL, measurement_period_end NULL,
  sample_size NULL, suppression_state NULL,        # preserve NHCHIS suppression
  methodology_url, source_url, source_version, retrieved_at, provenance_json
)
```
Additive · reversible · provider-neutral · **state-neutral** (no `nh_*` names) · provenance-complete.
`service_location_id` is **NULL** when a source is provider-level only — we **never fabricate location
specificity** (Phase 18).

## 4. Source registry (`CostSource`)
First-class provenance for every source: `HOSPITAL_MRF`, `PROVIDER_PUBLISHED_SCHEDULE`,
`PROVIDER_ESTIMATOR`, `STATE_CLAIMS_DATASET` (instances: `NHCHIS`, future `MA_APCD`),
`STATEWIDE_RATES_REPORT`. Carries operator, dataset name/version, license/terms, attribution,
refresh cadence. Sources are data, not code — new states add rows, not schema.

## 5. Comparability guard (Phase 11 — critical)
A comparison ("you save $X") is allowed **only** when both amounts share: procedure/code, setting,
`billing_component`, `scope`, and a comparable `metric_type` **within the same `source_class`**.
`CLAIMS_DERIVED median_allowed_amount` is **never** auto-compared against `PROVIDER_PUBLISHED
cash_price`; they render side-by-side with distinct labels and no savings math. The **existing
hospital comparability engine is untouched**; this guard wraps cross-class comparisons.

## 6. Consumer model + labelling (Phases 12–13, 31, 33–34)
Provider/procedure pages show **separate, source-labelled sections**, only when real data exists:
- **Published prices** — Cash $X · Published insurance rates $A–$B.
- **Claims-based cost information** — "Typical allowed amount $Y · based on NH claims · period YYYY–YYYY"
  (never "what you'll pay"; actual responsibility varies by plan/deductible — no individualized advice).
Missing data → "Published pricing not currently available in Carevero" / "Cost information not
currently available" — **never `$0`, never "0 procedures"**.

## 7. Critical regression (Phase 39)
A `CLAIMS_DERIVED` record must **never** serialize or display as a provider-published price. Tests
must assert metric_type/source_class survive DB→API→UI→search→map→Ask Carevero, and that the
comparability guard rejects cross-class savings claims.

## 8. Ask Carevero (Phases 25–26)
May *explain* the difference between cash / negotiated / claims-based cost using grounded data;
may never generate/estimate/infer a price. `ai_modified_prices=0`; medical hard-gate unchanged.

## 9. Multi-state readiness (Phase 36)
Nothing is NH-specific: `CLAIMS_DERIVED` + a `CostSource` row (`NHCHIS`) generalize to MA APCD, ME,
VT, CT, RI by adding source rows — no structural rewrite. Same strategy applies to MA when its data
and license path are cleared.

## 10. Status
Design complete. **Implementation deferred** until (a) the NH HealthCost/NHCHIS reuse path is cleared
by the owner (see `docs/NH_HEALTHCOST_GAP_ANALYSIS.md` §2), or (b) provider-published fee schedules
are acquired — either of which gives real data to populate `CostEstimate`. The hospital MRF pipeline
is unaffected.
