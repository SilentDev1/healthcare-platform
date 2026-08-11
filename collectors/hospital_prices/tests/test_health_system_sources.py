import uuid

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from collectors.hospital_prices.health_systems import propagate_system_sources
from collectors.hospital_prices.inventory import HealthSystemEntry, HospitalInventory
from packages.database import Base, Facility, FacilityPriceSource


def _inventory() -> HospitalInventory:
    system = HealthSystemEntry(
        name="Example System", domain="example.org", members=["HOSPITAL A", "HOSPITAL B"]
    )
    return HospitalInventory([], {system.name: system}, {}, {})


def test_facility_specific_source_is_not_propagated() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        first = Facility(
            id=uuid.uuid4(), legal_name="HOSPITAL A", display_name="Hospital A", active=True
        )
        second = Facility(
            id=uuid.uuid4(), legal_name="HOSPITAL B", display_name="Hospital B", active=True
        )
        session.add_all([first, second])
        session.flush()
        session.add(
            FacilityPriceSource(
                facility_id=first.id,
                source_type="hospital_mrf",
                machine_readable_file_url="https://example.org/hospital-a.json",
                discovery_method="cms_hpt_txt",
                active=True,
                file_role="standard_charges",
            )
        )
        session.commit()

        result = propagate_system_sources(session, _inventory())

        assert result["Example System"] == 0
        assert (
            session.scalar(
                select(FacilityPriceSource).where(FacilityPriceSource.facility_id == second.id)
            )
            is None
        )


def test_explicit_multi_facility_source_can_be_propagated() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        first = Facility(
            id=uuid.uuid4(), legal_name="HOSPITAL A", display_name="Hospital A", active=True
        )
        second = Facility(
            id=uuid.uuid4(), legal_name="HOSPITAL B", display_name="Hospital B", active=True
        )
        session.add_all([first, second])
        session.flush()
        session.add(
            FacilityPriceSource(
                facility_id=first.id,
                source_type="hospital_mrf_directory",
                machine_readable_file_url="https://example.org/system-directory.json",
                discovery_method="verified_system_directory",
                active=True,
                file_role="health_system_directory",
            )
        )
        session.commit()

        result = propagate_system_sources(session, _inventory())

        assert result["Example System"] == 1
        propagated = session.scalar(
            select(FacilityPriceSource).where(FacilityPriceSource.facility_id == second.id)
        )
        assert propagated is not None
        assert propagated.discovery_method == "health_system_propagation"
