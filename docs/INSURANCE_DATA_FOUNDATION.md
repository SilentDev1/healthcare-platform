# Insurance Data Foundation — findings & what "show me my insurance" requires

The next consumer feature ("I have Blue Cross — show me prices relevant to my
insurance") depends on keeping three things **distinct and truthful**. This
documents the current data model, what is safe to say today, and what
authoritative data is still required.

## 1. Three concepts Carevero must never conflate

| Concept | Meaning | Source Carevero has |
|---|---|---|
| **Published negotiated price** | A rate a hospital listed for a payer/plan in its transparency file | ✅ hospital MRFs (present) |
| **Network participation** | Whether a specific plan considers this provider in-network | ⚠️ official provider directories (foundation present, data sparse) |
| **Coverage / benefits** | Whether *your* plan covers *this* service for *you* | ❌ requires member-specific benefits (out of scope) |

A hospital publishing a negotiated rate for "Blue Cross" proves **only** that a
rate was published. It does **not** prove the user's specific plan is in-network,
nor that the service is covered.

## 2. What already exists (good news)

- **Pricing side:** `PayerEntity` / `PayerAlias`, `InsurancePlanEntity` /
  `InsurancePlanAlias`, and price summaries carry `payer_entity_id` /
  `insurance_plan_entity_id`. The consumer UI already says
  "Published insurance prices" / "N companies publish rates" and **never**
  "insurance accepted / covered / in-network" (enforced by the i18n truthfulness
  guard and the consumer-language glossary).
- **Network side (migration 0009, `packages/network_foundation.py`):** a proper,
  conservative foundation already exists and is separate from pricing:
  - `InsuranceNetworkEntity` (network ≠ payer brand ≠ plan product).
  - `ProviderDirectorySource` (versioned official directory metadata, freshness).
  - `NetworkParticipationObservation` (historical, plan/network-specific evidence
    with `confidence`, `review_status`, `expires_at` — *never an inferred claim*).
  - `match_facility_by_identifiers()` matches on **unique strong identifiers**
    (NPI/CCN/org id) only; names/addresses stay review evidence.
  - `conservative_network_status()` + `freshness_status()` collapse to
    `NETWORK_STATUS_UNKNOWN` / `STALE_DIRECTORY_DATA` unless evidence is strong
    and fresh.

**So the architecture already forbids fabricated network claims.** What is
missing is authoritative *data*, not schema.

## 3. What "show me Blue Cross prices" can truthfully do TODAY

Using only published MRF rates (already shipped in the comparison endpoint):

- Filter/annotate results by the **published** payer/plan the user selected.
- Say "Blue Cross has published rates at N of M hospitals for this procedure"
  and show those published amounts, with the standing disclaimer that a published
  rate does not confirm network status or coverage.
- Never render a green "in-network ✓". Never imply coverage.

This is a real, useful, honest feature and needs **no** new data.

## 4. What true network-status claims would require (future, gated)

To show "your plan is in-network here" Carevero needs authoritative inputs:

1. **Payer provider directories** — CMS requires machine-readable provider
   directories; ingest per payer/plan into `ProviderDirectorySource` +
   `NetworkParticipationObservation`. Strong-identifier match only; freshness and
   confidence gate the claim; conflicts → `CONFLICT_REVIEW_REQUIRED`.
2. **Plan identity resolution** — the user's *specific* plan (not just "Blue
   Cross"): product line, network, metal tier. `InsurancePlanEntity` supports
   this; a consumer plan picker + reviewed plan mapping is needed.
3. **Freshness policy** — directories go stale fast; `freshness_days` + `expires_at`
   must down-rank/suppress stale evidence to `STALE_DIRECTORY_DATA`.
4. **Coverage/benefits** — genuinely member-specific (deductible, prior auth,
   medical necessity). This is **not** a Carevero claim; always defer to the
   insurer. Keep the existing "confirm benefits with your insurer" language.

## 5. Rules (unchanged, reaffirmed)

- Published rate ≠ accepted ≠ covered ≠ in-network.
- No `Insurance accepted ✓` without fresh, strong, reviewed directory evidence.
- Prefer "published insurance prices" / "{payer} has published rates here".
- Network status, when ever shown, is an *observation with a date and source*,
  never an inference, and degrades safely to UNKNOWN.

## 6. Recommended sequence

1. Ship the honest "filter by published payer/plan" consumer feature (data ready).
2. Add a consumer plan picker + reviewed plan mapping (identity only).
3. Pilot one payer's provider directory into the existing network tables (NH),
   surface a conservative, dated "listed in {payer} directory (as of …)" chip —
   distinct from price and from coverage.
4. Expand payer directories with MA; keep the same conservative semantics.
