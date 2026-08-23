"""Regression gate for the NY hospital identity seed (Phase 5). SQLite, no prod, no pricing."""

from __future__ import annotations

# ruff: noqa: E501
import json
from pathlib import Path

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from packages.database import Facility, FacilityLocation, LocationCapability
from packages.database.models import Base
from packages.database.pricing_models import FacilityProcedurePriceSummary
from scripts.seed_ny_hospitals import SEED_PATH, _disposition_ccns, seed


def _session() -> Session:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    return Session(engine)


def test_seeds_157_operating_hospitals() -> None:
    s = _session()
    counts = seed(s)
    assert counts["facilities"] == 157
    assert counts["locations"] == 157
    assert counts["capabilities"] == 157
    assert counts["skipped_forbidden"] == 0  # disposition CCNs are not in hospitals[] at all
    assert s.scalar(select(func.count()).select_from(Facility)) == 157
    locs = list(s.scalars(select(FacilityLocation)))
    assert all(loc.state == "NY" for loc in locs)
    assert all(loc.location_type == "hospital_campus" for loc in locs)
    assert all(loc.address_line_1 and loc.region and loc.county for loc in locs)
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
    assert s.scalar(select(func.count()).select_from(Facility)) == 157


def test_writes_no_pricing() -> None:
    s = _session()
    seed(s)
    assert s.scalar(select(func.count()).select_from(FacilityProcedurePriceSummary)) == 0


def test_facility_dedup_key_is_ccn() -> None:
    s = _session()
    seed(s)
    ccns = [c for (c,) in s.execute(select(Facility.cms_certification_number))]
    assert len(ccns) == len(set(ccns)) == 157


def test_no_disposition_ccn_is_seeded() -> None:
    s = _session()
    seed(s)
    seed_data = json.loads(Path(SEED_PATH).read_text())
    forbidden = _disposition_ccns(seed_data["_meta"])
    assert forbidden  # sanity: there are dispositions
    seeded = {c for (c,) in s.execute(select(Facility.cms_certification_number))}
    assert not (seeded & forbidden), f"disposition CCNs leaked into seed: {seeded & forbidden}"


def test_all_locations_are_ny_only() -> None:
    s = _session()
    seed(s)
    states = {st for (st,) in s.execute(select(FacilityLocation.state).distinct())}
    assert states == {"NY"}
