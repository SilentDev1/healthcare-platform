"""Media issue detector: same-image-different-address, shared-building, missing attribution."""

from __future__ import annotations

# ruff: noqa: E501
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from packages.database import (
    Base,
    Facility,
    FacilityLocation,
    FacilityMedia,
    LocationCapability,
)
from scripts.detect_media_issues import find_issues


def _session() -> Session:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    return Session(engine)


def _fac_loc(session: Session, name: str, addr: str, city: str, cap: str) -> Facility:
    f = Facility(legal_name=name, display_name=name, facility_type="X", active=True)
    session.add(f)
    session.flush()
    loc = FacilityLocation(
        facility_id=f.id, location_name=name, location_type="service_location", active=True,
        address_line_1=addr, city=city, state="NH", postal_code="03060",
    )
    session.add(loc)
    session.flush()
    session.add(LocationCapability(facility_location_id=loc.id, capability=cap, active=True))
    session.flush()
    return f


def test_same_image_different_address_flagged_shared_building_separate() -> None:
    session = _session()
    a = _fac_loc(session, "Quest — Derry", "6 Tsienneto Rd Ste LL102", "Derry", "laboratory")
    b = _fac_loc(session, "Derry Imaging — Derry", "6 Tsienneto Road", "Derry", "imaging")
    c = _fac_loc(session, "Quest — Nashua", "300 Main St", "Nashua", "laboratory")
    # same image on a+b (same building, different suites) -> shared-building (OK)
    for f in (a, b):
        session.add(FacilityMedia(facility_id=f.id, cdn_url="https://img/one.jpg",
                                  source_type="wikimedia", verification_status="verified"))
    # same image reused on c (Nashua, different address) -> unrelated-address flag
    session.add(FacilityMedia(facility_id=c.id, cdn_url="https://img/one.jpg",
                              source_type="wikimedia", verification_status="verified"))
    session.commit()
    issues = find_issues(session)
    assert len(issues["SAME_IMAGE_UNRELATED_ADDRESS"]) == 1
    assert len(issues["SHARED_BUILDING_SAME_ADDRESS"]) == 0  # once Nashua joins, group spans addresses


def test_missing_attribution_for_cc_by() -> None:
    session = _session()
    f = _fac_loc(session, "Lab", "1 A St", "Nashua", "laboratory")
    session.add(FacilityMedia(facility_id=f.id, cdn_url="u", source_type="wikimedia",
                              license_type="CC BY-SA 4.0", attribution_text=None,
                              verification_status="verified"))
    session.commit()
    assert len(find_issues(session)["MISSING_ATTRIBUTION"]) == 1


def test_source_city_mismatch() -> None:
    session = _session()
    f = _fac_loc(session, "Quest — Nashua", "300 Main St", "Nashua", "laboratory")
    session.add(FacilityMedia(facility_id=f.id, cdn_url="u", source_type="wikimedia",
                              attribution_text="Quest building in Manchester, NH",
                              license_type="CC BY-SA", verification_status="verified"))
    session.commit()
    issues = find_issues(session)
    assert len(issues["SOURCE_CITY_MISMATCH"]) == 1


def test_hospital_image_on_nonhospital() -> None:
    session = _session()
    f = _fac_loc(session, "Some Lab", "1 A St", "Nashua", "laboratory")
    session.add(FacilityMedia(facility_id=f.id, cdn_url="u", source_type="official_hospital",
                              verification_status="verified"))
    session.commit()
    assert len(find_issues(session)["HOSPITAL_IMAGE_ON_NONHOSPITAL"]) == 1


def test_clean_when_no_issues() -> None:
    session = _session()
    f = _fac_loc(session, "Quest — Nashua", "300 Main St", "Nashua", "laboratory")
    session.add(FacilityMedia(facility_id=f.id, cdn_url="u", source_type="wikimedia",
                              license_type="CC BY-SA", attribution_text="X / CC BY-SA",
                              alt_text="Exterior of Quest in Nashua", verification_status="verified"))
    session.commit()
    issues = find_issues(session)
    assert all(len(v) == 0 for v in issues.values())
