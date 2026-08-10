# Phase 4.4 friction log

Date: 2026-08-10

Scope: anonymous consumer search, price comparison, facility detail, trust,
accessibility, responsive behavior, and production readiness. No new data
acquisition or post-beta product scope was introduced.

| ID | Severity | Journey | Finding | Resolution | Status |
| --- | --- | --- | --- | --- | --- |
| F-01 | P1 | Search | PostgreSQL returned no candidates for consumer synonyms such as “knee scan” and “CAT scan” because synonym expansion happened after SQL filtering. | Expanded synonym targets before the PostgreSQL predicate and added regression coverage. | Fixed |
| F-02 | P0 | Compare | A payer-filtered result could enter comparison without its payer context, producing an all-payer range that looked like the selected payer. | Preserved payer state in comparison URLs and API requests and explicitly labeled selected-payer ranges. | Fixed |
| F-03 | P1 | Compare | Anonymous session selections leaked between different procedures. | Scoped session storage by procedure slug. | Fixed |
| F-04 | P1 | Compare | Session-backed selected states could differ between server markup and hydration. | Moved selection state to `useSyncExternalStore` with a stable server snapshot. | Fixed |
| F-05 | P0 | Facility | Facility pages used the first 50 payer summaries, creating repeated procedure rows and potentially omitting data. | Added a consumer procedure-overview endpoint aggregated by procedure and physical location. | Fixed |
| F-06 | P0 | Provenance | Fixture prices could make a facility appear priced on the map and inflate homepage coverage. | Excluded `file://` fixtures from all public map, facility overview, comparison, and coverage representations. | Fixed |
| F-07 | P1 | Location identity | Multi-location hospital systems were difficult to interpret in facility pricing. | Kept physical location names and settings on every aggregated procedure row; verified Portsmouth (3) and Parkland (2). | Fixed |
| F-08 | P2 | Search | Invalid numeric ZIP input had no actionable feedback. | Added five-digit ZIP validation and city/ZIP help text. | Fixed |
| F-09 | P2 | Empty states | Payer-zero and no-price states could be mistaken for network or coverage conclusions. | Added explicit language that absence is not evidence of acceptance, network participation, or coverage. | Fixed |
| F-10 | P2 | Compare | A fourth comparison selection failed without explaining the three-item limit. | Disabled the action and explained how to remove an item. | Fixed |
| F-11 | P2 | Compare | Completed comparisons had no anonymous sharing path. | Added Web Share support with a clipboard fallback; no account required. | Fixed |
| F-12 | P2 | Trust | Source labels lacked consumer-friendly freshness and official-link wording; facility pages repeated hundreds of links. | Standardized source/freshness labels and consolidated official links by source and location. | Fixed |
| F-13 | P2 | First impression | Free anonymous access and the estimate/medical-advice boundary were not immediately clear. | Added concise homepage assurance and persistent trust navigation. | Fixed |
| F-14 | P2 | Recovery | Consumer routes lacked branded 404 and runtime recovery pages. | Added branded not-found and error states; valid missing records return the not-found experience. | Fixed |
| F-15 | P2 | SEO | Public pages had incomplete metadata and sitemap coverage while search/compare could be indexed as thin stateful pages. | Added useful canonical metadata and JSON-LD, API-driven sitemap entries, and `noindex` boundaries for search/compare. | Fixed |
| F-16 | P2 | Portability | Consumer pages repeated launch-state literals. | Centralized launch region, map center, and zoom configuration without introducing multi-state infrastructure. | Fixed |

## Accepted beta limitations

- Official-source publishable prices currently cover 11 of 26 active launch-region hospitals. This is displayed honestly; fixture data is never substituted.
- Published negotiated rates do not establish network status, benefits, authorization, or the consumer's final responsibility.
- Distance/radius sorting is not offered because precise consumer-origin distance is not yet implemented.
- Browser verification used the Chromium-based in-app browser. Standards-based markup and responsive CSS are expected to work in current Safari and Firefox, but native cross-browser device-lab certification remains a pre-public-launch task.
- Private-beta feedback collection must use the beta coordinator's existing communication channel; no speculative account, form, CRM, or PHI collection was added.

No unresolved P0 or P1 issue remains in the verified scope.
