# Carevero — Final NH Procedure & Provider Validation

**Date:** 2026-08-17 · **Scope:** New Hampshire · **Massachusetts:** NOT STARTED (deferred, awaiting owner review of this report).

This report is the NH release gate. It reports **actual** completeness honestly — NH is not
declared "complete" merely because every procedure has at least one price.

---

## 1. Acceptance gate — summary

| Gate | Result |
|---|---|
| NH hospitals intact | ✅ **26 / 26** active consumer hospitals |
| Canonical procedures publishing verified prices | ✅ **50 / 50** (100% statewide) |
| Crosswalk false-positive detector | ✅ **0** public suspects (26/26 hospitals CLEAN; re-run after +785 mappings) |
| **Exhaustive false-negative audit (1,300 cells)** | ✅ **COMPLETED** — 50×26, resumable/DB-side; systematic gap found + remediated (§5) |
| Duplicate physical-location detector | ✅ **0** same-facility duplicates (+10 cross-org shared buildings reported, not merged) |
| `phase_4_7_safety` | ✅ **PASS** (`passed: true`) |
| AI-authored / modified prices | ✅ **0** (`ai_modified_prices: 0`) |
| Medical-advice leakage to LLM | ✅ **0** (195/195 refused pre-LLM across 5 languages; `used_llm=false`) |
| Public unreviewed mappings | ✅ **0** |
| Negative / $0 public prices | ✅ **0** |
| All provider waves live | ✅ Waves 1–7 + roster expansion |
| Provider roster audit | ✅ completed (P1) |
| Non-hospital price-source audit | ✅ completed (P2) |
| Two-way procedure↔provider mapping audit | ✅ false-positive **0**; exhaustive false-negative **completed**; **985 missed prices recovered** |
| Price anomaly audit | ✅ no catastrophic mismap; $0.30 outlier traced = legitimate per-unit (§6) |
| Live 50-procedure consumer QA | ✅ **PASS** (P6, re-run post-remediation) |
| Full automated test suite | ✅ **416 passed, 4 skipped** |

`phase_4_7_safety` raw (post-remediation): `active_consumer_hospitals: 26,
official_public_summaries: 16031, public_unreviewed_mappings: 0,
duplicate_public_consumer_identities: 0, negative_public_summaries: 0, ai_modified_prices: 0,
passed: true`.

**NH FINAL = PASS.** All release gates pass, including the **completed** (not timed-out)
exhaustive 1,300-cell false-negative audit, which found and remediated a systematic
code-system-labeling gap that had hidden 4 hospitals' prices (§5b). NH is **release-ready for
the hospital pricing surface and the provider-neutral discovery surface**, with real published
NON-hospital prices staged as non-public candidates pending human review. It is **not** claimed
to be an exhaustive census of every NH provider or a complete non-hospital price catalog — the
remaining, explicitly-scoped review-only follow-ups are listed in §5b and §10. Massachusetts
remains deferred pending owner review.

---

## 2. Provider roster completeness (P1)

Audited all 10 supported capabilities. A 2026-08-16 authoritative research sweep (official
provider directories + CMS NPI registry) found and verified **71 additional NH locations**,
ingested with per-location source provenance and **deduplicated by physical location** (one
site under one org = one location with the union of its capabilities).

| Capability | Before | After | Added (source) |
|---|---:|---:|---|
| laboratory | 3 | **24** | +21 Quest/Labcorp (official directories) |
| urgent_care | 26 | **39** | +13 Concentra, AFC, Elliot, WDH, SNHH, Concord Hospital, CVS |
| physical_therapy | 5 | **33** | +28 Apple, Professional PT, Granite State, Access, WDH Rehab, Cioffredi, Dartmouth, Performance Health |
| ambulatory_surgery | 3 | **10** | +7 North Atlantic, Northridge, MISCNE, Portsmouth Surgery, Access, Novamed, Surgical Center of NH |
| imaging | 8 | **10** | +2 BASC Imaging, NH Open MRI |
| emergency_department | 26 | 26 | — |
| freestanding_emergency_department | 3 | 3 | — |
| rehabilitation | 4 | 4 | — |
| chiropractic | 3 | 3 | The Joint confirmed complete (no additional verifiable NH clinics) |
| hospital | 26 | 26 | audited MRF pipeline (unchanged) |

Map pins **76 → 148**. **Deliberately EXCLUDED** (documented, not fabricated): CVS MinuteClinic
extra sites (fetch-blocked), Dartmouth walk-in departments (in-clinic, not standalone urgent
care), Surgery Center of Greater Nashua (hospital-affiliation unconfirmed), Select PT Nashua
(official site 403), Concord Hospital outpatient PT (403), closed facilities (Tellica NH,
North Country Endoscopy), out-of-state false matches. Chiropractic long tail (solo practices)
not enumerable from official multi-location directories.

---

## 3. Non-hospital published pricing (P2)

Every supported non-hospital organization was researched for authoritative, provider-published
prices. **Never inferred; estimator/claims-derived data excluded.**

**Built (this release):** a **Derry Imaging** cash-price collector — real prices transcribed
from the official price page (Chest X-ray $95, Abd US $325, CT Chest $450, CT Abd/Pelvis $1,135,
MRI Brain/Lumbar $800), 42 rows across 7 locations, written at
**`publication_status=candidate_review` (NON-PUBLIC)** with full provenance. Consumer endpoints
require `publishable`, so these never reach consumers automatically; promotion is a human-review
step. Verified: baseline 26/26·50/50 unchanged, safety PASS, Derry Imaging absent from public
procedure pages.

**Researched & buildable next (documented in `data/nh_nonhospital_published_prices.json`):**
Labcorp OnDemand & QuestHealth (CBC $29, Lipid $59, CMP $49 — national self-pay, clean HTML),
The Joint Chiropractic ($55 visit / $29 new-patient), ConvenientMD ($175 flat + occ-health PDF),
ClearChoiceMD ($160 prompt-pay).

**Excluded (no provider-published cash price):** Shields (calculator only), Bedford/Nashua/
Concord ASCs (phone quote only), **NH HealthCost** (claims-**estimated** medians — reference
cross-check only, not a price source per the no-inference rule).

---

## 4. Location quality (P3)

- **Geocoded** the 3 hospital-affiliated freestanding ERs (Plaistow, Dover, Seabrook) via
  ZIP-centroid — now on the map (hospital pins 25 → 26).
- **Duplicate physical-location detector: 0** same-facility duplicates. Normalizer folds
  Drive/Dr, Road/Rd, Street/St, Highway/Hwy, Boulevard/Blvd, Suite/Unit.
- **10 cross-org shared buildings reported (review-only, not merged)** — legitimate distinct
  organizations sharing one street address (Derry Imaging + Quest co-locations; Portsmouth
  Surgery Center + Professional PT at 325 Lafayette Rd; Northeast Rehab + SNHH Immediate Care at
  29 Northwest Blvd; etc.). Ambiguous same-address rows are never auto-merged.
- The pre-existing **Parkland Derry duplicate** (from the 0014 backfill) was proven-identical and
  consolidated earlier this session (coords merged onto the priced survivor, all 10 FK classes
  re-pointed, duplicate deleted, backup taken).

---

## 5. Two-way procedure↔provider mapping audit (P4) — EXHAUSTIVE

### 5a. False-positive direction
`detect_crosswalk_false_positives` → **26/26 hospitals CLEAN, 0 public suspect descriptions, 0
records affected**, re-run AFTER the remediation below (with +785 new mappings). This is the
direction that would have caught the historical `$29,058 penile-prosthesis → chest-x-ray`
failure; none exists.

### 5b. Exhaustive false-negative audit — 1,300 cells (50 procedures × 26 hospitals), COMPLETED
The earlier implementation timed out (correlated `NOT EXISTS` + `LIKE` over all 5.8M records).
It was **redesigned** (`scripts/audit_false_negative_mapping.py`, unit-tested) to run to
completion: per-hospital sharding (each hospital's ~220k records touched once), set-based
coverage queries (bounded approved-code `IN`-lists + `facility_id` index), candidate `LIKE`
scoped to one facility AND only uncovered procedures, and a per-hospital result emitted the
moment it finishes (Cloud Logging = resumable checkpoint; `--skip-ccns` resumes). It classifies
every cell into the six required states.

**A systematic false-negative gap was found and fixed.** Four hospitals — **Elliot, Exeter,
Monadnock, Southern NH Medical Center** — publish standard procedure codes LABELED as `HCPCS`
in their MRFs (`HCPCS:85025` "Complete cbc automated", `HCPCS:71250` "CT CHEST W/O CONTRAST",
`HCPCS:72148` "Mri lumbar spine w/o dye"), while our crosswalk stored the same codes under
`CPT`. Exact `(system, code)` matching dropped them, so these hospitals were **absent from the
live site** for ~130 procedure listings (confirmed absent for CBC/CT-chest/MRI-lumbar before
the fix). Pre-remediation the four published only **4–6 of 50** procedures each. The other gates
could not catch this — they don't check "is a hospital absent because its code failed to map."

**Remediation (deterministic, authoritative, reversible):** CPT (5-digit numeric, 00100-99999)
IS HCPCS Level I, so `HCPCS:NNNNN` ≡ `CPT:NNNNN` by definition — not a fuzzy match.
`scripts/remediate_code_system_equivalence.py` added an approved `HCPCS:NNNNN` alias for each
approved numeric `CPT:NNNNN` (**64 aliases**, tagged `version="cpt_hcpcs_l1_equiv"`, reversible;
never aliases Level-II G/J codes, REV_CODE, or MS_DRG). The existing `reproject_approved_code_
mappings` then created **785 new exact-approved-code mappings (0 removed)** from the
HCPCS-labeled raw records, and `rebuild_price_summaries` reprojected. **No fuzzy/AI/wording
mapping was created; candidate discovery stays separate from approved mappings.**

**Result of the fix:**

| Metric | Before | After |
|---|---:|---:|
| PUBLISHING_VERIFIED_PRICE cells | 899 | **1,116** |
| REVIEW_REQUIRED cells | 206 | **38** |
| DESCRIPTION_CANDIDATE_NOT_MAPPED | 91 | 74 |
| MATCHING_APPROVED_RAW_RECORD_NO_SUMMARY | 5 | 3 |
| NO_MATCHING_RAW_RECORD | 99 | 69 |
| KNOWN_CODE_NOT_MAPPED | 0 | 0 |
| Public price summaries | 15,047 | **16,031** (+984 real prices recovered) |

The four hospitals now publish 40+ procedures each; e.g. CBC coverage 18→24 hospitals, CT-chest
19→24, MRI-lumbar 16→22. Coverage was **never forced** — Exeter remains correctly absent from
cataract-surgery (genuinely not offered). All gates re-run and passed (false-positive 0, safety
PASS, `ai_modified_prices=0`, P6 PASS, 416 tests green).

**Remaining review-only candidates (never auto-published):** 38 REVIEW_REQUIRED + 74
DESCRIPTION_CANDIDATE cells are legitimate human-review items — contrast/method variants of an
approved code (e.g. CT-with-contrast `71260`, open-vs-arthroscopic repair) or local/CDM codes —
not a systematic gap. 3 MATCHING_APPROVED_RAW_RECORD_NO_SUMMARY (Littleton deliveries, Speare
cardiac-cath) are reviewed-mapped records that didn't project a summary — a follow-up. Each is
listed for human review; none is a code-system labeling miss.

---

## 6. Price anomaly audit (P5)

Across all **15,047** live price rows for the 50 procedures:
- **0** $0 prices, **0** negative prices, **0** exact-duplicate (location, payer, plan, setting,
  component) rows → no cross-location contamination.
- Extreme-ratio screen (>25× / <0.02× per-procedure median) flagged **254 rows**, concentrated in
  **inherently high-variance canonical procedures** (allergy-testing, surgical-pathology,
  screening-mammogram, sleep-study, ECG, urinalysis) where one canonical slug legitimately spans
  many CPT codes of very different scope (a single-allergen test vs a comprehensive panel). These
  are **price dispersion, not mismappings** — confirmed by the 0 false-positive result.
- **The $0.30 outlier — TRACED to source, LEGITIMATE (kept, not removed).**
  `scripts/trace_price_anomaly.py` resolved Concord Hospital-Laconia allergy-testing $0.30 to
  raw record `57951`: description **"PF-Percut allergy skin tests"**, code **CPT:95004** (the
  exact approved allergy-testing code — a PER-TEST code, descriptor "specify number of tests"),
  gross $3.00, cash $0.90, negotiated range **$0.30–$3,484.78** (parser `cms_hpt_csv`). The
  $0.30 is a legitimate **per-unit negotiated rate** for a per-allergen test; the $3,484 max is
  the full-panel rate. Correctly mapped — NOT a parsing/mapping error. This also explains the
  allergy-testing price dispersion. Retained per the "trace before removing" rule.
- **No catastrophic mismap** (wrong-procedure high-dollar) recurs; re-verified after +785
  mappings (false-positive detector still 0).

---

## 7. AI medical-safety regression (P7)

- **235-prompt multilingual eval** (en, es, vi, zh-CN, zh-TW): **195/195 medical-advice prompts
  refused deterministically before any LLM call** (`used_llm=false`); **0 leaks**. **40/40**
  legitimate price/provider queries correctly allowed (0 over-blocked).
- AI is **structured-intent-only** and cannot generate, estimate, alter, infer, or fill prices;
  `ai_modified_prices: 0` in the safety audit.
- `services/api/tests/test_ai_medical_safety.py` (31 tests) green.

---

## 8. 50-procedure coverage table

Hospitals-with-published-price and total price rows per canonical procedure (live API, NH):

| Procedure | Hospitals w/ price | Price rows |
|---|---:|---:|
| abdominal-ultrasound | 26 | 378 |
| basic-metabolic-panel | 26 | 370 |
| bone-density-scan | 26 | 393 |
| chest-x-ray | 26 | 349 |
| electrocardiogram | 26 | 388 |
| lipid-panel | 26 | 375 |
| mri-brain-without-contrast | 26 | 374 |
| thyroid-test | 26 | 370 |
| urinalysis | 26 | 398 |
| cardiac-stress-test | 25 | 381 |
| echocardiogram | 25 | 325 |
| pregnancy-test | 25 | 394 |
| surgical-pathology | 25 | 363 |
| upper-endoscopy | 25 | 341 |
| a1c-test | 24 | 402 |
| complete-blood-count | 24 | 304 |
| ct-chest | 24 | 348 |
| mri-knee-without-contrast | 24 | 352 |
| screening-mammogram | 24 | 386 |
| cesarean-delivery | 23 | 386 |
| comprehensive-metabolic-panel | 23 | 323 |
| pap-test | 23 | 338 |
| pelvic-ultrasound | 23 | 314 |
| physical-therapy-evaluation | 23 | 320 |
| vaginal-delivery | 23 | 378 |
| colonoscopy | 22 | 248 |
| ct-abdomen-pelvis | 22 | 302 |
| diagnostic-mammogram | 22 | 311 |
| ed-visit-level-1 | 22 | 281 |
| ed-visit-level-2 | 22 | 283 |
| ed-visit-level-3 | 22 | 284 |
| ed-visit-level-4 | 22 | 284 |
| ed-visit-level-5 | 22 | 282 |
| gallbladder-removal | 22 | 422 |
| hip-replacement | 22 | 274 |
| knee-replacement | 22 | 274 |
| mri-lumbar-spine-without-contrast | 22 | 310 |
| urgent-care-visit | 22 | 194 |
| covid-test | 21 | 304 |
| sleep-study | 20 | 333 |
| strep-test | 20 | 334 |
| carpal-tunnel-release | 19 | 228 |
| flu-vaccine | 19 | 261 |
| hernia-repair | 19 | 214 |
| rotator-cuff-repair | 18 | 205 |
| cardiac-catheterization | 17 | 397 |
| cataract-surgery | 17 | 254 |
| dialysis-session | 17 | 479 |
| allergy-testing | 13 | 152 |
| annual-wellness-visit | 13 | 71 |

Lowest coverage (allergy-testing 13, annual-wellness-visit 13, dialysis 17) reflects
genuine service-line availability and MRF publication patterns, not a mapping gap — all 50 clear
the false-positive gate. `annual-wellness-visit` has the fewest price rows (71); worth a future
candidate-discovery pass to confirm no hospital terminology variant is being missed.

---

## 9. Provider-type coverage (directory facets, live)

hospital 26 · emergency_department 26 · freestanding_emergency_department 3 · urgent_care 39 ·
laboratory 24 · imaging 10 · ambulatory_surgery 10 · rehabilitation 4 · physical_therapy 33 ·
chiropractic 3 — **148 map locations across 10 capabilities**.

---

## 10. Remaining follow-ups (documented, none blocking; all price-not-available today)

1. **Promote & expand non-hospital prices:** review the Derry Imaging candidates for publish;
   build the researched-ready collectors (Labcorp/Quest OnDemand, The Joint, ConvenientMD,
   ClearChoiceMD).
2. **Fuller rosters** where an authoritative machine-readable list was blocked: NH DHHS ASC list
   (HTTP 403), additional CVS MinuteClinic sites, Select PT, Concord Hospital outpatient PT,
   independent chiropractic.
3. **Candidate-discovery sweep** for the lowest-coverage procedures (allergy-testing,
   annual-wellness-visit) to confirm no hospital-terminology variant is missed.
4. **Trace** the single sub-$1 allergy-testing outlier to its raw source.
5. **Model refinement:** hospital-affiliated non-hospital sites (WDH rehab at the hospital campus)
   are separate facilities flagged as shared buildings — consider linking to the hospital org.

---

## Massachusetts

**NOT STARTED.** Per directive, MA remains deferred pending owner review of this NH report.
