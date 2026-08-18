# NH Canonical Procedure Gaps — evidence-backed candidates

Status: **proposal only**. Nothing here is added to the catalog. The NH release runs on a
fixed **50/50** canonical procedure set; adding a canonical procedure is a deliberate,
reviewed change that must not silently alter the 50/50 gate or the coverage denominator.
Last updated: 2026-08-17.

Each candidate below is backed by a **real published price** we already verified but
**cannot map** because no canonical procedure exists. Do NOT invent a mapping to a
loosely-related existing slug (that would be a false-positive mapping).

## Candidates

### 1. Hemoglobin A1c (HbA1c) — ✅ ALREADY CANONICAL (correction, 2026-08-18)
- **NOT A GAP.** HbA1c already exists as canonical procedure **`a1c-test`** ("Hemoglobin A1C
  test", category `laboratory`) — one of the existing **50**. An earlier note in this file
  mislabeled it a gap (a grep missed the `-test` slug suffix); that was incorrect and is
  retracted here.
- **Verified live (2026-08-18):** search `A1C` / `A1C test` / `HbA1c` / `Hemoglobin A1c` /
  `hba1c` all resolve to `a1c-test`; `diabetes test` correctly stays ambiguous (unknown, not
  auto-A1C). Hospital coverage: **24/26** hospitals publish an `a1c-test` price (cash $12–$146,
  negotiated $6–$9). No new procedure was created — creating `hemoglobin-a1c` would DUPLICATE
  `a1c-test` and corrupt the 50/50 baseline, so it was deliberately NOT done.
- **DTC:** verified Quest ($45 total = $39 + required $6 fee) and LabCorp OnDemand ($39
  all-inclusive) HbA1c prices are wired to `a1c-test` in `data/nh_dtc_lab_options.json`, so the
  procedure's DTC section renders them.
- **Naming note:** the slug is `a1c-test` (not `hemoglobin-a1c`); consumer_name is already
  "Hemoglobin A1C test". A slug rename was avoided — it would break 24 live hospital mappings
  and existing URLs for no consumer benefit.

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

### 5. Vitamin D test (25-hydroxyvitamin D) — ✅ ADDED as canonical #51 (2026-08-18)
- **Slug** `vitamin-d-test` ("Vitamin D test", laboratory) · **CPT 82306** (exact approved
  mapping; 82652 = the different 1,25-dihydroxy form, excluded).
- **Live:** search (vitamin d / vitamin d test / 25-hydroxy) → `vitamin-d-test`; **16/26 hospitals**
  publish it (cash $78–$326 sample, median ~$185); DTC Quest **$81** ($75 + $6 fee) / LabCorp **$99**
  (all-inclusive), both verified 2026-08-18. Baseline 50→51; fp-detector 26/26 CLEAN; safety PASS.
- Medical gate hardened alongside: "Do I need a vitamin D test?" refuses pre-LLM.

### 6. PSA (prostate-specific antigen) — ✅ ADDED as canonical #52 (2026-08-18)
- **Slug** `psa-test` ("Prostate-specific antigen (PSA) test", laboratory) · **CPT 84153** (exact
  approved mapping; total PSA). Aliases: psa / psa test / prostate specific antigen / prostate-
  specific antigen test. NOT aliased: broad "prostate test/exam" (DRE, MRI, biopsy).
- **Live:** search → `psa-test`; **16/26 hospitals** publish it (cash $30–$208 sample, median
  ~$108); DTC LabCorp **$69** (all-inclusive) / Quest **$75** ($69 + $6 fee), verified 2026-08-18.
  Baseline 51→52; fp-detector 26/26 CLEAN; safety PASS. "Should I get a PSA test?" refuses pre-LLM.

### 7. "Diabetes test" (ambiguous)
- **Evidence:** search term "diabetes test". **Ambiguous** — could mean HbA1c, fasting
  glucose, or OGTT. Per project rule (no fuzzy-mapping of ambiguous medical concepts) this
  is intentionally NOT mapped. If HbA1c is adopted (candidate #1), route "diabetes test" to
  a clarification between HbA1c and glucose rather than assuming one.
- **Blocker:** `NEEDS_REVIEW` (ambiguity).
