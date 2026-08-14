"""Regression test for restart_price_import: subquery delete + clean re-import.

The delete of a source's children must use a subquery on source_file_id, never a
materialized IN-list of record ids — a large source (97k+ rows) would exceed
PostgreSQL's 65535 bind-parameter limit. Here we prove the delete+re-import path is
functionally correct and leaves exactly one clean import (no duplicates).
"""

from pathlib import Path

from sqlalchemy import Engine, create_engine, func, select
from sqlalchemy.orm import Session

from collectors.hospital_prices.config import HospitalPriceSettings
from collectors.hospital_prices.fixture_generator import generate_cms_wide_fixture
from collectors.hospital_prices.importer import import_price_source
from collectors.hospital_prices.normalization import seed_payers
from packages.database import (
    Base,
    Facility,
    FacilityLocation,
    FacilityPriceSource,
    HospitalPriceRecord,
    ImportRun,
    PriceServiceCode,
    SourceFile,
)
from packages.database.models import SourceStatus
from scripts.restart_price_import import restart
from scripts.seed_price_mappings import seed_price_mappings


def _engine() -> Engine:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    return engine


def test_restart_deletes_then_reimports_without_duplicates(tmp_path: Path) -> None:
    fixture = generate_cms_wide_fixture(tmp_path / "mrf.csv", rows=80, payers=2, plans_per_payer=1)
    engine = _engine()
    with Session(engine) as session:
        facility = Facility(
            cms_certification_number="990001", legal_name="TEST HOSPITAL", display_name="Test"
        )
        facility.locations.append(
            FacilityLocation(
                address_line_1="1 Test St", city="Concord", state="NH", postal_code="03301"
            )
        )
        session.add(facility)
        session.flush()
        seed_payers(session)
        seed_price_mappings(session)
        source = SourceFile(
            source_name="mrf",
            source_url=fixture.resolve().as_uri(),
            source_type="hospital_price_mrf",
            storage_path=str(fixture),
            checksum_sha256="f" * 64,
            file_size=fixture.stat().st_size,
            parser_version="1.0.0",
            status=SourceStatus.COMPLETED,
        )
        session.add(source)
        session.flush()
        price_source = FacilityPriceSource(
            facility_id=facility.id,
            source_type="hospital_mrf",
            source_page_url="https://example.test/prices",
            machine_readable_file_url=fixture.resolve().as_uri(),
            declared_format="csv",
            active=True,
            discovery_method="test",
            source_file_id=source.id,
        )
        session.add(price_source)
        session.flush()
        source_file_id = source.id

        first = import_price_source(session, price_source, HospitalPriceSettings())
        assert first.records_normalized == 80
        codes_before = session.scalar(select(func.count(PriceServiceCode.id)))

        # Re-import from scratch (what a crosswalk change requires).
        summary = restart(source_file_id, session=session)
        assert summary.records_normalized == 80

    with Session(engine) as verify:
        # Exactly one clean set of records — the old ones were deleted, not duplicated.
        records = verify.scalar(select(func.count(HospitalPriceRecord.id))) or 0
        assert records == 80
        codes_after = verify.scalar(select(func.count(PriceServiceCode.id))) or 0
        assert codes_after == codes_before
        # Old import run(s) removed; a single fresh completed run remains.
        runs = verify.scalars(select(ImportRun)).all()
        assert len(runs) == 1
    engine.dispose()
