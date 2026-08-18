"""Regression gate for the MA hospital identity seed (Phase 2). SQLite, no prod, no pricing."""

from __future__ import annotations

# ruff: noqa: E501
import json
from pathlib import Path

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from packages.database import Facility, FacilityLocation, LocationCapability, Organization
from packages.database.models import Base
from packages.database.pricing_models import FacilityProcedurePriceSummary
from scripts.seed_ma_hospitals import CMS_PATH, SEED_PATH, seed


def _session() -> Session:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    return Session(engine)


def test_seeds_53_operating_hospitals() -> None:
    s = _session()
    counts = seed(s)
    assert counts["facilities"] == 53
    assert counts["locations"] == 53
    assert counts["capabilities"] == 53
    assert counts["skipped_forbidden"] == 0  # closed/specialty are not in hospitals[] at all
    assert s.scalar(select(func.count()).select_from(Facility)) == 53
    # every location is MA, hospital_campus, has an address + region
    locs = list(s.scalars(select(FacilityLocation)))
    assert all(loc.state == "MA" for loc in locs)
    assert all(loc.location_type == "hospital_campus" for loc in locs)
    assert all(loc.address_line_1 and loc.region and loc.county for loc in locs)
    # every location carries exactly the hospital capability
    caps = list(s.scalars(select(LocationCapability)))
    assert {c.capability for c in caps} == {"hospital"}


def test_is_idempotent() -> None:
    s = _session()
    seed(s)
    again = seed(s)
    assert again["facilities"] == 0
    assert again["locations"] == 0
    assert again["capabilities"] == 0
    assert again["organizations"] == 0
    assert s.scalar(select(func.count()).select_from(Facility)) == 53
    assert s.scalar(select(func.count()).select_from(FacilityLocation)) == 53


def test_writes_no_pricing() -> None:
    s = _session()
    seed(s)
    assert s.scalar(select(func.count()).select_from(FacilityProcedurePriceSummary)) == 0


def test_facility_dedup_key_is_ccn() -> None:
    s = _session()
    seed(s)
    ccns = [f.cms_certification_number for f in s.scalars(select(Facility))]
    assert len(ccns) == len(set(ccns)) == 53


def test_closed_and_specialty_never_seeded() -> None:
    seed_data = json.loads(Path(SEED_PATH).read_text())
    forbidden = {e["ccn"] for e in seed_data["_meta"]["excluded_closed"]}
    forbidden |= {x.split()[0] for x in seed_data["_meta"]["specialty_acute_bucket_separately"]}
    s = _session()
    seed(s)
    seeded_ccns = {f.cms_certification_number for f in s.scalars(select(Facility))}
    assert forbidden.isdisjoint(seeded_ccns)


def test_independent_hospital_gets_own_org() -> None:
    s = _session()
    seed(s)
    # Milford Regional is the lone "Independent" — its org is the hospital, typed independent_hospital
    org = s.scalar(select(Organization).where(Organization.canonical_name == "Milford Regional Medical Center"))
    assert org is not None and org.organization_type == "independent_hospital"


def test_shipped_data_present() -> None:
    seed_data = json.loads(Path(SEED_PATH).read_text())
    cms = json.loads(Path(CMS_PATH).read_text())
    assert len(seed_data["hospitals"]) == 53
    by_ccn = {r["facility_id"]: r for r in cms["hospitals"]}
    for h in seed_data["hospitals"]:  # every operating hospital has an authoritative CMS address
        assert by_ccn[h["ccn"]]["address"]
