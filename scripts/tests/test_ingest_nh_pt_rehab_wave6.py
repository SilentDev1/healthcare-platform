"""Wave 6 NH PT + rehabilitation: distinct capabilities, dual-capability locations, idempotency."""

from __future__ import annotations

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from packages.database import (
    Base,
    Facility,
    FacilityLocation,
    FacilityProcedurePriceSummary,
    LocationCapability,
    LocationServiceAvailability,
    Organization,
)
from scripts.ingest_nh_pt_rehab_wave6 import VERIFIED_REHAB, ingest


def _session() -> Session:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    return Session(engine)


def _caps(session: Session, loc_id: object) -> list[str]:
    return sorted(
        session.scalars(
            select(LocationCapability.capability).where(
                LocationCapability.facility_location_id == loc_id
            )
        )
    )


def test_ingests_distinct_pt_and_rehab_capabilities() -> None:
    session = _session()
    result = ingest(session)
    assert result["facilities"] == len(VERIFIED_REHAB)
    # Distinct capabilities present, never conflated.
    all_caps = set(
        session.scalars(select(LocationCapability.capability))
    )
    assert all_caps == {"rehabilitation", "physical_therapy"}
    # Single org, rehabilitation network.
    orgs = list(session.scalars(select(Organization)))
    assert len(orgs) == 1 and orgs[0].organization_type == "rehabilitation"
    # Every capability has provenance + every location is geocoded.
    for loc in session.scalars(select(FacilityLocation)):
        assert loc.latitude is not None and loc.longitude is not None


def test_dual_capability_locations_carry_both() -> None:
    """The Portsmouth and Salem-Butler addresses host BOTH a rehab hospital and a PT clinic."""
    session = _session()
    ingest(session)
    dual = 0
    for loc in session.scalars(select(FacilityLocation)):
        caps = _caps(session, loc.id)
        if caps == ["physical_therapy", "rehabilitation"]:
            dual += 1
    assert dual == 2  # Portsmouth (105 Corporate Dr) + Salem (70 Butler St)


def test_no_duplicate_physical_locations_created() -> None:
    """Same-address rehab+PT collapse to one location — never duplicate physical rows."""
    session = _session()
    ingest(session)
    # 7 distinct physical locations from 9 directory listings (2 collapsed).
    assert session.scalar(select(func.count()).select_from(FacilityLocation)) == 7


def test_ingestion_is_idempotent() -> None:
    session = _session()
    ingest(session)
    second = ingest(session)
    assert second == {"organizations": 0, "facilities": 0, "locations": 0, "capabilities": 0}


def test_no_price_and_no_asserted_procedure_availability() -> None:
    session = _session()
    ingest(session)
    assert session.scalar(select(func.count()).select_from(FacilityProcedurePriceSummary)) == 0
    assert session.scalar(select(func.count()).select_from(LocationServiceAvailability)) == 0


def test_dry_run_persists_nothing() -> None:
    session = _session()
    ingest(session, dry_run=True)
    assert session.scalar(select(func.count()).select_from(Facility)) == 0
