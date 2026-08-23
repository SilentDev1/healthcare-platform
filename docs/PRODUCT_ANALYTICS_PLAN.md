# Carevero — Product Analytics Plan

**Purpose:** replace opinion with evidence in future UX audits by measuring whether real people
answer their question — *"Where should I go for this service, and what will it cost me?"*

**Privacy stance (non-negotiable):** Carevero is a public, no-account, health-price tool. Analytics
must be **aggregate and non-identifying**. Never put a searched procedure, a facility, a price, or
any health-adjacent value into a URL, a third-party pixel, or an identifiable event. No cross-site
tracking. A searched condition is sensitive data — treat it that way. Prefer first-party,
cookieless, aggregate counts over any hosted analytics SDK.

## The one funnel that matters

```
arrive → search (Ask or manual) → see a price → compare → view facility detail
```

Every drop-off between two steps is a friction hypothesis for the next audit.

| # | Event (aggregate only) | Question it answers |
|---|---|---|
| 1 | `home_view` | Are people landing? |
| 2 | `search_started` (Ask vs manual, no query text) | Do they engage the primary action? |
| 3 | `results_shown` (result_count bucket: 0 / 1–3 / 4+) | Do searches return usable results? |
| 4 | `price_seen` (has_published_price: bool) | Do they reach an actual price? |
| 5 | `no_price_shown` | How often is the honest "not available" state hit? |
| 6 | `compare_opened` (n facilities bucket) | Do they use the compare tool? |
| 7 | `detail_view` | Do they commit to a specific facility? |
| 8 | `self_pay_toggled` | How salient/used is the cash-first path? |
| 9 | `locale` (dimension on all above) | Is any locale underperforming? |

**Explicitly NOT collected:** procedure names/slugs, facility ids, price values, free-text Ask
queries, IP-derived precise location, or anything joinable to a person.

## North-star & guardrail metrics

- **North star:** *price-reach rate* = `price_seen` ÷ `search_started`. Rises when the plain-language
  layer works and coverage is real.
- **Honesty guardrail:** *no-price rate* (`no_price_shown` ÷ `results_shown`). This should be
  **visible, not hidden** — a rising no-price rate is a coverage signal, never a reason to soften
  the "not available" copy into a fake number.
- **Compare-engagement:** `compare_opened` ÷ `results_shown`.

## Implementation notes

- First-party endpoint (`POST /api/v1/analytics/event`) writing aggregate counters; or a
  privacy-respecting cookieless aggregate tool. No client-side third-party scripts.
- Events fire from existing components (home, search, `ComparisonFacilityCard`, compare panel,
  detail) — no new consumer surfaces.
- Ship behind a config flag; default off until the privacy review signs off.

## Status

**Not yet implemented** (P3 backlog item from `docs/PRODUCT_UX_AUDIT.md`). This document is the
spec; instrumentation is a separate, owner-reviewed change because it introduces a new data path.
