# NH Canonical Procedure Gaps — evidence-backed candidates

Status: **proposal only**. Nothing here is added to the catalog. The NH release runs on a
fixed **50/50** canonical procedure set; adding a canonical procedure is a deliberate,
reviewed change that must not silently alter the 50/50 gate or the coverage denominator.
Last updated: 2026-08-17.

Each candidate below is backed by a **real published price** we already verified but
**cannot map** because no canonical procedure exists. Do NOT invent a mapping to a
loosely-related existing slug (that would be a false-positive mapping).

## Candidates

### 1. Hemoglobin A1c (HbA1c) — blood test — **RECOMMENDED ADD (reviewed 2026-08-18)**
- **Evidence:** Quest questhealth.com HbA1c `496M` list **$39.00** (+ required $6 fee = $45 total,
  2026-08-17); **LabCorp OnDemand** `diabetes-risk-hbA1c-test` **$39.00** all-inclusive (verified
  2026-08-18). Both national DTC self-pay products exist and are verified.
- **Reviewed analysis (passes canonical-review rules):**
  - *Specificity:* unambiguous — a single analyte with one standard code, **CPT 83036**
    (HbA1c; 83037 is the point-of-care variant). Not a panel, not overlapping with CMP/BMP.
  - *Consumer usefulness:* high — diabetes monitoring is a top consumer lab search; both major
    labs sell it DTC. Distinct from the ambiguous "diabetes test" query (which stays a
    clarification between HbA1c and glucose — see candidate #7).
  - *Data support:* verified DTC prices from two organizations; hospital MRFs commonly publish
    83036, so hospital coverage is likely once mapped.
- **Recommendation:** ADD as canonical, deliberately, via the reviewed baseline-change sequence
  below. This is the strongest candidate (clean code + real dual-source data).
- **Exact implementation (deliberate — changes the 50/50 baseline to 51/51):**
  1. `scripts/seed_procedure_catalog.py`: add `hemoglobin-a1c` (consumer_name "Hemoglobin A1c
     (HbA1c)", category `laboratory`, CPT 83036, aliases a1c/hba1c/"diabetes blood test").
  2. Update every **50-count assertion** to 51 explicitly (search: `50/50`, tests asserting
     procedure totals, any release-gate constant) — never silently redefine the baseline.
  3. Reseed catalog + `scripts.rebuild_search_index` (job); map hospital 83036 rows via the normal
     approved-mapping flow; run fp-detector + `phase_4_7_safety`.
  4. Add HbA1c to `data/nh_dtc_lab_options.json` (Quest $45 total incl. fee; LabCorp $39) so the
     DTC section renders it automatically.
- **Until executed:** `NO_CANONICAL_PROCEDURE` (do not force-map).

### 2. Urgent-care visit (flat self-pay)
- **Evidence (documented earlier):** ConvenientMD flat urgent-care visit ~$175 (cap ~$265);
  ClearChoiceMD prompt-pay self-pay urgent-care visit ~$160. Both are visit-level flat
  self-pay prices, not a CPT-coded procedure.
- **Why a gap:** no canonical "urgent care visit" procedure; urgent-care today is a
  capability/location type, not a priced canonical service.
- **Proposed slug:** `urgent-care-visit` (E/M visit-level; note self-pay flat, not E/M code).
- **Blocker classification:** `NO_CANONICAL_PROCEDURE` / `PACKAGE_NOT_PROCEDURE`.

### 3. Physical therapy — evaluation and per-session
- **Evidence:** several NH PT providers publish self-pay eval + per-visit rates (roster in
  `data/nh_roster_expansion.json`; specific prices to be captured under the ledger).
- **Why a gap:** PT is a location capability; no canonical `pt-evaluation` / `pt-session`.
- **Proposed slugs:** `physical-therapy-evaluation` (CPT 97161–97163), `physical-therapy-session`
  (treatment visit). Keep eval and session distinct — different services/prices.
- **Blocker classification:** `NO_CANONICAL_PROCEDURE`.

### 4. Chiropractic visit
- **Evidence (documented earlier):** The Joint Chiropractic single visit ~$55, new-patient
  ~$29 (thejoint.com/plans-pricing). Membership/package pricing also present.
- **Why a gap:** no canonical chiropractic visit procedure; some prices are memberships.
- **Proposed slug:** `chiropractic-adjustment` (CPT 98940–98942). Separate any membership
  price as `MEMBERSHIP_PRICE`, not a per-visit procedure.
- **Blocker classification:** `NO_CANONICAL_PROCEDURE` / `MEMBERSHIP_PRICE`.

## Process to adopt any candidate (not done here)

1. Confirm the CPT/HCPCS identity and a clear consumer definition.
2. Add to the catalog as a **new** procedure (grows 50 → 50+N deliberately); update the
   release gate to the new N explicitly so "50/50" is never silently redefined.
3. Only then map the verified prices and run the normal review/promotion gates.

Until then these prices remain unmappable and are recorded as blockers in the acquisition
ledger — not published, not force-fit onto a wrong canonical slug.

## Additional lab candidates discovered via search-demand sweep (2026-08-17)

These are real consumer search terms that currently return no match because no
canonical procedure exists. Do NOT force-map; recorded for review.

### 5. Vitamin D test (25-hydroxyvitamin D)
- **Evidence:** high-frequency consumer search ("vitamin d test"); Quest/LabCorp both
  sell a DTC vitamin D product. Proposed slug `vitamin-d-test` (CPT 82306).
- **Blocker:** `NO_CANONICAL_PROCEDURE`.

### 6. PSA (prostate-specific antigen)
- **Evidence:** common preventive/self-pay search ("psa test"); Quest/LabCorp DTC product.
  Proposed slug `psa-test` (CPT 84153). Consumer name "PSA (prostate screening)".
- **Blocker:** `NO_CANONICAL_PROCEDURE`.

### 7. "Diabetes test" (ambiguous)
- **Evidence:** search term "diabetes test". **Ambiguous** — could mean HbA1c, fasting
  glucose, or OGTT. Per project rule (no fuzzy-mapping of ambiguous medical concepts) this
  is intentionally NOT mapped. If HbA1c is adopted (candidate #1), route "diabetes test" to
  a clarification between HbA1c and glucose rather than assuming one.
- **Blocker:** `NEEDS_REVIEW` (ambiguity).
