"""Wave 4 NH imaging ingestion: verified data, capability, idempotency, no overreach."""

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
from scripts.ingest_nh_imaging_wave4 import VERIFIED_IMAGING, ingest


def _session() -> Session:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    return Session(engine)


def test_ingests_verified_imaging_with_capability_and_provenance() -> None:
    session = _session()
    result = ingest(session)
    assert result["facilities"] == len(VERIFIED_IMAGING)
    for loc in session.scalars(select(FacilityLocation)):
        caps = [
            c.capability
            for c in session.scalars(
                select(LocationCapability).where(LocationCapability.facility_location_id == loc.id)
            )
        ]
        assert caps == ["imaging"]
        assert loc.latitude is not None and loc.longitude is not None
        cap = session.scalar(
            select(LocationCapability).where(LocationCapability.facility_location_id == loc.id)
        )
        assert cap is not None and cap.evidence_source_id is not None  # provenance
    for org in session.scalars(select(Organization)):
        assert org.organization_type == "imaging_center"


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
