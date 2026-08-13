"""Resumable large-MRF import: per-batch commits, safe resume, no duplicates.

Very large MRFs cannot finish inside a single platform task window. These tests
prove the importer commits progress per batch, resumes from the active checkpoint
on a later invocation (whether stopped by the soft deadline or by a mid-import
crash), and never re-imports already-committed rows.
"""

import time
from pathlib import Path

import pytest
from sqlalchemy import Engine, create_engine, func, select
from sqlalchemy.orm import Session

from collectors.hospital_prices import importer as importer_module
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
    ImportCheckpoint,
    ImportRun,
    PriceServiceCode,
    SourceFile,
)
from packages.database.models import ImportStatus, SourceStatus
from scripts.seed_price_mappings import seed_price_mappings


class _Clock:
    """Deterministic monotonic clock: first reading 0, all later readings huge.

    Lets a test trip the soft deadline at the first committed-batch boundary
    without depending on real wall-clock time.
    """

    def __init__(self, readings_at_zero: int = 1) -> None:
        self._calls = 0
        self._readings_at_zero = readings_at_zero

    def __call__(self) -> float:
        self._calls += 1
        return 0.0 if self._calls <= self._readings_at_zero else 10_000.0


def _engine() -> Engine:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    return engine


def _seed_facility(session: Session, ccn: str = "990001") -> Facility:
    facility = Facility(
        cms_certification_number=ccn,
        legal_name="TEST HOSPITAL",
        display_name="Test Hospital",
    )
    facility.locations.append(
        FacilityLocation(
            address_line_1="1 Test St", city="Concord", state="NH", postal_code="03301"
        )
    )
    session.add(facility)
    session.flush()
    return facility


def _price_source(
    session: Session, facility: Facility, fixture: Path, settings: HospitalPriceSettings
) -> FacilityPriceSource:
    source = SourceFile(
        source_name="mrf",
        source_url=fixture.resolve().as_uri(),
        source_type="hospital_price_mrf",
        storage_path=str(fixture),
        checksum_sha256="d" * 64,
        file_size=fixture.stat().st_size,
        parser_version=settings.hospital_price_parser_version,
        status=SourceStatus.DOWNLOADED,
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
    return price_source


def _counts(session: Session, facility_id: object) -> tuple[int, int]:
    """(records, distinct source_record_identifiers) for a facility."""
    records = (
        session.scalar(
            select(func.count(HospitalPriceRecord.id)).where(
                HospitalPriceRecord.facility_id == facility_id
            )
        )
        or 0
    )
    distinct_ids = (
        session.scalar(
            select(func.count(func.distinct(HospitalPriceRecord.source_record_identifier))).where(
                HospitalPriceRecord.facility_id == facility_id
            )
        )
        or 0
    )
    return records, distinct_ids


def test_soft_deadline_stops_then_resumes_without_duplicates(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = generate_cms_wide_fixture(tmp_path / "big.csv", rows=120, payers=2, plans_per_payer=1)
    engine = _engine()
    with Session(engine) as session:
        facility = _seed_facility(session)
        facility_id = facility.id
        seed_payers(session)
        seed_price_mappings(session)
        price_source = _price_source(
            session, facility, fixture, HospitalPriceSettings(hospital_price_batch_size=20)
        )
        source_file_id = price_source.source_file_id
        session.commit()

        # First run: soft deadline trips at the first committed batch. The importer
        # calls the same `time` module, so patching it here controls its clock.
        monkeypatch.setattr(time, "monotonic", _Clock(readings_at_zero=1))
        first = import_price_source(
            session,
            price_source,
            HospitalPriceSettings(
                hospital_price_batch_size=20,
                hospital_price_import_soft_deadline_seconds=1,
            ),
        )
        assert first.interrupted is True
        assert 0 < first.records_normalized < 120
        committed_after_first = first.records_normalized

        # Durable: the partial batch is committed, run is resumable, checkpoint active.
        run = session.scalar(select(ImportRun).where(ImportRun.source_file_id == source_file_id))
        assert run is not None and run.status == ImportStatus.INTERRUPTED
        checkpoint = session.scalar(
            select(ImportCheckpoint).where(ImportCheckpoint.source_file_id == source_file_id)
        )
        assert checkpoint is not None and checkpoint.status == "active"
        records, distinct_ids = _counts(session, facility_id)
        assert records == committed_after_first
        assert records == distinct_ids  # no duplicates in the committed partial

        # Second run: no deadline — resumes from the checkpoint and completes.
        second = import_price_source(
            session,
            price_source,
            HospitalPriceSettings(hospital_price_batch_size=20),
        )
        assert second.interrupted is False
        assert second.skipped_unchanged is False
        assert second.records_normalized == 120  # resumed count + newly imported

    with Session(engine) as verify:
        records, distinct_ids = _counts(verify, facility_id)
        assert records == 120  # every row imported exactly once
        assert distinct_ids == 120  # no duplicate records
        # Exactly one checkpoint, now completed; exactly one run, now completed.
        checkpoints = verify.scalars(select(ImportCheckpoint)).all()
        assert len(checkpoints) == 1 and checkpoints[0].status == "completed"
        runs = verify.scalars(select(ImportRun)).all()
        assert len(runs) == 1 and runs[0].status in (
            ImportStatus.COMPLETED,
            ImportStatus.COMPLETED_WITH_ERRORS,
        )
        # Codes were written for the resumed rows too (children follow their records).
        code_count = verify.scalar(select(func.count(PriceServiceCode.id))) or 0
        assert code_count == 120
    engine.dispose()


def test_crash_mid_import_leaves_resumable_checkpoint_and_completes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = generate_cms_wide_fixture(
        tmp_path / "crash.csv", rows=100, payers=2, plans_per_payer=1
    )
    engine = _engine()

    real_flush = importer_module._flush_batch
    state = {"calls": 0}

    def flaky_flush(session, batch, caches, profiler):  # type: ignore[no-untyped-def]
        state["calls"] += 1
        # Let the first batch commit, then crash during the second flush.
        if state["calls"] == 2:
            raise RuntimeError("simulated crash mid-import")
        return real_flush(session, batch, caches, profiler)

    with Session(engine) as session:
        facility = _seed_facility(session)
        facility_id = facility.id
        seed_payers(session)
        seed_price_mappings(session)
        price_source = _price_source(
            session, facility, fixture, HospitalPriceSettings(hospital_price_batch_size=20)
        )
        source_file_id = price_source.source_file_id
        session.commit()

        monkeypatch.setattr(importer_module, "_flush_batch", flaky_flush)
        with pytest.raises(RuntimeError, match="simulated crash"):
            import_price_source(
                session, price_source, HospitalPriceSettings(hospital_price_batch_size=20)
            )

        # First batch survived the crash; run is resumable, not FAILED.
        run = session.scalar(select(ImportRun).where(ImportRun.source_file_id == source_file_id))
        assert run is not None and run.status == ImportStatus.INTERRUPTED
        records, distinct_ids = _counts(session, facility_id)
        assert 0 < records < 100
        assert records == distinct_ids
        first_batch_records = records

        # Recovery run (no crash) resumes and finishes with no duplicates.
        monkeypatch.setattr(importer_module, "_flush_batch", real_flush)
        summary = import_price_source(
            session, price_source, HospitalPriceSettings(hospital_price_batch_size=20)
        )
        assert summary.records_normalized == 100
        assert summary.records_normalized > first_batch_records

    with Session(engine) as verify:
        records, distinct_ids = _counts(verify, facility_id)
        assert records == 100
        assert distinct_ids == 100
        runs = verify.scalars(select(ImportRun)).all()
        assert len(runs) == 1
        assert runs[0].status in (ImportStatus.COMPLETED, ImportStatus.COMPLETED_WITH_ERRORS)
    engine.dispose()


def test_completed_import_is_not_resumed_or_duplicated(tmp_path: Path) -> None:
    fixture = generate_cms_wide_fixture(tmp_path / "done.csv", rows=60, payers=2, plans_per_payer=1)
    engine = _engine()
    with Session(engine) as session:
        facility = _seed_facility(session)
        facility_id = facility.id
        seed_payers(session)
        seed_price_mappings(session)
        price_source = _price_source(
            session, facility, fixture, HospitalPriceSettings(hospital_price_batch_size=25)
        )
        session.commit()

        first = import_price_source(
            session, price_source, HospitalPriceSettings(hospital_price_batch_size=25)
        )
        assert first.records_normalized == 60
        assert first.skipped_unchanged is False

        # A completed source is a no-op — never re-imported, never duplicated.
        second = import_price_source(
            session, price_source, HospitalPriceSettings(hospital_price_batch_size=25)
        )
        assert second.skipped_unchanged is True

        records, distinct_ids = _counts(session, facility_id)
        assert records == 60 == distinct_ids
    engine.dispose()
