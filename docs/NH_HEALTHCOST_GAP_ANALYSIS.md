# NH HealthCost — Research, Cost Semantics, Reuse Determination & Gap Analysis

Phase 1–7 of the multi-source cost directive. Research only; **no production data changed.**
All facts below are from official sources (cited); nothing is inferred from UI labels alone.

## 1. Source facts (official)

| Item | Finding | Source |
|---|---|---|
| Operator | **New Hampshire Insurance Department** (state agency), Concord NH | nhhealthcost.nh.gov |
| Underlying data | **NHCHIS** — NH Comprehensive Health Care Information System, an all-payer claims database (since 2005), statutory basis **RSA 420‑G**, rule **INS 4000** | nhchis.com; insurance.nh.gov |
| Code system | **CPT** (medical) / **CDT** (dental) — services ARE code-defined | methodology-health-costs-consumers |
| Cost metric (insured, carrier selected) | **Median amount PAID** (insurer + patient) based on the **negotiated / "allowed" amount** — explicitly *not* provider charges | methodology page |
| Cost metric (uninsured) | **Charges minus any provider uninsured discount** (NHID has *not* verified discounts) | methodology page |
| Risk adjustment | None (actual calculated rates) | search result |
| Component scope | Varies: imaging includes **facility + professional**; some are single procedures; bundled services combine components | methodology page |
| Suppression | Ceiling >95th pct of charges removed; per-provider drop lowest 1% + highest 5%; **not published if high variability + <4 patients** | methodology page |
| Granularity | **Ambiguous** — likely provider-level aggregation, not clearly per physical location | methodology page |
| Payer specificity | **Yes** — figure depends on the carrier selected (per-payer negotiated median) | methodology page |
| Measurement period | Not stated on methodology page (needs the dataset/period metadata) | methodology page |
| Structured data | Authoritative data available **only via formal NHCHIS public-use / limited-use data-request processes** (application + data-use agreement) | nhchis.com |
| Consumer-site terms | **No explicit reuse license / copyright / permission statement** on the site or methodology page | methodology page |

**Corrected semantics (supersedes my earlier "gov_estimated_charge" shorthand):** NH HealthCost is
**not one metric**. It is, per payer context: (a) **claims-derived median negotiated/allowed amount**
(insured), or (b) **provider charge minus unverified uninsured discount** (uninsured). Both are
**historical, claims/charge-derived, payer-contextual** — categorically different from a provider's
own *published cash price* or a hospital MRF *standard charge / negotiated rate*.

## 2. Reuse determination (Phase 3) — ⛔ OWNER DECISION REQUIRED

Per the directive's stop condition #1 ("licensing/reuse materially ambiguous") and #2 (a formal
agreement / owner action is required), the NH HealthCost **ingestion path is paused pending owner
input**:

- The **authoritative** underlying data (NHCHIS) is obtainable **only through a formal public-use or
  limited-use data request** with a **data-use agreement** — an application the owning organization
  must file and agree to (fees/terms possible). I cannot complete that autonomously.
- The consumer website carries **no explicit reuse license**. Absence of a license is *not*
  permission. Bulk programmatic reuse of the rendered consumer values for a commercial product,
  absent explicit terms, is **materially ambiguous** — and the directive says prefer the underlying
  official dataset over scraping, don't scrape for convenience, and don't proceed when reuse is
  ambiguous.

**Owner decision (one of):**
1. Pursue the **NHCHIS data-use agreement** (public-use or limited-use extract) — gives authoritative,
   structured, properly-licensed data. Preferred. Requires owner/organization to apply.
2. Obtain **written confirmation** from NHID that reuse of the consumer NH HealthCost values is
   permitted for Carevero, with attribution terms.
3. Decline the NHHC path; rely on the provider-published acquisition track.

Until (1) or (2), **no NH HealthCost values will be ingested.** The **cost-data architecture is
designed now** (see `docs/COST_DATA_ARCHITECTURE.md`) so that, if/when the license path clears, the
NHCHIS layer drops in additively with no rework.

## 3. Gap analysis (representative; no bulk scraping)

- **Procedure overlap — strong.** NH HealthCost services are **CPT/CDT-coded**, so mapping to
  Carevero's code-based canonical procedures would be **exact-code** where a matching CPT exists
  (EXACT_CODE_MATCH), not name-only. Carevero's 50 canonical hospital procedures (MRI/CT/X-ray/labs/
  colonoscopy/etc.) are common CPT services present in NHHC. Bundled/episode services (some imaging,
  surgery) are MULTI_COMPONENT / EPISODE_OF_CARE and must not be equated to a facility-only price.
- **Provider overlap — broad but granularity-ambiguous.** NHHC lists NH providers across imaging,
  urgent care, labs, ASC, PT, chiropractic (Derry Imaging + ConvenientMD confirmed), i.e. it covers
  much of the 122. But NHHC granularity is **provider-level (ambiguous)**, so a value may apply to an
  organization/entity rather than a specific branch — it must be stored at the correct level, never
  fanned out to every location to inflate coverage (Phase 18).
- **Metric separation — mandatory.** Any NHHC value would be stored as a **claims-derived** cost with
  payer context + measurement period + component scope + suppression state, and **never** serialized
  or displayed as a provider-published price (Phase 39 critical regression).

Full per-procedure and per-provider gap tables will be completed against the **authoritative
structured extract** once the reuse path is cleared — doing them by scraping the consumer site now
would both be unreliable and pre-judge the reuse decision.

## 4. Complementary track (unblocked) — continues

Provider-**published** price acquisition (`data/nh_pricing_acquisition_ledger.json`,
`docs/NH_PROVIDER_PRICING_AUDIT.md`) is **not** blocked and remains the active autonomous track:
national-lab DTC (Quest/LabCorp), urgent-care self-pay (ConvenientMD $175/$265 cap, ClearChoiceMD
prompt-pay), imaging, PT/chiro self-pay, and **affiliated-hospital MRF linkage** (Wentworth-Douglass,
Elliot). Published prices remain valuable even where claims data exists.
