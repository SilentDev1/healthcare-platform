import uuid
from pathlib import Path

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from collectors.nppes_organizations.config import NppesSettings
from collectors.nppes_organizations.importer import run_import
from packages.database import (
    Base,
    Facility,
    FacilityAlias,
    FacilityIdentifier,
    FacilityIdentityCandidate,
    FacilityLocation,
    SourceFile,
)
from packages.database.models import SourceStatus
from packages.identity import (
    IdentityInput,
    match_facility,
    normalize_address,
    normalize_domain,
    normalize_name,
    normalize_phone,
)
from packages.search import rebuild_index, search
from scripts.seed_procedure_catalog import SERVICES, seed_catalog


def test_normalization_is_deterministic() -> None:
    assert normalize_name("Acme Health, Inc.") == "acme health"
    assert normalize_address("1 Main Street") == "1 main st"
    assert normalize_phone("+1 (603) 555-0100") == "6035550100"
    assert normalize_domain("https://www.example.org/path") == "example.org"


def _seed_facility(session: Session) -> Facility:
    source = SourceFile(
        source_name="CMS",
        source_url="https://data.cms.gov/test.csv",
        source_type="cms_hospitals_csv",
        storage_path="test.csv",
        checksum_sha256="a" * 64,
        file_size=1,
        parser_version="test",
        status=SourceStatus.COMPLETED,
    )
    session.add(source)
    session.flush()
    facility = Facility(
        id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
        cms_certification_number="300001",
        legal_name="CONCORD HOSPITAL",
        display_name="Concord Hospital",
        facility_type="Acute Care Hospitals",
        phone="6032252711",
        source_file_id=source.id,
    )
    facility.locations.append(
        FacilityLocation(
            address_line_1="250 PLEASANT ST", city="CONCORD", state="NH", postal_code="03301"
        )
    )
    session.add(facility)
    session.flush()
    return facility


def test_identity_nppes_catalog_and_search_are_idempotent(tmp_path: Path) -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        facility = _seed_facility(session)
        session.add(
            FacilityAlias(
                facility_id=facility.id,
                alias_name="Concord Health",
                normalized_alias="concord health",
                alias_type="trade",
            )
        )
        session.commit()
        address_match = match_facility(
            session, IdentityInput(name="Concord Hospital", address="250 Pleasant Street")
        )
        assert address_match.exact and address_match.method == "exact_name_address"
        name_only = match_facility(session, IdentityInput(name="Concord Health"))
        assert not name_only.exact and name_only.method == "name_only"
        settings = NppesSettings(nppes_raw_data_dir=tmp_path)
        fixture = Path("data/fixtures/nppes_organizations.json")
        first = run_import(session, fixture, settings)
        second = run_import(session, fixture, settings)
        assert first.facilities_matched == 1
        assert first.candidates_created == 2
        assert second.skipped_unchanged
        assert (
            session.scalar(
                select(func.count(FacilityIdentifier.id)).where(
                    FacilityIdentifier.identifier_type == "NPI_ORGANIZATION"
                )
            )
            == 1
        )
        assert session.scalar(select(func.count(FacilityIdentityCandidate.id))) == 2
        one = seed_catalog(session)
        two = seed_catalog(session)
        assert one.procedures == two.procedures == len(SERVICES) == 50
        assert rebuild_index(session) == 63
        assert rebuild_index(session) == 63
        assert search(session, "MRI brain")[0].entity_type == "procedure"
        assert search(session, "Concord Hospital")[0].entity_type == "facility"
        assert search(session, "Concor", state="NH")[0].match_reason == "prefix_or_phrase"
    engine.dispose()
