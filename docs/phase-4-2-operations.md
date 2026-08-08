# Phase 4.2 Pipeline Operations Guide

## Overview

Phase 4.2 provides a statewide hospital pricing pipeline for New Hampshire. The pipeline processes hospital price transparency data through four stages: discovery, download, import, and post-processing.

## Pipeline Stages

### 1. Discovery

Scans hospital websites for CMS Hospital Price Transparency (HPT) machine-readable files.

```bash
make pipeline-discover-nh
```

### 2. Download

Downloads machine-readable files from discovered sources.

```bash
make pipeline-download-nh
```

### 3. Import

Parses downloaded files and imports pricing data into the database.

```bash
make pipeline-import-nh
```

### 4. Post-process

Rebuilds price summaries, runs quality checks, and evaluates pricing health.

```bash
make pipeline-postprocess-nh
```

### Full Pipeline

Runs all four stages sequentially.

```bash
make pipeline-full-nh
```

## Operational Scripts

### Audit NH Hospitals

Check coverage of all 28 NH acute-care hospitals.

```bash
make audit-nh-hospitals
```

### Statewide Scorecard

Generate composite readiness score (target: 90%+).

```bash
make statewide-scorecard
```

### Procedure Coverage

Report per-facility procedure coverage.

```bash
make procedure-coverage
```

### Geocode Facilities

Populate facility coordinates for map display.

```bash
make geocode-nh
```

### Benchmarks

Run performance benchmarks (target: >= 300 rows/sec).

```bash
make benchmark-pricing-import
```

## Quality System

### Auto-Triage Rules

The quality module (`collectors/hospital_prices/quality.py`) applies three automatic triage rules to pricing anomalies:

1. **suspicious_zero on lab items** → auto-suppress (zero-price lab items are common)
2. **blank_payer with gross_charge** → downgrade to warning (record has useful data despite missing payer)
3. **extremely_large_price on known high-cost DRGs** → auto-suppress (transplants, complex revisions legitimately exceed $1M)

### Freshness Scoring

Source freshness is scored based on days since last successful download:

| Days Since Download | Score |
| ------------------- | ----- |
| ≤ 30                | 100   |
| ≤ 60                | 80    |
| ≤ 90                | 50    |
| ≤ 180               | 20    |
| > 180               | 0     |

### Health Score Components

Each facility receives an overall pricing health score composed of 8 equally-weighted components:

1. Source discovery (has active source?)
2. Download status (has downloaded file?)
3. Parse status (has parsed records?)
4. Mapping score (% of records with procedure mappings)
5. Payer normalization (% of rates with matched payers)
6. Anomaly score (penalized per open high-severity anomaly)
7. Freshness score (based on download recency)
8. Price coverage (publishable summary count)

## Verification

```bash
make verify-phase-4-2
```

This runs: fixture pipeline, search index rebuild, benchmarks, final report, full test suite, linting, type checking, builds, and npm audit.

## Safety Invariants

- 0 AI-modified prices
- 0 auto-merges
- 0 public unreviewed mappings
- 0 negative prices accepted
- 0 incomplete provenance chains
- 0 PHI exposure
- 0 insurer TiC files
- 0 cloud deployments
