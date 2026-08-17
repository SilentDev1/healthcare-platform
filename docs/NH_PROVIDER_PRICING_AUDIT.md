# NH Non-Hospital Pricing Acquisition — Audit & Strategy

**Baseline (production authority, 2026-08-17):** 148 NH locations · **26 priced** · **122 unpriced**.
All non-hospital capabilities are **0 priced** (urgent_care 0/39, physical_therapy 0/33,
laboratory 0/24, ambulatory_surgery 0/10, imaging 0/10, rehabilitation 0/4, chiropractic 0/3);
EDs 26/26 and hospitals 26/28 are priced via hospital MRFs. So the 122 gap is entirely
**non-hospital pricing acquisition**.

The 122 unpriced locations belong to **34 organizations** (organization-first is essential —
one source can cover many locations). Full per-location matrix + resumable dispositions:
`data/nh_pricing_acquisition_ledger.json`; roster table: `docs/NH_MISSING_PRICING_ACQUISITION.md`.

## 🔑 Primary source discovered: NH HealthCost (state government)

`nhhealthcost.nh.gov` — the **New Hampshire Insurance Department's** price-transparency tool —
publishes **per-provider, per-procedure** cost data derived from the **NH Comprehensive
Healthcare Information System** (all-payer claims, updated quarterly). Confirmed on-site for
non-hospital NH providers across capabilities (Derry Imaging → ~20 imaging procedures
$144–$5,141; ConvenientMD → present). This is **authoritative government-published pricing**
(source-authority tier #7) and likely covers the majority of the 122 NH providers.

**But its semantics require a reviewed design (not a rushed ingest):**
- **Price type is distinct:** "estimate of the total charge before any uninsured discount",
  claims-derived — **NOT** the provider's own published cash price. Must be stored as a new
  `price_type` (e.g. `gov_estimated_charge`) with full provenance, and **comparability-guarded**
  (Phase 20) so it never silently competes against hospital-MRF cash/negotiated prices.
- **No CPT codes** — description-only. Requires **deterministic, evidence-backed description →
  canonical-procedure mapping**, with the false-positive detector run after each batch.
- **HTML only** (no CSV/JSON/API on provider pages) — needs a dedicated collector that fetches
  per-provider pages. **Phase 14 gate:** verify robots.txt / terms permit programmatic access;
  do not bypass any protection.

This is the recommended **primary next batch**, because one collector could unlock a large
fraction of the 122 across imaging, urgent care, labs, ASC, PT, chiro. It is deliberately
**not** ingested in this pass because introducing a new authoritative source + new price_type +
comparability model is exactly the "schema decision that could affect production pricing" the
directive says to design carefully — owner-visible before it ships.

## Organization dispositions (top orgs = ~75 of 122 locations)

| Org | Locs | Cap | Finding | Reason code(s) |
|---|---:|---|---|---|
| ConvenientMD | 15 | urgent care | Own site: $175 base visit, $265 cap (labs separate) — org-wide, **visit-level not per-CPT**. Also on NH HealthCost. | PUBLIC_CASH_SCHEDULE_FOUND; GOV_SOURCE; SERVICE_NOT_SPECIFIC |
| Quest Diagnostics | 14 | laboratory | questhealth.com DTC self-pay test prices — **national/org-wide** e-commerce, JS; bundle→canonical mapping needed | PUBLIC_CASH_SCHEDULE_FOUND; NEW_COLLECTOR |
| ClearChoiceMD | 11 | urgent care | "Prompt pay" self-pay program (ccmdcenters.com/prompt-pay) — research applicability | PUBLIC_PRICE_SOURCE_FOUND (to verify) |
| LabCorp | 10 | laboratory | Labcorp OnDemand DTC self-pay — same national model as Quest | PUBLIC_CASH_SCHEDULE_FOUND; NEW_COLLECTOR |
| Derry Imaging | 7 | imaging | Own site = **custom quote only** (patient data); NH HealthCost has ~20 procedures | GOV_SOURCE; REQUIRES_PATIENT_DATA |
| Northeast Rehab Network | 7 | PT/rehab | PT self-pay session rates — research; membership≠procedure | NEEDS_MANUAL_REVIEW |
| Wentworth-Douglass | 7 | PT/urgent care | **Affiliated to a priced NH hospital** — parent MRF may cover these; verify via MRF location/NPI linkage | AFFILIATED_HOSPITAL_SOURCE; NEEDS_DB_LINKAGE |
| Elliot Health System | 3 | urgent care | Affiliated to a priced NH hospital — same MRF-linkage check | AFFILIATED_HOSPITAL_SOURCE; NEEDS_DB_LINKAGE |
| The Joint Chiropractic | 3 | chiropractic | Single-visit cash price defensible; membership/package must NOT become a procedure price | PUBLIC_PRICE_SOURCE; SERVICE_NOT_SPECIFIC |

Remaining ~25 smaller organizations (PT/chiro/ASC/lab singletons) carry `NEEDS_MANUAL_REVIEW`
in the ledger and are pending the same organization-first research.

## Fastest safe wins (recommended order for the next batch)
1. **Affiliated-hospital MRF linkage (Phase 12/17)** — Wentworth-Douglass, Elliot, and any
   unpriced location whose parent hospital is already a priced Carevero hospital. Requires a
   **DB read** of existing raw hospital price records for applicable location/NPI/service-location
   identifiers. No external source, fully evidence-backed — the safest reduction of the gap.
2. **NH HealthCost collector** (owner-reviewed design: new price_type + comparability + robots
   check + description mapping) — broadest coverage.
3. **National-lab DTC** (Quest / LabCorp) — org-wide cash test prices, mapped to canonical
   CBC/CMP/lipid/A1C/TSH/UA, labelled org-wide applicability.
4. Per-chain urgent-care / PT / chiro self-pay where a fixed public cash amount is defensible.

## Guardrails (unchanged, enforced every batch)
No fabricated/estimated/AI/inferred prices; no `$0` for missing; no "0 procedures" for
"no pricing" (use "Published pricing not currently available in Carevero"). Every price keeps
full provenance + price_type + scope/component; false-positive detector = 0; 26/26 · 50/50
hospital baseline untouched; `ai_modified_prices = 0`.
