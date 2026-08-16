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

## WAVE 2 — NH URGENT CARE — ✅ LIVE (2026-08-16)

Authoritative research from each chain's OFFICIAL directory (ConvenientMD:
`convenientmd.com/locations`; ClearChoiceMD: `ccmdcenters.com/locations/new-hampshire-urgent-care`).
Ingested (idempotent `scripts/ingest_nh_urgent_care_wave2.py`, tested) 26 fully
address-verified NH walk-in clinics:

| Organization | Locations | Capability | Price |
|---|---|---|---|
| ConvenientMD (urgent_care) | 15 — Bedford, Concord, Dover, Stratham, Keene, Merrimack, Nashua, Portsmouth, Windham, Belmont, Littleton, Londonderry, Manchester, Plaistow, West Lebanon | urgent_care | not available |
| ClearChoiceMD (urgent_care) | 11 — Alton, Epping, Gilford, Goffstown, Hooksett, Lebanon, Nashua, Plaistow, Rochester, Seabrook, Tilton | urgent_care | not available |

- **Capability discipline:** modeled as `urgent_care`, a DISTINCT capability from
  `emergency_department` — these clinics are never conflated with hospital ERs (test-enforced).
- **Verified:** organization identity + NH presence + street address + city/ZIP + phone +
  official URL (provenance `SourceFile` → directory). Coordinates: ZIP-centroid (approximate).
- **Price:** none published machine-readable → `price_available=false` (valid state; never $0).
- **Service availability:** intentionally NOT asserted per-procedure (no per-location priced
  menu source). Follow-up if an authoritative urgent-care price/service source appears.
- **Live (verified):** directory facet `urgent_care: 26` (paginated, `total=26`), search
  "urgent care"/"walk in clinic" → canonical_capability `urgent_care`, map 26 urgent_care pins
  (full NH map 54 = 25 hospital + 26 urgent_care + 3 lab). Detail page `is_hospital=false`,
  no CMS, no fabricated prices. Baseline 26/26·50/50 and safety PASS held.

## WAVE 3 — NH EMERGENCY DEPARTMENTS — ✅ LIVE (2026-08-16)

Capability-only wave (`scripts/ingest_nh_emergency_departments_wave3.py`, tested). NH's EDs
are hospital-based, so NO new facilities were created — an ED capability was layered onto the
existing hospital LOCATIONS, classified from the CMS facility-type designation already on
each facility:

| Class | Basis | Capability added | Count |
|---|---|---|---|
| Critical Access Hospital | 42 CFR 485.618 requires 24/7 emergency services | `emergency_department` | 13 |
| Acute Care Hospital | NH short-term general hospitals (CMS "Emergency Services = Yes") | `emergency_department` | 13 |
| Hospital-affiliated freestanding ER | `location_type=freestanding_emergency_room` | `freestanding_emergency_department` | 3 |
| Psychiatric (NH Hospital, Hampstead) | no general ED | **excluded** | 2 |

- **Freestanding ERs discovered:** Portsmouth Regional → **Dover** & **Seabrook**; Parkland →
  **Plaistow** (HCA-affiliated). Given the DISTINCT `freestanding_emergency_department`
  capability, never conflated with a hospital-campus ED or with `urgent_care`. (My initial
  assumption that NH had no freestanding ERs was wrong — the pre-write `--verbose` audit
  against prod caught it before any capability was written.)
- **Additive/reversible:** new LocationCapability rows only; no facilities, no pricing touched,
  audited hospital pipeline unmodified. Idempotent, provenance-backed (regulatory designation).
- **Live (verified):** directory facet `emergency_department: 26`, `freestanding_emergency_department: 3`;
  search "emergency room"→`emergency_department`, "freestanding er"→`freestanding_emergency_department`.
  Baseline 26/26·50/50 and safety PASS held.
- **Known follow-ups (flagged):** (a) a pre-existing DUPLICATE Parkland Derry `hospital_campus`
  location from the 0014 backfill (spawned a separate consolidation task — invisible to
  consumers, inflates counts); (b) the 3 freestanding-ER location rows lack coordinates, so
  they are discoverable in directory/search but not yet on the map (geocode follow-up).

## WAVE 4 — NH INDEPENDENT IMAGING — ✅ LIVE (2026-08-16)

Authoritative research from each provider's OFFICIAL directory (Derry Imaging:
`derryimaging.com/derry-imaging-2/locations`; Shields: `shields.com/locations`). Ingested
(idempotent `scripts/ingest_nh_imaging_wave4.py`, tested) 8 verified independent imaging
locations, capability `imaging`, `organization_type=imaging_center`:

| Organization | Locations | Capability | Price |
|---|---|---|---|
| Derry Imaging | 7 — Derry, Bedford, Concord, Dover, Londonderry, Raymond, Windham | imaging | not available |
| Shields Health Care Group | 1 — Portsmouth (Shields MRI) | imaging | not available |

- **Verified:** organization + NH presence + street address + city/ZIP + phone + official URL
  (provenance `SourceFile`). Coordinates: ZIP-centroid (all 8 geocoded → on map).
- **Price:** none machine-readable → `price_available=false` (never $0). **Follow-up flagged:**
  Derry Imaging is a price-transparency leader ("40–70% less than hospitals") — a strong
  candidate for a future cash-price ingestion (real prices + `LocationServiceAvailability`).
- **Service availability:** intentionally NOT asserted per-procedure (needs a priced menu).
- **Live (verified):** directory facet `imaging: 8`; search "imaging center"/"radiology
  center" → canonical_capability `imaging` (8 locations); map 8 imaging pins (full NH map 62 =
  25 hospital + 26 urgent_care + 8 imaging + 3 lab). Baseline 26/26·50/50 and safety PASS held.

## DATA-QUALITY FIX — PARKLAND DERRY DUPLICATE LOCATION — ✅ RESOLVED (2026-08-16)

Migration 0014's backfill left PARKLAND MEDICAL CENTER (CMS 300017) with two FacilityLocation
rows for the SAME physical Derry campus (1 Parkland Dr / "1 PARKLAND DRIVE", 03038): an ACTIVE
priced survivor (913 price summaries, 143,926 records) with NO coordinates, and an INACTIVE
geocoded twin holding only 2 capabilities. Because one was inactive, consumers already saw
Parkland once — but the geocode sat on the dead row, so Parkland was the one hospital missing
from the map.

Resolved WITHOUT data loss (`scripts/consolidate_parkland_derry_duplicate.py`, unit-tested,
run against a pre-change Cloud SQL backup):
- **Proved identity first** (read-only inspector across all 10 facility_location FK tables):
  same facility, type, city/state/ZIP, normalized address.
- Deterministic survivor = the row with the pricing; **merged the twin's coordinates onto it**
  (Parkland now has a map pin — 25→26 hospital pins); re-pointed all 10 FK classes; deduped
  the 2 colliding capabilities; asserted zero remaining refs; deleted the duplicate — one txn.
- **Regression guard:** `scripts/detect_duplicate_locations.py` flags any same-facility
  same-address location pair so backfills cannot recreate this. Now reports 0.
- **Verified:** Parkland appears once (`price_available` true, 50 procedures); baseline
  26/26·50/50; false-positive detector 0 (Parkland CLEAN); safety PASS; duplicate detector 0.

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
| 2 | Urgent care (ConvenientMD, ClearChoiceMD) | ✅ **live (2 orgs, 26 verified locations)** |
| 3 | Emergency departments / freestanding ER (as capabilities, no dup hospitals) | ✅ **live (26 hospital EDs + 3 freestanding ERs)** |
| 4 | Imaging centers (independent) | ✅ **live (2 orgs, 8 verified locations)** |
| 5 | Ambulatory surgery centers | ⏳ not started |
| 6 | Physical therapy + rehabilitation (kept distinct) | ⏳ not started |
| 7 | Chiropractic | ⏳ not started |

Per-wave report fields: provider category; organizations discovered/verified; locations
discovered/verified; services verified; locations with/without prices; price records;
source types; provenance; mapping gaps; safety issues; **26/26 · 50/50 · 0 FP · safety
PASS** re-verified; production deployment; commit.
