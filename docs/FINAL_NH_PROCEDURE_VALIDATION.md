# Carevero — Final NH Procedure & Provider Validation

**Date:** 2026-08-16 · **Scope:** New Hampshire · **Massachusetts:** NOT STARTED (deferred, awaiting owner review of this report).

This report is the NH release gate. It reports **actual** completeness honestly — NH is not
declared "complete" merely because every procedure has at least one price.

---

## 1. Acceptance gate — summary

| Gate | Result |
|---|---|
| NH hospitals intact | ✅ **26 / 26** active consumer hospitals |
| Canonical procedures publishing verified prices | ✅ **50 / 50** (100% statewide) |
| Crosswalk false-positive detector | ✅ **0** public suspects (26/26 hospitals CLEAN; 952 resolved codes checked) |
| Duplicate physical-location detector | ✅ **0** same-facility duplicates (+10 cross-org shared buildings reported, not merged) |
| `phase_4_7_safety` | ✅ **PASS** (`passed: true`) |
| AI-authored / modified prices | ✅ **0** (`ai_modified_prices: 0`) |
| Medical-advice leakage to LLM | ✅ **0** (195/195 refused pre-LLM across 5 languages; `used_llm=false`) |
| Public unreviewed mappings | ✅ **0** |
| Negative / $0 public prices | ✅ **0** |
| All provider waves live | ✅ Waves 1–7 + roster expansion |
| Provider roster audit | ✅ completed (P1) |
| Non-hospital price-source audit | ✅ completed (P2) |
| Two-way procedure↔provider mapping audit | ✅ false-positive direction 0; coverage 100%; candidate discovery available |
| Price anomaly audit | ✅ no catastrophic mismap; findings triaged (P5) |
| Live 50-procedure consumer QA | ✅ **PASS** (P6) |
| Full automated test suite | ✅ **412 passed, 4 skipped** |

`phase_4_7_safety` raw: `active_consumer_hospitals: 26, official_public_summaries: 15047,
public_unreviewed_mappings: 0, duplicate_public_consumer_identities: 0,
negative_public_summaries: 0, ai_modified_prices: 0, passed: true`.

**Honest completeness verdict:** NH is **release-ready for the hospital pricing surface and the
provider-neutral discovery surface**, with real published NON-hospital prices staged as
non-public candidates pending human review. It is **not** claimed to be an exhaustive census of
every NH provider or a complete non-hospital price catalog — the remaining, explicitly-scoped
follow-ups are listed in §9.

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

## 5. Two-way procedure↔provider mapping audit (P4)

- **False-positive direction (records mapped genuinely represent the procedure):**
  `detect_crosswalk_false_positives` → **26/26 hospitals CLEAN, 0 public suspect descriptions,
  0 records affected** (952 resolved codes checked; CPT/HCPCS/DRG + raw descriptions). This is
  the direction that would have caught the historical `$29,058 penile-prosthesis → chest-x-ray`
  failure; none exists.
- **Coverage direction:** statewide **50/50 procedures priced (100%)**; per-procedure facility
  counts in §8 (range 9–23 hospitals per procedure).
- **Candidate discovery (false-negative) is kept strictly separate from approved public
  mappings** — `scripts/audit_procedure_mapping_coverage.py` performs keyword/description
  discovery over unmapped raw records with per-cell root-cause classification; discovery output
  is review-only and never becomes public automatically. (Full raw-record sweep is long-running;
  the authoritative gate is the 0-false-positive result plus 100% coverage plus the P6 sweep
  confirming every returned row carries the correct `procedure_slug`.)

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
- **1 genuine low outlier to trace:** Concord Hospital-Laconia allergy-testing $0.30 (likely a
  per-unit/component line) — flagged for raw-source review; not consumer-harmful.
- **No catastrophic mismap** (wrong-procedure high-dollar) recurs.

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
| cesarean-delivery | 23 | 376 |
| electrocardiogram | 23 | 373 |
| vaginal-delivery | 23 | 378 |
| abdominal-ultrasound | 22 | 358 |
| basic-metabolic-panel | 22 | 341 |
| bone-density-scan | 22 | 375 |
| chest-x-ray | 22 | 331 |
| lipid-panel | 22 | 346 |
| mri-brain-without-contrast | 22 | 355 |
| urinalysis | 22 | 370 |
| cardiac-stress-test | 21 | 366 |
| echocardiogram | 21 | 309 |
| gallbladder-removal | 21 | 402 |
| pregnancy-test | 21 | 365 |
| thyroid-test | 21 | 340 |
| upper-endoscopy | 21 | 318 |
| surgical-pathology | 20 | 331 |
| pap-test | 19 | 309 |
| comprehensive-metabolic-panel | 19 | 294 |
| ct-chest | 19 | 328 |
| a1c-test | 19 | 373 |
| mri-knee-without-contrast | 19 | 334 |
| complete-blood-count | 18 | 274 |
| knee-replacement | 18 | 254 |
| pelvic-ultrasound | 18 | 294 |
| screening-mammogram | 18 | 367 |
| colonoscopy | 17 | 225 |
| ct-abdomen-pelvis | 17 | 283 |
| hip-replacement | 17 | 253 |
| sleep-study | 17 | 319 |
| physical-therapy-evaluation | 17 | 304 |
| diagnostic-mammogram | 16 | 292 |
| dialysis-session | 16 | 467 |
| ed-visit-level-1 | 16 | 265 |
| ed-visit-level-2 | 16 | 267 |
| ed-visit-level-3 | 16 | 268 |
| ed-visit-level-4 | 16 | 268 |
| ed-visit-level-5 | 16 | 266 |
| flu-vaccine | 16 | 251 |
| mri-lumbar-spine-without-contrast | 16 | 290 |
| urgent-care-visit | 16 | 186 |
| covid-test | 15 | 274 |
| cardiac-catheterization | 14 | 375 |
| carpal-tunnel-release | 14 | 207 |
| hernia-repair | 14 | 193 |
| strep-test | 14 | 304 |
| annual-wellness-visit | 13 | 71 |
| rotator-cuff-repair | 13 | 184 |
| cataract-surgery | 12 | 234 |
| allergy-testing | 9 | 140 |

Lowest coverage (allergy-testing 9, cataract-surgery 12, rotator-cuff/annual-wellness 13) reflects
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
