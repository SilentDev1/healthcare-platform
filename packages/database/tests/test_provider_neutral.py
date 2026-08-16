"""Provider-neutral foundation: organization / location / capability / availability.

Proves the core separations the provider-neutral model requires:
- one organization owns many service locations;
- one location has many capabilities (ER and urgent care are DISTINCT);
- "service offered here" is modeled independently of "Carevero has a price";
so a verified location that offers a service with no Carevero price is representable
(and must render "price not available", never $0).
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from packages.database import (
    Base,
    Facility,
    FacilityLocation,
    LocationCapability,
    LocationServiceAvailability,
    Organization,
    Procedure,
)
from scripts.seed_procedure_catalog import seed_catalog


@pytest.fixture()
def session() -> Session:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    s = Session(engine)
    seed_catalog(s)
    s.commit()
    return s


def _location(facility: Facility, **kw: object) -> FacilityLocation:
    defaults: dict[str, object] = {
        "location_type": "hospital_campus",
        "address_line_1": "1 Main St",
        "city": "Nashua",
        "state": "NH",
        "postal_code": "03060",
    }
    defaults.update(kw)
    loc = FacilityLocation(facility=facility, **defaults)
    return loc


def test_one_organization_owns_many_locations(session: Session) -> None:
    org = Organization(
        canonical_name="Quest Diagnostics",
        display_name="Quest Diagnostics",
        organization_type="independent_lab",
    )
    nashua = Facility(legal_name="Quest — Nashua", display_name="Quest — Nashua", organization=org)
    manch = Facility(
        legal_name="Quest — Manchester", display_name="Quest — Manchester", organization=org
    )
    session.add_all([org, nashua, manch, _location(nashua), _location(manch, city="Manchester")])
    session.commit()

    fetched = session.get(Organization, org.id)
    assert fetched is not None
    assert {f.display_name for f in fetched.facilities} == {"Quest — Nashua", "Quest — Manchester"}
    # Organization type is NOT hospital — provider-neutral.
    assert fetched.organization_type == "independent_lab"


def test_location_has_many_capabilities_er_distinct_from_urgent_care(session: Session) -> None:
    org = Organization(canonical_name="Elliot Health", display_name="Elliot Health System")
    fac = Facility(legal_name="Elliot Hospital", display_name="Elliot Hospital", organization=org)
    loc = _location(fac)
    session.add_all([org, fac, loc])
    session.flush()
    for cap in ("hospital", "emergency_department", "laboratory", "imaging", "physical_therapy"):
        session.add(LocationCapability(facility_location_id=loc.id, capability=cap))
    session.commit()

    caps = {
        c.capability
        for c in session.scalars(
            select(LocationCapability).where(LocationCapability.facility_location_id == loc.id)
        )
    }
    assert caps == {"hospital", "emergency_department", "laboratory", "imaging", "physical_therapy"}
    # ER and urgent care are separate capability identifiers; ER present, urgent_care absent.
    assert "emergency_department" in caps
    assert "urgent_care" not in caps


def test_duplicate_capability_rejected(session: Session) -> None:
    fac = Facility(legal_name="X", display_name="X")
    loc = _location(fac)
    session.add_all([fac, loc])
    session.flush()
    session.add(LocationCapability(facility_location_id=loc.id, capability="laboratory"))
    session.commit()
    session.add(LocationCapability(facility_location_id=loc.id, capability="laboratory"))
    with pytest.raises(IntegrityError):
        session.commit()


def test_service_offered_without_price_is_representable(session: Session) -> None:
    """The crux: a lab that offers CBC but has no Carevero price is a valid state."""
    org = Organization(
        canonical_name="Quest", display_name="Quest", organization_type="independent_lab"
    )
    fac = Facility(legal_name="Quest — Nashua", display_name="Quest — Nashua", organization=org)
    loc = _location(fac, location_type="service_location")
    session.add_all([org, fac, loc])
    session.flush()
    session.add(
        LocationCapability(facility_location_id=loc.id, capability="independent_laboratory")
    )
    cbc = session.scalar(select(Procedure).where(Procedure.slug == "complete-blood-count"))
    assert cbc is not None
    session.add(
        LocationServiceAvailability(
            facility_location_id=loc.id,
            procedure_id=cbc.id,
            availability_status="offered",
        )
    )
    session.commit()

    avail = session.scalar(
        select(LocationServiceAvailability).where(
            LocationServiceAvailability.facility_location_id == loc.id,
            LocationServiceAvailability.procedure_id == cbc.id,
        )
    )
    assert avail is not None
    assert avail.availability_status == "offered"
    # There is NO price summary for this location/procedure — offered != priced.
    # (Price availability is the separate pricing chain; absence here means
    # "Price not currently available in Carevero", never $0.)


def test_availability_and_price_are_independent_states(session: Session) -> None:
    fac = Facility(legal_name="Y", display_name="Y")
    loc = _location(fac)
    session.add_all([fac, loc])
    session.flush()
    cmp_proc = session.scalar(
        select(Procedure).where(Procedure.slug == "comprehensive-metabolic-panel")
    )
    assert cmp_proc is not None
    # availability=unknown is valid even when a price might exist elsewhere.
    session.add(
        LocationServiceAvailability(
            facility_location_id=loc.id,
            procedure_id=cmp_proc.id,
            availability_status="unknown",
        )
    )
    session.commit()
    row = session.scalar(select(LocationServiceAvailability))
    assert row is not None
    assert row.availability_status in {"offered", "not_offered", "unknown"}


def test_duplicate_availability_rejected(session: Session) -> None:
    fac = Facility(legal_name="Z", display_name="Z")
    loc = _location(fac)
    session.add_all([fac, loc])
    session.flush()
    proc = session.scalar(select(Procedure))
    assert proc is not None
    session.add(
        LocationServiceAvailability(
            facility_location_id=loc.id, procedure_id=proc.id, availability_status="offered"
        )
    )
    session.commit()
    session.add(
        LocationServiceAvailability(
            facility_location_id=loc.id, procedure_id=proc.id, availability_status="not_offered"
        )
    )
    with pytest.raises(IntegrityError):
        session.commit()


def test_hospital_backfill_semantics_representable(session: Session) -> None:
    """Existing hospital: 1 org (1:1), one location with 'hospital' capability."""
    org_id = uuid.uuid4()
    org = Organization(
        id=org_id,
        canonical_name="Concord Hospital",
        display_name="Concord Hospital",
        organization_type="hospital_system",
    )
    fac = Facility(
        id=org_id,  # backfill reuses the facility UUID as the org id
        legal_name="Concord Hospital",
        display_name="Concord Hospital",
        cms_certification_number="300001",
        organization_id=org_id,
    )
    loc = _location(fac)
    session.add_all([org, fac, loc])
    session.flush()
    session.add(LocationCapability(facility_location_id=loc.id, capability="hospital"))
    session.commit()

    assert fac.organization_id == org.id
    assert fac.organization is not None
    assert fac.organization.organization_type == "hospital_system"
    assert [c.capability for c in loc.capabilities] == ["hospital"]
