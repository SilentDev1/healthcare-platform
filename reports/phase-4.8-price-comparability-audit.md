# Phase 4.8 — Price Comparability Audit (NH)

Read-only statewide audit (`scripts/audit_price_comparability.py`) of published
cash prices per facility/procedure. No source records were modified.

## Root cause of the Cheshire "$175–$1,356" range

Cheshire Medical Center publishes, for **MRI brain without contrast**:

| service setting | billing scope (`included_component_scope`) | cash |
|---|---|---|
| outpatient | facility | $1,355.99 |
| inpatient | facility | $1,355.99 |
| outpatient | professional | $174.98 |
| inpatient | professional | $174.98 |

`$174.98` is the **professional (radiologist read) fee**; `$1,355.99` is the
**facility fee**. Both legitimately map to the procedure. The comparison endpoint
min/maxed cash across `included_component_scope`, producing a misleading
`$175–$1,356` range. The data model already stored the scope — the endpoint
simply collapsed it.

## Fix

`summarize_cash_components` groups published cash by `(service_setting,
billing_scope)`, selects a single **comparable primary** (a complete facility
charge: facility/global/combined/bundled, preferring outpatient), and lists other
components separately. Cheshire MRI brain now shows a comparable **$1,355.99**
facility price with the $175 professional fee as an additional published price.
The savings engine keys cohorts on `(setting, billing_scope)` and only uses a
single exact directly-comparable cash amount — facility is never compared to
professional/technical/component, cash never to negotiated, and no cross-setting
or cross-procedure comparison occurs.

## Statewide results (live production, 26 NH hospitals)

| Metric | Count |
|---|---|
| Facility/procedure combinations audited | **605** |
| Clean (single setting + single component) | 317 |
| Mixed service setting | 244 |
| Mixed billing component | 153 |
| Partial-component-only (no complete facility charge) | 24 |
| Previously misleading ranges (mixed + ≥3× ratio) | **111** |

## Automatically resolved vs still ambiguous

- **Cross-component / cross-setting ranges (153 + 244):** resolved for display and
  savings — a single comparable primary is chosen; other components are listed
  separately; savings never crosses components or settings.
- **Partial-component-only (24):** classified `not_comparable`; shown but excluded
  from savings (no complete facility charge exists).
- **Wide ranges within one setting+scope (manual review):** many hospitals map
  several distinct billing codes/line items to one consumer procedure (for
  example bone-density $0.44–$1,566 within outpatient/facility). These are a
  **procedure-mapping granularity** issue, not a component issue. They are
  surfaced by this audit for review, are excluded from savings (not a single
  exact value), and are **not** auto-deleted. Recommended follow-up: code-level
  procedure disambiguation.

## Savings exclusions

A published price is excluded from any savings claim unless it is
`directly_comparable`, has a known setting and complete facility scope, and is a
single exact cash amount. All ranges, partial components, unknown scopes, and
cross-scope/setting pairs are excluded.

## Provenance

Every displayed price remains traceable to facility, source file, source URL,
raw record, mapping, setting, and billing scope. No synthetic prices, averages,
or midpoints are created.
