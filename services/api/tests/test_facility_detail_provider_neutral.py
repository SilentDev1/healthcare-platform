"""Facility detail is provider-neutral: capabilities + organization + hospital-only gate.

The is_hospital flag gates hospital-only UI (CMS quality). A hospital reports is_hospital
True; an independent lab reports is_hospital False so CMS quality never renders for it.
"""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from packages.database import (
    Base,
    Facility,
    FacilityLocation,
    LocationCapability,
    Organization,
)
from services.api.app.main import get_facility


def _session() -> Session:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    return Session(engine)


def _location(fac: Facility, **kw: object) -> FacilityLocation:
    defaults: dict[str, object] = {
        "location_type": "hospital_campus",
        "address_line_1": "1 Main",
        "city": "Nashua",
        "state": "NH",
        "postal_code": "03060",
    }
    defaults.update(kw)
    return FacilityLocation(facility=fac, **defaults)


def test_hospital_detail_is_hospital_true_with_capabilities() -> None:
    session = _session()
    org = Organization(
        canonical_name="Concord", display_name="Concord", organization_type="hospital_system"
    )
    fac = Facility(
        legal_name="Concord Hospital",
        display_name="Concord Hospital",
        cms_certification_number="300001",
        organization=org,
    )
    loc = _location(fac)
    session.add_all([org, fac, loc])
    session.flush()
    session.add(LocationCapability(facility_location_id=loc.id, capability="hospital"))
    session.commit()

    resp = get_facility(fac.id, session)
    assert resp.is_hospital is True
    assert "hospital" in resp.capabilities
    assert resp.organization_type == "hospital_system"


def test_lab_detail_is_hospital_false_never_shows_hospital_quality() -> None:
    session = _session()
    org = Organization(
        canonical_name="Quest",
        display_name="Quest Diagnostics",
        organization_type="independent_lab",
    )
    fac = Facility(
        legal_name="Quest — Nashua",
        display_name="Quest Diagnostics — Nashua",
        cms_certification_number=None,  # labs have no CCN
        organization=org,
    )
    loc = _location(fac, location_type="service_location")
    session.add_all([org, fac, loc])
    session.flush()
    session.add(LocationCapability(facility_location_id=loc.id, capability="laboratory"))
    session.commit()

    resp = get_facility(fac.id, session)
    # The crux: a non-hospital location must report is_hospital False so the web hides
    # CMS quality / hospital schema for it.
    assert resp.is_hospital is False
    assert resp.capabilities == ["laboratory"]
    assert resp.organization_name == "Quest Diagnostics"
    assert resp.organization_type == "independent_lab"
