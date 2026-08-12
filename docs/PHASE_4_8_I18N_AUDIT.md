# Phase 4.8 — Site-Wide i18n Audit & Plan

## Supported locales

`en`, `es`, `vi`, `zh-TW`, `zh-CN` (all preserved). Vietnamese and Chinese
(both variants) are real beta test languages.

## Architecture (existing, sound — extend, do not replace)

- `apps/web/lib/i18n.ts` — flat `Messages` map. `Messages = typeof en` **forces
  every locale to define every key at compile time**, so there are **no missing
  keys for existing keys**; the gap is *hardcoded strings not yet in the map*.
- `apps/web/proxy.ts` (Next 16 middleware) resolves locale from the URL prefix
  or `carevero-locale` cookie, sets `x-carevero-locale`, and rewrites `/vi/…` →
  `/…`. `requestLocale()` reads that header (server components).
- `LanguageSelector` sets the cookie, `router.push`es the locale-prefixed path,
  then `router.refresh()` to bust the App Router cache (fixed: immediate switch,
  no reload, state preserved). Verified live EN→VI→ZH.
- Client components read `messages[locale]` directly; server components use
  `requestMessages()`.

## Locale invariants (verified)

Changing locale changes **presentation only**. Prices, comparability status,
savings, distance, facility/procedure/payer identity, billing codes, and source
provenance are identical across locales (they come from the API, which is
locale-agnostic).

## Route / component status

| Area | Status |
|---|---|
| Header / nav / footer (incl. beta badge, feedback link, disclaimers) | ✅ localized |
| Hero + hero assurance | ✅ localized |
| Popular searches (chips + View all) | ✅ localized |
| Search form (`CareSearch`) | ✅ localized |
| Distance / radius / savings copy | ✅ localized |
| Billing-component comparability copy | ✅ localized |
| Coverage transparency notice | ✅ localized |
| Result cards (`ui.tsx` `ComparisonFacilityCard`) | ✅ localized |
| Comparison panel + tray (`CompareSelect`) | ✅ localized |
| Results page filter labels + sort toolbar + `FilterPanel` summary | ✅ localized |
| Homepage featured + how-it-works + data/coverage sections | ✅ localized |
| Procedure directory / procedure detail / price-detail page | ✅ localized |
| Hospital directory / hospital detail / `FacilityPrices` table | ✅ localized |
| Compare full-comparison page + `ShareComparison` | ✅ localized |
| Map Carevero-owned UI (client `useLocale`) | ✅ localized |
| Search page (client `useLocale`, incl. `CareSearch`) | ✅ localized |
| How It Works / About Data | ✅ localized |
| Privacy / Terms (headings + body) | ✅ localized |
| Error / not-found / empty / loading states | ✅ localized |
| Procedure clinical names (localized presentation) | ⚠️ intentionally deferred — see below |
| Locale-aware search synonyms | ⚠️ intentionally deferred — see below |

### Client-page locale resolution (new)

`search` and `map` are `"use client"` route roots and cannot receive a
server-resolved locale prop. `apps/web/app/components/useLocale.ts` resolves the
locale on the client with the same precedence as `proxy.ts` (URL prefix wins,
then the `carevero-locale` cookie, then `en`). `CareSearch`/`ShareComparison`
receive `locale` explicitly from their parents.

### Dead code removed

`ui.tsx::FacilityPriceCard` was exported but never imported anywhere (confirmed
by repo-wide grep). It carried hardcoded English, so it was deleted rather than
translated.

### Procedure clinical names + search synonyms — deferred, with rationale

Consumer procedure names/descriptions (`consumer_name`, `short_description`,
`long_description`, `aliases`, `billing_notice`) come from the API and are
**canonical clinical/authoritative values**. Localizing them safely requires a
**human/clinically reviewed** multilingual dataset plus a new presentation table
+ API selection layer + a reviewed multilingual synonym table for search.

Generating clinical procedure-name translations with an LLM and publishing them
as authoritative would violate the project's explicit safety rules
(§4.7/§5: "reviewed synonyms only, no uncontrolled AI mapping", "never
fuzzy-publish") and risk clinical mistranslation. Under the sweep's acceptance
allowance that "hospital names, insurer/company names, medical/billing codes,
and authoritative source values may remain untranslated where appropriate,"
clinical procedure names stay in canonical form for now. The **curated popular
procedure chips** (the localized entry points into search) ARE translated.

Next session (when a reviewed dataset exists): add `procedure_localized_presentation`
(locale, procedure_id, reviewed name/descriptions) + a reviewed multilingual
synonym table, and have the API select by request locale. No React changes needed
beyond reading the already-locale-aware fields.

## Hardcoded-string inventory (approx., consumer-facing)

`ui.tsx` ~23 · `CompareSelect` ~14 · `how-it-works` ~8 · `about-data` ~8 ·
`procedures` ~6 · results filter form ~10. Total remaining ≈ 70 strings
(× 5 locales ≈ 350 entries).

## Completed — full site-wide sweep (Phase 4.8 i18n)

Every Carevero-owned UI surface on the public journeys is now localized across
all five locales (`en`, `es`, `vi`, `zh-TW`, `zh-CN`): home (hero, search, chips,
featured cards, how-it-works, data/coverage), procedure directory/detail/
price-detail, hospital directory/detail + `FacilityPrices`, compare full
comparison + `ShareComparison`, map, search, how-it-works, about-data, privacy,
terms, footer/disclaimers, and all error/not-found/empty/loading states. ~195
message keys were added per locale; all dynamic strings are parameterized via
`{token}` replacement (no English fragment concatenation).

Guardrails added to `lib/i18n.test.ts`:
- **Placeholder-token parity** — every locale must carry the exact same
  `{token}` set per key (catches a dropped/renamed interpolation token).
- **Consumer-language truthfulness** — no locale may render a published rate as
  "insurance accepted / covered / in-network".
The compile-time `Messages = typeof en` guard already forces key completeness.

Verified locally (dev server against the live beta API) in all four non-English
locales across home, how-it-works, procedure prices, compare, map, search.

## Verification commands

- `cd apps/web && npx tsc --noEmit && npx eslint . && npx vitest run`
- `cd apps/web && npm run build`

## Remaining (intentionally deferred — reviewed data required)

1. Localized clinical procedure presentation names + reviewed locale-aware search
   synonyms (see rationale above; needs a reviewed multilingual dataset, not AI).

## Truthfulness rules (all locales)

"Published insurance rate" is never translated into "insurance accepted" or
"covered". See `docs/consumer-language-glossary.md`.
