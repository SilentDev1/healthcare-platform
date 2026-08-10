# Phase 4.3 product architecture

## Current consumer boundary

Carevero's primary journey remains public and anonymous: search, results, comparison, facility detail, price explanation, quality, and source attribution require no account. Comparison selections are short-lived browser session state and are encoded into the comparison URL. The API returns consumer concepts rather than ingestion, parser, quarantine, or retry internals.

The current public domains remain distinct without being split into premature services:

- procedure catalog and consumer search;
- canonical facilities and physical service locations;
- publishable pricing and payer/plan labels;
- CMS quality observations;
- source attribution and freshness; and
- anonymous consumer comparison.

Public price responses remain traceable to normalized summaries and their source files. Local fixture sources are explicitly excluded from public price representations. Provider-managed or commercial data does not exist in this phase and therefore cannot overwrite collected transparency data.

## Preserved extension points

- **Optional consumer identity:** a future identity layer can persist the same facility, location, procedure, search, and comparison identifiers currently carried in anonymous state. Anonymous access must remain the default; account conversion should occur only when a user asks to save or receive alerts.
- **Organization identity:** future provider, employer, broker, and Carevero administration membership belongs in an organization/authorization domain separate from consumer preferences. No speculative user, role, membership, or permission tables are created now.
- **Provider supplements:** future verified descriptions, contacts, scheduling URLs, and service availability should use provenance-aware supplemental records. They must not mutate or masquerade as government or hospital MRF observations.
- **Commercial representations:** future Carevero Intelligence and licensed APIs should read normalized data through independent commercial schemas/endpoints, authentication, quotas, and contracts. Public and admin endpoints are not a commercial API substitute.
- **Organic versus sponsored:** current results are organic only. If sponsorship is introduced, it should be a separately labeled presentation type merged after organic ranking, never a ranking input or mutation of price, quality, confidence, provenance, or freshness.
- **Conversion actions:** future call, schedule, quote, save, and share actions can attach to the current facility-location and procedure identities. They should render only when a verified destination and real capability exist.
- **Savings:** any future savings figure must store or expose its deterministic comparison basis (selected facility, nearby maximum, or nearby median). Phase 4.3 displays actual published prices and makes no savings claim.

## Privacy and monetization guardrails

Phase 4.3 introduces no PHI, medical history, insurer TiC ingestion, authentication, RBAC, billing, Stripe, subscriptions, advertisements, lead forms, booking, provider portal, employer portal, or analytics product. Future consumer preferences should remain non-clinical unless a separately approved product and security design establishes a genuine need.

Carevero's core comparison experience remains free. Future B2B monetization must not weaken anonymous access, provenance, or organic-result independence.
