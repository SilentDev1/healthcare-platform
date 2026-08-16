# NH Provider-Neutral Expansion — status & wave tracker

Carevero is evolving from "which hospital is cheapest?" to "where can I get this
service, and what verified price information exists?" — across hospitals, labs, urgent
care, ER, imaging, ASCs, PT/rehab, chiropractic, and more. This doc tracks the
foundation and each NH provider wave. **Massachusetts is deferred** until the major NH
provider categories are proven.

Regression gates (never manipulate; verify after every change):
NH hospitals **26/26**, canonical procedures **50/50**, crosswalk false-positives **0**,
`phase_4_7_safety` **PASS**, raw hospital pricing/provenance preserved, 5-locale UI.

---

## FOUNDATION — ✅ DEPLOYED (2026-08-16)

Additive migration **`0014`** (reversible, idempotent) shipped and applied in prod:

- `organizations` + `Facility.organization_id` — business/health-system layer above
  locations; one org owns many locations. Backfill: 1 org per facility (1:1), reusing
  the facility UUID; type `hospital_system`.
- `location_capabilities` — one location → MANY capabilities; **ER (`emergency_department`)
  and `urgent_care` are DISTINCT** and never conflated. Backfill: `hospital` per location.
- `location_service_availability` — **"service offered here" is SEPARATE from "Carevero
  has a price."** offered / not_offered / unknown, evidence-backed. A verified location
  that offers a service with no price renders "Price not currently available in
  Carevero", never $0. Empty until waves populate it.
- `FacilityLocation.region/subregion` — sub-state filtering (NH ignores; MA needs it).
- `FacilityPriceSource.source_class` — non-hospital feeds not forced into MRF semantics.
  Backfill: `HOSPITAL_MRF`.

**Prod backfill verified** (`scripts/provider_neutral_coverage.py`): 28 organizations
(all hospital_system), 31 service locations, 32 `hospital` capabilities, 55 `HOSPITAL_MRF`
sources. Baseline unchanged: 26/26 · 50/50, safety PASS, 0 FP. Pre-migration Cloud SQL
backup taken. Rollback: `alembic downgrade 0013` (drops additive tables/columns only).

Observability is a **separate** axis from the hospital X/26 metric — offered vs priced
are reported as distinct counts, never collapsed.

### Foundation — remaining before Wave 1 data surfaces to consumers
- [ ] Provider-neutral **directory API**: generalize `location_type=="hospital_campus"`
      filter → capability filter; add `capabilities[]`, `organization`,
      `service_availability`, keep `price_available` + hospital-only fields.
- [ ] Provider-neutral **search**: resolve organization / service location / capability
      (e.g. "Quest Nashua", "urgent care Manchester") alongside procedures/categories;
      deterministic data still determines results.
- [ ] Provider-neutral **UI**: result cards show location name / organization / location
      TYPE / distance / service / price-state; neutral i18n keys alongside hospital keys;
      **state + provider-type + price-available filters** built now.
- [ ] **Map** capability pins/filters/clustering.
- [ ] AI resolver/tool contracts updated for provider-neutral entities (read-only; AI
      cannot invent provider/location/service/price). *(AI provider currently disabled.)*

---

## WAVE 1 — NH INDEPENDENT LABS — ✅ LIVE (2026-08-16)

Authoritative research from each provider's OFFICIAL location directory
(`locations.questdiagnostics.com/nh` — Quest lists 13 NH cities; `locations.labcorp.com/nh`
— Labcorp Bedford + others). Ingested (idempotent `scripts/ingest_nh_labs_wave1.py`,
tested) the fully address-verified sites:

| Organization | Location | Address | Capability | Price |
|---|---|---|---|---|
| Quest Diagnostics (independent_lab) | Nashua | 300 Main St #301B, 03060 | laboratory | not available |
| Quest Diagnostics | Manchester | 195 McGregor St, 03102 | laboratory | not available |
| Laboratory Corporation of America | Bedford | 101 Riverway Pl, 03110 | laboratory | not available |

- **Verified:** organization identity + NH presence + street address + phone + official URL
  (provenance `SourceFile` → directory). Coordinates: ZIP-centroid (honestly approximate).
- **Price:** none published in machine-readable form → `price_available=false` ("Published
  price not currently available in Carevero" — a valid, expected state; never $0).
- **Service availability:** intentionally NOT asserted per-procedure. The directory verifies
  the LOCATION and that it is a laboratory, not a per-location canonical test menu — asserting
  CBC/etc. without a test-menu source would be assumption, not evidence. Follow-up: source an
  authoritative per-location test menu, then add `LocationServiceAvailability(offered)`.
- **Live:** discoverable in the directory (`capability=laboratory` filter → 3), "lab"/
  "laboratory" capability search group, and the capability-aware map (3 lab pins). Rendered as
  "Independent Lab", no CMS (is_hospital false). Baseline 26/26·50/50 and safety PASS held.
- **Known gap / next:** remaining Quest NH cities (Amherst, Bedford, Claremont, Concord,
  Derry, Dover, Gilford, Goffstown, Londonderry, Pelham, Salem) and more Labcorp sites need
  address verification before ingest; per-location test menus for service availability.

## SOURCE-RESEARCH TEMPLATE (complete BEFORE each wave's ingestion)

For every provider category answer, with provenance:
1. Authoritative organization/location source? 2. Authoritative service-availability
source? 3. Public pricing source? 4. Machine-readable? 5. Location-specific pricing?
6. Coding system (CPT/HCPCS/…)? 7. Price type (cash/negotiated/estimate)? 8. Update
frequency? 9. Durable provenance? 10. Safe to automate? 11. Licensing/terms? 12. What
NOT to import. **Non-hospital pricing is different — do not force non-hospital providers
through the hospital MRF importer.** "PROVIDER FOUND / SERVICE VERIFIED / PRICE UNKNOWN"
is an expected, first-class state. Never $0; never fabricate availability or price.

---

## WAVES (deploy + QA each independently; do not wait for all)

| Wave | Category | Status |
|---|---|---|
| 1 | Independent laboratories (Quest, Labcorp) | ✅ **live (2 orgs, 3 verified locations)** |
| 2 | Urgent care (ConvenientMD, ClearChoiceMD, health-system — verify) | ⏳ not started |
| 3 | Emergency departments / freestanding ER (as capabilities, no dup hospitals) | ⏳ not started |
| 4 | Imaging centers (independent + hospital-affiliated) | ⏳ not started |
| 5 | Ambulatory surgery centers | ⏳ not started |
| 6 | Physical therapy + rehabilitation (kept distinct) | ⏳ not started |
| 7 | Chiropractic | ⏳ not started |

Per-wave report fields: provider category; organizations discovered/verified; locations
discovered/verified; services verified; locations with/without prices; price records;
source types; provenance; mapping gaps; safety issues; **26/26 · 50/50 · 0 FP · safety
PASS** re-verified; production deployment; commit.
