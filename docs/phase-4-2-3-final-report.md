# PHASE 4.2.3 — FINAL NH ACQUISITION REPORT

Generated: 2026-08-10. Scope: New Hampshire. Active consumer denominator: 26 acute-care
and critical-access hospitals; the two state psychiatric hospitals remain explicitly excluded.

## Outcome

| Metric                    | Phase 4.2.1 | Phase 4.2.2 | Phase 4.2.3 |
| ------------------------- | ----------: | ----------: | ----------: |
| Active consumer hospitals |          26 |          26 |          26 |
| Publishable hospitals     |           6 |          12 |          12 |
| Normalized records        |    361,000+ |   1,197,796 |   1,208,694 |
| Publishable summaries     |           — |       4,173 |       4,173 |

Phase 4.2.3 added three verified official sources. Exeter, Upper Connecticut Valley, and
Weeks were downloaded; Exeter and UCVH produced 10,898 additional normalized records.
The recovered records have not produced reviewed procedure mappings, so they do not yet
change the publishable denominator. Statewide catalog coverage is 48/50 procedures (96%),
but it is concentrated in a minority of hospitals and is not statewide facility coverage.

## Complete active-hospital matrix

| Hospital                          | CCN    | Classification               | Exact state/blocker                                                                                         |
| --------------------------------- | ------ | ---------------------------- | ----------------------------------------------------------------------------------------------------------- |
| Alice Peck Day Memorial Hospital  | 301305 | PUBLISHABLE                  | 7 publishable summaries                                                                                     |
| Androscoggin Valley Hospital      | 301310 | PUBLISHABLE                  | 5 publishable summaries                                                                                     |
| Catholic Medical Center           | 300034 | PUBLISHABLE                  | 2 publishable summaries                                                                                     |
| Cheshire Medical Center           | 300019 | PUBLISHABLE                  | 2 publishable summaries                                                                                     |
| Concord Hospital                  | 300001 | PUBLISHABLE                  | 624 publishable summaries                                                                                   |
| Concord Hospital–Franklin         | 301306 | PUBLISHABLE                  | 645 publishable summaries                                                                                   |
| Concord Hospital–Laconia          | 300005 | SOURCE_FOUND_DOWNLOAD_FAILED | Three discovered entries; none has a downloaded source file                                                 |
| Cottage Hospital                  | 301301 | SOURCE_NOT_FOUND             | Official page exposes old chargemaster/price-transparency content, but no current verified MRF was captured |
| Elliot Hospital                   | 300012 | SOURCE_FOUND_DOWNLOAD_FAILED | Stored source is the Southern NH landing page, not an MRF                                                   |
| Exeter Hospital                   | 300023 | PARSED_NOT_PUBLISHABLE       | Official BILH-linked CMS 3.0 JSON; 5,925 records, zero reviewed procedure mappings                          |
| Frisbie Memorial Hospital         | 300014 | PUBLISHABLE                  | 974 publishable summaries                                                                                   |
| Huggins Hospital                  | 301312 | SOURCE_FOUND_DOWNLOAD_FAILED | Stored URL is an HTML chargemaster landing page                                                             |
| Littleton Regional Healthcare     | 301302 | PARSED_NOT_PUBLISHABLE       | 20,586 legacy/CDM-dominant records; mapping score 0.74%                                                     |
| Mary Hitchcock Memorial Hospital  | 300003 | SOURCE_FOUND_DOWNLOAD_FAILED | Only fixture `file://` entries are stored; no production MRF assigned                                       |
| Memorial Hospital, The            | 301307 | PUBLISHABLE                  | 128 publishable summaries                                                                                   |
| Monadnock Community Hospital      | 301309 | SOURCE_NOT_FOUND             | Official site links a consumer estimator and insurer TiC directory, not an accepted hospital MRF            |
| New London Hospital               | 301304 | SOURCE_FOUND_DOWNLOAD_FAILED | Only fixture `file://` entries are stored; no production MRF assigned                                       |
| Parkland Medical Center           | 300017 | PUBLISHABLE                  | 866 publishable summaries                                                                                   |
| Portsmouth Regional Hospital      | 300029 | PUBLISHABLE                  | 853 publishable summaries                                                                                   |
| Southern NH Medical Center        | 300020 | SOURCE_FOUND_DOWNLOAD_FAILED | Stored URL is its HTML price-transparency landing page                                                      |
| Speare Memorial Hospital          | 301311 | SOURCE_FOUND_DOWNLOAD_FAILED | Stored URL is an unrelated 340B article, not an MRF                                                         |
| St Joseph Hospital                | 300011 | PUBLISHABLE                  | 23 publishable summaries                                                                                    |
| Upper Connecticut Valley Hospital | 301300 | PARSED_NOT_PUBLISHABLE       | Official CMS 3.0 CSV; 4,973 records, zero reviewed procedure mappings                                       |
| Valley Regional Hospital          | 301308 | SOURCE_NOT_FOUND             | No verified current MRF captured from the official/Dartmouth system pages                                   |
| Weeks Medical Center              | 301303 | DOWNLOADED_NOT_PARSED        | Official CMS 3.0 CSV downloaded; the latest database attempt still has zero records                         |
| Wentworth-Douglass Hospital       | 300018 | PUBLISHABLE                  | 44 publishable summaries                                                                                    |

Hampstead Hospital (CCN 304001) and New Hampshire Hospital (CCN 304000) are excluded
psychiatric facilities and are not part of the 26-hospital consumer denominator.

## Acquisition and parser recovery

- Added a state-independent verified-source registry keyed by exact CCN, with official source
  page, MRF URL, system/vendor, format, and human-readable evidence.
- Added the official-page-linked North Country CSVs for UCVH and Weeks. Both vendor objects
  advertised byte ranges, CSV MIME types, and `Last-Modified: 2026-07-28`.
- Added BILH's official Exeter JSON (`last_updated_on: 2026-04-01`). Python/OpenSSL rejected
  the origin's unsafe legacy renegotiation; the system TLS client retrieved it without weakening
  application TLS policy, after which the normal bounded checksum/local registration path was used.
- Extended generic discovery to accept two authorized hospital-transparency vendor domains.
- Fixed CMS 3.0 CSV metadata/header handling for spaces around pipe-delimited column names.
- Added deterministic selection of source-labeled CPT/HCPCS/MS-DRG/APC codes from CMS code
  slots before falling back to facility CDM. No fuzzy description mapping was introduced.
- Fixed restart cleanup ordering so import-run provenance observations are removed before their
  referenced import run. PostgreSQL prevented the unsafe ordering before any partial cleanup committed.

Downloads remain streaming and bounded-memory with incremental SHA-256, temporary `.part` files,
atomic completion, timeouts, retries, Range resumability, archive expansion limits, and configurable
safety ceilings. The recovered files were 1,070,965 bytes (UCVH), 7,583,354 bytes (Weeks), and
6,494,980 bytes (Exeter).

## Consumer procedure and mapping blockers

The catalog has statewide prices for 48/50 procedures (96%). Facility coverage remains uneven:
Frisbie, Memorial, Parkland, and Portsmouth each cover 48/50; Concord and Franklin cover 28/50;
St Joseph covers 23/50; Wentworth-Douglass covers 19/50; the small publishable facilities cover
1–4 procedures each. The recovered facilities currently cover 0/50 publicly.

The principal remaining publication opportunity is source-explicit multi-code evidence in Exeter,
UCVH, and Weeks: rows place CDM/revenue codes beside CPT/HCPCS. The parser now selects recognized
standard codes deterministically, but the database still needs a successful mapping/projection pass
and review before publication. Littleton remains a facility-specific CDM blocker. No fuzzy mapping,
cross-facility CDM leakage, or unreviewed public mapping was used.

## Multi-state readiness

All new behavior is state-independent. The registry assigns sources by CCN, discovery recognizes
generic verified vendors, parser selection depends on CMS schema/code labels, and facility-specific
identity remains isolated. State is only an operational scope filter.

## Verification and safety

- PostgreSQL integrity: enforced during recovery; no active import jobs at final reconciliation.
- Migration: `0007 (head)`.
- Ruff: passed after formatting changed files.
- Targeted pytest: 13 downloader/parser tests passed; 18 parser/pipeline tests passed earlier in recovery.
- npm audit: 0 vulnerabilities.
- Secret scan and `git diff --check`: passed.
- Strict mypy, full pytest+coverage, complete ESLint/Prettier/TypeScript/Vitest, and web/admin
  production builds did not produce completion markers in the local run; processes were terminated
  under local resource pressure and must be rerun before release.
- Safety assertions: PHI 0; AI-modified prices 0; automatic fuzzy facility merges 0; public
  unreviewed mappings 0; negative public prices 0; insurer TiC ingestion 0; cloud deployments 0.

## Decision

NH is at 12/26 publishable hospitals, below the 18/26 threshold. Do not begin Phase 4.3 yet.
The smallest high-yield next effort is: (1) complete reviewed mapping/projection for the three newly
recovered CMS 3.0 facilities; (2) enumerate the Dartmouth system directory for Mary Hitchcock,
New London, and Valley Regional by CCN/NPI; and (3) resolve the SolutionHealth vendor sessions for
Elliot and Southern NH. Those eight facilities are the shortest plausible path from 12 to at least 18.
