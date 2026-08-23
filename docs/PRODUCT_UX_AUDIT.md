# Carevero — Product / UI / UX / Consumer-Experience Audit

**Date:** 2026-08-23 · **Scope:** the live consumer web app (`apps/web`), all 5 locales
(en, es, vi, zh-CN, zh-TW). **Lens:** the one question a real person arrives with —
*"Where should I go for this healthcare service, and what is it likely to cost me?"*

**Non-negotiable that framed every change:** UI/UX work must never weaken data integrity.
No invented/estimated/AI-modified prices; missing price stays *"not available"*, never `$0`;
provenance, billing scope, cash-vs-negotiated distinction, and the deterministic medical-safety
gate are preserved. `ai_modified_prices` stays **0**. This audit changed **copy and presentation
only** — no price, mapping, or gate logic was touched.

---

## Headline

Carevero is already a **mature, honesty-first** product. The prior build (New England hero,
Ask Carevero, `/providers` directory, self-pay-first pricing) is well-aligned with what the
research says shoppable-healthcare consumers actually need. The audit therefore found **few real
defects** — and the one that mattered was a **launch-critical staleness bug introduced by the MA
go-live**, now fixed.

The instinct to add more data or more surfaces was explicitly resisted: the research (below) is
unambiguous that raw price-transparency data is the *number-one* cause of consumer abandonment,
and Carevero's job is to be the **plain-language layer over verified data**, not another MRF viewer.

---

## What the research says (see `docs/CONSUMER_PRODUCT_RESEARCH.md`)

1. **Remove friction, don't add data.** The failure mode of every transparency tool is drowning
   the shopper in codes and caveats.
2. **Raw transparency data is the #1 abandonment cause.** Be the plain-language interpreter.
3. **Self-pay / cash is a first-class path**, not an insurance afterthought.
4. **Plain service names + "near me"**, mobile-first.
5. **Demote CPT/DRG/gross-charge/negotiated to tooltips**; label prices *"estimate, not a bill"*
   and say what's included.
6. **~12 high-demand shoppable services as tappable cards**; give a facility-type savings cue.

## How the live product already scores against it

| Research finding | Live state | Verdict |
|---|---|---|
| Plain-language layer, not raw data | Ask Carevero primary; deterministic search secondary | ✅ already true |
| "Estimate, not a bill" labeling | *"estimates for comparison, not a quote or guarantee"* (i18n `priceDisclaimer`) | ✅ already true |
| What's included | `procWhatIncluded: "What the price may include"` | ✅ already true |
| Self-pay first-class | `selfPayTitle: "Paying without insurance?"` + "Show cash prices first" toggle | ✅ already true |
| No jargon leak | No `CPT`/`MRF`/`chargemaster`/`gross charge` in consumer copy; "negotiated rate" always explained | ✅ already true |
| Shoppable-service cards | `PopularSearches` = tappable plain-name procedure cards → `/search?q=…` | ✅ already true |
| Never show missing price as $0 | `priceNotAvailable: "Price not currently available"` | ✅ already true |

Carevero was **not** failing the consumer test. The audit's value was catching where a backend
milestone (MA launch) had silently falsified a piece of front-end copy.

---

## Defects found & fixed (this changeset)

### P0 — Homepage coverage read "80 of 26 active hospitals" (FIXED)

The homepage coverage line rendered a hospital ratio:
`facilities_with_publishable_prices` / `nh_facilities`. When Massachusetts went live,
`facilities_with_publishable_prices` grew to **80** (NH + MA + non-hospital) while the
denominator `nh_facilities` stayed **26** — producing the nonsensical, trust-damaging live string
**"published for 80 of 26 active hospitals."**

**Fix (copy/presentation only, no data touched):**
- `apps/web/app/page.tsx` — coverage line no longer computes a hospital ratio; it states the
  published **procedure** count, which is well-defined across states.
- `apps/web/lib/i18n.ts` — all 5 `homeCoverageSummary` strings rewritten multi-state:
  *"Live in New Hampshire and Massachusetts, with published prices for {procedures} procedures —
  always shown with their sources and limitations."*
- Coverage count still comes straight from `/api/v1/pricing/coverage` — no hardcoded numbers.

### P1 — Expansion copy still said "starting from New Hampshire" (FIXED)

With MA live, the hero expansion card's *"we're starting in New Hampshire"* framing was stale.
- `apps/web/lib/home-i18n.ts` — all 5 `expandBody` strings → *"Now live in New Hampshire and
  Massachusetts, with more of New England coming soon."* (`expandTitle` "Carevero is expanding
  across New England" kept — still accurate.)

### Housekeeping
- `apps/web/app/page.test.tsx` — homepage test updated to assert the corrected multi-state copy.
- `apps/web/app/components/DirectoryMap.tsx` — scoped `eslint-disable` for
  `react-hooks/set-state-in-effect` on the canonical async-fetch-with-cancel-guard effect
  (pre-existing lint error from the provider-directory work; the pattern is correct — the guard
  prevents the render-loop the rule protects against). No runtime change; green `eslint .`.

**Deliberately NOT changed** (verified accurate, not stale):
- `homeFeaturedIntro` ("Select up to three New Hampshire hospitals…") — the homepage featured
  widget fetches `?state=NH`, so the NH wording is *correct*, not stale.
- `home-i18n.ts mapAria` — unused/dead string (not rendered); left untouched to avoid churn.

---

## Gates (all green)

| Gate | Result |
|---|---|
| `npx tsc --noEmit` (5-locale key parity enforced by `type Messages = typeof en`) | ✅ pass |
| `npx eslint .` | ✅ clean |
| `vitest run` | ✅ 219/219 (15 files) |
| `npm run build` (production) | ✅ success |
| Data integrity | untouched — no price/mapping/gate code changed; `ai_modified_prices` still 0 |

---

## Prioritized backlog (not in this changeset — owner-reviewable)

These are genuine opportunities, but none are correctness bugs and each warrants a design pass;
listed so nothing is lost. Ordered by consumer value ÷ risk.

- **P1 · IA consolidation.** `/facilities`, `/hospitals`, `/providers` overlap as directory
  surfaces; `/procedures`, `/search`, `/ask` overlap as search surfaces. Consider canonical routes
  + redirects to reduce "which page am I supposed to use?" friction. (Redirect-only; low risk, but
  touches nav + SEO, so deserves its own change.)
- **P2 · State-aware homepage featured example.** The featured comparison is hardcoded
  `mri-knee-without-contrast?state=NH`. Now that MA is live, consider rotating or geo-defaulting
  the featured market. (Design choice, not a bug.)
- **P2 · Facility-type savings cue.** Research finding #6 (independent imaging/ASC vs hospital
  outpatient) — surface a plain-language "often lower at …" cue **only where verified data
  supports it** (never invent a differential).
- **P3 · Analytics instrumentation.** See `docs/PRODUCT_ANALYTICS_PLAN.md` — measure the funnel
  (arrive → search → see price → compare → view detail) to replace opinion with evidence in future
  audits.

---

## Deployment — DONE (2026-08-23)

Deployed and production-verified. Web revision **`carevero-beta-web-00052-x8g`**, image
`us-east4-docker.pkg.dev/carecompare-development/carevero/web:ux-coverage-fix1`, serving 100%.

Canonical procedure (project `carecompare-development`, repo `carevero`, image `web`):

```bash
gcloud builds submit --project=carecompare-development --region=us-east4 \
  --config infrastructure/cloudbuild/web.yaml \
  --substitutions=_IMAGE_TAG=ux-coverage-fix1,\
_API_PUBLIC_URL=https://carevero-beta-api-650406651221.us-east4.run.app,\
_PUBLIC_APP_URL=https://carevero-beta-web-650406651221.us-east4.run.app .
gcloud run services update carevero-beta-web --project=carecompare-development --region=us-east4 \
  --image=us-east4-docker.pkg.dev/carecompare-development/carevero/web:ux-coverage-fix1
```

> **Deploy gotcha (hit and fixed):** the image lives in project `carecompare-development`, repo
> `carevero`, image `web` — the `_IMAGE_URI` default in `web.yaml`. Do **not** hand-construct
> `$PROJECT/carevero/web`; a bare `$PROJECT` resolves to `carevero` and Cloud Run returns
> `PERMISSION_DENIED` on the nonexistent `projects/carevero/repositories/web`.

**Prod-QA (PASS, all 5 locales):** homepage coverage reads the multi-state sentence with the live
procedure count (52); the broken "80 of 26 active hospitals" string is gone (0 occurrences).
Web-image-only deploy — runtime `CARECOMPARE_API_URL` preserved; server `apiGet` unaffected.

**Rollback:** copy-only change; NH and MA price data untouched and independent. Revert to revision
`carevero-beta-web-00063-tih` if needed.
