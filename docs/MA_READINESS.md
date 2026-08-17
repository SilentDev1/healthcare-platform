# Carevero — Massachusetts Readiness & Foundation Plan

**Status:** NH exit gate PASSED (see `FINAL_NH_PROCEDURE_VALIDATION.md`). MA foundation STARTED
2026-08-17. **The verified NH baseline (26/26, 50/50, safety PASS, 0 false-positives, 0
duplicate locations) must not be altered by any MA work.**

## Architecture reuse (no redesign)

MA reuses the existing provider-neutral model verbatim:
- `Organization → FacilityLocation → LocationCapability / LocationServiceAvailability / prices`.
- `FacilityLocation.region` / `FacilityLocation.subregion` (added in migration **0014**) carry
  MA geography — NH leaves them null; MA populates them. **No schema change is required.**
- The same hospital MRF pipeline (parse → approved-code mapping → reviewed → publishable
  summary), the same false-positive/false-negative/duplicate/anomaly detectors, the same
  provider-neutral directory/search/map/detail, and the same NH provider-wave collectors are
  reused. MA is NOT modeled as a flat hospital list.
- The CPT↔HCPCS code-system equivalence remediations already in place apply to MA MRFs too.

## MA regional taxonomy (VERIFIED against CMS hospital distribution + MA HPC/CHIA service areas)

MA must be regionally filterable, not one flat list. **Locked at 10 regions** (research adjusted
the initial 8: split Western MA → Pioneer Valley + Berkshires; carve Southeastern MA / South
Coast out of South Shore — these are distinct provider markets with separate networks):

| region | anchor areas |
|---|---|
| Greater Boston | Boston, Cambridge, Newton, Brookline, Quincy, Milton, Winchester, Melrose |
| North Shore | Salem, Beverly, Gloucester, Newburyport, Burlington (Lahey) |
| Merrimack Valley | Lawrence, Lowell, Haverhill, Methuen |
| MetroWest | Framingham, Natick, Marlborough, Milford, Concord |
| South Shore | Weymouth, Plymouth, Brockton |
| Southeastern MA / South Coast | New Bedford, Fall River, Taunton, Attleboro, Wareham |
| Central Massachusetts | Worcester, Leominster, Clinton, Gardner, Athol, Southbridge |
| Pioneer Valley | Springfield, Holyoke, Northampton, Greenfield, Westfield, Palmer |
| Berkshires | Pittsfield, Great Barrington, North Adams |
| Cape Cod & Islands | Hyannis, Falmouth, Nantucket, Martha's Vineyard |

## Verified MA hospital identity (CMS-anchored — the seed for step 1)

Source: CMS Hospital General Information (`data.cms.gov` dataset `xubh-q36u`, state=MA), cross-
checked vs Mass.gov (Steward) + MHA. **~53 operating general acute + 4 CAH = ~57 to seed.**
Captured to `data/ma_hospitals_seed.json` for the (future) `ingest_ma_hospitals_foundation.py`.

- **EXCLUDE (closed — CMS may still carry the CCN):** Carney 220017, Nashoba Valley 220098,
  Norwood 220126.
- **Steward re-parents (seed under NEW owner):** St. Elizabeth's→BMC-Brighton 220036; Good
  Samaritan→BMC 220111; Saint Anne's→Brown University Health 220020; Morton→Brown 220073; Holy
  Family→Merrimack Health 220080.
- **Specialty acute (bucket separately, NOT general acute):** Mass Eye & Ear 220075, New England
  Baptist 220088, AdCare 220062.
- **Multi-campus single-CCN (needs per-campus handling):** Southcoast 220074 (3), Cambridge
  Health Alliance 220011 (3), Northeast/Beverly 220033 (2), Holy Family 220080 (2), HealthAlliance
  220001 (2), MetroWest 220175 (2).
- **System MRF portals to prioritize:** Mass General Brigham, Beth Israel Lahey Health, UMass
  Memorial, Baystate, Boston Medical Center, Tufts Medicine, Berkshire Health Systems, Cape Cod
  Healthcare, Tenet, Brown University Health, Heywood.

## Acquisition sequence (mirrors the proven NH order)

1. **Facility identity + hospital foundation FIRST** — seed MA short-term acute-care +
   critical-access hospitals from CMS (CCN + official name + city/ZIP + type), tagged with
   `region`/`subregion`. Exclude closed/merged facilities (e.g., 2024 Steward closures). This is
   the CMS-anchored identity layer, same as NH.
2. **Hospital MRF pricing** — ingest each MA hospital's machine-readable standard-charge file
   through the existing audited pipeline; run the full gate (false-positive/false-negative/
   anomaly/safety) exactly as NH.
3. **Provider waves** — reuse the NH wave collectors for MA labs, urgent care, ED/freestanding
   ER, imaging, ASC, PT, rehab, chiropractic (authoritative per-location research → verify →
   ingest; offered≠priced; never $0).
4. **Consumer QA + MA exit gate** — same criteria as the NH exit gate, per MA region.

## Safety invariants carried into MA

Never manufacture/infer a price; offered-without-price is a valid state; additive migrations
only; candidate discovery separate from approved mappings; AI medical gate unchanged; and the
**NH production baseline is never touched** by MA ingestion (MA rows are additive and
region-tagged; NH rows have null region and are unaffected).

## Started so far (2026-08-17)

- This readiness/plan document.
- Authoritative MA hospital-roster + regional-taxonomy research (CMS + MA HPC/CHIA + official
  sites), including closed/merged-facility exclusions — in progress.

Next concrete step after the roster returns: build `scripts/ingest_ma_hospitals_foundation.py`
(CMS-anchored identity, region-tagged, idempotent, tested, dry-run) — no NH change.
