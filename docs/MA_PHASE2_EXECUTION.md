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

## Step 3 — MRF acquisition matrix (53/53) ✅

`docs/MA_MRF_ACQUISITION.md` + `data/ma_hospital_price_sources.json`: 4 parallel official-source
discovery sweeps → **51 MRF_FOUND** (HEAD-verified: csv 19, zip 15, json 14, unknown 3) + **2
SOURCE_BLOCKED** (Sturdy 220008, Holyoke 220024 — WAF 403). Every format maps to the existing NH
pipeline (ZipMemberSource + parsers); shared national `ProcedureCodeMapping` catalog → no new MA
mappings. Registered into `FacilityPriceSource` via `scripts/seed_ma_price_sources.py` (verified_manual).

## Step 4 — Diverse pilot (10 hospitals, 2 waves) — PASS gate green ✅

Pilot spans 7 regions, 9 systems, 4 formats, academic+community+CAH, 8 distinct MRF hosts.

**Wave A (5): 2 imported clean, 3 exposed systemic issues** (exactly the pilot's purpose):
- ✅ **MGH** (220071, MGB zip 3.6 MB) — 159,489 records, **49/52 procedures published**.
- ✅ **Martha's Vineyard** (221300, MGB zip, CAH) — 10,452 records, **38 procedures**.
- ❌ UMass Memorial (220163) — download rejected: declared size > 750 MB cap.
- ❌ Beth Israel Deaconess (220086) — `SSL: UNSAFE_LEGACY_RENEGOTIATION_DISABLED` (bidmc.org).
- ❌ Cape Cod (220012) — `StringDataRightTruncation`: Craneware CDM code blob > `code` varchar(100).

**Pilot pass-gate (on the clean imports): GREEN** — NH intact (`passed:true`, 26 hospitals, 16,709 NH
summaries preserved, +184 MA public; hospital_price_records +169,941 = MGH+MV exactly; all
zero-invariants 0, **ai_modified_prices 0**); MA **fp-detector 53/53 CLEAN, 0 suspects**. Live API:
MGH MRI-brain $3,858, Martha's Vineyard $2,116.50, honest `facility` scope.

**3 systemic fixes** (committed `155a0f0`, image `ma-pilot2`; 96 pipeline tests pass) — not suppressed:
1. `hospital_price_max_bytes` 750 MB → 3 GB (large academic MRFs).
2. TLS `OP_LEGACY_SERVER_CONNECT` for MRF downloads (bidmc.org et al.); cert verification stays on.
3. Cap `PriceServiceCode.code/raw_code` to varchar(100) (Craneware CDM blobs); canonical codes short, unaffected.

**Wave B (retry 3 fixed + 5 new)** — the 2 big fixes were confirmed working (UMass 756 MB + BIDMC both
downloaded on retry), but **the job hit the 2 hr Cloud Run task timeout mid-import**: batching many large
MRFs in one job is too much. It left partial, summary-less (invisible) records + a stuck import run.

## Step 5 — Recovery to a clean baseline ✅

- `scripts/reset_ma_pricing.py` (`--fast` bulk delete + **orphan sweep by facility_id**) cleared the stuck run
  and all ~957K partial wave-B records, keeping the clean wave-A imports (MGH, Martha's Vineyard).
- **Clean baseline confirmed:** `hospital_price_records = 5,968,919` (exact post-wave-A number), `passed: true`,
  NH intact (26 hospitals, 16,893 summaries, all zero-invariants 0, ai_modified 0). Live: MA directory 53,
  MA priced 2 (MGH 49 / MV 38), NH 148 — all correct.
- Wave-B CCNs' sources are reset to needs-download for clean re-import.

## Corrected scaling strategy (multi-session)

Each large academic MRF (UMass 756 MB, Baystate 444 MB, BWH, BMC) is a **30–60 min isolated ingestion job**;
Cloud Run jobs cap at 2 hr. So pricing all 53 is inherently **sequential, multi-session** work — done in
**small waves with large hospitals one-per-job**, gating (safety + fp) after each. Exact per-wave commands +
the wave-B/remaining CCN list are tracked in the internal ops notes (machine-actionable resume point). Job image `ma-scale4`.

## Phase-2 status: PARTIAL (safe, proven, ongoing)

Directory + identity + MRF discovery **complete**; pipeline **proven & hardened** (2 hospitals priced live,
4 ingest bugs fixed); NH **never harmed**. Remaining: sequential small-wave pricing ingestion of the other 51.
