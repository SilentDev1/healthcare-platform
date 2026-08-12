# Carevero Consumer Language Glossary

Carevero is for ordinary patients and families — not billing specialists. Use
the **consumer term** in visible UI; the technical term may appear as secondary
progressive-disclosure detail. Every consumer string must go through i18n
(`apps/web/lib/i18n.ts`), never hardcoded English. This glossary is the source of
truth for future UI and AI copy.

| Technical / internal term | Consumer-facing term | Plain-language explanation |
|---|---|---|
| discounted cash price | Cash price | The price if you pay yourself, without insurance. |
| negotiated / normalized payer rate | Published insurance price | A price the hospital published for an insurer. Does **not** confirm coverage or network. |
| payer | Insurer / insurance | — |
| service setting | Where care is given | Hospital outpatient, hospital inpatient, emergency department, doctor's office. |
| included_component_scope = facility | Hospital/facility charge | The hospital's charge for the service. |
| included_component_scope = professional | Doctor or professional charge | A separate charge for the physician's work (e.g. reading a scan). |
| included_component_scope = technical | Equipment/technical charge | The equipment/technical portion. |
| included_component_scope = global/combined | Combined price | A single price that already includes facility and professional parts. |
| included_component_scope = unknown | Not specified | "What this price covers was not specified in the hospital's published data." |
| comparability = directly_comparable | — | Prices can be compared fairly. |
| comparability = not_comparable / partially | These prices can't be compared fairly | They may cover different parts of your care or different types of visits. |
| published_price_difference | Published price difference | Difference between comparable published cash prices — not a guarantee of your cost. |
| gross charge | List price | The hospital's full list price before any discount. |
| machine-readable file / MRF | Hospital's published price file | The official price file hospitals must publish. |
| CPT / HCPCS / DRG / revenue code | Billing code | Shown only in expandable technical detail. |
| publishable summary | Published price | — |
| no normalized payer rates published | We couldn't find a published insurance price for this service. | — |
| cash price unavailable | Cash price not available | "We haven't found a published cash price for this service at this location." |

## Non-negotiable truthfulness rules

- Never turn "insurer appears in published rate data" into "Insurance accepted"
  or "Your insurance covers this." Say: *"This insurer appears in the hospital's
  published price data. This does not confirm the hospital is in your network or
  that your plan will cover this service."*
- Never present a price difference as guaranteed personal savings.
- When data is unknown, show the uncertainty; never invent a component or label.

## Status of adoption

Implemented so far: hero, nav, footer, popular searches, distance/savings, filter
labels, coverage notice, and the billing-component comparability copy are in
i18n. **Remaining (tracked):** several components still contain hardcoded English
(notably `CareSearch`, parts of `ui.tsx`, `CompareSelect` panel labels, and
procedure/hospital detail pages). Completing the site-wide sweep is the next
Phase 4.8 i18n task.
