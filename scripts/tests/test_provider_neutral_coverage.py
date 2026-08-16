"""Provider-neutral observability metrics, incl. the offered != priced split."""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from packages.database import (
    Base,
    Facility,
    FacilityLocation,
    FacilityPriceSource,
    LocationCapability,
    LocationServiceAvailability,
    Organization,
    Procedure,
)
from scripts.provider_neutral_coverage import provider_coverage
from scripts.seed_procedure_catalog import seed_catalog


@pytest.fixture()
def session() -> Session:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    s = Session(engine)
    seed_catalog(s)
    s.commit()
    return s


def test_counts_orgs_locations_capabilities_and_offered_vs_priced(session: Session) -> None:
    lab = Organization(
        canonical_name="Quest", display_name="Quest", organization_type="independent_lab"
    )
    hospital = Organization(
        canonical_name="Concord", display_name="Concord", organization_type="hospital_system"
    )
    lab_fac = Facility(legal_name="Quest — Nashua", display_name="Quest — Nashua", organization=lab)
    hosp_fac = Facility(legal_name="Concord", display_name="Concord", organization=hospital)
    lab_loc = FacilityLocation(
        facility=lab_fac, address_line_1="1", city="Nashua", state="NH", postal_code="03060"
    )
    hosp_loc = FacilityLocation(
        facility=hosp_fac, address_line_1="2", city="Concord", state="NH", postal_code="03301"
    )
    session.add_all([lab, hospital, lab_fac, hosp_fac, lab_loc, hosp_loc])
    session.flush()

    session.add_all(
        [
            LocationCapability(
                facility_location_id=lab_loc.id, capability="independent_laboratory"
            ),
            LocationCapability(facility_location_id=hosp_loc.id, capability="hospital"),
            LocationCapability(facility_location_id=hosp_loc.id, capability="laboratory"),
        ]
    )
    cbc = session.scalar(select(Procedure).where(Procedure.slug == "complete-blood-count"))
    bmp = session.scalar(select(Procedure).where(Procedure.slug == "basic-metabolic-panel"))
    assert cbc is not None and bmp is not None

    # Lab offers CBC and BMP (verified) but Carevero has NO price for either.
    session.add_all(
        [
            LocationServiceAvailability(
                facility_location_id=lab_loc.id, procedure_id=cbc.id, availability_status="offered"
            ),
            LocationServiceAvailability(
                facility_location_id=lab_loc.id, procedure_id=bmp.id, availability_status="offered"
            ),
        ]
    )
    session.add(
        FacilityPriceSource(
            facility_id=lab_fac.id,
            source_type="provider_published_price",
            machine_readable_file_url="https://quest.example/prices",
            discovery_method="manual",
            source_class="PROVIDER_PUBLISHED_PRICE",
        )
    )
    session.commit()

    cov = provider_coverage(session)
    assert cov["organizations_total"] == 2
    assert cov["organizations_by_type"] == {"independent_lab": 1, "hospital_system": 1}
    assert cov["service_locations_total"] == 2
    assert cov["locations_by_capability"] == {
        "independent_laboratory": 1,
        "hospital": 1,
        "laboratory": 1,
    }
    assert cov["services_verified_offered"] == 2
    # The critical separation: both offered services have NO Carevero price and are
    # counted as offered-without-price — never as $0, never hidden.
    assert cov["offered_services_with_published_price"] == 0
    assert cov["offered_services_without_published_price"] == 2
    assert cov["price_sources_by_class"] == {"PROVIDER_PUBLISHED_PRICE": 1}


def test_empty_is_all_zero_not_error(session: Session) -> None:
    cov = provider_coverage(session)
    assert cov["organizations_total"] == 0
    assert cov["service_locations_total"] == 0
    assert cov["offered_services_without_published_price"] == 0
