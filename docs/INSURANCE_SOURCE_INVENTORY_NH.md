# New Hampshire official insurance-source inventory

Research checked 2026-08-11. This is a feasibility inventory, not imported network evidence. No
facility is marked in-network from these links alone.

| Payer/source                         | Official directory evidence                                                                                                                                                                                                                                    | Machine/API access                                                                                                                                   | Phase 4.7 assessment                                                                                                                    |
| ------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------- |
| Anthem Blue Cross and Blue Shield NH | [Anthem Find Care](https://www.anthem.com/find-care/?cnslocale=en_US_nh) supports NH and describes plan-participating doctors/hospitals.                                                                                                                       | Public interactive directory; no stable documented bulk/API endpoint confirmed in this review.                                                       | Feasible interactive plan-specific verification; connector requires terms and endpoint review.                                          |
| Harvard Pilgrim Health Care          | [2026 NH plan offerings](https://www.harvardpilgrim.org/enroll/new-hampshire-individual-and-family-plans/new-hampshire-plan-offerings) identifies the NH Local Choice HMO network and official directory dependency. Official plan PDF directories also exist. | Public web/PDF; no general documented machine API confirmed.                                                                                         | Feasible per named plan/network, with version/date capture; PDF can become stale.                                                       |
| UnitedHealthcare                     | Official UHC member/guest provider search is the preferred source.                                                                                                                                                                                             | Public interactive search varies by product; no stable general bulk endpoint confirmed.                                                              | Requires product/network selection and endpoint/terms review before automation.                                                         |
| Aetna                                | [Aetna Find a Doctor](https://www.aetna.com/individuals-families/find-a-doctor.html) permits guest plan selection; Aetna warns users to confirm participation because directories change.                                                                      | Public interactive directory; some product-specific directories/PDFs, no stable general bulk endpoint confirmed.                                     | Feasible plan-specific verification; freshness and plan identity are mandatory. Automated copying may be restricted by directory terms. |
| Cigna Healthcare                     | Official Cigna provider directory/search is the preferred source.                                                                                                                                                                                              | Public interactive product search; no stable general bulk endpoint confirmed.                                                                        | Requires named product/network and terms review before connector work.                                                                  |
| NH Healthy Families / Ambetter       | [NH Healthy Families member directory](https://www.nhhealthyfamilies.com/members.html) links an official network provider search; Medicaid and Marketplace/Ambetter are distinct products.                                                                     | Public interactive directory. CMS rules require applicable Medicaid managed-care public Provider Directory APIs; endpoint discovery remains pending. | High-priority connector candidate after discovering the official API capability statement and plan IDs.                                 |
| NH Medicaid fee-for-service          | NH DHHS directs users to the NH MMIS “Find a Healthcare Provider” search and separately identifies Medicaid MCOs.                                                                                                                                              | Public search; machine endpoint not confirmed.                                                                                                       | Treat fee-for-service enrollment separately from each MCO network.                                                                      |
| Medicare Advantage organizations     | [CMS Provider Directory API guidance](https://www.cms.gov/priorities/burden-reduction/overview/interoperability/frequently-asked-questions/provider-directory-api) requires public contracted-provider APIs; CMS points to PDex Plan-Net.                      | Public API, though app registration/API keys may be required. CMS CY2026 guidance supports FHIR or machine-readable JSON approaches.                 | Best standards-based path; observations must include contract/plan/segment and source version.                                          |
| Marketplace QHP issuers              | CMS notes FFE QHP provider directories use a specified machine-readable format; [CMS Marketplace API](https://developer.cms.gov/public-apis/) offers plan/provider data with a requested API token.                                                            | Machine-readable/API; API key and rate limits.                                                                                                       | Promising for plan catalog and directory evidence; validate issuer update semantics and identifiers.                                    |

## Current Carevero payer data

Carevero's hospital-MRF payer aliases and plan strings remain pricing provenance. They indicate only
that a hospital published a negotiated rate for that payer/plan text. The production audit report
records observed negotiated-rate payer coverage; it does not relabel those observations as accepted,
covered, or in-network.

The live public payer endpoint reported these published-summary counts on 2026-08-11: Anthem Blue
Cross and Blue Shield 2,311; Aetna 1,035; Harvard Pilgrim 960; Tufts Health Plan 871; Cigna 668;
Medicaid 167; Medicare 150; UnitedHealthcare 132; Ambetter 46; and Other/unknown 29. These are
negotiated-rate summary coverage counts, not network-participation counts. Source aliases and plan
names remain in normalized pricing provenance; the 50-item golden sample demonstrates examples such
as Anthem PPO/HMO/FEP, Harvard Pilgrim HMO/Individual, Cigna HMO, Tufts PPO, Aetna, Medicaid, and
UnitedHealthcare.

## Source priority and next work

Use official insurer/plan directories first, then official CMS/payer APIs or official files. A future
verified provider submission is supplemental and separately attributed. Search-engine results,
reviews, and third-party directories are not evidence sources.

Before implementing the first connector: inventory canonical Carevero payer aliases against exact
plan/network identifiers, confirm source terms and update cadence, save capability metadata and
checksum/version evidence, test NPI/CCN/location matching, and route ambiguity or disagreement to
review. Do not start insurer Transparency in Coverage ingestion in this phase.
