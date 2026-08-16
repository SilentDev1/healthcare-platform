"""Parkland Derry duplicate-location consolidation + duplicate detector."""

from __future__ import annotations

import uuid

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from packages.database import (
    Base,
    Facility,
    FacilityLocation,
    LocationCapability,
    SourceFile,
)
from packages.database.models import SourceStatus
from packages.database.pricing_models import (
    FacilityProcedurePriceSummary,
)
from scripts.consolidate_parkland_derry_duplicate import consolidate
from scripts.detect_duplicate_locations import (
    find_cross_org_shared_buildings,
    find_duplicate_physical_locations,
    normalize_address,
)


def _session() -> Session:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    return Session(engine)


def _parkland(session: Session) -> Facility:
    f = Facility(
        legal_name="PARKLAND MEDICAL CENTER",
        display_name="PARKLAND MEDICAL CENTER",
        facility_type="Acute Care Hospitals",
        cms_certification_number="300017",
        active=True,
    )
    session.add(f)
    session.flush()
    return f


def _scenario(session: Session) -> tuple[Facility, FacilityLocation, FacilityLocation]:
    """Reproduce prod: active priced campus w/o coords + inactive geocoded twin w/ dup caps."""
    f = _parkland(session)
    survivor = FacilityLocation(
        facility_id=f.id,
        location_name="Parkland Medical Center",
        location_type="hospital_campus",
        active=True,
        address_line_1="1 Parkland Dr",
        city="DERRY",
        state="NH",
        postal_code="03038",
        latitude=None,
        longitude=None,
    )
    dup = FacilityLocation(
        facility_id=f.id,
        location_name=None,
        location_type="hospital_campus",
        active=False,
        address_line_1="1 PARKLAND DRIVE",
        city="DERRY",
        state="NH",
        postal_code="03038",
        latitude=42.8685,
        longitude=-71.3564,
    )
    session.add_all([survivor, dup])
    session.flush()
    source = SourceFile(
        source_name="parkland mrf", source_url="https://example/mrf", source_type="mrf",
        storage_path="p", checksum_sha256="x", file_size=0, parser_version="t",
        status=SourceStatus.COMPLETED,
    )
    session.add(source)
    session.flush()
    # survivor holds the pricing
    session.add(
        FacilityProcedurePriceSummary(
            facility_id=f.id,
            facility_location_id=survivor.id,
            procedure_id=uuid.uuid4(),
            service_setting="outpatient",
            record_count=1,
            source_file_id=source.id,
            publication_status="published",
            completeness_score=1.0,
        )
    )
    # both carry hospital + emergency_department (Wave 3 added ED to both) -> collisions
    for loc in (survivor, dup):
        for cap in ("hospital", "emergency_department"):
            session.add(
                LocationCapability(facility_location_id=loc.id, capability=cap, active=True)
            )
    # Commit the baseline so a dry-run rollback undoes only the consolidation's own changes,
    # exactly as in production where the data is already committed.
    session.commit()
    return f, survivor, dup


def test_detector_flags_the_duplicate() -> None:
    session = _session()
    _scenario(session)
    dups = find_duplicate_physical_locations(session)
    assert len(dups) == 1
    assert dups[0]["facility"] == "PARKLAND MEDICAL CENTER"
    assert set(dups[0]["active_flags"]) == {True, False}


def test_consolidation_merges_coords_and_deletes_duplicate() -> None:
    session = _session()
    f, survivor, dup = _scenario(session)
    dup_id = dup.id

    result = consolidate(session, apply=True)
    assert result["status"] == "applied"

    # Duplicate row is gone.
    assert session.get(FacilityLocation, dup_id) is None
    # Exactly one location remains for the facility.
    remaining = list(
        session.scalars(select(FacilityLocation).where(FacilityLocation.facility_id == f.id))
    )
    assert len(remaining) == 1
    kept = remaining[0]
    assert kept.id == survivor.id
    # Survivor inherited the coordinates.
    assert kept.latitude is not None and kept.longitude is not None
    # Pricing preserved on survivor.
    assert (
        session.scalar(
            select(func.count())
            .select_from(FacilityProcedurePriceSummary)
            .where(FacilityProcedurePriceSummary.facility_location_id == survivor.id)
        )
        == 1
    )
    # Capabilities deduped (no collision), survivor keeps exactly hospital + emergency_department.
    caps = sorted(
        session.scalars(
            select(LocationCapability.capability).where(
                LocationCapability.facility_location_id == survivor.id
            )
        )
    )
    assert caps == ["emergency_department", "hospital"]
    # Detector now clean.
    assert find_duplicate_physical_locations(session) == []


def test_consolidation_is_idempotent() -> None:
    session = _session()
    _scenario(session)
    consolidate(session, apply=True)
    second = consolidate(session, apply=True)
    assert second["status"] == "no_duplicate"


def test_dry_run_changes_nothing() -> None:
    session = _session()
    f, survivor, dup = _scenario(session)
    result = consolidate(session, apply=False)
    assert result["status"] == "dry_run"
    assert session.get(FacilityLocation, dup.id) is not None
    assert (
        session.scalar(select(func.count()).select_from(FacilityLocation)) == 2
    )


def test_normalizer_folds_abbreviations() -> None:
    assert normalize_address("65 Calef Highway") == normalize_address("65 Calef Hwy")
    assert normalize_address("1 Parkland Drive") == normalize_address("1 Parkland Dr")
    assert normalize_address("29 Northwest Boulevard") == normalize_address("29 Northwest Blvd")


def test_cross_org_shared_building_reported_not_merged() -> None:
    """Two different orgs at the same street address are reported, never merged."""
    session = _session()
    pairs = [("Lab Co", "6 Tsienneto Rd, Ste LL102"), ("Imaging Co", "6 Tsienneto Road")]
    for org_name, addr in pairs:
        f = Facility(legal_name=org_name, display_name=org_name, facility_type="X", active=True)
        session.add(f)
        session.flush()
        session.add(
            FacilityLocation(
                facility_id=f.id, location_name=org_name, location_type="service_location",
                active=True, address_line_1=addr, city="Derry", state="NH", postal_code="03038",
            )
        )
    session.flush()
    shared = find_cross_org_shared_buildings(session)
    assert len(shared) == 1
    assert len(shared[0]["facilities"]) == 2
    # Not a same-facility duplicate -> gate stays clean.
    assert find_duplicate_physical_locations(session) == []


def test_refuses_when_addresses_differ() -> None:
    """If the two rows are NOT the same physical place, do not merge."""
    session = _session()
    f = _parkland(session)
    a = FacilityLocation(
        facility_id=f.id, location_name="Campus A", location_type="hospital_campus",
        active=True, address_line_1="1 Parkland Dr", city="DERRY", state="NH", postal_code="03038",
    )
    b = FacilityLocation(
        facility_id=f.id, location_name="Campus B", location_type="hospital_campus",
        active=True, address_line_1="99 Different Blvd", city="DERRY", state="NH",
        postal_code="03038",
    )
    session.add_all([a, b])
    session.flush()
    result = consolidate(session, apply=True)
    assert result["status"] == "not_provably_identical"
    assert session.scalar(select(func.count()).select_from(FacilityLocation)) == 2
