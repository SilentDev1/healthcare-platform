# Phase 4.9 AI Evaluation Report

Evaluation date: 2026-08-13. Scope: local isolated branch with synthetic/fixture data; no
production mutation and no public deployment.

## Results

| Category | Result | Evidence |
|---|---|---|
| Typed request/intent/context | PASS | extra fields/control characters rejected |
| Natural-language procedure resolution | PASS | reviewed search projection only |
| Material clarification | PASS | mammogram; MRI/CT/delivery rules covered in code |
| Deterministic result retrieval | PASS | `/ai/query` calls existing comparison function |
| Price grounding | PASS | unsupported dollar amounts rejected; absent price renders none |
| Distance grounding | PASS | unsupported mileage rejected; absent distance renders none |
| Comparability/savings | PASS | non-comparable fixture produces no savings/difference prose |
| Insurance wording | PASS | explicit published-price caveat; prohibited network claims rejected |
| Missing-data honesty | PASS | no-price response does not assert no service |
| Prompt injection | PASS | instruction-like facility/source data cannot authorize unsupported value |
| English | PASS | deterministic localized safety path |
| Spanish | PASS | deterministic localized safety path |
| Vietnamese | PASS | deterministic localized safety path |
| Simplified Chinese | PASS | deterministic localized safety path |
| Traditional Chinese | PASS | deterministic localized safety path |
| Provider failure fallback | PASS | provider absence/error/rejected output returns deterministic answer |
| Static quality | PASS | Ruff and strict mypy |

Focused command: `pytest -q services/api/tests/test_ai_safety.py services/api/tests/test_api.py`
— **32 passed**. Full repository suite: `pytest -q` — **164 passed**. Ruff reports no
issues and strict mypy reports no issues across 177 source files.

## Adversarial cases

Automated guards cover invented price, invented distance, “definitely in-network,” absent facts,
non-comparable context, extra arbitrary fields, and source text containing “IGNORE PREVIOUS
INSTRUCTIONS.” The safety prompt additionally prohibits guesses, coverage, acceptance, best-
hospital claims, diagnosis, invented availability, ratings, plans, sources, and savings.

## Known failure cases and limitations

- Deterministic natural-language extraction is intentionally conservative and will ask for the
  procedure when reviewed search cannot resolve it. It is not a general multilingual clinical
  translator.
- The initial numeric grounding guard recognizes dollar-formatted amounts and English “miles.”
  Structured deterministic fallback remains the fail-closed path for rejected provider output;
  broader locale-aware semantic output validation is required before widening private beta.
- No live-vendor evaluation was run because no provider secret is committed or required locally.
- Exact plan-alias matching remains limited by existing normalized plan data.
- UI insertion is deliberately deferred to the post-Phase-4.8 integration pass to avoid collision
  with the active consumer interface.
