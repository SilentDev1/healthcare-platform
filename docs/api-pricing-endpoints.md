# API Pricing Endpoints (Phase 4.2)

## Public Endpoints

### GET /api/v1/pricing/freshness

Returns per-facility source freshness data.

**Response:**
```json
{
  "items": [
    {
      "facility_id": "uuid",
      "facility_name": "Hospital Name",
      "last_download": "2024-01-15T10:00:00Z",
      "days_since_download": 30,
      "freshness_score": 100.0
    }
  ]
}
```

### GET /api/v1/pricing/scorecard

Returns statewide readiness scorecard.

**Response:**
```json
{
  "state": "NH",
  "total_facilities": 28,
  "component_scores": {
    "discovery": 85.0,
    "parsing": 78.0,
    "mapping": 72.0,
    "quality": 90.0,
    "freshness": 65.0,
    "coverage": 45.0
  },
  "overall_readiness": 72.5,
  "target": 90.0,
  "meets_target": false,
  "details": { ... }
}
```

### GET /api/v1/pricing/facility-scores

Paginated facility pricing health scores.

**Query Parameters:**
- `page` (int, default 1)
- `page_size` (int, default 20)
- `sort` ("overall_score" | "facility_name", default "overall_score")
- `min_score` (float, optional) — filter facilities below this score

**Response:**
```json
{
  "items": [
    {
      "facility_id": "uuid",
      "facility_name": "Hospital Name",
      "overall_score": 75.0,
      "source_discovery_score": 100.0,
      "download_score": 100.0,
      "parse_score": 80.0,
      "mapping_score": 60.0,
      "payer_normalization_score": 70.0,
      "anomaly_score": 90.0,
      "freshness_score": 50.0,
      "price_coverage_score": 40.0
    }
  ],
  "total": 28,
  "page": 1,
  "page_size": 20
}
```

### GET /api/v1/facilities/{id}/pricing-health

Single facility pricing health breakdown.

**Response:**
```json
{
  "facility_id": "uuid",
  "overall_score": 75.0,
  "source_discovery_score": 100.0,
  "download_score": 100.0,
  "parse_score": 80.0,
  "mapping_score": 60.0,
  "payer_normalization_score": 70.0,
  "anomaly_score": 90.0,
  "freshness_score": 50.0,
  "price_coverage_score": 40.0,
  "details": { ... }
}
```

Returns 404 if facility has no pricing health score.

### GET /api/v1/facilities/map-data

GeoJSON FeatureCollection for the facility map.

**Query Parameters:**
- `pricing_status` (optional) — filter by "publishable", "partial", or "no_data"

**Response:**
```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "geometry": {
        "type": "Point",
        "coordinates": [-71.56, 43.45]
      },
      "properties": {
        "facility_id": "uuid",
        "name": "Hospital Name",
        "city": "Concord",
        "state": "NH",
        "procedure_count": 15,
        "pricing_status": "publishable"
      }
    }
  ]
}
```

## Price Filtering (Enhanced)

### GET /api/v1/procedures/{slug}/prices

**Additional Query Parameters (Phase 4.2):**
- `service_setting` (optional) — filter by "inpatient", "outpatient", etc.
- `billing_class` (optional) — filter by "facility", "professional", etc.
- `payer` (optional) — filter by payer name
- `sort` (optional) — "cash_price_asc", "cash_price_desc"

## Admin Endpoints

### GET /api/v1/admin/dashboard

Enhanced with pricing metrics:
- `statewide_scorecard` — composite readiness data
- `recent_imports` — latest import runs
- `stale_sources` — sources needing refresh
- `open_anomalies` — anomalies awaiting review
