# Massachusetts Expansion Plan (Phase 5 readiness)

Do **not** begin bulk MA ingestion yet. This documents the plan and the
architecture audit so MA can be added as *data + config*, not a code fork.

## 1. Why MA is next and why it should be cheap

The platform is already keyed by data, not by `if state == "NH"`: facilities,
locations, procedures, payers, plans, sources, comparability, savings, distance,
i18n, and now facility-media are all state-neutral. Adding MA is primarily:
add MA facility identity + verified MRF sources + centroids, run the same
ingestion/enrichment, and flip a few NH-defaulted knobs (below).

## 2. Remaining NH-specific assumptions to generalize (audit result)

Small and contained — generalize before the MA launch:

| Location | Assumption | Fix |
|---|---|---|
| `main.py` pricing-coverage endpoint | `active_consumer_facility_ids(session, "NH")` hardcoded | accept a `state` param (default configurable), or a launch-region set |
| `main.py` admin dashboard | `FacilityLocation.state == "NH"` | parameterize / multi-state aggregate |
| `schemas.py` coverage | field named `nh_facilities` | rename to `active_facilities` (keep back-compat alias for one release) |
| `main.py` several endpoints | `state="NH"` **default** query param | keep default but drive from a `LAUNCH_STATES` config |
| `apps/web/lib/brand.ts` | `launchRegion` single-state (name, mapCenter, mapZoom) | make it a list/lookup keyed by state; pick from route/context |
| Web copy | "New Hampshire hospitals" in hero/coverage strings | parameterize region name via existing i18n `{region}` pattern (already used in `ledeSummary`) |
| Centroids fixture | `data/fixtures/zip_city_centroids.json` already NH+MA | verify MA ZIP/city coverage completeness |

Everything else (comparison, savings, distance, media, search, procedure
mapping, payer normalization) is already state-agnostic.

## 3. MA hospital universe & identity

- Source of truth: CMS Provider of Services / Care Compare for MA acute-care
  hospitals + CCNs (same collectors as NH: `collectors/cms_hospitals`,
  `collectors/cms_quality`). MA is a larger, higher-density market than NH.
- Identity: reuse `FacilityIdentifier` / `FacilityIdentityCandidate` /
  reviewed decisions. CCN remains the strong key; health-system grouping via
  `FacilityRelationship`. No new identity system.
- Multi-location: MA has many multi-campus systems (e.g. large AMCs with
  satellite sites) — `FacilityLocation` + service-location-scoped pricing/media
  already handle this; location association is the main review load.

## 4. Source discovery & MRF acquisition

- Reuse `collectors/hospital_prices/discovery.py` + the verified-source registry
  (`data/fixtures/verified_hospital_price_sources.json`) — add MA CCN → verified
  MRF URLs after review. Never ingest an unverified source.
- **Large files are the #1 MA risk.** MA systems publish very large MRFs. The
  NH Valley/CCN 301308 case (MRF beyond the 1.5 GB safety cap) is the canonical
  example. Before MA:
  - Land the **streaming-from-zip importer** (parse entries without materializing
    the whole file; the NH importer already stages extraction to local disk —
    extend it to stream). Design it as reusable ingestion infra, not MA-specific.
  - Keep the expansion cap + job memory tunables; prefer streaming over unbounded
    memory.
- Shared health-system files: several MA hospitals share one system-level MRF;
  the importer must map one file to many facilities/locations (NH already does
  this for Concord/Dartmouth systems).

## 5. Geocoding, payers, procedures

- Geocoding: coordinate-based haversine + bundled Census centroids; extend
  `zip_city_centroids.json` generator to MA (public-domain Census Gazetteer).
  Distance already crosses state lines (a Nashua NH user can see nearby MA sites).
- Payers: MA payer mix differs (BCBS MA, Harvard Pilgrim, Tufts, MassHealth).
  `PayerAlias`/`InsurancePlanAlias` normalization already generalizes; add MA
  payer aliases via review. **Never** assert network participation from a
  published rate (see docs/INSURANCE_DATA_FOUNDATION.md).
- Procedure mapping: reviewed mappings only; MA introduces more local/proprietary
  codes — same no-fuzzy-publish rule. Expect a review backlog, not code changes.

## 6. Storage / compute

- Pricing: MA record volume will be multiples of NH (~2.75M records). Cloud SQL
  `db-custom-1-3840` may need a tier bump; the price-refresh job (8Gi, gcsfuse)
  may need more memory or the streaming importer to stay within budget.
- Media: `facility_media` scales linearly; the GCS `facility_media_bucket` +
  variants keep egress bounded. No schema change for MA.

## 7. Coverage reporting & safety gates

- Generalize the coverage endpoint/metrics to per-state (and aggregate). Track
  `facilities_with_publishable_prices / active` per state.
- Safety gates unchanged and per-state: `phase_4_7_safety` invariants must stay
  0; no fabricated prices/savings; provenance preserved; reviewed mappings only.
- Rollout in batches by health system (discover → verify sources → import wave →
  audit → publish), mirroring the NH `phase-4-7-{dartmouth|regional|valley}`
  waves. Each batch is advisory-locked, additive, checksum-guarded.

## 8. Sequencing

1. Generalize the NH-specific knobs (§2) + land the streaming importer (§4).
2. MA facility identity + quality (CMS collectors) — read-only, safe.
3. MA verified-source registry (reviewed).
4. MA import waves (batched, audited).
5. MA centroids + payer aliases + procedure mappings (reviewed).
6. MA facility-media enrichment (same pipeline).
7. Per-state coverage reporting + web region generalization.

Nationwide (ME/VT/RI/CT → US) then repeats steps 2–7 per state with **zero**
ingestion-system forks.
