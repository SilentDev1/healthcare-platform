# AI Readiness Architecture (do NOT build the assistant yet)

This phase adds **no** LLM/chatbot. This documents the boundary so a future
assistant can be added safely: the deterministic engine computes and owns every
fact; AI only explains what the engine already produced.

## 1. The boundary

```
  Deterministic Carevero Data Engine   (source of truth — computes facts)
            │  structured, provenance-carrying result
            ▼
  Structured Consumer Result           (stable JSON contract)
            │
            ▼
  AI Explanation Layer                 (narrates; MUST NOT invent facts)
```

Target query: *"I live in Nashua and have Blue Cross, I need a knee MRI — show me
options within 30 miles and where the published comparable price is lower."*

Everything factual in the answer is already computed deterministically today:

| Fact | Engine source (already shipped) |
|---|---|
| procedure | catalog + reviewed synonyms/aliases |
| facility / service location | facilities + locations |
| published cash / negotiated price | price summaries + comparability layer |
| billing-component separation | `comparison_insights.summarize_cash_components` |
| directly-comparable savings | `comparison_insights.annotate` (savings guard) |
| distance / radius | `packages/geo.py` haversine + centroids |
| CMS quality | quality observations |
| published payer availability | payer/plan summaries |
| provenance / freshness | source files + checksums + dates |
| facility image | `facility_media` (verified only) |

The AI layer's job is to *select, order, and phrase* these — never to produce a
price, a distance, a savings number, a network claim, or an image.

## 2. Hard rules for the future AI layer

1. **No fabrication.** The model may only reference values present in the
   structured result. Prices, savings, distances, CMS ratings, comparability,
   network status, provenance, and images come from the engine verbatim.
2. **Comparability honesty.** If the engine marks two prices `not_comparable`,
   the AI must not present them as comparable or compute a "savings".
3. **Insurance truthfulness.** Published rate ≠ accepted ≠ covered ≠ in-network
   (see docs/INSURANCE_DATA_FOUNDATION.md). The AI repeats the engine's
   conservative status and the "confirm with your insurer" caveat.
4. **No medical advice.** Educational framing only; defer clinical decisions to a
   professional (mirrors existing disclaimers).
5. **Locale.** Explanations honor the active locale; the engine stays
   locale-agnostic (facts identical across locales, as today).
6. **Grounding + citation.** Every claim traces to a result field; surface the
   same source links/dates the deterministic UI already shows.

## 3. What to expose to make AI safe (mostly already true)

- The comparison endpoint already returns a structured, provenance-carrying,
  locale-agnostic result (`ProcedureComparisonResponse` with per-item
  comparability, savings basis, distance, reason codes, image refs). This IS the
  AI-consumable contract; keep it stable and additive.
- Add (when building AI): a thin read-only "decision context" assembler that
  bundles procedure + origin + radius + selected payer into one structured object
  the model consumes; it calls the same deterministic functions, adds nothing.
- Tool-use pattern: give the model *retrieval tools* over engine outputs, not
  free-text generation of numbers. The model chooses which engine facts to show.

## 4. Non-goals for the AI phase

- No autonomous price/mapping/network/image generation or "estimation".
- No writing to pricing, comparability, network, or media tables.
- No bypassing the review gates (reviewed mappings, verified media, conservative
  network status).

## 5. Provider note

When the assistant is built, follow the chosen LLM provider's API guidance for model
choice, tool use, and caching. Not part of this phase.
