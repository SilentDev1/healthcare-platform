# Massachusetts Hospital MRF Acquisition Matrix — Phase 2

All 53 operating MA hospitals accounted for. Each `MRF_FOUND` URL was HEAD/range-verified during
discovery against the **official** hospital or health-system price-transparency page (no third-party
pricing substituted; aggregators used only to locate official URLs). This records **where** to fetch
each hospital's machine-readable standard-charges file — **not prices, nothing published**.

**Status:** {'MRF_FOUND': 51, 'SOURCE_BLOCKED': 2}  ·  **Formats (found):** {'csv': 19, 'json': 14, 'unknown': 3, 'zip': 15}  ·  retrieved 2026-08-18

## Format reuse

Every format maps to the existing NH pipeline: ZIP → `streaming.ZipMemberSource`, CSV/JSON(CMS HPT 3.0)/XML → `parsers.py`. Shared national `ProcedureCodeMapping` catalog → **no new MA procedure mappings**. No hospital-specific parsers.

## By health system

### Baystate Health (4)

| CCN | Hospital | Region | Format | Status | MRF host |
|---|---|---|---|---|---|
| 220016 | Baystate Franklin Medical Center | Pioneer Valley | csv | MRF_FOUND | baystatehealth.canto.com |
| 220030 | Baystate Wing Hospital | Pioneer Valley | csv | MRF_FOUND | baystatehealth.canto.com |
| 220065 | Baystate Noble Hospital | Pioneer Valley | csv | MRF_FOUND | baystatehealth.canto.com |
| 220077 | Baystate Medical Center | Pioneer Valley | csv | MRF_FOUND | baystatehealth.canto.com |

### Berkshire Health Systems (3)

| CCN | Hospital | Region | Format | Status | MRF host |
|---|---|---|---|---|---|
| 220046 | Berkshire Medical Center | Berkshires | csv | MRF_FOUND | bhs-publicdownload.s3.us-east-1.amazonaws.com |
| 221302 | Fairview Hospital | Berkshires | csv | MRF_FOUND | bhs-publicdownload.s3.us-east-1.amazonaws.com |
| 221304 | North Adams Regional Hospital | Berkshires | csv | MRF_FOUND | bhs-publicdownload.s3.us-east-1.amazonaws.com |

### Beth Israel Lahey Health (9)

| CCN | Hospital | Region | Format | Status | MRF host |
|---|---|---|---|---|---|
| 220002 | Mount Auburn Hospital | Greater Boston | json | MRF_FOUND | mountauburnhospital.org |
| 220029 | Anna Jaques Hospital | North Shore | json | MRF_FOUND | ajh.org |
| 220033 | Northeast Hospital Corporation (Beverly Hospital) | North Shore | json | MRF_FOUND | beverlyhospital.org |
| 220060 | Beth Israel Deaconess Hospital - Plymouth | South Shore | json | MRF_FOUND | bidplymouth.org |
| 220083 | Beth Israel Deaconess Hospital - Needham | Greater Boston | json | MRF_FOUND | bidneedham.org |
| 220086 | Beth Israel Deaconess Medical Center | Greater Boston | json | MRF_FOUND | bidmc.org |
| 220105 | Winchester Hospital | Greater Boston | json | MRF_FOUND | winchesterhospital.org |
| 220108 | Beth Israel Deaconess Hospital - Milton | Greater Boston | json | MRF_FOUND | bidmilton.org |
| 220171 | Lahey Hospital & Medical Center | North Shore | json | MRF_FOUND | www.lahey.org |

### Boston Medical Center Health System (3)

| CCN | Hospital | Region | Format | Status | MRF host |
|---|---|---|---|---|---|
| 220031 | Boston Medical Center | Greater Boston | zip | MRF_FOUND | www.bmchealthsystem.org |
| 220036 | Boston Medical Center - Brighton | Greater Boston | zip | MRF_FOUND | www.bmchealthsystem.org |
| 220111 | Good Samaritan Medical Center | South Shore | zip | MRF_FOUND | www.bmchealthsystem.org |

### Brown University Health (2)

| CCN | Hospital | Region | Format | Status | MRF host |
|---|---|---|---|---|---|
| 220020 | Saint Anne's Hospital | Southeastern MA / South Coast | csv | MRF_FOUND | www.brownhealth.org |
| 220073 | Morton Hospital | Southeastern MA / South Coast | csv | MRF_FOUND | www.brownhealth.org |

### Cambridge Health Alliance (1)

| CCN | Hospital | Region | Format | Status | MRF host |
|---|---|---|---|---|---|
| 220011 | Cambridge Health Alliance | Greater Boston | csv | MRF_FOUND | www.challiance.org |

### Cape Cod Healthcare (2)

| CCN | Hospital | Region | Format | Status | MRF host |
|---|---|---|---|---|---|
| 220012 | Cape Cod Hospital | Cape Cod & Islands | unknown | MRF_FOUND | apim.services.craneware.com |
| 220135 | Falmouth Hospital | Cape Cod & Islands | unknown | MRF_FOUND | apim.services.craneware.com |

### Emerson Health (1)

| CCN | Hospital | Region | Format | Status | MRF host |
|---|---|---|---|---|---|
| 220084 | Emerson Hospital | MetroWest | csv | MRF_FOUND | emersonhealth.org |

### Heywood Healthcare (2)

| CCN | Hospital | Region | Format | Status | MRF host |
|---|---|---|---|---|---|
| 220095 | Heywood Hospital | Central Massachusetts | json | MRF_FOUND | mrfs.hyvehealthcare.com |
| 221303 | Athol Memorial Hospital | Central Massachusetts | json | MRF_FOUND | mrfs.hyvehealthcare.com |

### Independent (1)

| CCN | Hospital | Region | Format | Status | MRF host |
|---|---|---|---|---|---|
| 220090 | Milford Regional Medical Center | MetroWest | csv | MRF_FOUND | ummh-price-transparency.s3.us-east-2.amazonaws.com |

### Mass General Brigham (8)

| CCN | Hospital | Region | Format | Status | MRF host |
|---|---|---|---|---|---|
| 220015 | Cooley Dickinson Hospital | Pioneer Valley | zip | MRF_FOUND | www.massgeneralbrigham.org |
| 220035 | North Shore Medical Center (Salem Hospital) | North Shore | zip | MRF_FOUND | www.massgeneralbrigham.org |
| 220071 | Massachusetts General Hospital | Greater Boston | zip | MRF_FOUND | www.massgeneralbrigham.org |
| 220101 | Newton-Wellesley Hospital | Greater Boston | zip | MRF_FOUND | www.massgeneralbrigham.org |
| 220110 | Brigham and Women's Hospital | Greater Boston | zip | MRF_FOUND | www.massgeneralbrigham.org |
| 220119 | Brigham and Women's Faulkner Hospital | Greater Boston | zip | MRF_FOUND | www.massgeneralbrigham.org |
| 220177 | Nantucket Cottage Hospital | Cape Cod & Islands | zip | MRF_FOUND | www.massgeneralbrigham.org |
| 221300 | Martha's Vineyard Hospital | Cape Cod & Islands | zip | MRF_FOUND | www.massgeneralbrigham.org |

### Merrimack Health (2)

| CCN | Hospital | Region | Format | Status | MRF host |
|---|---|---|---|---|---|
| 220010 | Lawrence General Hospital | Merrimack Valley | csv | MRF_FOUND | www.mhlawrencehospital.org |
| 220080 | Holy Family Hospital | Merrimack Valley | csv | MRF_FOUND | methuen-haverhill.merrimackhealth.org |

### Signature Healthcare (1)

| CCN | Hospital | Region | Format | Status | MRF host |
|---|---|---|---|---|---|
| 220052 | Signature Healthcare Brockton Hospital | South Shore | csv | MRF_FOUND | signature-healthcare.org |

### South Shore Health (1)

| CCN | Hospital | Region | Format | Status | MRF host |
|---|---|---|---|---|---|
| 220100 | South Shore Hospital | South Shore | json | MRF_FOUND | zencloud-southshorehealth.s3.us-east-1.amazonaws.com |

### Southcoast Health (1)

| CCN | Hospital | Region | Format | Status | MRF host |
|---|---|---|---|---|---|
| 220074 | Southcoast Hospitals Group | Southeastern MA / South Coast | unknown | MRF_FOUND | www.southcoast.org |

### Sturdy Health (1)

| CCN | Hospital | Region | Format | Status | MRF host |
|---|---|---|---|---|---|
| 220008 | Sturdy Memorial Hospital | Southeastern MA / South Coast | unknown | SOURCE_BLOCKED · Rebranded Sturdy Health (sturdymemorial.org -> sturdyhealth.org). Site WAF returns HTTP 403 to automated fetch of /cms-hpt.txt and /.well-known/cms-hpt.txt, so the direct MRF URL could not be verified; not fabricating. MRF is expected to exist. EIN not confirmed. |  |

### Tenet Healthcare (2)

| CCN | Hospital | Region | Format | Status | MRF host |
|---|---|---|---|---|---|
| 220175 | MetroWest Medical Center | MetroWest | json | MRF_FOUND | mrfs.hyvehealthcare.com |
| 220176 | Saint Vincent Hospital | Central Massachusetts | json | MRF_FOUND | mrfs.hyvehealthcare.com |

### Trinity Health Of New England (1)

| CCN | Hospital | Region | Format | Status | MRF host |
|---|---|---|---|---|---|
| 220066 | Mercy Medical Center | Pioneer Valley | zip | MRF_FOUND | hpt.trinity-health.org |

### Tufts Medicine (3)

| CCN | Hospital | Region | Format | Status | MRF host |
|---|---|---|---|---|---|
| 220063 | Lowell General Hospital | Merrimack Valley | zip | MRF_FOUND | www.tuftsmedicine.org |
| 220070 | MelroseWakefield Healthcare | Greater Boston | zip | MRF_FOUND | www.tuftsmedicine.org |
| 220116 | Tufts Medical Center | Greater Boston | zip | MRF_FOUND | www.tuftsmedicine.org |

### UMass Memorial Health (4)

| CCN | Hospital | Region | Format | Status | MRF host |
|---|---|---|---|---|---|
| 220001 | UMass Memorial HealthAlliance-Clinton Hospital | Central Massachusetts | csv | MRF_FOUND | ummh-price-transparency.s3.us-east-2.amazonaws.com |
| 220019 | UMass Memorial Health - Harrington Hospital | Central Massachusetts | csv | MRF_FOUND | ummh-price-transparency.s3.us-east-2.amazonaws.com |
| 220049 | Marlborough Hospital | MetroWest | csv | MRF_FOUND | ummh-price-transparency.s3.us-east-2.amazonaws.com |
| 220163 | UMass Memorial Medical Center | Central Massachusetts | csv | MRF_FOUND | ummh-price-transparency.s3.us-east-2.amazonaws.com |

### Valley Health Systems (1)

| CCN | Hospital | Region | Format | Status | MRF host |
|---|---|---|---|---|---|
| 220024 | Holyoke Medical Center | Pioneer Valley | csv | SOURCE_BLOCKED · Rebranded Holyoke Health (holyokehealth.com). Site WAF returns HTTP 403 to automated fetch of /cms-hpt.txt, /.well-known/cms-hpt.txt, and the Cost for Care page, so the direct MRF URL could not be captured; not fabricating. Cost for Care page describes an annually-updated CSV MRF; EIN not confirmed. |  |

## Blocked (follow-up) 

- **220008 Sturdy Memorial Hospital** — SOURCE_BLOCKED. Rebranded Sturdy Health (sturdymemorial.org -> sturdyhealth.org). Site WAF returns HTTP 403 to automated fetch of /cms-hpt.txt and /.well-known/cms-hpt.txt, so the direct MRF URL could not be verified; not fabricating. MRF is expected to exist. EIN not confirmed. Evidence: https://www.sturdyhealth.org/patients-visitors/billing-insurance/
- **220024 Holyoke Medical Center** — SOURCE_BLOCKED. Rebranded Holyoke Health (holyokehealth.com). Site WAF returns HTTP 403 to automated fetch of /cms-hpt.txt, /.well-known/cms-hpt.txt, and the Cost for Care page, so the direct MRF URL could not be captured; not fabricating. Cost for Care page describes an annually-updated CSV MRF; EIN not confirmed. Evidence: https://www.holyokehealth.com/patients-visitors/cost-for-care/

SOURCE_BLOCKED = official site returns 403 to automated fetch (WAF); MRF almost certainly exists. Retry later with a different fetch path or record as a known gap. Fail-forward: does not block the other 51.
