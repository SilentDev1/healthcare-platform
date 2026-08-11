# Insurance and network evidence model

Carevero keeps four claims separate:

1. **Published negotiated rate:** a hospital MRF contains a payer/plan rate.
2. **Network participation:** an official plan/network source identifies the facility as
   participating at an observed time.
3. **Service coverage:** plan benefits and conditions cover a service in a particular situation.
4. **Patient responsibility:** a member-specific amount after benefits, deductible, copay,
   coinsurance, authorization, and claim processing.

Phase 4.7 supports the first claim and builds evidence storage for the second. It does not infer the
second from the first and does not implement the third or fourth.

## Domain model

- `PayerEntity`: canonical organization/brand with source aliases.
- `InsurancePlanEntity`: payer-specific product. A payer brand is not a universal network.
- `InsuranceNetworkEntity`: named contracted network, independently addressable from plan product.
- `ProviderDirectorySource`: versioned official URL/type, payer/plan/network scope, state scope,
  retrieval/effective dates, checksum, access characteristics, and freshness policy.
- `NetworkParticipationObservation`: historical source assertion for one plan/network and one
  facility/location, including match evidence, source and normalized evidence, confidence, review,
  effective/observed/expiry dates, and state.

No observation is overwritten silently. National identity models have optional source state scope;
observations carry explicit state so NH and future states cannot leak into each other.

## Status and publication rules

Supported evidence states are `IN_NETWORK_VERIFIED`, `OUT_OF_NETWORK_VERIFIED`,
`NETWORK_STATUS_UNKNOWN`, `DIRECTORY_LISTED`, `DIRECTORY_NOT_LISTED`,
`STALE_DIRECTORY_DATA`, and `CONFLICT_REVIEW_REQUIRED`.

Absence is not out-of-network unless the official source explicitly defines complete negative
semantics. Conflicting official observations resolve conservatively to review-required and public
unknown. Plan/network scope is mandatory wherever the source supplies it. Stale observations cannot
be presented as guaranteed current.

Only approved, fresh, unambiguous official observations may later support public “Verified
in-network for [specific plan]” language. Until such data is imported, the UI continues to say
“Published negotiated rate available” and “Network status not verified,” with “Confirm with your
insurer before scheduling.”

## Matching policy

Strong identifiers (NPI, CCN where applicable, and official organization IDs) are evaluated before
address, phone, or name evidence. A unique strong-identifier match may link a facility/location.
Fuzzy name alone never auto-links; ambiguous and unmatched records require review. Multi-location
systems must resolve the physical location rather than inheriting a parent hospital's status.

## Connector boundary

`ProviderDirectoryConnector` defines `discover`, `fetch`, `normalize`, `match_facility`, and
`record_observation`. Payer-specific adapters belong behind this boundary only after official source
terms, plan semantics, identifiers, and update behavior are understood. It prevents the public API
from depending on payer-specific payloads.

The audit command checks source freshness, plan/facility identity, conflicts, ambiguous matches, and
missing provenance:

```bash
python -m scripts.audit_network_participation --state NH
```

## Future boundaries

Insurer Transparency in Coverage data may later complement hospital MRF rates and directory network
evidence, but it is not network proof by itself. Eligibility, benefits, member IDs, date of birth,
deductibles, authorization, and patient responsibility remain outside this phase. No PHI is stored.
