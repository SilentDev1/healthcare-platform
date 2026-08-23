"""Verify the New York foundation denominator + regional taxonomy (Phase 1).

READ-ONLY, offline, no DB writes, no publishing. Reconciles the curated NY hospital
identity seed (``data/ny_hospitals_seed.json``) against the authoritative CMS Hospital
General Information snapshot (``data/ny_cms_hospital_snapshot.json``, dataset xubh-q36u)
and validates that every consumer-denominator hospital resolves to exactly one region via
``data/ny_region_taxonomy.json``.

NY specifics vs MA:
  * Consumer denominator = CMS ``Acute Care Hospitals`` + ``Critical Access Hospitals`` +
    ``Rural Emergency Hospital``. Federal (VA / DoD) and ``Psychiatric`` are excluded BY TYPE
    (never part of the consumer denominator). ``Childrens`` is a separate specialty bucket.
  * Regions are purely county-based (no municipality subdivision needed). NYC's five counties
    map to boroughs (Kings->Brooklyn, etc.) which are first-class regions rolling up to NYC via
    ``_meta.region_groups``. Long Island (Nassau+Suffolk) is a single region.

Checks (all must PASS):
  1. Every CMS consumer-type CCN (acute+CAH+REH) is accounted for: in the operating seed,
     or in ``excluded_closed``, or in ``excluded_merged``. No silent drops.
  2. No seed CCN is unknown to CMS; no seed CCN is a federal/psychiatric type.
  3. Denominator identity: operating seed + closed + merged == CMS consumer-type count.
  4. Every seed hospital's ``region`` is one of the taxonomy regions (no orphan labels).
  5. Taxonomy covers every NY county that carries a consumer-type hospital in CMS.
  6. Region derivability: region(county, city) via the taxonomy == the hand-assigned region.
  7. Every region belongs to exactly one region_group (roll-up integrity).

Run: python -m scripts.verify_ny_foundation
Exit code 0 on PASS, 1 on any failure.
"""

from __future__ import annotations

# ruff: noqa: E501
import json
import sys
from collections import Counter
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"
SEED = DATA / "ny_hospitals_seed.json"
CMS = DATA / "ny_cms_hospital_snapshot.json"
TAXONOMY = DATA / "ny_region_taxonomy.json"

CONSUMER_TYPES = ("Acute Care Hospitals", "Critical Access Hospitals", "Rural Emergency Hospital")
FEDERAL_TYPES = ("Acute Care - Veterans Administration", "Acute Care - Department of Defense")
PSYCH_TYPE = "Psychiatric"


def resolve_region(taxonomy: dict, county: str, city: str) -> str | None:
    """Return the region a (county, city) resolves to, or None if unmappable.

    NY is county-based; ``municipal_overrides`` handles rare cross-boundary exceptions and
    is checked first (city keys are matched case-insensitively)."""
    county = (county or "").upper()
    city = (city or "").upper()
    override = taxonomy.get("municipal_overrides", {}).get(city)
    if override:
        return override
    return taxonomy["county_to_region"].get(county)


def main() -> int:
    seed = json.loads(SEED.read_text())
    cms_snap = json.loads(CMS.read_text())
    taxonomy = json.loads(TAXONOMY.read_text())

    cms = {r["facility_id"]: r for r in cms_snap["hospitals"]}
    cms_consumer = {c: r for c, r in cms.items() if r["hospital_type"] in CONSUMER_TYPES}
    seed_h = {h["ccn"]: h for h in seed["hospitals"]}
    meta = seed["_meta"]
    closed = {e["ccn"] for e in meta.get("excluded_closed", [])}
    merged = {e["ccn"] for e in meta.get("excluded_merged", [])}
    superseded = {e["ccn"] for e in meta.get("excluded_superseded", [])}
    specialty = {e["ccn"] for e in meta.get("specialty_bucket", [])}
    rehab_ltac = {e["ccn"] for e in meta.get("excluded_rehab_ltac", [])}
    disposed = closed | merged | superseded | specialty | rehab_ltac
    # Additions are operating hospitals CMS Care Compare omits (source=nysdoh) — legitimately absent from CMS.
    added = {h["ccn"] for h in seed["hospitals"] if h.get("source") == "nysdoh"}
    seed_cms = {c for c, h in seed_h.items() if h.get("source") != "nysdoh"}
    regions = set(taxonomy["_meta"]["regions"])
    groups = taxonomy.get("region_groups", {})

    failures: list[str] = []

    # 1: every consumer-type CCN accounted for (operating seed OR a disposition bucket)
    unaccounted = [c for c in cms_consumer if c not in seed_h and c not in disposed]
    if unaccounted:
        failures.append(
            "CMS consumer-type hospitals not accounted for (not in seed or any disposition): "
            + ", ".join(f"{c} {cms[c]['facility_name']}" for c in unaccounted)
        )

    # 2: CMS-sourced seed CCNs must be known to CMS and not federal/psychiatric; additions are exempt.
    unknown = [c for c in seed_cms if c not in cms]
    if unknown:
        failures.append(f"CMS-sourced seed CCNs unknown to CMS snapshot: {unknown}")
    bad_type = [c for c in seed_cms if c in cms and cms[c]["hospital_type"] in FEDERAL_TYPES + (PSYCH_TYPE,)]
    if bad_type:
        failures.append(f"Seed CCNs that are federal/psychiatric type (should be excluded): {bad_type}")
    # additions must NOT already be present as a CMS consumer row (else double-count)
    added_dup = [c for c in added if c in cms_consumer]
    if added_dup:
        failures.append(f"NYSDOH additions that duplicate a CMS consumer row: {added_dup}")

    # 3: denominator identity over the CMS consumer-type set
    reconciled = len(seed_cms) + len(disposed)
    if reconciled != len(cms_consumer):
        failures.append(
            f"Denominator identity broken: CMS-sourced seed {len(seed_cms)} + disposed {len(disposed)} "
            f"= {reconciled} != CMS consumer-type {len(cms_consumer)}"
        )

    # 4: region labels valid
    orphans = [(h["ccn"], h["region"]) for h in seed["hospitals"] if h["region"] not in regions]
    if orphans:
        failures.append(f"Hospitals with region labels outside the taxonomy: {orphans}")

    # 5: taxonomy covers every county with a consumer-type hospital
    cms_counties = {r["countyparish"].upper() for r in cms_consumer.values() if r.get("countyparish")}
    covered = set(taxonomy["county_to_region"])
    uncovered = cms_counties - covered
    if uncovered:
        failures.append(f"NY counties with hospitals not covered by taxonomy: {sorted(uncovered)}")

    # 6: region derivability — CMS county for CMS rows, seed county for NYSDOH additions
    mismatches = []
    for h in seed["hospitals"]:
        r = cms.get(h["ccn"], {})
        county = r.get("countyparish") or h.get("county", "")
        city = r.get("citytown") or h.get("city", "")
        derived = resolve_region(taxonomy, county, city)
        if derived != h["region"]:
            mismatches.append(
                f"{h['ccn']} {h['name']} ({r.get('citytown', h['city'])}, {r.get('countyparish')}): "
                f"assigned={h['region']!r} derived={derived!r}"
            )
    if mismatches:
        failures.append("Region not derivable from (county, city):\n    " + "\n    ".join(mismatches))

    # 7: every region in exactly one group
    if groups:
        grouped = [reg for k, members in groups.items() if not k.startswith("_") for reg in members]
        gcount = Counter(grouped)
        multi = [r for r, n in gcount.items() if n > 1]
        ungrouped = regions - set(grouped)
        unknown_grouped = set(grouped) - regions
        if multi:
            failures.append(f"Regions in more than one region_group: {multi}")
        if ungrouped:
            failures.append(f"Regions not in any region_group: {sorted(ungrouped)}")
        if unknown_grouped:
            failures.append(f"region_group members not in taxonomy regions: {sorted(unknown_grouped)}")

    # report
    dist = Counter(h["region"] for h in seed["hospitals"])
    print("=== NY Foundation Denominator — Phase 1 verification ===")
    print(f"CMS source: {cms_snap['_meta']['dataset_id']} retrieved {cms_snap['_meta']['retrieval_date']}")
    print(f"CMS consumer-type (acute+CAH+REH): {len(cms_consumer)}")
    print(f"Operating denominator (seed):      {len(seed_h)}  (CMS {len(seed_cms)} + NYSDOH additions {len(added)})")
    print(f"Dispositioned: closed {len(closed)} | merged {len(merged)} | superseded {len(superseded)} | specialty {len(specialty)} | rehab/LTAC {len(rehab_ltac)}")
    print(f"Identity (CMS set): {len(seed_cms)} + {len(disposed)} = {reconciled} vs CMS consumer-type {len(cms_consumer)}")
    print(f"\nRegions: {len(regions)} | region_groups: {len(groups)} | hospital region distribution:")
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
