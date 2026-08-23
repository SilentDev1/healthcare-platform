"""Regression gate for the NY foundation denominator + regional taxonomy (Phase 1).

Keeps the curated NY hospital seed reconciled to the cached CMS snapshot (+ NYSDOH additions
that CMS Care Compare omits) and every hospital region-derivable from the taxonomy.
Identity/geography only — no pricing.
"""

# ruff: noqa: E501

from __future__ import annotations

import json
from pathlib import Path

from scripts.verify_ny_foundation import CMS, CONSUMER_TYPES, SEED, TAXONOMY, main, resolve_region


def test_verifier_passes() -> None:
    assert main() == 0


def test_denominator_identity_reconciles_to_cms() -> None:
    seed = json.loads(Path(SEED).read_text())
    cms = json.loads(Path(CMS).read_text())
    meta = seed["_meta"]
    cms_consumer = [r for r in cms["hospitals"] if r["hospital_type"] in CONSUMER_TYPES]
    seed_cms = [h for h in seed["hospitals"] if h.get("source") != "nysdoh"]
    disposed = (
        len(meta["excluded_closed"]) + len(meta["excluded_merged"]) + len(meta["excluded_superseded"])
        + len(meta["specialty_bucket"]) + len(meta["excluded_rehab_ltac"])
    )
    # The CMS consumer-type set partitions cleanly into operating (CMS-sourced) + dispositions.
    assert len(seed_cms) + disposed == len(cms_consumer) == 152
    # Additions are extra operating hospitals CMS omits.
    added = [h for h in seed["hospitals"] if h.get("source") == "nysdoh"]
    assert len(seed["hospitals"]) == len(seed_cms) + len(added) == 157


def test_no_addition_duplicates_a_cms_row() -> None:
    seed = json.loads(Path(SEED).read_text())
    cms_ids = {r["facility_id"] for r in json.loads(Path(CMS).read_text())["hospitals"]}
    for h in seed["hospitals"]:
        if h.get("source") == "nysdoh":
            assert h["ccn"] not in cms_ids, f"addition {h['ccn']} already in CMS snapshot"


def test_every_hospital_region_is_derivable() -> None:
    seed = json.loads(Path(SEED).read_text())
    cms = {r["facility_id"]: r for r in json.loads(Path(CMS).read_text())["hospitals"]}
    taxonomy = json.loads(Path(TAXONOMY).read_text())
    regions = set(taxonomy["_meta"]["regions"])
    for h in seed["hospitals"]:
        r = cms.get(h["ccn"], {})
        county = r.get("countyparish") or h.get("county", "")
        city = r.get("citytown") or h.get("city", "")
        derived = resolve_region(taxonomy, county, city)
        assert h["region"] in regions
        assert derived == h["region"], f"{h['ccn']} {h['name']}: {derived} != {h['region']}"


def test_taxonomy_covers_all_ny_hospital_counties() -> None:
    cms = json.loads(Path(CMS).read_text())
    taxonomy = json.loads(Path(TAXONOMY).read_text())
    covered = set(taxonomy["county_to_region"])
    hospital_counties = {
        r["countyparish"].upper()
        for r in cms["hospitals"]
        if r["hospital_type"] in CONSUMER_TYPES and r.get("countyparish")
    }
    assert hospital_counties <= covered


def test_no_closed_or_specialty_leakage_into_seed() -> None:
    seed = json.loads(Path(SEED).read_text())
    meta = seed["_meta"]
    seed_ccns = {h["ccn"] for h in seed["hospitals"]}
    for bucket in ("excluded_closed", "excluded_merged", "excluded_superseded", "specialty_bucket", "excluded_rehab_ltac"):
        for e in meta[bucket]:
            assert e["ccn"] not in seed_ccns, f"{bucket} CCN {e['ccn']} leaked into operating seed"
