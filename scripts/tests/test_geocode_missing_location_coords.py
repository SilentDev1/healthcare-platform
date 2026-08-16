"""Geocode-missing-coords backfill: only touches null-coord rows, never overwrites."""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

import scripts.geocode_missing_location_coords as mod
from packages.database import Base, Facility, FacilityLocation, LocationCapability


def _session() -> Session:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    return Session(engine)


def _loc(session: Session, name: str, *, lat=None, lng=None, zip_="03820") -> FacilityLocation:
    f = Facility(legal_name=name, display_name=name, facility_type="X", active=True)
    session.add(f)
    session.flush()
    loc = FacilityLocation(
        facility_id=f.id, location_name=name, location_type="freestanding_emergency_room",
        active=True, address_line_1="1 A St", city="Dover", state="NH", postal_code=zip_,
        latitude=lat, longitude=lng,
    )
    session.add(loc)
    session.flush()
    session.add(
        LocationCapability(
            facility_location_id=loc.id, capability="freestanding_emergency_department", active=True
        )
    )
    session.flush()
    return loc


def test_geocodes_only_missing_and_never_overwrites(monkeypatch) -> None:
    session = _session()
    missing = _loc(session, "Missing ER")
    have = _loc(session, "Has Coords", lat=Decimal("1.0"), lng=Decimal("2.0"))

    monkeypatch.setattr(mod, "resolve_origin", lambda **kw: (43.19, -70.87))
    result = mod.geocode(session, capability="freestanding_emergency_department", apply=True)

    assert result["geocoded"] == 1
    got = session.get(FacilityLocation, missing.id)
    assert got.latitude is not None and got.longitude is not None
    # Existing coordinates are preserved untouched.
    kept = session.get(FacilityLocation, have.id)
    assert kept.latitude == Decimal("1.0") and kept.longitude == Decimal("2.0")


def test_dry_run_persists_nothing(monkeypatch) -> None:
    session = _session()
    _loc(session, "Missing ER")
    monkeypatch.setattr(mod, "resolve_origin", lambda **kw: (43.19, -70.87))
    mod.geocode(session, apply=False)
    rows = list(session.scalars(select(FacilityLocation)))
    assert all(r.latitude is None for r in rows)
