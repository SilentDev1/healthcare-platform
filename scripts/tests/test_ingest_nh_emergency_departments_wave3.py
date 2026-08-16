"""Wave 3 NH ED capability: layered on hospital locations, psychiatric excluded, idempotent."""

from __future__ import annotations

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from packages.database import (
    Base,
    Facility,
    FacilityLocation,
    LocationCapability,
)
from scripts.ingest_nh_emergency_departments_wave3 import ingest


def _session() -> Session:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    return Session(engine)


def _hospital(session: Session, name: str, ftype: str) -> FacilityLocation:
    facility = Facility(
        legal_name=name, display_name=name, facility_type=ftype, active=True
    )
    session.add(facility)
    session.flush()
    loc = FacilityLocation(
        facility_id=facility.id,
        location_name=name,
        location_type="hospital_campus",
        active=True,
        address_line_1="1 Hospital Way",
        city="Anytown",
        state="NH",
        postal_code="03000",
    )
    session.add(loc)
    session.flush()
    session.add(
        LocationCapability(facility_location_id=loc.id, capability="hospital", active=True)
    )
    session.flush()
    return loc


def _fixture(session: Session) -> dict[str, FacilityLocation]:
    return {
        "acute": _hospital(session, "General Acute Hospital", "Acute Care Hospitals"),
        "cah": _hospital(session, "Rural CAH", "Critical Access Hospitals"),
        "psych": _hospital(session, "State Psychiatric Hospital", "Psychiatric"),
    }


def _caps(session: Session, loc_id: str) -> list[str]:
    return sorted(
        session.scalars(
            select(LocationCapability.capability).where(
                LocationCapability.facility_location_id == loc_id
            )
        )
    )


def test_ed_added_to_acute_and_cah_but_not_psychiatric() -> None:
    session = _session()
    locs = _fixture(session)
    result = ingest(session)
    assert result["capabilities_added"] == 2
    assert result["excluded_psychiatric"] == 1
    assert _caps(session, locs["acute"].id) == ["emergency_department", "hospital"]
    assert _caps(session, locs["cah"].id) == ["emergency_department", "hospital"]
    # Psychiatric hospital keeps ONLY its hospital capability — never an asserted ER.
    assert _caps(session, locs["psych"].id) == ["hospital"]


def test_creates_no_new_facilities_or_locations() -> None:
    session = _session()
    _fixture(session)
    before_f = session.scalar(select(func.count()).select_from(Facility))
    before_l = session.scalar(select(func.count()).select_from(FacilityLocation))
    ingest(session)
    assert session.scalar(select(func.count()).select_from(Facility)) == before_f
    assert session.scalar(select(func.count()).select_from(FacilityLocation)) == before_l


def test_provenance_attached_to_ed_capability() -> None:
    session = _session()
    _fixture(session)
    ingest(session)
    for cap in session.scalars(
        select(LocationCapability).where(
            LocationCapability.capability == "emergency_department"
        )
    ):
        assert cap.evidence_source_id is not None


def test_idempotent() -> None:
    session = _session()
    _fixture(session)
    ingest(session)
    second = ingest(session)
    assert second["capabilities_added"] == 0


def test_dry_run_persists_nothing() -> None:
    session = _session()
    _fixture(session)
    ingest(session, dry_run=True)
    assert (
        session.scalar(
            select(func.count())
            .select_from(LocationCapability)
            .where(LocationCapability.capability == "emergency_department")
        )
        == 0
    )
