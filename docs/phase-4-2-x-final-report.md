# Phase 4.2.x final data report

Verified against local PostgreSQL on 2026-08-10. The active NH consumer denominator is 26;
the two psychiatric/state facilities remain canonical but excluded. Final readiness is 69.2%.

## Facility, location, and provenance model

A `Facility` is the canonical CMS-certified billing entity. A `FacilityLocation` is a physical
campus or freestanding service location. A `FacilityPriceSource` belongs to the canonical
facility and, only when deterministic evidence exists, a physical location. Observations retain
source and location provenance. Public summaries group by facility, location, procedure, payer,
plan, service setting, and component scope; source file is provenance, not consumer identity.
The summary/source junction retains every contributing file.

Portsmouth's official files map to Portsmouth, Dover, and Seabrook. Parkland's official files map
to Derry and Plaistow. Address suffix normalization prevents duplicate physical locations. All
four source-pair analyses are `DISTINCT_LOCATION_OVERLAPPING_SCHEDULE`; source-file checksums are
distinct. Public grouping produces one row per consumer identity per location, with no duplicate
rows caused only by overlapping source files.

System-propagated source URLs are reconciled only when the complete normalized facility name is
present in the filename. This corrected 97,817 Laconia records previously attached to Franklin.
Laconia remains blocked because its local CDM codes have no reviewed procedure mapping.

## NH hospital matrix

| Hospital (CCN)                      | Source/download/parse | Records | Published summaries | Primary blocker                                |
| ----------------------------------- | --------------------: | ------: | ------------------: | ---------------------------------------------- |
| Alice Peck Day (301305)             |           yes/yes/yes |     yes |                   7 | —                                              |
| Androscoggin Valley (301310)        |           yes/yes/yes |     yes |                   5 | —                                              |
| Catholic Medical Center (300034)    |           yes/yes/yes |     yes |                   2 | —                                              |
| Cheshire Medical Center (300019)    |           yes/yes/yes |     yes |                   2 | —                                              |
| Concord Hospital (300001)           |           yes/yes/yes | 104,116 |                 887 | —                                              |
| Concord–Franklin (301306)           |           yes/yes/yes |  81,621 |                 645 | —                                              |
| Concord–Laconia (300005)            |           yes/yes/yes |  97,817 |                   0 | `NO_STANDARD_CODE`; `UNREVIEWED_MAPPING`       |
| Cottage Hospital (301301)           |              no/no/no |       0 |                   0 | `NO_SOURCE`                                    |
| Elliot Hospital (300012)            |             yes/no/no |       0 |                   0 | `DOWNLOAD_FAILED` (HTML landing page)          |
| Exeter Hospital (300023)            |           yes/yes/yes |     yes |                   3 | —                                              |
| Frisbie Memorial (300014)           |           yes/yes/yes |     yes |                 974 | —                                              |
| Huggins Hospital (301312)           |             yes/no/no |       0 |                   0 | `DOWNLOAD_FAILED` (HTML page)                  |
| Littleton Regional (301302)         |           yes/yes/yes |  20,586 |                   0 | `UNSUPPORTED_SCHEMA`; `NO_STANDARD_CODE`       |
| Mary Hitchcock Memorial (300003)    |  candidate only/no/no |       0 |                   0 | `DOWNLOAD_FAILED`; fixture candidates rejected |
| Memorial Hospital, The (301307)     |           yes/yes/yes |     yes |                 128 | —                                              |
| Monadnock Community (301309)        |              no/no/no |       0 |                   0 | `NO_SOURCE`                                    |
| New London Hospital (301304)        |  candidate only/no/no |       0 |                   0 | `DOWNLOAD_FAILED`; fixture candidates rejected |
| Parkland Medical Center (300017)    |           yes/yes/yes | 287,852 |               1,732 | —; Derry + Plaistow verified                   |
| Portsmouth Regional (300029)        |           yes/yes/yes | 516,465 |               2,559 | —; Portsmouth + Dover + Seabrook verified      |
| Southern NH Medical Center (300020) |             yes/no/no |       0 |                   0 | `DOWNLOAD_FAILED` (HTML landing page)          |
| Speare Memorial (301311)            |             yes/no/no |       0 |                   0 | `DOWNLOAD_FAILED` (non-MRF article)            |
| St Joseph Hospital (300011)         |           yes/yes/yes |     yes |                  23 | —                                              |
| Upper Connecticut Valley (301300)   |           yes/yes/yes |     yes |                  34 | —                                              |
| Valley Regional (301308)            |              no/no/no |       0 |                   0 | `NO_SOURCE`                                    |
| Weeks Medical Center (301303)       |           yes/yes/yes |     yes |                  32 | —                                              |
| Wentworth-Douglass (300018)         |           yes/yes/yes |     yes |                  44 | —                                              |

Totals: 23 discovered, 31/44 active source associations downloaded, 17 facilities parsed,
15/26 publishable, 1,729,684 normalized records, 115,552 observations, 7,077 publishable
summaries, and average pricing health 56.43. Catalog coverage is 48/50; only vaginal and
Cesarean delivery have no publishable result.

## Procedure coverage

Counts are publishable facilities / physical locations; cash and negotiated are facility counts.

| Procedure                     | Facilities/locations | Cash | Negotiated |
| ----------------------------- | -------------------: | ---: | ---------: |
| Abdominal ultrasound          |                10/13 |   10 |          5 |
| Allergy testing               |                  4/7 |    0 |          3 |
| Annual wellness visit         |                  5/8 |    0 |          3 |
| Basic metabolic panel         |                10/13 |   10 |          5 |
| Bone density scan             |                10/13 |   10 |          5 |
| COVID-19 diagnostic test      |                  4/7 |    4 |          3 |
| CT abdomen/pelvis             |                  6/9 |    6 |          4 |
| CT chest                      |                 8/11 |    8 |          5 |
| Cardiac catheterization       |                 7/10 |    2 |          5 |
| Cardiac stress test           |                 9/12 |    9 |          5 |
| Carpal tunnel release         |                  4/7 |    0 |          3 |
| Cataract surgery              |                  6/9 |    2 |          5 |
| Cervical cancer screening     |                 9/12 |    7 |          5 |
| Cesarean delivery             |                  0/0 |    0 |          0 |
| Chest X-ray                   |                11/14 |   11 |          6 |
| Cholesterol/lipid panel       |                10/13 |   10 |          5 |
| Colonoscopy                   |                  6/9 |    2 |          4 |
| Complete blood count          |                 8/11 |    5 |          5 |
| Comprehensive metabolic panel |                 7/10 |    7 |          3 |
| Diagnostic mammogram          |                  5/8 |    5 |          3 |
| Dialysis session              |                 9/12 |    7 |          5 |
| Echocardiogram                |                 9/12 |    9 |          5 |
| Electrocardiogram             |                10/13 |   10 |          5 |
| ED level 1                    |                  5/8 |    5 |          3 |
| ED level 2                    |                  5/8 |    5 |          3 |
| ED level 3                    |                  5/8 |    5 |          3 |
| ED level 4                    |                  5/8 |    5 |          3 |
| ED level 5                    |                  5/8 |    5 |          3 |
| Flu vaccination               |                 9/12 |    8 |          5 |
| Gallbladder removal           |                 8/11 |    3 |          5 |
| Hemoglobin A1C                |                 7/10 |    7 |          5 |
| Hernia repair                 |                  4/7 |    0 |          3 |
| Hip replacement               |                 9/12 |    4 |          5 |
| Knee replacement              |                 7/10 |    3 |          5 |
| MRI brain                     |                11/14 |   11 |          6 |
| MRI knee                      |                 8/11 |    8 |          6 |
| MRI lumbar                    |                  6/9 |    6 |          4 |
| Sleep study                   |                 8/11 |    7 |          5 |
| Pelvic ultrasound             |                  6/9 |    6 |          3 |
| Physical therapy evaluation   |                  6/9 |    6 |          3 |
| Pregnancy test                |                 9/12 |    9 |          5 |
| Rotator cuff repair           |                  4/7 |    0 |          3 |
| Screening mammogram           |                 8/11 |    8 |          6 |
| Strep test                    |                  4/7 |    4 |          3 |
| Surgical pathology            |                 9/12 |    9 |          5 |
| TSH test                      |                10/13 |   10 |          5 |
| Upper endoscopy               |                 9/12 |    7 |          5 |
| Urgent care visit             |                  5/8 |    5 |          3 |
| Urinalysis                    |                10/13 |   10 |          5 |
| Vaginal delivery              |                  0/0 |    0 |          0 |

## Stopping decision and national readiness

The 18/26 target is not defensibly reachable in this pass. The remaining gap requires verified
direct MRF URLs/vendor flows or facility-specific reviewed CDM crosswalks. Stored landing pages,
articles, and fixture URLs are not accepted as MRFs, and no fuzzy mapping was promoted.

Massachusetts ingestion requires no core architecture change: use the generic state pipeline,
inventory/configuration, discovery, and reviewed mapping inputs. State-scoped synthetic MA/ME
tests remain part of the suite. Consumer product development should wait for a small targeted
official-source/vendor pass if 18/26 remains a hard gate.
