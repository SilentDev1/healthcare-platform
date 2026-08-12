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
| Header / nav / footer | ✅ localized |
| Hero + hero assurance | ✅ localized |
| Popular searches (chips + View all) | ✅ localized |
| **Search form (`CareSearch`)** | ✅ **localized (this change)** |
| Distance / radius / savings copy | ✅ localized |
| Billing-component comparability copy | ✅ localized |
| Coverage transparency notice | ✅ localized |
| Result cards (`ui.tsx`) — badges, "Comparing", "Published cash price", "View details", price-details labels | ⬜ **hardcoded English (next)** |
| Comparison panel (`CompareSelect`) — Cash price / Setting / CMS rating / Distance / Clear all / Save comparison | ⬜ **hardcoded English (next)** |
| Results page filter labels (availability/setting/rating/facility type, Apply/Clear) | ⬜ partial |
| Procedure directory / procedure page | ⬜ hardcoded English |
| Hospital directory / hospital detail | ⬜ hardcoded English |
| How It Works / About Data | ⬜ hardcoded English |
| Map Carevero-owned UI | ⬜ hardcoded English |
| Error / empty / loading states | ⬜ mostly hardcoded English |
| Procedure names (localized presentation) | ⬜ not started (canonical identity stays neutral) |
| Locale-aware search synonyms | ⬜ not started |

## Hardcoded-string inventory (approx., consumer-facing)

`ui.tsx` ~23 · `CompareSelect` ~14 · `how-it-works` ~8 · `about-data` ~8 ·
`procedures` ~6 · results filter form ~10. Total remaining ≈ 70 strings
(× 5 locales ≈ 350 entries).

## Completed this installment

Search form fully localized across all five locales (labels, placeholders,
helper text, validation error, insurer/rate label, submit button). This is the
primary journey entry point that was previously English in VI/ZH.

## Remaining plan (prioritized, each shipped as a complete tested slice)

1. `ui.tsx` result cards + `CompareSelect` comparison panel (highest traffic).
2. Results-page filter form labels + empty/error states.
3. Procedure & hospital directory/detail pages.
4. How It Works / About Data / map UI / footer disclaimers.
5. Parameterized dynamic messages ("N hospitals found", "N miles away", etc.).
6. Localized procedure presentation names + locale-aware search synonyms.
7. i18n completeness/hardcoded-string guard test; full VI + zh-CN + zh-TW + es
   E2E browser QA; responsive QA.

## Truthfulness rules (all locales)

"Published insurance rate" is never translated into "insurance accepted" or
"covered". See `docs/consumer-language-glossary.md`.
