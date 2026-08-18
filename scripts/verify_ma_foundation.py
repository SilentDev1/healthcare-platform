"""Verify the Massachusetts foundation denominator + regional taxonomy (Phase 1).

READ-ONLY, offline, no DB writes, no publishing. Reconciles the curated MA hospital
identity seed (``data/ma_hospitals_seed.json``) against the authoritative CMS Hospital
General Information snapshot (``data/ma_cms_hospital_snapshot.json``, dataset xubh-q36u)
and validates that every hospital in the denominator resolves to its assigned region via
``data/ma_region_taxonomy.json``.

Checks (all must PASS):
  1. Denominator reconciliation — CMS acute+CAH == operating seed + specialty bucket + closed.
  2. No seed hospital is missing from CMS; no seed CCN is unknown to CMS.
  3. Every seed hospital's ``region`` is one of the 10 taxonomy regions (no orphan labels).
  4. Taxonomy covers all MA counties that carry an acute/CAH hospital in CMS.
  5. Region derivability — for every seed hospital, region(county, city) via the taxonomy
     equals the hand-assigned region (catches silent mislabels).

Run: python -m scripts.verify_ma_foundation
Exit code 0 on PASS, 1 on any failure.
"""

from __future__ import annotations

# ruff: noqa: E501
import json
import sys
from collections import Counter
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"
SEED = DATA / "ma_hospitals_seed.json"
CMS = DATA / "ma_cms_hospital_snapshot.json"
TAXONOMY = DATA / "ma_region_taxonomy.json"

ACUTE_CAH = ("Acute Care Hospitals", "Critical Access Hospitals")


def resolve_region(taxonomy: dict, county: str, city: str) -> str | None:
    """Return the region a (county, city) resolves to, or None if unmappable."""
    county = (county or "").upper()
    city = (city or "").upper()
    municipal = taxonomy.get("municipal_overrides", {}).get(city)
    if municipal:
        return municipal
    direct = taxonomy["county_to_region"].get(county)
    if direct:
        return direct
    eastern = taxonomy["eastern_metro_counties"].get(county)
    if eastern:
        return eastern["city_overrides"].get(city, eastern["default_region"])
    return None


def main() -> int:
    seed = json.loads(SEED.read_text())
    cms_snap = json.loads(CMS.read_text())
    taxonomy = json.loads(TAXONOMY.read_text())

    cms = {r["facility_id"]: r for r in cms_snap["hospitals"]}
    cms_ac = {c: r for c, r in cms.items() if r["hospital_type"] in ACUTE_CAH}
    seed_h = {h["ccn"]: h for h in seed["hospitals"]}
    excluded = {e["ccn"] for e in seed["_meta"]["excluded_closed"]}
    specialty = {s.split()[0] for s in seed["_meta"]["specialty_acute_bucket_separately"]}
    regions = set(taxonomy["_meta"]["regions"])

    failures: list[str] = []

    # 1 + 2: reconciliation
    missing = [c for c in cms_ac if c not in seed_h and c not in excluded and c not in specialty]
    unknown = [c for c in seed_h if c not in cms]
    if missing:
        failures.append(f"CMS acute/CAH hospitals absent from seed (not closed/specialty): {missing}")
    if unknown:
        failures.append(f"Seed CCNs unknown to CMS snapshot: {unknown}")
    reconciled = len(seed_h) + len(specialty) + len(excluded)
    if reconciled != len(cms_ac):
        failures.append(
            f"Denominator identity broken: operating {len(seed_h)} + specialty {len(specialty)} "
            f"+ closed {len(excluded)} = {reconciled} != CMS acute/CAH {len(cms_ac)}"
        )

    # 3: region labels valid
    orphans = [(h["ccn"], h["region"]) for h in seed["hospitals"] if h["region"] not in regions]
    if orphans:
        failures.append(f"Hospitals with region labels outside the taxonomy: {orphans}")

    # 4: taxonomy covers every county that has an acute/CAH hospital
    cms_counties = {r["countyparish"].upper() for r in cms_ac.values() if r.get("countyparish")}
    covered = set(taxonomy["county_to_region"]) | set(taxonomy["eastern_metro_counties"])
    uncovered = cms_counties - covered
    if uncovered:
        failures.append(f"MA counties with hospitals not covered by taxonomy: {sorted(uncovered)}")

    # 5: region derivability
    mismatches = []
    for h in seed["hospitals"]:
        r = cms.get(h["ccn"], {})
        derived = resolve_region(taxonomy, r.get("countyparish", ""), r.get("citytown", h["city"]))
        if derived != h["region"]:
            mismatches.append(
                f"{h['ccn']} {h['name']} ({r.get('citytown', h['city'])}, {r.get('countyparish')}): "
                f"assigned={h['region']!r} derived={derived!r}"
            )
    if mismatches:
        failures.append("Region not derivable from (county, city):\n    " + "\n    ".join(mismatches))

    # report
    dist = Counter(h["region"] for h in seed["hospitals"])
    print("=== MA Foundation Denominator — Phase 1 verification ===")
    print(f"CMS source: {cms_snap['_meta']['dataset_id']} retrieved {cms_snap['_meta']['retrieval_date']}")
    print(f"CMS acute+CAH (incl. closed/specialty): {len(cms_ac)}")
    print(f"Operating general acute+CAH denominator: {len(seed_h)}")
    print(f"Specialty acute (separate bucket):       {len(specialty)}  {sorted(specialty)}")
    print(f"Closed (excluded, CMS-lagged):           {len(excluded)}  {sorted(excluded)}")
    print(f"Identity check: {len(seed_h)} + {len(specialty)} + {len(excluded)} = {reconciled} vs CMS {len(cms_ac)}")
    print(f"\nRegions: {len(regions)} | counties covered: {len(covered)} | hospital region distribution:")
    for reg in taxonomy["_meta"]["regions"]:
        print(f"  {dist.get(reg, 0):2d}  {reg}")

    if failures:
        print("\nRESULT: FAIL")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("\nRESULT: PASS — denominator reconciled to CMS, taxonomy complete & every hospital region-derivable.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
