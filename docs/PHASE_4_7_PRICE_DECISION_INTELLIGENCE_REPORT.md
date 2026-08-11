# Phase 4.7 Price Decision Intelligence Report

## 1. Root cause of broad cash ranges

Carevero did not mix cash and insurance prices. The public comparison endpoint did,
however, collapse distinct source descriptions within one canonical procedure into an
unexplained minimum/maximum. For Catholic Medical Center's MRI knee without contrast,
the official file contains CPT 73721 at $4,902 for left and right unilateral rows and
$9,068 for a bilateral row. The source distinction is legitimate and is now preserved
in price details and explained wherever multiple cash values are displayed.

## 2. Root cause of broad negotiated ranges

The old headline aggregated every normalized payer, plan, source rate method, and
service variant at a physical location. This produced mathematically correct but poor
decision context. For CMC, the endpoints were an Anthem Individual On Exchange
fee-schedule rate of $203.07 and a Tufts PPO percent-of-charge bilateral rate of
$6,458.23. Global ranges are now secondary. Without insurance selection, the UI lists
available payers; after explicit payer/plan selection, only matching published rates
become primary.

## 3. CMC MRI investigation

- Facility/location: Catholic Medical Center, Manchester
- Official checksum: `84022dfea9adb756a7176d2618fc48dc2961281c4b2e32e6b8c714f92b637d06`
- Mapping: reviewed exact CPT 73721 → MRI knee without contrast, confidence 1.0
- Cash source rows: 123838 bilateral $9,068; 136177 left $4,902; 138668 right $4,902
- Setting/component: outpatient/facility
- Finding: valid laterality/quantity variants were hidden by the former aggregation

The private, read-only lineage export in the provenance bucket contains all 292 CMC
observations, raw descriptions, codes, payer/plan identities, row identifiers, source
timestamps, URL, and checksum. It is intentionally not committed to Git.

## 4. Concord MRI investigation

Concord publishes one $1,728.30 cash value across left/right and inpatient/outpatient
source rows (CPT 73721 with LT/RT modifiers). The global negotiated endpoints were
$249.67 (Medicare managed, outpatient) and $5,530.56 (UnitedHealthcare, outpatient).
The exact cash presentation is legitimate; the negotiated global headline was not a
useful insurance-specific comparison.

## 5. Franklin MRI investigation

Concord Hospital–Franklin publishes one $931.80 cash value across left/right and
inpatient/outpatient source rows. The negotiated endpoints were $251.08 (Anthem
Pathways, outpatient) and $2,969.03 (Tufts, inpatient). The cash presentation remains
exact; negotiated rates are now scoped by explicit consumer selection.

## 6. Payer normalization architecture

Raw payer text remains immutable on rate details. Deterministic aliases resolve to a
canonical payer entity and slug; unknown payers remain review-required and cannot be
silently promoted. Public responses expose canonical payer identity while the source
detail remains traceable to the raw record.

## 7. Plan normalization architecture

Plans are independently normalized under a payer, preserving the raw plan string and
the payer/plan boundary. The API accepts a plan UUID only after optional payer
selection. It does not infer a plan from a payer name and does not convert a published
plan rate into an acceptance, network, or coverage claim.

## 8. Insurance-aware UX

The anonymous comparison flow now exposes location, self-pay context, optional payer,
and optional plan. Cards prioritize published cash prices plus matching negotiated
rates only when insurance is selected. Without a selection, cards show payer
availability and a consumer can open grouped price details.

## 9. Network and coverage distinction

Every insurance surface states that a published negotiated rate does not prove network
participation or benefit coverage. The price, provider-directory network evidence, and
patient benefit concepts remain separate domains. No network inference was added.

## 10. Price semantic model

Consumer detail records classify cash/self-pay, payer-only negotiated, payer-and-plan
negotiated, gross charge, de-identified minimum, de-identified maximum, and unknown
unsafe values. Cash, gross, and negotiated values are never relabeled or combined.
Hospital rate method is carried separately when the source supplies it.

## 11. Price aggregation rules

Cash values come only from publishable discounted-cash observations. Matching
negotiated ranges use the selected payer/plan and retain setting/component boundaries
in deterministic summaries. Global negotiated bounds remain accessible only as
secondary detail. Percentiles were not promoted because code variant, setting,
component, and source-rate-method comparability cannot yet be guaranteed across all
current files.

## 12. Outlier diagnostics

The statewide read-only audit now groups negotiated summaries by facility, physical
location, procedure, setting, and component scope and flags spreads of 10× or greater.
Flags preserve source truth and trigger review; they never delete or modify a rate.

## 13. Price-detail UX

A new noindex route presents cash and payer-grouped negotiated records with amount,
plan, hospital description, billing code, laterality variant, setting, component scope,
rate method, and official source access. Gross and de-identified bounds are secondary.
Large result sets declare truncation and direct consumers to narrow by payer/plan.

## 14. API changes

- `GET /api/v1/procedures/{slug}/comparison` supports `payer` and `plan`.
- Comparison items include matching counts, distinct payer/plan counts, payer
  availability, cash-value context, secondary global bounds, deterministic
  completeness, spread diagnostics, and separated freshness fields.
- `GET /api/v1/procedures/{slug}/locations/{location_id}/price-details` returns a
  bounded consumer projection rather than raw ingestion payloads.

## 15. Database and index changes

Migration 0010 preserves official modifiers longer than 20 characters. Migration 0011
adds composite consumer-detail and insurance-summary indexes. Migration 0011 uses
idempotent PostgreSQL index DDL because legacy migration 0004 creates pricing tables
from current ORM metadata on a clean database.

## 16. Query-performance measurements

The pre-change live MRI comparison measured 161–203 ms end-to-end across the required
procedure sample. On the realistic local PostgreSQL dataset after migration 0011, warm
MRI comparison requests measured 65–79 ms, payer+plan comparison requests 52–61 ms,
and source-detail requests 41–116 ms. The first cold comparison was 262 ms. These meet
the <500 ms target and the preferred <250 ms warm target. Post-deployment measurements
are recorded in the final live verification section below.

## 17. Accessibility verification

Controls use labels, native selects, semantic details/summary, tables with scoped
headers, mobile data labels, non-color status text, visible keyboard interactions, and
responsive card layouts. Price context wraps at large text and narrow widths.

## 18. Internationalization verification

Shared messages now include comparison, coverage, self-pay, insurance, plan, network
warning, and price-detail concepts. English, Vietnamese, Simplified Chinese, and
Traditional Chinese remain complete beta locales. Hospital, plan, billing-code, and
source values are not translated.

Browser verification at 1,440 px and 390 px confirmed no horizontal overflow, a true
single-column mobile card layout, complete payer+plan keyboard-select flow, a working
two-of-three comparison selection, and consumer-readable source details.

## 19. Test results

To be finalized after production deployment. The pre-deployment baseline is Ruff PASS,
strict MyPy PASS across 147 source files, pytest 116 PASS, ESLint PASS, Prettier PASS,
TypeScript PASS, 22 Vitest tests PASS, public/admin production builds PASS, npm audit 0
vulnerabilities, secret scan PASS, and clean
PostgreSQL migration 0001→0011 plus 0011 downgrade/re-upgrade PASS.

## 20. Live beta verification

To be finalized after safe deployment and smoke testing.

## 21. Remaining limitations

- Published negotiated rates do not establish network participation or coverage.
- Professional/interpretation fees cannot be assumed included.
- Source descriptions do not always provide a reliable bundle taxonomy.
- Distribution percentiles remain suppressed where semantic comparability is unknown.
- Distance remains unavailable where consumer coordinates are not supplied.

## 22. Massachusetts readiness

All filtering and projections are state-neutral and remain keyed by canonical facility,
physical location, procedure, payer, plan, setting, and component. Massachusetts does
not require a core redesign.

## 23. Recommended next phase

The next approved phase should add reviewed service-variant taxonomy and independent
provider-directory network evidence before considering distribution statistics or
stronger insurance guidance.
