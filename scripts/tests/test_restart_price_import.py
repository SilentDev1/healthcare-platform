"""Regression test for restart_price_import: subquery delete + clean re-import.

The delete of a source's children must use a subquery on source_file_id, never a
materialized IN-list of record ids — a large source (97k+ rows) would exceed
PostgreSQL's 65535 bind-parameter limit. Here we prove the delete+re-import path is
functionally correct and leaves exactly one clean import (no duplicates).
"""

import uuid
from pathlib import Path
from unittest.mock import patch

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
    HospitalPriceRateDetail,
    HospitalPriceRecord,
    ImportRun,
    PriceServiceCode,
    SourceFile,
)
from packages.database.models import SourceStatus
from scripts.restart_price_import import _delete_records_in_chunks, restart
from scripts.seed_price_mappings import seed_price_mappings


def _seed_imported_source(session: Session, fixture: Path, ccn: str) -> tuple[uuid.UUID, int]:
    """Create a facility+source and import the fixture; return (source_file_id, rows)."""
    facility = Facility(
        cms_certification_number=ccn, legal_name="TEST HOSPITAL", display_name="Test"
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
    summary = import_price_source(session, price_source, HospitalPriceSettings())
    return source.id, summary.records_normalized


def _engine() -> Engine:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    return engine


def test_restart_deletes_then_reimports_without_duplicates(tmp_path: Path) -> None:
    fixture = generate_cms_wide_fixture(tmp_path / "mrf.csv", rows=80, payers=2, plans_per_payer=1)
    engine = _engine()
    with Session(engine) as session:
        source_file_id, rows = _seed_imported_source(session, fixture, ccn="990001")
        assert rows == 80
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


def test_delete_records_in_chunks_batches_and_clears_children(tmp_path: Path) -> None:
    """A small chunk_size must force multiple committed batches and leave no orphans.

    This is the large-source guard: the delete of 97k records + their rate-detail
    fan-out must not run as one un-batched, multi-hour transaction. With 80 records
    and chunk_size=10 the loop commits ~8 times; each child table is fully cleared.
    """
    fixture = generate_cms_wide_fixture(tmp_path / "mrf.csv", rows=80, payers=2, plans_per_payer=1)
    engine = _engine()
    with Session(engine) as session:
        source_file_id, rows = _seed_imported_source(session, fixture, ccn="990002")
        assert rows == 80
        # Children exist before the delete (otherwise the test would pass vacuously).
        assert (session.scalar(select(func.count(HospitalPriceRateDetail.id))) or 0) > 0
        assert (session.scalar(select(func.count(PriceServiceCode.id))) or 0) > 0

        with patch.object(session, "commit", wraps=session.commit) as spy_commit:
            deleted = _delete_records_in_chunks(session, source_file_id, chunk_size=10)

        assert deleted == 80
        # 80 records / 10 per chunk => 8 chunks, each committing once. Proves batching:
        # a single un-batched delete would have committed at most once here.
        assert spy_commit.call_count == 8

        # No records and no orphaned children of any kind remain.
        assert (session.scalar(select(func.count(HospitalPriceRecord.id))) or 0) == 0
        assert (session.scalar(select(func.count(HospitalPriceRateDetail.id))) or 0) == 0
        assert (session.scalar(select(func.count(PriceServiceCode.id))) or 0) == 0
    engine.dispose()
