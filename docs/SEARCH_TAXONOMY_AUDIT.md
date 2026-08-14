# Search Taxonomy and Intent Audit

Audit date: 2026-08-13. Scope: isolated `feature/search-semantics-fix` branch,
fixture-backed canonical catalog. Category membership is read from active `Procedure` rows; no
pricing observations are queried or aggregated.

## Root cause and fix

The database category `Laboratory`, the directory label `Lab tests`, and underscore-based UI keys
were independent definitions. The search index therefore could not resolve the visible label.
`data/consumer_procedure_categories.json` is now the reviewed shared registry for canonical slugs,
i18n keys, five-locale labels, and reviewed aliases. Both the procedure directory and search index
consume it. Canonical procedure rows remain the sole membership/count source.

## Visible-category consistency

| Consumer category | Canonical ID | Procedures | Search | AI-visible | Result |
|---|---|---:|---|---|---|
| Cardiology | `cardiology` | 4 | resolves | yes | PASS |
| Emergency care | `emergency` | 6 | resolves | yes | PASS |
| Eye care | `ophthalmology` | 1 | resolves | yes | PASS |
| Gastroenterology | `gastroenterology` | 2 | resolves | yes | PASS |
| Imaging | `imaging` | 10 | resolves | yes | PASS |
| Lab tests | `laboratory` | 11 | resolves | yes | PASS |
| Women's health | `maternity` | 2 | resolves | yes | PASS |
| Orthopedics | `orthopedics` | 4 | resolves | yes | PASS |
| Other services | `other` | 3 | resolves | yes | PASS |
| Outpatient surgery | `outpatient-surgery` | 2 | resolves | yes | PASS |
| Preventive care | `preventive` | 4 | resolves | yes | PASS |
| Rehabilitation | `rehabilitation` | 1 | resolves | yes | PASS |

**12/12 visible categories pass.** `inpatient-surgery` is retained in the registry for future
catalog membership but is not displayed because it currently has zero active procedures.

## Resolution policy

Deterministic matching runs first: exact procedure, reviewed procedure alias, exact localized or
canonical category, reviewed category alias, conservative category prefix, facility, city, and ZIP.
Category matches expand to canonical procedure cards and never query prices. `knee scan` is no
longer treated as an MRI synonym; it returns canonical imaging candidates with a clarification.

Unknown/conversational queries are marked `ai_fallback_eligible`. The new AI contract accepts only
typed proposals and rejects category/procedure IDs absent from active canonical data. The AI branch
should import `category_registry_for_ai()` and `validate_ai_intent()` into its existing read-only
tool/orchestrator layer after branch integration. No second provider or AI orchestration stack was
created here.

## Search-quality evaluation

Representative cases are stored in `data/verification/search_intent_eval.json`: exact terms,
aliases, categories, facilities/locations, conversational inputs, misspellings, ambiguity,
diagnostic questions, unsupported services, injection attempts, and complex price/distance intent.
Current deterministic PASS cases include category consistency, exact procedure, reviewed aliases,
facility/location, multilingual category labels, ambiguity/medical boundaries, unsupported honesty,
and canonical AI-candidate rejection. Live provider evaluation remains deferred until the AI branch
is integrated and enabled in private beta.

## AI branch integration contract

After Phase 4.8/main stabilization:

1. Merge this search branch first so the shared taxonomy and resolver are authoritative.
2. Rebase or merge `feature/carevero-ai-foundation` with conflict review in `main.py`, API tests,
   `packages/search`, and search schemas.
3. Extend `CareveroReadOnlyTools` with `category_registry_for_ai`, category lookup/membership, and
   `validate_ai_intent`; do not copy taxonomy into `services/ai`.
4. Have AI orchestration run only when `ai_fallback_eligible=true`; validate every proposed slug
   before calling comparison/pricing APIs.
5. Preserve deterministic results when AI flags are off, provider calls fail, or candidates reject.

No deployment or production index rebuild was performed by this branch.
