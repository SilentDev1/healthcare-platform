# Price accuracy model

Carevero verifies what a hospital published; it does not guarantee the final amount a patient
will owe. A public price is considered fully accurate only when all four dimensions below pass.

## Accuracy dimensions

1. **Source accuracy:** the source is an official hospital machine-readable file, identified by
   immutable source URL, archive path, SHA-256 checksum, download timestamp, and import run.
2. **Value accuracy:** the `Decimal` used by the public observation equals the source numeric field
   exactly. Formatting-only normalization (for example, `$1,250.00` to `1250.00`) is allowed.
   Rounding, estimation, inflation adjustment, or AI transformation is not allowed.
3. **Semantic accuracy:** the record retains the source code and description and is attached to the
   correct procedure, canonical facility, physical location, payer and plan (when present), service
   setting, billing class/component scope, and price type. Public mappings must be exact approved
   code mappings or reviewed mappings; fuzzy-only mappings fail.
4. **Publication accuracy:** only `publishable` observations and summaries may enter public API
   projections. Negative amounts, unresolved locations, unnormalized negotiated payers, suppressed
   sources, and review-required mappings remain non-public.

Passing value equality alone is not “verified accurate.”

## Evidence chain

`FacilityProcedurePriceObservation` stores the direct amount and consumer semantics. It points to
`HospitalPriceRecord`, which preserves facility/location, source file and import run, record/row
locator, source-payload hash, bounded raw payload, parser name/version, original description,
setting, billing class, and exact numeric columns. Service codes retain source code-system and raw
code values. Procedure mappings retain method, confidence, review decision, reviewer, and approved
code mapping. Negotiated details preserve the original payer/plan strings alongside canonical payer
and plan references.

`SourceFile` identifies the official URL, archive path, SHA-256, source publication/download dates,
and parser version. The source URL is attribution; the checksum identifies the immutable version.

## Direct and derived values

Direct observation mappings are deterministic:

| Public observation type | Immutable normalized source field         |
| ----------------------- | ----------------------------------------- |
| `gross`                 | `gross_charge`                            |
| `discounted_cash`       | `discounted_cash_price`                   |
| `deidentified_min`      | `deidentified_minimum_negotiated_rate`    |
| `deidentified_max`      | `deidentified_maximum_negotiated_rate`    |
| `payer_negotiated`      | `HospitalPriceRateDetail.negotiated_rate` |

Public summaries are derived and labeled as ranges/medians, not direct source quotes. Their inputs
are the publishable observation IDs linked through summary provenance. Calculation is exact minimum,
maximum, and median within one facility/location/procedure/payer/plan/setting/component scope. The
calculation never combines incompatible locations or settings.

Consumer comparison keeps cash/self-pay separate from negotiated rates. Without an explicit payer
selection, the primary representation is payer availability and exact payer/plan/rate counts; the
cross-payer minimum and maximum is secondary source context only. With a payer and optional plan,
only matching published rates enter the primary range. Distribution percentiles remain suppressed
when code variant, setting, component, or rate-method comparability is not established.

Exact duplicate rate tuples within one hospital source row are normalized once to satisfy the
provenance model's source-row/payer/plan/amount identity. This removes duplicate encodings, not
outliers, and never changes the published amount. Distinct source rows and semantic scopes remain
separate observations.

## Audit statuses

- `FULL_SOURCE_VERIFIED`: exact value and semantics pass; archived raw source exists and SHA-256
  matches.
- `PROVENANCE_VERIFIED`: exact value and semantics pass using bounded immutable evidence, but the
  complete raw source was not locally reconstructed.
- `SOURCE_FILE_UNAVAILABLE`: required bounded provenance is incomplete.
- `VALUE_MISMATCH`: normalized amount differs from the source numeric column.
- `SEMANTIC_MISMATCH`: value matches but one or more semantic associations fail.
- `MAPPING_REVIEW_REQUIRED`: mapping is missing or neither exact-approved nor reviewed.

Audit runs are reproducible by state, filters, sample size, mode, and seed. The command is read-only
by default:

```bash
python -m scripts.audit_public_prices --state NH --sample-size 100 --seed 4700
```

Filters include `--facility`, `--procedure`, `--payer`, and `--full`. Audit tables are append-only
evidence storage for a future explicitly recorded run; they are not required for read-only audits.

## Consumer language

Use “Hospital-published price,” “Source verified” only when full-source criteria pass, “Source
unavailable for recheck” where appropriate, and “Derived from published rates” for summaries.
Always state that published prices are estimates for comparison and not a quote or final bill.
