# Massachusetts Phase 2 — Execution Log

Live, running record of MA Phase 2 (hospital directory + MRF pricing expansion). Autonomous, fail-forward,
NH-safe. **NH is the safety baseline and must remain intact at every step.**

## Production baseline (pre-MA, captured 2026-08-18)

`phase_4_7_safety` (prod), **passed: true**:
`facility_count=148, active_consumer_hospitals=26 (NH), hospital_price_records=5,798,978,
observations=334,093, official_public_summaries=16,709, source_files=145`, and every zero-invariant = 0
(negatives, missing-provenance, unreviewed-mappings, duplicate-identities, location mismatches, **ai_modified_prices**).
NH API directory = 148; catalog = 52. Regression price-row anchors: MRI 381, colonoscopy 248, VitD 289, PSA 289, A1C 402.

## Step 1 — MA hospital identity seed → PRODUCTION ✅

- **Script:** `scripts/seed_ma_hospitals.py` (idempotent; Facility keyed on CCN, FacilityLocation on physical-location unique key, org by canonical_name, `hospital` capability w/ provenance). Identity/geography only — **zero pricing**.
- **Image:** `job:ma-seed1` (Cloud Build `a00856fa`; MA data files added to `infrastructure/docker/job.Dockerfile`). Job `carevero-beta-price-audit` (SA `carevero-beta-job@…`, Secret Manager `DATABASE_URL`).
- **Dry-run (prod):** `{organizations:21, facilities:53, locations:53, capabilities:53, skipped_forbidden:0}` — rolled back.
- **Apply (prod):** same counts, committed.
- **Idempotency (prod re-run):** `{all: 0}` — duplicate-safe. ✅

### Post-seed safety re-check — NH INTACT ✅ (passed: true)

| Metric | Pre-MA | Post-MA | Verdict |
|---|---:|---:|---|
| active_consumer_hospitals (NH) | 26 | 26 | unchanged ✓ |
| official_public_summaries | 16,709 | 16,709 | NH pricing intact ✓ |
| hospital_price_records | 5,798,978 | 5,798,978 | unchanged ✓ |
| observations | 334,093 | 334,093 | unchanged ✓ |
| facility_count | 148 | 201 | +53 MA (expected) ✓ |
| source_files | 145 | 146 | +1 CMS MA source ✓ |
| all 10 zero-invariants | 0 | 0 | ✓ |
| **passed** | true | **true** | ✓ |

NH API directory still 148 after MA seed. No NH row disappeared, was reclassified, or changed price.

## Step 2 — MA directory live (identity, price-unavailable) ✅

Live via `GET /api/v1/facilities/directory?state=MA`:
- **total = 53**; facility_types = Acute Care Hospitals + Critical Access Hospitals.
- **regions facet = all 10** with counts: Greater Boston 14, Pioneer Valley 7, Central MA 6, North Shore 4, MetroWest 4, South Shore 4, Southeastern 4, Cape & Islands 4, Merrimack Valley 3, Berkshires 3 (= 53). Region browsing UX works (NH's region facet is empty — MA is the first with real regions).
- Honest semantics: `pricing_status = pricing_not_available_yet`, `price_available = false`, `published_procedure_count = 0`. **Not** "0 procedures" / "no services".

### Public state-dropdown flip — DEFERRED (gated) ⏸

`packages/markets.py` sets **MA `consumer_visible=False`** (public `states[]` dropdown still NH-only). MA is
queryable by `?state=MA` for QA but not yet advertised in the consumer state picker. Flipping it is a one-line,
instantly-reversible change but is a deliberate consumer-semantics decision (directive §53) and the code carries
an explicit "don't flip until later gates" guard. **Plan:** flip as part of "MA activation" once the pricing
pilot has published real MA prices, so MA does not launch as an all-empty directory (directive §42). Rollback:
set `consumer_visible=False`, redeploy API.

## Next

- **MRF acquisition matrix** for all 53 (`docs/MA_MRF_ACQUISITION.md`) — discover official standard-charges files, group by system, profile/cluster formats before any parser.
- **Diverse ~10-hospital pilot** ingestion → validate → scale to 43 → publish only verified prices.
- Coverage dashboard: `docs/MA_PRICING_COVERAGE.md`.
