# Massachusetts Hospital Identity Audit — Phase 2

**Scope:** the 53 operating general acute + critical-access hospitals (`data/ma_hospitals_seed.json`).
**Source of truth:** CMS Hospital General Information snapshot (`data/ma_cms_hospital_snapshot.json`,
dataset `xubh-q36u`, retrieved 2026-08-18). **Identity/geography only — no pricing.**
**Result: PASS** — every hospital is a distinct real facility; no closed/specialty leakage; region reconciles to 53.

## Checks

| # | Check | Result |
|---|---|---|
| 1 | CCN uniqueness | **53/53 unique**, no duplicate CCNs |
| 2 | Duplicate physical address | **None** — no two distinct CCNs share a street address |
| 3 | Multi-campus single-CCN facilities | 6 flagged (one identity each — do **not** split) |
| 4 | Closed-hospital leakage (Carney/Nashoba/Norwood) | **None** in the active denominator |
| 5 | Specialty-acute leakage (Mass Eye&Ear/NE Baptist/AdCare) | **None** in the active denominator |
| 6 | Name vs CMS-name divergence | 2 benign (health-system-prefixed CMS labels) |
| 7 | Region resolves 1-of-10, reconciles to 53 | **PASS** (via `scripts/verify_ma_foundation.py`) |

## Multi-campus single-CCN facilities (seed one identity each)

These bill under a single CCN across more than one physical site. Carevero seeds **one facility
location per CCN** (the CMS primary-campus address); satellite campuses under the same CCN are a
later location-refinement step, **not** separate hospitals. Splitting them would fabricate distinct
facilities; collapsing distinct CCNs would hide real ones — neither is done.

- `220011` Cambridge Health Alliance (Cambridge)
- `220033` Northeast Hospital Corporation / Beverly Hospital (Beverly)
- `220080` Holy Family Hospital (Methuen)
- `220175` MetroWest Medical Center (Framingham)
- `220074` Southcoast Hospitals Group (Fall River)
- `220001` UMass Memorial HealthAlliance-Clinton Hospital (Leominster)

## Name divergences (benign — consumer name retained)

CMS has begun prefixing some facilities with their owning system; the seed keeps the common
consumer-facing name and records the CMS string as an alternate. No identity ambiguity.

- `220010` Lawrence General Hospital ↔ CMS "MERRIMACK HEALTH LAWRENCE HOSPITAL"
- `220073` Morton Hospital ↔ CMS "BROWN UNIVERSITY HEALTH MORTON HOSPITAL"

## Region reconciliation (all 53)

| Region | Hospitals |
|---|---:|
| Greater Boston | 14 |
| Pioneer Valley | 7 |
| Central Massachusetts | 6 |
| North Shore | 4 |
| MetroWest | 4 |
| South Shore | 4 |
| Southeastern MA / South Coast | 4 |
| Cape Cod & Islands | 4 |
| Merrimack Valley | 3 |
| Berkshires | 3 |
| **Total** | **53** |

Region is derived from (county, city) via `data/ma_region_taxonomy.json` — no arbitrary marketing
labels; every assignment is reproducible.

## Health-system distribution (21 systems)

Beth Israel Lahey Health (9), Mass General Brigham (8), UMass Memorial Health (4), Baystate Health (4),
Boston Medical Center Health System (3), Tufts Medicine (3), Berkshire Health Systems (3), and 14
smaller systems/independents (Merrimack Health, Tenet, Brown University Health, Heywood, Cape Cod
Healthcare ×2 each; Cambridge Health Alliance, Milford Regional [Independent], Emerson, South Shore,
Signature, Sturdy, Southcoast, Mercy/Trinity, Holyoke/Valley ×1). A health system owning multiple
hospitals is **not** a duplicate — each CCN is a distinct facility.

## Directory seeding decisions (identity/geography only)

- **Organization** = the health system where distinct, else the hospital itself (e.g. Milford "Independent" → organization = the hospital).
- **Facility + FacilityLocation** = one per CCN, primary-campus CMS address, `active=true`.
- **facility_type** = the CMS `hospital_type` string verbatim ("Acute Care Hospitals" / "Critical Access Hospitals") — matches the existing directory facet vocabulary.
- **region** = taxonomy-derived (populated; the NH region facet is empty, so MA regions are a genuine UX gain).
- **pricing_status** = price-unavailable until Carevero ingests + publishes a verified price. An MRF URL existing is **not** price availability.
