# Carevero AI Safety Contract

## Allowed assertions

The assistant may restate or explain a value only when the current `CareveroAIContext` supplies it:
facility identity/location, published cash or insurance price, deterministic distance, CMS rating,
billing component/setting, comparability state, deterministic published-price difference,
freshness, and provenance. It may translate explanatory prose while preserving proper names,
codes, and source identifiers.

## Prohibited assertions

The assistant must not invent or override a price, facility, payer, plan, distance, rating,
availability, billing component, comparison, price difference, or source. It must not claim that a
hospital is best, accepts insurance, is in-network, covers a service, or guarantees savings/final
cost unless a future distinct authoritative evidence layer explicitly supplies that fact.

## Price and savings truth

Hospital MRF observations and Carevero's publication gates own price truth. The Phase 4.8 engine
owns comparability and differences. Only an exact single published cash price in the same canonical
procedure, compatible setting, and complete billing scope may participate. Partial/unknown/range
prices remain visible but never become a savings statement. Preferred wording is “published-price
difference”; personal savings are never promised.

## Insurance and coverage truth

`published_rate_exists`, future `network_participation_verified`, and `coverage_unknown` are
separate evidence states. Phase 4.9 only knows published-price association. Required caveat: the
published association does not confirm the specific plan is in-network or the service is covered.

## Medical advice boundary

Carevero compares pricing and explains data. It does not diagnose, triage, choose a procedure, or
recommend treatment. It may ask whether an order specifies contrast, screening/diagnostic, body
area, or delivery type. If asked what care to get, it directs the user to the clinician/order.

## Missing data and availability

Missing remains missing. “No published price found” never becomes “service unavailable.” Unless
separately verified, service availability is `unknown`. No model-generated gap filling is allowed.

## Grounding and prompt injection

The versioned system prompt defines structured Carevero data as the sole factual authority and
marks all source strings as untrusted data. Provider text is rejected if it introduces dollar or
mileage values absent from context or makes prohibited network/coverage/best-hospital claims.
Rejected output, provider error, timeout, or rate limiting uses a deterministic localized fallback.

## Privacy and security

Do not request diagnoses, records, DOB, SSN, member ID, full insurance cards, or unrelated PHI.
Do not log prompts or conversation text. API secrets come only from secure runtime configuration,
are never sent back to clients, and are not logged. The assistant has no arbitrary SQL, admin,
write, import, browser, URL-fetch, payment, email, booking, or account tool.

## Operational response

Keep all AI flags off by default. If a grounding or safety regression appears, disable
`AI_EXPLANATIONS_ENABLED` while leaving deterministic search/pricing available. If intent parsing
is affected, also disable `AI_INTENT_SEARCH_ENABLED`; the normal Carevero search remains the
fallback.
