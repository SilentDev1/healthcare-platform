# NH Procedure × Hospital Mapping Coverage Audit

**Generated:** 2026-08-15 · **Scope:** 50 canonical Carevero consumer procedures ×
26 active NH consumer hospitals (1,300 procedure×hospital combinations) · **DB:**
`carevero-beta-postgres` (production), migration head `0013`.

> **Coverage ≠ correctness ≠ per-procedure availability.** This audit keeps three
> facts strictly separate and never infers one from another:
> 1. **A hospital publishes prices** (has any publishable summary).
> 2. **A hospital publishes a price relevant to a procedure** (has records whose
>    codes/descriptions plausibly correspond).
> 3. **Carevero has *safely mapped* that price** to the procedure (a reviewed,
>    deterministic, approved-code mapping — the only path to consumer visibility).

Tools (all committed, read-only unless noted):
- `scripts/audit_procedure_mapping_coverage.py` — per-cell coverage + root-cause.
- `scripts/detect_crosswalk_false_positives.py` — re-validates every stored
  crosswalk resolution against the current crosswalk (read-only).
- `scripts/remediate_crosswalk_false_positives.py` — surgical removal w/ manifest,
  dry-run, and rollback artifact.

---

## 1. Headline numbers (post-remediation, verified)

| Metric | Value |
|---|---|
| NH hospitals publishing prices | **26 / 26** |
| Canonical procedures with ≥1 hospital verified-mapped price | **48 / 50** |
| Procedure × hospital combinations audited | **1,300** |
| False-positive mappings detected | **1,406** |
| False-positive mappings removed | **1,406** |
| Derived observations removed (by rebuild) | ~15,133 |
| Public summaries changed/removed | corrections within surviving summaries; ~10 removed |
| Hospitals with false positives (before) | **17 / 26** |
| Hospitals CLEAN after remediation | **26 / 26** |
| Raw hospital price records altered | **0** (5,798,978 unchanged) |
| Safety audit | **PASS** (all invariants 0) |

**Coverage held at 26/26 and 48/50 through the remediation** — removing 1,406
false positives *corrected prices* (e.g. removed a drug's price from a bone-density
range) without dropping any hospital or procedure below publishable, because the
affected procedures retain legitimate records at those hospitals. No number was
forced; the truthful figure simply did not fall.

---

## 2. The two uncovered procedures (investigated, not just "0")

Both maternity procedures show **0 publishing hospitals**. Root cause is identical
and is **a code difference / missing reviewed mapping**, NOT missing data:

| Procedure | Registered approved codes | Reality in hospital data |
|---|---|---|
| `vaginal-delivery` | MS-DRG **774, 775** (retired) | 16/26 hospitals have delivery records under **current** MS-DRGs (805/806/807) and/or CPT 59400 → `KNOWN_CODE_NOT_MAPPED`; 8 `NO_MATCHING_RAW_RECORD`; 2 `SUMMARY_BUILD_GAP` |
| `cesarean-delivery` | MS-DRG **765, 766, 767** (retired) | 14/26 hospitals have records under current MS-DRGs (783–788) and/or CPT 59510 → `KNOWN_CODE_NOT_MAPPED`; 10 `NO_MATCHING_RAW_RECORD`; 2 `SUMMARY_BUILD_GAP` |

**Classification: code difference + missing reviewed crosswalk.** The approved
registry holds **superseded** MS-DRG numbers. The hospitals publish the services
under the current-year DRGs and CPT delivery codes; Carevero simply has not
registered those codes. This is legitimately recoverable (see §6) by adding the
current, standard delivery codes to the reviewed `ProcedureCodeMapping` registry —
an evidence-backed, deterministic mapping, **not** a fuzzy one. It is deliberately
deferred to a reviewed follow-up rather than rushed to force 50/50.

---

## 3. Global false-positive investigation (the important finding)

The too-broad crosswalk description patterns that mis-mapped Concord-Laconia were a
**global** defect: any hospital imported before the crosswalk fixes carried the
same spurious mappings. A read-only detector re-applied the corrected crosswalk to
every stored crosswalk resolution (`raw_code_type` local → standard `code_system`)
and flagged every record whose stored resolution the current crosswalk would no
longer produce.

**Result: 17 of 26 hospitals affected; 1,406 spurious mappings, all feeding public
prices.** Every one was verified against the corrected crosswalk (deterministic —
only records that fail the corrected rules were flagged). Representative examples:

| Procedure (mis-mapped to) | Real service that was mis-mapped | Rule at fault |
|---|---|---|
| bone-density-scan (77080) | `TOBRA/DEXAMETH OPTH SUSP`, `LISDEXAMFETAMIN 40MG CAP` (drugs) | `dexa`/drug collision |
| upper-endoscopy (43235) | `MINNESOTA 4 LUMEN ESOPHAGOGASTRIC` (a tube), `HC ESOPHAGOSCOPY` | bare `esophago` |
| cardiac-stress-test (93015) | `Fetal Non-Stress Test`, `PULMONARY STRESS TEST` | bare `stress test` |
| chest-x-ray (71046) | `PROS PENL AMS 700CXR …` (penile prosthesis) | bare `cxr` |
| pap-test (88175) | `N. gonorrhoeae, Thin Prep`, `Split Night PSG/CPAP Test` | `thin prep`/`pap test` |
| hip/knee-replacement (27130/27447) | `Revision of total hip/knee arthroplasty` | missing revision guard |
| urinalysis | a drug/supply line | drug collision |

### Removed by procedure

| Procedure | Mappings removed |
|---|---|
| bone-density-scan | 602 |
| upper-endoscopy | 534 |
| cardiac-stress-test | 140 |
| chest-x-ray | 48 |
| pap-test | 38 |
| hip-replacement | 32 |
| knee-replacement | 11 |
| urinalysis | 1 |
| **Total** | **1,406** |

### Per-hospital classification (before → after)

All 17 flagged hospitals were `REIMPORT_RECOMMENDED` before remediation; after the
surgical cleanup **all 26 are CLEAN** (re-run detector: 0 remaining suspects).

| CCN | Hospital | Suspect records (before) | After |
|---|---|---|---|
| 301308 | Valley Regional | 542 | CLEAN |
| 300001 | Concord Hospital | 333 | CLEAN |
| 301306 | Concord–Franklin | 245 | CLEAN |
| 301303 | Weeks Medical Center | 94 | CLEAN |
| 300003 | Mary Hitchcock | 48 | CLEAN |
| 301302 | Littleton Regional | 28 (+1 drug) | CLEAN |
| 300019 | Cheshire Medical Center | 28 | CLEAN |
| 301304 | New London Hospital | 18 | CLEAN |
| 300018 | Wentworth-Douglass | 18 | CLEAN |
| 300011 | St Joseph Hospital | 17 | CLEAN |
| 301311 | Speare Memorial | 10 | CLEAN |
| 300017 | Parkland Medical Center | 8 | CLEAN |
| 300012 | Elliot Hospital | 4 | CLEAN |
| 300034 | Catholic Medical Center | 3 | CLEAN |
| 300029 | Portsmouth Regional | 3 | CLEAN |
| 300020 | Southern NH Medical Center | 3 | CLEAN |
| 300014 | Frisbie Memorial | 3 | CLEAN |
| — | 9 others (incl. Laconia) | 0 | CLEAN |

### Root causes fixed (crosswalk), then remediated (data)

1. `165ee9a` `\bdexa\b` (pre-session) — bare `dexa` matched `dexamethasone`.
2. `1125773` — 6 too-broad patterns tightened (`cxr`, `esophago`, `stress test`,
   `thin prep`/`pap test`, knee/hip revision guards). Narrowing only.
3. `f8df5d0` — a **drug/supply guard**: `apply_cdm_crosswalk` refuses any line with
   an unambiguous dosage form (tab/cap/susp/soln/drops/otic/ophth/…) or numeric drug
   strength (`\d+ mg/mcg/meq/units`). Catches drug-name/abbreviation collisions the
   patterns cannot (`DEXA 4MG TAB` dexamethasone vs a DEXA scan). Verified against
   the full Laconia file: **zero legitimate procedures suppressed** (`inj`, `enema`,
   `patch` deliberately excluded — they collide with real procedures).

---

## 4. Remediation operation (auditable)

- **Method:** surgical removal of only the mappings the corrected crosswalk no
  longer supports. For each affected record the tool re-derives its *legitimate*
  approved procedures under the current crosswalk; a mapping any real code still
  supports is never touched. Stale resolved code slots revert to their raw local
  code (what a re-import stores on NO_MATCH).
- **Not done:** no MRF deleted/re-imported; no raw price record or rate detail
  altered; no legitimate mapping removed; no fuzzy/AI mapping created.
- **Manifest / rollback artifact:** full JSON (mapping IDs, record/facility,
  procedure, raw description/codes, public-price impact) written to the sources
  bucket (`remediation_manifest_dryrun.json`, `remediation_rollback_applied.json`,
  and round-2 variants). A pre-remediation Cloud SQL backup was taken.
- **Dry-run before apply:** round 1 dry-run proved exactly 1,405 mappings; round 2
  (post drug-guard) proved 1 (Littleton urinalysis). Both then applied.
- **Observations/summaries:** regenerated by `rebuild_price_summaries` from the
  surviving reviewed mappings (deletes-and-rebuilds, so no orphan observations).

### Coverage before → after

| | Hospitals publishing | Publishable procedures | Observations | Public summaries |
|---|---|---|---|---|
| Before remediation | 26/26 | 48/50 | 313,117 | 14,303 |
| After remediation | 26/26 | 48/50 | 297,984 | 14,293 |

---

## 5. Consumer-facing validation & safety

- **Spot-check (chest x-ray, Laconia):** $60.30–$106.50 (real CXR) — **not** the
  $29,058 penile-prosthesis price the buggy crosswalk produced.
- **Safety audit (`phase_4_7_safety`, post-remediation): PASS.** All invariants 0:
  public_unreviewed_mappings 0, ai_modified_prices 0, negative_public_summaries 0,
  missing_public_provenance 0, duplicate_public_consumer_identities 0, record/
  observation facility-location mismatches 0 (no orphan observations), active_imports 0.
- **Raw prices unchanged:** `hospital_price_records` = 5,798,978 before and after.

### High-use procedures (consumer priority) — post-remediation coverage

Verified-mapped price at N/26 hospitals. Note bone-density (22), upper-endoscopy
(21) and cardiac-stress (21) held their coverage **after** 602/534/140 false
positives were removed — proof the removals corrected prices without erasing
legitimate coverage.

| Procedure | Hospitals | Procedure | Hospitals |
|---|---|---|---|
| electrocardiogram | 23/26 | mri-brain-without-contrast | 22/26 |
| abdominal-ultrasound | 22/26 | basic-metabolic-panel | 22/26 |
| lipid-panel | 22/26 | bone-density-scan | 22/26 |
| pregnancy-test | 21/26 | cardiac-stress-test | 21/26 |
| upper-endoscopy | 21/26 | comprehensive-metabolic-panel | 19/26 |
| mri-knee-without-contrast | 19/26 | complete-blood-count (CBC) | 18/26 |
| screening-mammogram | 18/26 | pelvic-ultrasound | 18/26 |
| colonoscopy | 17/26 | physical-therapy-evaluation | 17/26 |
| ct-abdomen-pelvis | 17/26 | diagnostic-mammogram | 16/26 |
| ed-visit (levels 1–5) | 16/26 | covid-test | 15/26 |
| strep-test | 14/26 | **vaginal / cesarean delivery** | **0/26** (§2) |

None of the high-use services is *unexpectedly* zero: only the two deliveries are
0, and that is a registered-code gap (§2), not absent data.

---

## 6. Follow-up — legitimate coverage recovery (reviewed, not fuzzy)

Determined from *legitimate missing mappings*, not a blanket re-import:

1. **Maternity (vaginal/cesarean delivery):** add the current standard delivery
   codes to the reviewed `ProcedureCodeMapping` registry — CPT 59400 (vaginal) /
   59510 (cesarean) and current MS-DRGs (805/806/807; 783–788), each verified
   against its official CMS definition — then re-import (or targeted remap) the
   16/14 hospitals that already carry those records. Would move 48→50.
2. **No re-import needed for the false-positive fix** — the surgical cleanup already
   corrected all 17 hospitals in place. A future *routine* re-import (any hospital)
   will additionally revert the reverted code slots' cosmetics; not required for
   price correctness.
3. **Weakest-coverage procedures (§7)** are the next data-quality priority —
   investigate each for terminology/code differences before assuming hospitals
   don't publish them.

---

## 7. Per-procedure coverage & the 10 weakest

### The 10 weakest by real (verified-mapped) coverage — next data-quality priority

`recoverable` = hospitals that likely offer it but Carevero has not mapped it
(`KNOWN_CODE_NOT_MAPPED` / `LOCAL_CODE_NEEDS_REVIEW` / component/setting/summary
gaps) — the actionable backlog. **Investigate before assuming hospitals don't
publish these.**

| # | Procedure | Publishing | Recoverable | Likely cause |
|---|---|---|---|---|
| 1 | cesarean-delivery | 0/26 | 16 | superseded MS-DRG (§2) |
| 2 | vaginal-delivery | 0/26 | 18 | superseded MS-DRG (§2) |
| 3 | allergy-testing | 9/26 | 12 | local/variant CPT codes not registered |
| 4 | cataract-surgery | 12/26 | 2 | code/description variants |
| 5 | annual-wellness-visit | 13/26 | 7 | HCPCS G-code variants (G0402/G0438/G0439) |
| 6 | rotator-cuff-repair | 13/26 | 9 | arthroscopy code variants |
| 7 | cardiac-catheterization | 14/26 | 3 | cath code family variants |
| 8 | carpal-tunnel-release | 14/26 | 8 | open vs endoscopic code variants |
| 9 | hernia-repair | 14/26 | 0 | genuinely narrower availability |
| 10 | strep-test | 14/26 | 3 | rapid-strep description/code variants |

### Full 50-procedure matrix (publishing hospitals / 26, recoverable, registered codes)

| Procedure | Publishing | Recoverable | Registered approved codes |
|---|---|---|---|
| electrocardiogram | 23/26 | 0 | CPT:93000/93005/93010 |
| abdominal-ultrasound | 22/26 | 3 | CPT:76700 |
| basic-metabolic-panel | 22/26 | 4 | CPT:80048 |
| bone-density-scan | 22/26 | 2 | CPT:77080 |
| chest-x-ray | 22/26 | 1 | CPT:71046/71045, REV_CODE:0324 |
| lipid-panel | 22/26 | 4 | CPT:80061 |
| mri-brain-without-contrast | 22/26 | 1 | CPT:70551 |
| urinalysis | 22/26 | 1 | CPT:81001 |
| cardiac-stress-test | 21/26 | 1 | CPT:93015/93017/93018 |
| echocardiogram | 21/26 | 0 | CPT:93306/93303/93307 |
| gallbladder-removal | 21/26 | 1 | CPT:47562 |
| pregnancy-test | 21/26 | 3 | CPT:81025 |
| thyroid-test | 21/26 | 4 | CPT:84443 |
| upper-endoscopy | 21/26 | 0 | CPT:43235 |
| surgical-pathology | 20/26 | 2 | CPT:88305 |
| a1c-test | 19/26 | 7 | CPT:83036 |
| comprehensive-metabolic-panel | 19/26 | 1 | CPT:80053 |
| ct-chest | 19/26 | 5 | CPT:71250 |
| mri-knee-without-contrast | 19/26 | 1 | CPT:73721 |
| pap-test | 19/26 | 5 | CPT:88175 |
| complete-blood-count | 18/26 | 2 | CPT:85025, REV_CODE:0300 |
| knee-replacement | 18/26 | 3 | CPT:27447 |
| pelvic-ultrasound | 18/26 | 7 | CPT:76856 |
| screening-mammogram | 18/26 | 3 | CPT:77067 |
| colonoscopy | 17/26 | 2 | CPT:45378/45380/45385 |
| ct-abdomen-pelvis | 17/26 | 4 | CPT:74176/74177/74178 |
| hip-replacement | 17/26 | 2 | CPT:27130 |
| physical-therapy-evaluation | 17/26 | 4 | CPT:97161 |
| sleep-study | 17/26 | 3 | CPT:95810 |
| diagnostic-mammogram | 16/26 | 4 | CPT:77066 |
| dialysis-session | 16/26 | 2 | CPT:90935 |
| ed-visit-level-1…5 | 16/26 | 5 | CPT:99281–99285 |
| flu-vaccine | 16/26 | 4 | CPT:90686 |
| mri-lumbar-spine-without-contrast | 16/26 | 9 | CPT:72148 |
| urgent-care-visit | 16/26 | 0 | CPT:99213 |
| covid-test | 15/26 | 0 | CPT:87635 |
| cardiac-catheterization | 14/26 | 3 | CPT:93458 |
| carpal-tunnel-release | 14/26 | 8 | CPT:64721 |
| hernia-repair | 14/26 | 0 | CPT:49505 |
| strep-test | 14/26 | 3 | CPT:87880 |
| annual-wellness-visit | 13/26 | 7 | HCPCS:G0438 |
| rotator-cuff-repair | 13/26 | 9 | CPT:29827 |
| cataract-surgery | 12/26 | 2 | CPT:66984 |
| allergy-testing | 9/26 | 12 | CPT:95004 |
| cesarean-delivery | 0/26 | 16 | MS_DRG:765/766/767 (superseded) |
| vaginal-delivery | 0/26 | 18 | MS_DRG:774/775 (superseded) |

_Per-cell (procedure × hospital) detail with root-cause classification is available
from `scripts.audit_procedure_mapping_coverage` (full-matrix mode)._
