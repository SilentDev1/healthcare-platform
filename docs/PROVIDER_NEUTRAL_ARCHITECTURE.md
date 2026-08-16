# Provider-Neutral Architecture

Status: **FOUNDATION IMPLEMENTED + DEPLOYED (2026-08-16).** The additive schema layer
below is live in production as Alembic migration **`0014`** (the design originally
called this `0013`, but `0013` was taken by an unrelated FK-index migration, so the
provider-neutral migration shipped as `0014`). Models: `Organization`,
`LocationCapability`, `LocationServiceAvailability`, `Facility.organization_id`,
`FacilityLocation.region/subregion`, `FacilityPriceSource.source_class`
(`packages/database/models.py`, `pricing_models.py`). Backfill mapped everything to
hospital semantics (28 orgs 1:1, 32 `hospital` capabilities, 55 `HOSPITAL_MRF`
sources); baseline held **26/26 · 50/50**, safety PASS, 0 false-positive suspects.
Observability: `scripts/provider_neutral_coverage.py` (separate from the X/26 metric).
Remaining work: provider-neutral **API/search/UI** generalization, then the NH
non-hospital **waves** (labs first) — see `docs/NH_PROVIDER_EXPANSION.md`. Nothing here
weakens the current NH hospital pipeline, provenance, comparability, reviewed-mapping
safety, or resumable imports.

Product principle (locked): Carevero answers *"where can I get this care, what
verified price information do we have, how far away is it, and which prices are
actually comparable?"* — not merely *"which hospital is cheapest?"* Hospitals are
the **first and strongest pricing dataset**, not the product boundary.

The three concepts that must never collapse:

1. **PROVIDER / SERVICE LOCATION EXISTS**
2. **SERVICE IS OFFERED AT THAT LOCATION**
3. **CAREVERO HAS A VERIFIED PRICE FOR THAT SERVICE**

and the distinct "empty" states that must never all render as `0`/`$0`:
`NO PROVIDER` ≠ `NO SERVICE` ≠ `NO VERIFIED PRICE` ≠ `NO COMPARABLE PRICE` ≠
`NOT YET INGESTED`.

---

## 1. CURRENT MODEL (as-built)

Latest Alembic head: **0012** (linear, additive, idempotent-guard style).

**Provider / location**
- `Facility` — `packages/database/models.py:62`. `cms_certification_number` (unique,
  hospital CCN), `legal_name`, `display_name`, `facility_type` (free-text
  `String(100)`, from CMS, e.g. "Acute Care Hospitals"), `ownership_type`, `active`,
  `source_file_id`, `locations` → `FacilityLocation`. **No `Organization` entity** —
  Facility conflates organization + provider. Parent/child modeled loosely by
  `FacilityRelationship` (`models.py:409`) and a denormalized `health_system_name`
  string on the price source.
- `FacilityLocation` — `models.py:85`. Address, `city`, `state` (2-letter),
  `postal_code`, `county`, `latitude`, `longitude`, and **`location_type`**
  (`String(50)`, default/server_default `"hospital_campus"` — the only value used).
  This is the closest thing to a "capability" field but is single-valued.
- **No capability table** anywhere.

**Source / provenance**
- `SourceFile` — `models.py:211`. Generic: `source_type` free-text (values include
  `cms_hospitals_csv`, `nppes_json`, `hospital_price_mrf`), checksum, status, etc.
- `FacilityPriceSource` — `pricing_models.py:44`. **MRF-specific by design**:
  `machine_readable_file_url` (required), `cms_hpt_txt_url`, `declared_format`,
  `vendor_name`, `health_system_name`, `location_association_status`,
  `discovery_method`.
- Generic provenance: `FacilitySourceObservation` (`models.py:275`), `ImportRun`
  (`models.py:231`), `ImportCheckpoint`.

**Pricing (raw → consumer)**
- Raw, hospital-coupled by name/FK: `HospitalPriceRecord` (`pricing_models.py:230`,
  carries `setting`, `billing_class`, gross/cash/min/max, `facility_location_id`),
  `HospitalPriceRateDetail` (payer/plan negotiated rates), `PriceServiceCode`
  (`code_system`, `code`, FK `hospital_price_record_id`),
  `PriceRecordProcedureMapping` (reviewed → `procedure_id`).
- Consumer, generic-named: `FacilityProcedurePriceObservation`
  (`pricing_models.py:441`) and `FacilityProcedurePriceSummary`
  (`pricing_models.py:485`) — keyed by (facility, location, procedure, payer, plan,
  **`service_setting`**, **`included_component_scope`**), carrying cash/negotiated
  min/max/median, `publication_status`, provenance via `source_file_id` +
  `FacilityProcedurePriceSummarySource`.

**Consumer catalog — already provider-neutral**
- `Procedure`, `ProcedureCategory`, `ProcedureAlias`, `ProcedureCodeSystem`,
  `ProcedureCodeMapping`, `ProcedureBundle` (`models.py:478-578`). Code-system
  driven (CPT/HCPCS/MS-DRG/…) and setting-aware. No hospital coupling.

**Geo / market**
- `packages/markets.py` — `Market(code, name, consumer_visible, status)`,
  **state-only, no region/subregion tier**.
- `packages/geo.py` — offline centroid geocoding, coordinates on `FacilityLocation`.
  Cross-state by lat/lon.

**API**
- `GET /api/v1/facilities/directory` (`services/api/app/main.py:304`) — docstring
  "multi-state **hospital** directory"; hardcodes `location_type == "hospital_campus"`
  (`main.py:300,932`), `facility_type` filter, `cms_certification_number`.
  `pricing_status` from `coverage.py:8` (0 / <10 / ≥10 →
  `pricing_not_available_yet` / `limited_pricing` / `pricing_available`).
- Procedure comparison (`main.py:1715`, `/procedures/{slug}/comparison`) — item shape
  is **mostly provider-neutral already** (`facility_location_id`, `location_type`,
  `price_available`, cash/negotiated, `service_settings`, `comparability_status`,
  `distance_miles`, `source_url`); hospital-coupled fields are `cms_overall_rating`,
  `facility_type`.
- `GET /api/v1/pricing/coverage` (`main.py:2588`) — `nh_facilities`, state hardcoded
  "NH".

**Web / UI**
- Missingness is **already first-class**: `PriceRange` renders "Price not currently
  available" with `.price-missing` (`apps/web/app/components/ui.tsx:38`); `Money`
  renders "Not available" for `null` (`ui.tsx:15`); missing cash sorts to the end as
  `Infinity` (`ProcedureResults.tsx:43`); coverage `0` maps to status
  `pricing_not_available_yet`, not "0" (`coverage.py:15`).
- Terminology coupling: i18n has `hospitalsWithPrices*` ("{count} hospitals with
  published prices", `i18n.ts:96`), `availabilityAll: "All hospitals"`,
  `compareHospitals`, etc.; `ui.tsx:313` falls back to `facilityTypeHospital`.

---

## 2. HOSPITAL-SPECIFIC ASSUMPTIONS (what must generalize)

| Assumption | Location | Note |
|---|---|---|
| Provider identity == CCN | `Facility.cms_certification_number` | CCN is hospital-only; non-hospital providers use NPI/other |
| One location = "hospital_campus" | `FacilityLocation.location_type` default | single-valued; real locations have multiple capabilities |
| Directory shows only hospital campuses | `main.py:300,932` | filters `location_type=="hospital_campus"` |
| Price source == MRF | `FacilityPriceSource.*` | MRF-only fields; need multi-source classes |
| Raw price tables named `hospital_price_*` | `pricing_models.py:230,287` | naming/FK coupling only; behavior is generic |
| Coverage == NH hospitals | `coverage.py`, `main.py:2588` | `nh_facilities`; one metric |
| "N hospitals with prices" | i18n `hospitalsWithPrices*` | wrong noun for lab/imaging/etc. results |
| No "offered but unpriced" state | *(absent)* | **the key missing concept** |

---

## 3. WHAT ALREADY WORKS GENERICALLY (keep, do not rebuild)

- **Procedure catalog** — code-system driven, setting-aware, provider-neutral.
- **Comparability & billing-component safety** — `service_setting` +
  `included_component_scope` on observation/summary; savings only within approved
  cohorts (`services/api/app/comparison_insights.py`). Reusable across provider types
  unchanged.
- **Payer/plan entities** and **provenance/audit** tables — generic.
- **Geo** — coordinate-based, cross-state.
- **Missingness handling** — `null`/status-enum, not fake `0`, nearly everywhere.
- **Comparison response shape** — already "one row per physical service location"
  with `price_available` boolean and neutral fields.
- **Resumable importer** and **manual-stage tool** — source-agnostic ingestion.

---

## 4. PROPOSED MODEL (target)

```
ORGANIZATION            (Quest Diagnostics; a hospital system; an independent clinic)
      ↓ 1..n
SERVICE LOCATION        (Quest — Nashua; Hospital Campus; Imaging Center — Bedford)
      ↓ 1..n
LOCATION CAPABILITIES   (independent_laboratory; hospital + emergency_department + imaging)
      ↓ n..n
SERVICES / CANONICAL PROCEDURES   (CBC; MRI knee; PT evaluation)   ← existing catalog
      ↓
SERVICE AVAILABILITY    (offered? with what evidence/source?)      ← NEW, separate from price
      ↓
PRICE OBSERVATIONS      (verified price, when present)             ← existing pricing chain
      ↓
SOURCE + PROVENANCE     (source class, url, checksum, retrieval)   ← existing, generalized
```

The design keeps the **existing `Facility`/`FacilityLocation`** as the service-location
layer (rename is unnecessary and risky) and adds thin layers **above** (Organization)
and **beside** (Capabilities, ServiceAvailability, source class).

### 4a. ORGANIZATION MODEL
New `organizations` table: `id`, `canonical_name`, `organization_type`
(canonical id, e.g. `hospital_system`, `independent_lab`, `imaging_group`,
`physician_group`, extensible), `npi_org` / `ein` (nullable), `active`. Add nullable
`Facility.organization_id` FK. **Backfill: one organization per existing Facility
(1:1)** so nothing changes for hospitals; multi-location orgs (Quest) attach many
locations to one org later. `Facility` stays the location-bearing entity; the
organization is additive metadata, not a restructure.

### 4b. SERVICE LOCATION MODEL
Keep `FacilityLocation` as the service location. Add nullable `region` /
`subregion` columns (see §4f) and treat `FacilityLocation` as the join anchor for
capabilities and service availability. No behavior change for hospitals.

### 4c. CAPABILITY MODEL
New `location_capabilities` table: (`facility_location_id`, `capability` canonical id,
`evidence`/`source_id` nullable, `active`), unique on (location, capability).
**One location → many capabilities.** Capability is a **stable canonical identifier**;
display labels live in i18n. Seed taxonomy (examples, not a frozen universe):
`hospital, hospital_outpatient, emergency_department,
freestanding_emergency_department, urgent_care, walk_in, laboratory,
independent_laboratory, imaging, mri, ct, radiology, mammography,
ambulatory_surgery, endoscopy, physical_therapy, occupational_therapy,
speech_therapy, rehabilitation, chiropractic, primary_care, pediatrics,
specialty_clinic, dialysis, infusion, other`.
**Backfill: every existing `FacilityLocation` (all `hospital_campus`) →** capability
`hospital` (+ optionally `emergency_department`, `laboratory`, `imaging`,
`outpatient_rehabilitation` where the hospital's data evidences them). `location_type`
is retained as a coarse primary type; capabilities are the extensible truth.
ER and urgent care are **separate capabilities** and must never be conflated.

### 4d. SERVICE AVAILABILITY MODEL (the key new separation)
New `location_service_availability` table:
(`facility_location_id`, `procedure_id`, `availability_status`
∈ {`offered`, `not_offered`, `unknown`}, `evidence_source_id` nullable,
`verified_at`, `active`). This represents **"service is offered here"** independently
of whether Carevero has a price. Today availability is *implied* by a priced record;
this makes it explicit and lets a verified location show a service with **"Price not
currently available in Carevero"** rather than being hidden or shown as `$0`.
For hospitals, backfill is optional/derivable (a priced procedure ⇒ `offered`); the
table matters for future non-hospital location directories that publish service
menus without standardized prices.

### 4e. PRICE AVAILABILITY MODEL
Unchanged pricing chain (`FacilityProcedurePriceSummary` etc.). Price availability is
a **third, separate state** already expressed as publishable-summary presence + the
`price_available` boolean in the API. Rule reinforced: **missing price ⇒ `null` ⇒
"Price not currently available in Carevero"; NEVER `$0`; a count of `0` ⇒ a truthful
status string, never "no provider/service".** (Guard to add: ensure `Money`
(`ui.tsx:15`) can never render `$0` for a *missing* amount — upstream already sends
`null`, so this is a defensive test, not a behavior change; a genuine `$0` charge, if
ever real, is a real value and may show as `$0`.)

### 4f. SOURCE MODEL
Add a `source_class` canonical column to the source layer (nullable, additive),
values: `HOSPITAL_MRF`, `HEALTH_PLAN_TRANSPARENCY`, `PROVIDER_PUBLISHED_PRICE`,
`AUTHORIZED_PROVIDER_FEED`, `GOVERNMENT_DATA`, `OTHER_VERIFIED_SOURCE`. Existing
`FacilityPriceSource` rows backfill to `HOSPITAL_MRF`. Every source still requires
verification; this is taxonomy, not ingestion. Region/subregion: add nullable
`region`/`subregion` to `FacilityLocation` + a lookup in `packages/geo.py`
(MA needs sub-state filtering for its far larger provider population); NH ignores it.

---

## 5. IMPACT

**Search** (`packages/search`, `SearchDocument`): become provider-neutral — resolve
consumer terminology ("blood work" → laboratory category; "urgent care" → capability;
"rehab" → *clarify*, never silently → PT) while **deterministic Carevero data
determines results**. Add `capability` and `region` to the search doc. AI/fuzzy may
find candidate terminology; it must not approve mappings.

**API**: `directory` generalizes from `location_type=="hospital_campus"` to a
`capability` filter (default: all consumer-visible); response gains `capabilities[]`,
`organization`, `service_availability` and keeps `price_available`. Add
provider-neutral aggregates (see §6). Hospital-specific fields (`cms_overall_rating`,
CCN) remain, populated only for hospital locations. Comparison endpoints already
neutral in shape — add `capability`/`organization` and keep component-scope
comparability intact.

**UI**: generic procedure/search results say **"locations/places with published
prices"** (new i18n keys) while hospital-specific pages may keep "Hospitals". Add
capability filters *only for datasets we possess*. Location detail card gains
name / parent organization / capabilities / services / price-availability states —
no fabricated fields.

**Map**: pins/filters by capability (hospital, ER, urgent care, lab, imaging, surgery,
PT, rehab, chiropractic, clinic) as datasets arrive; card shows capabilities +
per-state price availability. No fabricated fields.

**AI contract**: prepare data contracts (capability, availability, provenance,
candidate-vs-approved separation) but **do not merge AI here**. AI may discover
candidates/intent/anomalies; it must **never** invent providers/locations/prices/
insurance/clinical mappings, approve candidates, change source prices, determine
clinical equivalence, or tell a consumer to avoid an ER because another setting is
cheaper. Candidate discovery stays separate from approved deterministic mapping
(mirrors `scripts/audit_procedure_mapping_coverage.py`).

---

## 6. COVERAGE METRICS (multiple honest numbers, never collapsed)

Keep `NH HOSPITAL MRF COVERAGE X/26` intact and **separate**. Add architecture for:
`TOTAL VERIFIED SERVICE LOCATIONS`, `VERIFIED LOCATIONS BY CAPABILITY`,
`LOCATIONS WITH VERIFIED SERVICE DATA`, `LOCATIONS WITH VERIFIED PRICING`,
`LOCATIONS WITH COMPARABLE PRICING FOR PROCEDURE X`,
`PROVIDER-TYPE DATASET COVERAGE`. Do not redefine hospital MRF coverage as
all-provider coverage.

---

## 7. MIGRATION PLAN (smallest safe additive step)

**Recommended first migration `0013` (additive only, reversible):**
1. `organizations` table + nullable `Facility.organization_id` FK; backfill 1 org per
   Facility.
2. `location_capabilities` table; backfill `hospital` for every existing location.
3. `location_service_availability` table (empty; derivable for hospitals later).
4. Nullable `source_class` column on the source layer; backfill `HOSPITAL_MRF`.
5. Nullable `region`/`subregion` on `FacilityLocation`.

All new tables/columns are **additive**; no existing column is dropped/renamed; the
raw `hospital_price_*` tables are **not** renamed (naming-only coupling; a rename is
high-risk and unnecessary now). Follow the repo's idempotent inspector-guard pattern
(`0007`, `0008`). API/UI generalization ships **behind the existing shapes** (new
fields additive; neutral i18n keys added alongside hospital keys) so nothing breaks.

Sequencing per directive — do this **only after** current NH work is stable:
finish Cottage import, preserve 24/26 baseline, Concord–Laconia mappings, the
50-procedure audit, mapping-gap fixes, search-taxonomy consistency — *then* land
`0013`, *then* research non-hospital datasets (labs first).

## 8. BACKWARD COMPATIBILITY
- Existing hospital rows unchanged; `organization_id`, capabilities, `source_class`
  all backfilled to hospital semantics.
- Existing endpoints keep their fields; new fields are additive and nullable.
- Hospital pages keep "Hospitals" terminology; only generic results adopt neutral
  copy. Coverage `X/26` metric untouched.
- No change to comparability, provenance, reviewed-mapping, savings, i18n behavior,
  facility identity, or resumable imports.

## 9. ROLLBACK PLAN
- `0013` `downgrade()` drops the additive tables/columns (no data loss to existing
  hospital tables, which are untouched). Pre-migration Cloud SQL backup as usual.
- API/UI generalization is feature-additive; reverting the web build restores prior
  copy without schema impact. Because the migration is additive-only, rollback is a
  standard `alembic downgrade -1` after restoring the backup if needed.

---

## 10. REQUIRED TEST SCENARIOS (must be representable)

| Case | Scenario | Representable after `0013`? |
|---|---|---|
| 1 | Hospital + CBC + verified price | ✅ today (priced summary) |
| 2 | Independent lab + CBC + verified price | ✅ org=lab, capability=`independent_laboratory`, priced summary |
| 3 | Independent lab + CBC **offered, no price** | ✅ **new**: `service_availability=offered`, no summary → "Price not currently available" |
| 4 | Hospital + MRI knee | ✅ today |
| 5 | Independent imaging center + same canonical MRI knee | ✅ capability=`mri`/`imaging`, same `procedure_id` |
| 6 | Hospital outpatient PT + PT evaluation | ✅ capability=`physical_therapy`, setting=outpatient |
| 7 | Independent PT clinic + same canonical service | ✅ org=clinic, same `procedure_id`; comparability guards keep hospital-vs-clinic scope honest |
| 8 | Chiropractic location + chiropractic service + **no price** | ✅ capability=`chiropractic`, availability=offered, no price |
| 9 | Urgent care location | ✅ capability=`urgent_care` (distinct from ER) |
| 10 | Hospital emergency department | ✅ capability=`emergency_department` (distinct from urgent care) |

ER (`emergency_department`) and urgent care (`urgent_care`) are **distinct
capabilities**; no cross-setting savings ("save $X by choosing urgent care over the
ER") without a separate reviewed clinical-equivalence product requirement (we do not
have one). Price alone never drives an emergency-care recommendation.

---

## 11. ACCEPTANCE (per directive)

The provider-neutral foundation is complete **only when provider identity, physical
location, capabilities, service availability, pricing availability, and provenance are
cleanly separated and existing hospital functionality remains intact** — not merely
when provider types are added to an enum. This document is the design gate; the
`0013` additive migration + the neutral API/UI/search contracts are the
implementation, to be scheduled after current NH work stabilizes and reviewed before
any production migration.

**Most important remaining architectural risk:** the missing **service-availability**
separation (offered ≠ priced). Until it exists, a verified non-hospital location that
offers a service but has no Carevero price cannot be represented honestly, which is
the crux of the provider-neutral promise. `0013`'s `location_service_availability`
table closes it.
