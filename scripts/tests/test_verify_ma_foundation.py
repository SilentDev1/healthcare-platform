"""Regression gate for the MA foundation denominator + regional taxonomy (Phase 1).

Keeps the curated MA hospital seed reconciled to the cached CMS snapshot and every
hospital region-derivable from the taxonomy. Identity/geography only — no pricing.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts.verify_ma_foundation import CMS, SEED, TAXONOMY, main, resolve_region

ACUTE_CAH = ("Acute Care Hospitals", "Critical Access Hospitals")


def test_verifier_passes() -> None:
    assert main() == 0


def test_denominator_identity_reconciles_to_cms() -> None:
    seed = json.loads(Path(SEED).read_text())
    cms = json.loads(Path(CMS).read_text())
    cms_ac = [r for r in cms["hospitals"] if r["hospital_type"] in ACUTE_CAH]
    operating = len(seed["hospitals"])
    specialty = len(seed["_meta"]["specialty_acute_bucket_separately"])
    closed = len(seed["_meta"]["excluded_closed"])
    assert operating == 53
    assert operating + specialty + closed == len(cms_ac) == 59


def test_every_hospital_region_is_derivable() -> None:
    seed = json.loads(Path(SEED).read_text())
    cms = {r["facility_id"]: r for r in json.loads(Path(CMS).read_text())["hospitals"]}
    taxonomy = json.loads(Path(TAXONOMY).read_text())
    regions = set(taxonomy["_meta"]["regions"])
    for h in seed["hospitals"]:
        r = cms[h["ccn"]]
        derived = resolve_region(taxonomy, r["countyparish"], r["citytown"])
        assert h["region"] in regions
        assert derived == h["region"], f"{h['ccn']} {h['name']}: {derived} != {h['region']}"


def test_taxonomy_covers_all_ma_hospital_counties() -> None:
    cms = json.loads(Path(CMS).read_text())
    taxonomy = json.loads(Path(TAXONOMY).read_text())
    covered = set(taxonomy["county_to_region"]) | set(taxonomy["eastern_metro_counties"])
    hospital_counties = {
        r["countyparish"].upper()
        for r in cms["hospitals"]
        if r["hospital_type"] in ACUTE_CAH and r.get("countyparish")
    }
    assert hospital_counties <= covered
