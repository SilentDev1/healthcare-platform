# Phase 4.9 AI Foundation Architecture

## Scope and non-goals

Phase 4.9 adds an anonymous, read-only consumer assistant for natural-language procedure
search, material clarification, grounded result explanations, and follow-up questions about the
current comparison. It does not diagnose, recommend treatment, determine coverage/network
status, modify data, book care, create accounts, send messages, browse the web, or replace the
existing search and pricing experience.

The implementation is isolated in `services/ai`, exposed by `services/api/app/ai_routes.py`, and
disabled by default. It adds no migration and does not modify Phase 4.8 consumer UI files.

## Data flow and trust boundaries

```text
consumer text
  -> validated AIRequest
  -> conservative intent extraction
  -> reviewed Procedure/SearchDocument and normalized payer lookup
  -> existing procedure_comparison() deterministic engine
  -> bounded CareveroAIContext (maximum 25 facilities)
  -> provider explanation
  -> numeric/network grounding guard
  -> localized deterministic fallback when unavailable or rejected
```

The model receives no database handle, credentials, arbitrary URL fetcher, SQL tool, raw MRF rows,
or mutation function. `CareveroReadOnlyTools` is the explicit allowlist boundary. Pydantic models
forbid extra fields and constrain identifiers, slugs, states, radii, locales, and lengths.

## Intent schema and clarification

`CareSearchIntent` carries canonical candidate ID/slug, confidence, clarification state,
location/radius, normalized payer/plan identifiers, service setting, price preference, sort,
locale, and bounded follow-up context. Procedure candidates come from the existing reviewed search
projection. The model cannot publish a new mapping. Material ambiguity rules cover mammogram type,
MRI contrast, CT body area, and delivery type; otherwise the assistant proceeds without an
interrogation.

## Grounded fact package

`CareveroAIContext` contains only the selected procedure, origin/filter context, up to 25 facility
facts, limitations, and explicit sources. Per-facility fields include deterministic distance,
CMS rating, comparable cash price, selected published insurance range, billing component/setting,
comparability status, deterministic price difference, availability state, freshness, and source
metadata. Hospital source strings are JSON-delimited untrusted data.

## Comparability, savings, payer, and medical boundaries

- The AI does not calculate distance or price differences. It only receives values returned by the
  existing comparison engine.
- `partially_comparable`, `not_comparable`, and `unknown` never produce savings prose.
- A published insurer price is described only as pricing associated with that insurer. It never
  proves acceptance, network participation, benefits, or coverage. Exact plan identity is
  preserved when present and never silently mixed.
- Procedure choice remains with the clinician/order. The assistant may clarify order wording but
  does not choose a clinically appropriate procedure.

## Provider abstraction and prompt versioning

`AIProvider` is a small protocol. `OpenAICompatibleProvider` is the initial replaceable HTTPS
adapter. Model, endpoint, secret, timeout, and output-token limit come from environment/Secret
Manager configuration. The safety prompt is versioned as `carevero-ai-safety-v1`. If the provider
is absent, fails, times out, or returns an unsupported number/network assertion, Carevero uses its
localized deterministic formatter.

## Privacy, telemetry, audit, and retention

No account is required. The API requests procedure, location, payer/plan preference, and radius;
the UI should not solicit diagnosis, records, DOB, SSN, member IDs, or insurance-card images.
Telemetry records trace ID, task, locale, provider class, success/fallback, clarification state,
facility count, and latency—not prompt/conversation text. Current logs follow the platform log
retention policy. Before private-beta deployment, configure a maximum 30-day retention for these
metadata traces; do not persist conversation bodies. Structured context can be reproduced from
request filters and current deterministic data; chain-of-thought is never stored.

## Cost and abuse controls

- disabled-by-default master and sub-feature flags;
- 20 AI requests/IP/path/minute by default;
- 500 output tokens and 12-second provider timeout by default;
- 500-character user messages and bounded 25-facility contexts;
- no per-keystroke calls and no raw database dumps;
- deterministic fallback with no provider dependency.

Generic localized definitions are suitable for application caching later. Result-specific answers
must not be shared across users without a complete semantic cache key and freshness boundary.

## i18n and scale

Supported locales are `en`, `es`, `vi`, `zh-TW`, and `zh-CN`. Facility/payer/plan names and source
identifiers are preserved. The deterministic engine remains locale-agnostic. The architecture has
no NH-specific prompt branch: state and results are data, so MA and national growth uses bounded
retrieval rather than stuffing a national catalog into a prompt.

## API

- `POST /api/v1/ai/intent`: validated intent and clarification only.
- `POST /api/v1/ai/query`: interpret, retrieve through the existing comparison engine, and explain.
- `POST /api/v1/ai/explain`: follow-up over a validated current result context.

All return 404 while their feature flags are off. Existing deterministic endpoints are unchanged
and remain available if AI is disabled or unavailable.
