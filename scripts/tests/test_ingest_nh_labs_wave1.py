"""Wave 1 NH independent-lab ingestion: verified data, capability, idempotency, no overreach."""

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
from scripts.ingest_nh_labs_wave1 import VERIFIED_LABS, ingest


def _session() -> Session:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    return Session(engine)


def test_ingests_verified_labs_with_laboratory_capability_and_provenance() -> None:
    session = _session()
    result = ingest(session)
    assert result["facilities"] == len(VERIFIED_LABS)
    # Each location is a lab with a capability, real coordinates, and a provenance source.
    for loc in session.scalars(select(FacilityLocation)):
        caps = [
            c.capability
            for c in session.scalars(
                select(LocationCapability).where(LocationCapability.facility_location_id == loc.id)
            )
        ]
        assert caps == ["laboratory"]
        assert loc.latitude is not None and loc.longitude is not None
        cap = session.scalar(
            select(LocationCapability).where(LocationCapability.facility_location_id == loc.id)
        )
        assert cap is not None and cap.evidence_source_id is not None  # provenance
    # Organizations are independent labs, not hospitals.
    for org in session.scalars(select(Organization)):
        assert org.organization_type == "independent_lab"


def test_ingestion_is_idempotent() -> None:
    session = _session()
    ingest(session)
    second = ingest(session)
    assert second == {"organizations": 0, "facilities": 0, "locations": 0, "capabilities": 0}


def test_no_price_and_no_asserted_procedure_availability() -> None:
    """Accuracy over coverage: verified location, but NO price and NO per-procedure
    availability is asserted (that needs a per-location test-menu source)."""
    session = _session()
    ingest(session)
    assert session.scalar(select(func.count()).select_from(FacilityProcedurePriceSummary)) == 0
    assert session.scalar(select(func.count()).select_from(LocationServiceAvailability)) == 0


def test_dry_run_persists_nothing() -> None:
    session = _session()
    ingest(session, dry_run=True)
    assert session.scalar(select(func.count()).select_from(Facility)) == 0
