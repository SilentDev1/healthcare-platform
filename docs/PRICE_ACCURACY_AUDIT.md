# Price accuracy audit

Audit date: 2026-08-11  
Audit version: 4.7.0  
Scope: Carevero private-beta public NH observations; read-only; seed 4700

## Production result

| Measure                                     |         Result |
| ------------------------------------------- | -------------: |
| Public candidate observations               |         86,867 |
| Audited observations                        |            100 |
| Canonical facilities                        |              9 |
| Physical locations                          |             12 |
| Procedures                                  |             34 |
| Published cash observations                 |             13 |
| Payer-negotiated observations               |             33 |
| Exact source-value matches                  | 100/100 (100%) |
| Semantic matches                            | 100/100 (100%) |
| Bounded provenance matches                  | 100/100 (100%) |
| Full archived-source/checksum verifications |          0/100 |
| Value, semantic, or mapping mismatches      |              0 |
| Suppressed because of this audit            |              0 |
| Unresolved audited records                  |              0 |

Only nine canonical hospitals had qualifying public observation-level records in the live query, so
the target of ten hospitals was not attainable without weakening the public-only scope. The sample
still covers 12 physical locations, including Portsmouth Regional Hospital, Dover Emergency Room,
Seabrook Emergency Room, Parkland Medical Center, and Plaistow Emergency Room. It also spans cash,
payer-negotiated, gross, deidentified minimum/maximum, imaging, lab, surgery, emergency, maternity,
and outpatient services, with small and large values and multiple payer/plan strings.

All audited direct observations exactly equaled their normalized source numeric columns and passed
procedure mapping, facility/location, payer/plan, setting, price-type, publication, and provenance
checks. The 50-item reviewed factual sample is stored at
`data/verification/price_golden_sample.json`.

The production archive mount did not reconstruct a complete raw file for the sampled historical
source versions, so results are honestly classified `PROVENANCE_VERIFIED`, not
`FULL_SOURCE_VERIFIED`. Verification used immutable source URL/checksum metadata, record locators,
payload hashes, bounded source payloads, parser versions, exact normalized columns, reviewed/exact
procedure mappings, and source-location associations. This is a source-retention limitation, not a
value mismatch; a future archive backfill should make historical raw versions available by checksum.

No price was modified to make the audit pass. Full-source verification always requires a matching
archived SHA-256; bounded provenance verification is reported separately and is never represented as
a raw-file row recheck.
