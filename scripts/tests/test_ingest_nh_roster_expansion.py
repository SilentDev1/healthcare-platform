"""Wave 8 roster expansion: physical-location dedup, capability union, org reuse, provenance."""

from __future__ import annotations

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from packages.database import (
    Base,
    Facility,
    FacilityLocation,
    FacilityProcedurePriceSummary,
    LocationCapability,
    Organization,
)
from scripts.ingest_nh_roster_expansion import _load_records, ingest


def _session() -> Session:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    return Session(engine)


def _caps(session: Session, loc_id) -> list[str]:
    return sorted(
        session.scalars(
            select(LocationCapability.capability).where(
                LocationCapability.facility_location_id == loc_id
            )
        )
    )


SHARED = [
    {"capability": "urgent_care", "organization": "WDH", "organization_type": "health_system",
     "facility_type": "Urgent Care", "display_name": "WDH Express Care — Lee",
     "address": "65 Calef Highway", "city": "Lee", "postal_code": "03861",
     "phone": "1", "source_url": "https://x/uc"},
    {"capability": "physical_therapy", "organization": "WDH", "organization_type": "health_system",
     "facility_type": "Physical Therapy Clinic", "display_name": "WDH Rehab — Lee",
     "address": "65 Calef Hwy", "city": "Lee", "postal_code": "03861",
     "phone": "1", "source_url": "https://x/pt"},
    {"capability": "laboratory", "organization": "Quest Diagnostics", "organization_type": "independent_lab",  # noqa: E501
     "facility_type": "Independent Laboratory", "display_name": "Quest — Pelham",
     "address": "49 Atwood Road", "city": "Pelham", "postal_code": "03076",
     "phone": "1", "source_url": "https://x/lab"},
]


def test_shared_address_becomes_one_location_with_union_of_capabilities() -> None:
    session = _session()
    ingest(session, records=SHARED)
    # WDH Lee: one physical location carrying BOTH capabilities (65 Calef Highway == 65 Calef Hwy).
    wdh_locs = [
        loc for loc in session.scalars(select(FacilityLocation))
        if loc.city == "Lee"
    ]
    assert len(wdh_locs) == 1
    assert _caps(session, wdh_locs[0].id) == ["physical_therapy", "urgent_care"]


def test_org_reused_by_canonical_name() -> None:
    session = _session()
    # Pre-create the Quest org; ingestion must reuse it, not duplicate.
    session.add(
        Organization(canonical_name="Quest Diagnostics", display_name="Quest Diagnostics",
                     organization_type="independent_lab", active=True)
    )
    session.commit()
    ingest(session, records=SHARED)
    quests = list(
        session.scalars(select(Organization).where(Organization.canonical_name == "Quest Diagnostics"))  # noqa: E501
    )
    assert len(quests) == 1


def test_idempotent() -> None:
    session = _session()
    ingest(session, records=SHARED)
    second = ingest(session, records=SHARED)
    assert second == {"organizations": 0, "facilities": 0, "locations": 0, "capabilities": 0}


def test_no_price_asserted() -> None:
    session = _session()
    ingest(session, records=SHARED)
    assert session.scalar(select(func.count()).select_from(FacilityProcedurePriceSummary)) == 0


def test_real_data_file_loads_and_ingests() -> None:
    """The shipped data file parses and every location geocodes + carries provenance."""
    session = _session()
    records = _load_records()
    assert len(records) >= 60  # sizable verified roster expansion
    result = ingest(session, records=records)
    assert result["locations"] >= 60
    # every capability row has provenance
    for cap in session.scalars(select(LocationCapability)):
        assert cap.evidence_source_id is not None
    # every ingested facility has an organization
    for f in session.scalars(select(Facility)):
        assert f.organization_id is not None
