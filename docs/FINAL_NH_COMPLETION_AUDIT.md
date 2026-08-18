# Carevero NH — Final Completion Audit

Authoritative NH completion record. Last updated: 2026-08-18 (combined Codex-UI release).

## Production (live)
- **API:** `carevero-beta-api-00064-hap` (100%) — provider-neutral comparison, `payment_context`, DTC-options endpoint, 52-procedure catalog, hardened medical gate (rollback `00062-quy`).
- **Web:** `carevero-beta-web-00063-tih` (100%) — Codex consumer-nav redesign (Find care ▾ / Ask drawer / Quick Search) + self-pay UX + DTC lab section (rollback `00062-qud`).
- **Job image:** `job:psa`. **Main:** `8eebe19` (backend + all Codex UI, clean fast-forward). **Migration:** `0015`.
- **Canonical procedures: 52** — the original 50 intact + `vitamin-d-test` (#51, CPT 82306) + `psa-test` (#52, CPT 84153). HbA1c is `a1c-test` (never duplicated).

## What works (live, verified)
- **Provider-neutral comparison** — non-hospital published prices appear at applicable locations; Derry Imaging $325 ultrasound ranks cheapest of 26 directly-comparable; hospital behavior unchanged.
- **Ask Carevero self-pay intent (P0)** — "I need a blood test without insurance" → Laboratory + `payment_context=self_pay`; medical/OOD/injection all refused **pre-LLM** (`used_llm=false`) across EN/ES/VI/ZH; **0** AI-authored prices.
- **Self-pay UX** — comparison "Paying without insurance?" banner + `?pay=self` cash-first mode (reorders only, never hides providers, never relabels negotiated as cash); Ask deep-links into it. i18n×5. Live-verified (SSR + browser).
- **Search quality** — 72/77 natural queries resolve; xray/thyroid-test wording fixed.
- **Provider directory** — 148 locations, provider-neutral, "Published price not currently available in Carevero" (never "0 procedures"), price/type/region filters, list/grid/map.

## Pricing coverage
- Total service locations: **148** · Hospitals **26/26**.
- Published-price locations: **33** (26 hospitals + 7 Derry Imaging).
- Verified-service / no published price: the remainder (labs, urgent care, PT, ASC, chiropractic, ED) — shown honestly as price-unavailable.
- Candidate-only (NON-PUBLIC): Quest **56** rows.

## Labs (Quest + LabCorp) — verified, NOT published (by design)
- **Quest DTC** (questhealth.com, 2026-08-17): CBC $35, CMP $55, Lipid $65, TSH $55, UA $46 (each = test + required **$6** physician fee); HbA1c $45 (canonical gap).
- **LabCorp OnDemand** (ondemand.labcorp.com, 2026-08-18): CBC $29, CMP $49, Lipid $59, TSH $49, HbA1c $39 — **all-inclusive** (no separate fee), cheaper than Quest on every test.
- **Decision:** both are national **org/product-level** DTC prices. Publishing them per-location would fabricate the "14 fake location prices" the directive forbids, so they stay `candidate_review` (NON-PUBLIC). Consumer publication requires an **org-level DTC price surface** (next feature). See `NH_LAB_PRICE_ARCHITECTURE.md`.

## Canonical catalog
- **52 canonical procedures** — original **50 intact** + Vitamin D (#51) + PSA (#52), both added deliberately with exact-code mappings (fp-detector CLEAN). HbA1c already existed as `a1c-test`. Remaining gaps (proposal only): urgent-care visit, PT eval/session, chiropractic, ambiguous "diabetes test". See `NH_CANONICAL_PROCEDURE_GAPS.md`.

## Safety (post-deploy, 2026-08-18)
- `phase_4_7_safety` **PASS**: 26 hospitals, negatives 0, missing-provenance 0, unreviewed-mappings 0, duplicate-identities 0, **ai_modified_prices 0**.
- fp-detector **26/26 CLEAN** (last run) · candidate leakage **0** (Quest verified non-public live).

## Blockers (classified)
- **Org-level DTC lab price surface** — *FUTURE ENHANCEMENT / TECHNICAL* (needed to publish Quest/LabCorp honestly).
- **Vitamin D / PSA / urgent-care visit / PT / chiropractic** — *CANONICAL REVIEW*.
- **NHCHIS / NH HealthCost** — *OWNER ACTION / LICENSING* (not scraped).
- **Full UI/mobile/a11y/perf/SEO deep audits** — *PARTIAL* (directory + comparison + self-pay audited; remainder pending).
- **Massachusetts** — *FUTURE* (not started).

## NH status: PARTIAL (strong + safe)
Hospital pricing, provider-neutral comparison, Ask reliability, search quality, self-pay UX, and the provider directory are live, safe, and verified. Non-hospital lab pricing is verified and staged, publication gated on the org-level DTC surface. UI polish and remaining pricing orgs continue.

## Massachusetts readiness: NOT READY
NH not yet at strongest state; MA not started. See `MA_EXECUTION_PLAN.md` when NH work is exhausted.
