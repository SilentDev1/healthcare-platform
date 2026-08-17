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

## MA regional taxonomy (draft — being verified against authoritative MA geography)

MA must be regionally filterable, not one flat list. Draft `region` values (subregion optional):

| region | anchor counties / areas |
|---|---|
| Greater Boston | Suffolk + inner metro (Boston, Cambridge, Somerville, Newton, Brookline, Quincy) |
| North Shore | Essex coast (Salem, Beverly, Gloucester, Peabody, Lynn) |
| South Shore | Plymouth/Norfolk coast (Weymouth, Plymouth, Brockton) |
| MetroWest | Framingham, Natick, Marlborough, Milford |
| Merrimack Valley | Lawrence, Lowell, Haverhill, Methuen |
| Central Massachusetts | Worcester County (Worcester, Leominster, Fitchburg) |
| Western Massachusetts | Pioneer Valley (Springfield, Northampton) + Berkshires (Pittsfield) — subregion split candidate |
| Cape Cod & Islands | Barnstable, Dukes, Nantucket (Hyannis, Falmouth) |

The authoritative-geography research (in progress) will confirm/adjust these — notably whether
Western MA should split into **Pioneer Valley** and **Berkshires** subregions, and exact
city→region assignments. The taxonomy is locked only after that verification.

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
