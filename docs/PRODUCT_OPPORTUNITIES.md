# Carevero Product Opportunities (grounded in demand research)

Date: 2026-08-17. Companion to `CONSUMER_SEARCH_DEMAND_RESEARCH.md`. Every item is judged by
one test: **does it help a consumer FIND, UNDERSTAND, or COMPARE Carevero data?** Anything that
drifts toward diagnosis/treatment/triage is rejected outright.

## BUILT + DEPLOYED (2026-08-17 → 2026-08-18)

- **Self-pay comparison UX — LIVE** (`carevero-beta-web-00061-qoy`): "Paying without insurance?"
  banner on `/procedures/{slug}/prices` + `?pay=self` cash-first mode (reorders only, never hides
  providers, never relabels a negotiated rate as cash); AskCarevero deep-links comparison with
  `?pay=self` when self-pay is detected. i18n×5, browser-verified.
- **Self-pay / uninsured intent recognition** (P0): "I need a blood test without insurance" now
  resolves to the Laboratory category with `payment_context=self_pay`; `/api/v1/search` exposes
  `payment_context`. Deterministic, medical gate untouched. (LIVE, `carevero-beta-api-00059-bek`.)
- **LabCorp OnDemand verified** (2026-08-18): all-inclusive DTC prices captured; Quest-vs-LabCorp
  comparison recorded (`NH_LAB_PRICE_ARCHITECTURE.md`).
- **Natural-language robustness**: payment/intent/provider-type noise stripping ("Compare MRI
  prices", "Find imaging centers", "self pay MRI near Concord") + spelling variants
  ("xray", "thyroid test"). Live false-no-match on a 77-query sweep dropped to documented
  canonical gaps only.
- **Price-fabrication injection guard** + broadened "ignore … restrictions" refusal + Spanish
  medical test-selection gap closed — all pre-LLM, `used_llm=false`.

## NEXT HIGH VALUE (build next; scoped, data exists, safe)

1. **"Paying without insurance?" affordance** (frontend). When `payment_context=self_pay` (or a
   toggle), lead with published cash/self-pay data and label it clearly. Never claim personalized
   out-of-pocket. *Why:* self-pay is a distinct, growing journey (theme #4). *Risk:* low (API
   already returns the signal). *Effort:* small FE change + i18n×5.
2. **Price component tooltips** ("What's included?"): cash vs negotiated, facility vs professional,
   bundled vs partial, DTC test + required physician fee. *Why:* theme #7 (jargon confusion).
   *Risk:* low (static, source-grounded copy). Reuse `included_component_scope` + notes already
   on summaries.
3. **Finish Quest / LabCorp DTC publish** (backend, careful). Per-location `LocationServiceAvailability`
   + DTC-vs-walk-in presentation; partial-promote clean mappings (CBC/CMP/Lipid). *Why:* theme #4.
   *Risk:* medium — must not fake 14 location prices; keep uncertain mappings candidate_review.
4. **Directory ZIP / near-me sort** affordance. *Why:* theme #5. Distance math already exists in
   the comparison annotate path; expose in `/providers`.
5. **Compare shortlist (session-only, no account)**: add/remove providers to a compare list,
   shareable via URL state if privacy-safe. *Why:* theme #1/#5 (compare is the core value).
   *Risk:* low if session/URL-only (no profiles). Document as next if overnight scope is tight.

## FUTURE (valuable, larger or needs review)

- **Canonical catalog expansion** (HbA1c, urgent-care visit, PT eval/session, chiropractic,
  vitamin D, PSA) — deliberate, reviewed; grows 50→50+N explicitly (see NH_CANONICAL_PROCEDURE_GAPS).
- **Popular / most-searched procedures** module on the homepage — only from defensible demand
  signals (this research), not fabricated "trending".
- **"My doctor ordered a test" compare flow** — compare locations/prices for an ordered test
  (strictly navigation; the pre-LLM gate already blocks the advice version).
- **Recently viewed** (session-local) — minor convenience; only if it demonstrably helps.

## DO NOT BUILD (medical-advice or mission drift)

- Symptom checker / diagnosis / "what test do I need for X".
- Treatment or medication recommender / dosage.
- ER-vs-urgent-care triage for a user's symptoms.
- "Best doctor for your condition" / quality-as-medical-judgement.
- AI health coach / chat that answers clinical questions.
- Any personalized out-of-pocket "your cost" claim (Carevero has no benefit data).
- Accounts/profiles storing health data.

Rationale: each of these either constitutes medical advice (refused pre-LLM by design) or implies
data Carevero does not have (personalized benefits), which would make the product untrustworthy.
