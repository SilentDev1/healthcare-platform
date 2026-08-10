# Phase 4.4 beta readiness report

Date: 2026-08-10  
Decision: **GO for private-beta deployment preparation**

Carevero's anonymous consumer journey is coherent, honest about incomplete data,
and ready to move into a controlled private-beta environment. Phase 4.4 did not
deploy the product or expand into accounts, AI, PHI, insurer TiC ingestion,
advertising, booking, payments, or commercial infrastructure.

## What was verified

- PostgreSQL-backed search and pricing APIs, with no SQLite substitution
- Natural-language procedure discovery, city/ZIP entry, filters, empty states,
  payer-zero states, sparse facilities, and multi-location hospital systems
- Anonymous URL/session comparison, three-item limit, payer preservation, and share
- Facility procedure overview aggregated by procedure and physical location
- CMS quality context, official hospital sources, freshness, and provenance
- Responsive and keyboard-oriented browser journeys, branded error recovery, SEO,
  sitemap, and robots behavior
- Production builds and a production-mode Chromium smoke test

The public coverage number is now intentionally 11 of 26 active hospitals rather
than the fixture-inflated 15 previously shown. The underlying source inventory is
unchanged; only the consumer representation was corrected. Forty-eight procedures
have at least one official-source publishable summary.

## Browser and performance observations

- Mobile QA covered 375, 390, and 430 px widths; controls remained readable and no
  journey-blocking horizontal overflow was observed.
- Desktop/tablet layouts preserve search, filters, comparison, and facility source
  hierarchy; the map remains route-isolated and uses OpenStreetMap tiles without a
  paid map key.
- Server pages use bounded consumer API calls rather than per-card requests: the
  results page uses one comparison response plus procedure/payer context, and the
  facility page uses facility, quality, and aggregated procedure-overview requests.
- The production build completed static generation successfully. Real production
  latency must be measured again in the eventual beta hosting environment because
  local timings include a development PostgreSQL dataset and workstation I/O.

## Automated verification

| Check | Result |
| --- | --- |
| Ruff formatting and lint | PASS — 127 files formatted, no lint findings |
| strict MyPy | PASS — 119 source files |
| pytest | PASS — 89 tests, 64% aggregate measured coverage |
| ESLint | PASS — public and admin |
| Prettier | PASS |
| TypeScript | PASS — all workspaces |
| Vitest | PASS — 16 tests across 11 files/workspaces |
| Public production build | PASS |
| Admin production build | PASS |
| npm audit | PASS — 0 vulnerabilities |

## Accessibility and trust assessment

Core controls use native buttons, links, inputs, labels, disclosure elements, and
tables. The app includes a skip link, explicit navigation labels, status/alert
regions, disabled-state explanations, and minimum touch targets. Price language
distinguishes published cash prices from negotiated ranges and repeatedly explains
that neither is a quote, network determination, benefit decision, or guaranteed
bill. No ranking, “best hospital,” arbitrary savings, or fake conversion action was
introduced.

## Remaining beta risks

- Official price coverage is incomplete (11/26) and must continue to be visible.
- Native Safari and Firefox certification should occur before a broad public launch.
- A beta owner and existing non-PHI feedback channel must be named during deployment
  preparation; product-side feedback collection was deliberately not invented.
- Hosting-specific monitoring, security headers, cache behavior, and performance
  budgets cannot be certified until a beta environment exists.

## Recommendation

Proceed with exactly one next phase: **Phase 4.5 — Private Beta Deployment
Preparation**. That phase should prepare the approved environment, release runbook,
monitoring, rollback, privacy-safe feedback operations, and hosted smoke tests. It
should not broaden product scope or restart acquisition work.
