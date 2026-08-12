# Phase 4.8 — Distance + Comparable Published-Price Decision Support

Deterministic distance and comparable-savings insights for the consumer
comparison experience. No AI is involved in any distance, eligibility, or
savings computation.

## Architecture

- **Origin geocoding** (`packages/geo.py`): offline, deterministic. Reads
  bundled public-domain **U.S. Census 2023 Gazetteer** centroids from
  `data/fixtures/zip_city_centroids.json` (786 NH+MA ZIPs, 348 cities, 38 KB).
  The schema is state-neutral and US-ready; extend the states in the generator
  to grow coverage. Distance is computed from latitude/longitude via the
  haversine formula and works across state lines — state is never a boundary.
- **Comparable insights** (`services/api/app/comparison_insights.py`): pure,
  testable functions that annotate comparison items with distance and a
  semantically guarded cash-price difference.
- **API**: `GET /procedures/{slug}/comparison` gains `origin_zip`,
  `origin_city`, and `radius_miles`. Items carry `distance_miles`,
  `comparable_cash_price`, `published_price_difference`, `difference_basis`,
  `is_lowest_comparable_cash`, `comparable_cash_facility_count`, and
  `lower_priced_nearby_option`. No misleading fields (no `guaranteed_savings`).

## Semantic comparability rules (the most important rule)

A published-price difference is only ever computed between prices that are:

1. the **same canonical procedure** (every comparison item is one procedure),
2. a **compatible service setting** (grouped by primary setting), and
3. a **single exact published cash / self-pay price** on each side.

Never compared: cash vs negotiated, cross-procedure, incompatible setting, or a
published cash **range** (min != max) — a range signals laterality/bundle
variation and is never reduced to one number. When fewer than two comparable
prices exist in a setting cohort, no claim is made. Missing pricing is never a
savings input and never implies the hospital lacks the service.

## Consumer presentation

- **Distance** shows on result cards ("8.4 miles"), as a "Nearest first" sort,
  and a radius filter (10/25/50/100 miles). Location is the distance **origin**,
  not a hard filter — all matching hospitals stay visible; radius only drops
  hospitals with a known distance beyond it (unknown-distance hospitals remain).
- **Savings** shows as a factual badge: "Lowest published cash price shown" for
  the cohort minimum, or "Published-price difference: +$X" for others, with the
  basis "compared with the lowest published cash price shown; your final cost
  may differ." A nearby lower-priced comparable option is surfaced when present.
  No "guaranteed savings" / "your cost" language.
- **Comparison panel** adds Distance and Published-price difference rows.
- A non-blocking **Save comparison** extension point is present; anonymous use
  is fully preserved (no signup wall).
- All strings are translated across en / es / vi / zh-TW / zh-CN.

## Verification (§39)

- **Distance calculation:** PASS — Nashua (03060) → Southern NH Medical Center
  0.9 mi, Catholic Medical Center 17.1 mi, Elliot 32.4 mi (live).
- **Cross-state ready:** PASS — NH+MA centroids bundled; distance is coordinate
  based, no state boundary.
- **Distance filtering (radius):** PASS.
- **Distance sorting:** PASS — nearest-first verified live.
- **Comparable savings:** PASS — deterministic, cohort by setting.
- **Cash savings:** PASS — MRI knee: Concord $1,728 (+$796 vs lowest);
  mammogram: CMC $1,443 (+$846), Frisbie $1,299 (+$702), live.
- **Payer-specific savings:** PARTIAL — payer/plan comparison context is
  preserved end-to-end; a payer-scoped difference row is a follow-up.
- **Plan-specific savings:** NOT SUPPORTED yet (plan context preserved).
- **Semantic compatibility rules:** PASS — tests cover range exclusion,
  cross-setting exclusion, cash-vs-negotiated exclusion, single-item cohorts.
- **Misleading savings blocked:** PASS.
- **Nearby lower-price alternative:** PASS.
- **Mobile:** PASS — cards stack, no horizontal overflow.
- **Translation:** PASS — five locales; Vietnamese verified live.
- **Performance:** PASS — coverage ~0.8 s, homepage ~0.46 s, results ~0.63 s;
  distance/savings are O(n) over the bounded result set, no per-request geocoding
  network calls.
- **Account conversion extension:** READY (non-blocking Save comparison).
- **Anonymous access preserved:** PASS.

## Safety

`phase_4_7_safety` passed after deploy: 22/26 publishable hospitals preserved,
fixture/negative/provenance/unreviewed/duplicate invariants all 0. Image/distance
availability does not affect price results; default organic ordering is unchanged
(distance only reorders when the consumer selects "Nearest first").

## Massachusetts / US readiness

No React or schema changes are required to add MA — only MA facility data and
additional centroids. No `if state == "NH"` logic exists in distance/savings.

## Known limitations

- Savings intentionally silent where cash prices are ranges or a setting cohort
  has fewer than two comparable single-value cash prices (safe by design).
- Payer/plan-scoped difference rows and a fuller full-comparison savings section
  remain follow-ups.
- Some service locations lack coordinates and show no distance (never hidden).
