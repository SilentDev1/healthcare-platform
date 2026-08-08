# Statewide Coverage Methodology

## Overview

Phase 4.2 targets 90%+ statewide readiness for New Hampshire hospital price comparison. Coverage is measured as a composite score across six equally-weighted dimensions.

## Reference Set

The NH reference set includes 28 acute-care hospitals identified by CMS Certification Number (CCN). These are cross-referenced against:

- CMS Hospital Compare data
- NPPES NPI registry
- Hospital websites for price transparency file locations

## Coverage Dimensions

### 1. Discovery (weight: 1/6)

Percentage of NH facilities with at least one active `FacilityPriceSource` record.

**Formula:** `facilities_with_sources / total_facilities × 100`

### 2. Parsing (weight: 1/6)

Percentage of NH facilities with at least one parsed `HospitalPriceRecord`.

**Formula:** `facilities_with_records / total_facilities × 100`

### 3. Mapping (weight: 1/6)

Average `mapping_score` across facilities with `PricingHealthScore` records. Measures what fraction of parsed records have been mapped to standard procedures.

### 4. Quality (weight: 1/6)

Average `anomaly_score` across facilities. Penalizes facilities with open high-severity anomalies (20 points per anomaly, minimum 0).

### 5. Freshness (weight: 1/6)

Average `freshness_score` across facilities. Based on days since last successful download:

| Recency    | Score |
| ---------- | ----- |
| ≤ 30 days  | 100   |
| ≤ 60 days  | 80    |
| ≤ 90 days  | 50    |
| ≤ 180 days | 20    |
| > 180 days | 0     |

### 6. Coverage (weight: 1/6)

Percentage of catalog procedures with at least one publishable price from any NH facility.

**Formula:** `procedures_with_prices / total_procedures × 100`

## Composite Score

```
overall_readiness = (discovery + parsing + mapping + quality + freshness + coverage) / 6
```

Target: **≥ 90%**

## Procedure Code Mappings

Phase 4.2 expands from 14 to 51 deterministic CPT/HCPCS/DRG code mappings:

- **Labs:** CBC, CMP, BMP, lipid panel, A1C, TSH, urinalysis, pregnancy test, strep test, COVID-19 test, pathology, Pap smear
- **Imaging:** X-ray, MRI, CT, ultrasound, DEXA, mammogram
- **Cardiac:** echocardiogram, EKG, stress test, cardiac catheterization
- **Surgery:** cataract, hernia, cholecystectomy, knee replacement, hip replacement, carpal tunnel, rotator cuff
- **Maternity:** cesarean delivery (MS-DRG 766), vaginal delivery (MS-DRG 775)
- **Emergency:** ED visits (CPT 99281–99285)
- **Office/Other:** office visit, physical therapy, sleep study, allergy testing, flu vaccine, annual wellness, dialysis

All mappings are code-based (CPT, HCPCS, or MS-DRG), deterministic, and idempotent.

## Parser Format Support

Supported CMS HPT CSV header variants:

**Description columns:** description, item description, item/service, item_service, procedure
**Code columns:** code, billing code, procedure_code, hcpcs_code, cpt_code
**Price columns:** standard charges, gross charge, discounted cash price, negotiated rate

Unsupported formats receive `ParserReview(status="unsupported_deferred")` with documented reason.

## Historical Price Tracking

`PriceChangeSnapshot` records capture price changes between import runs:

- Previous and current cash/negotiated medians
- Percentage change calculations
- Linked to import runs for provenance
- Created automatically during `rebuild_price_summaries()`

## Safety Constraints

All pricing data flows through deterministic, auditable pipelines:

- No AI-modified prices
- No automatic merges of unreviewed data
- No public display of unreviewed mappings
- No negative prices accepted
- Full provenance chain from source file to published summary
- No PHI in any pricing record
