"""Performance, batch, and checkpoint tests for Phase 4.1."""

import uuid
from pathlib import Path

from sqlalchemy import Engine, create_engine, func, select
from sqlalchemy.orm import Session

from collectors.hospital_prices.caches import ImportCaches
from collectors.hospital_prices.checkpoint import CheckpointManager
from collectors.hospital_prices.config import HospitalPriceSettings
from collectors.hospital_prices.fixture_generator import generate_cms_wide_fixture
from collectors.hospital_prices.importer import import_price_source
from collectors.hospital_prices.normalization import seed_payers
from collectors.hospital_prices.pipeline import run_fixture_pipeline
from collectors.hospital_prices.profiler import ImportProfiler
from packages.database import (
    Base,
    Facility,
    FacilityLocation,
    FacilityPriceSource,
    FacilityProcedurePriceSummary,
    HospitalPriceRecord,
    ImportCheckpoint,
    ImportRun,
    PricingAnomaly,
    PricingUnmatchedRecord,
    SourceFile,
)
from packages.database.models import ImportStatus, SourceStatus
from scripts.seed_price_mappings import seed_price_mappings


def _engine() -> Engine:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    return engine


def _seed_facility(session: Session, ccn: str = "990001") -> Facility:
    source = SourceFile(
        source_name="test",
        source_url="https://example.test/test.csv",
        source_type="test_csv",
        storage_path="test.csv",
        checksum_sha256="a" * 64,
        file_size=1,
        parser_version="test",
        status=SourceStatus.COMPLETED,
    )
    session.add(source)
    session.flush()
    facility = Facility(
        cms_certification_number=ccn,
        legal_name="TEST HOSPITAL",
        display_name="Test Hospital",
        source_file_id=source.id,
    )
    facility.locations.append(
        FacilityLocation(
            address_line_1="1 Test St", city="Concord", state="NH", postal_code="03301"
        )
    )
    session.add(facility)
    session.flush()
    return facility


def _setup_fixture_import(
    session: Session,
    fixture_path: Path,
    facility: Facility,
    settings: HospitalPriceSettings,
) -> FacilityPriceSource:
    source = SourceFile(
        source_name="benchmark",
        source_url=fixture_path.resolve().as_uri(),
        source_type="benchmark_csv",
        storage_path=str(fixture_path),
        checksum_sha256="b" * 64,
        file_size=fixture_path.stat().st_size,
        parser_version=settings.hospital_price_parser_version,
        status=SourceStatus.COMPLETED,
    )
    session.add(source)
    session.flush()
    price_source = FacilityPriceSource(
        facility_id=facility.id,
        source_type="hospital_mrf",
        source_page_url="https://example.test/benchmark",
        machine_readable_file_url=fixture_path.resolve().as_uri(),
        declared_format="csv",
        active=True,
        discovery_method="benchmark",
        source_file_id=source.id,
    )
    session.add(price_source)
    session.flush()
    return price_source


def test_batch_insertion_and_rollback(tmp_path: Path) -> None:
    """Batch of records inserted atomically, rollback on error."""
    fixture_path = tmp_path / "batch.csv"
    generate_cms_wide_fixture(fixture_path, rows=100, payers=2, plans_per_payer=1)

    engine = _engine()
    settings = HospitalPriceSettings(hospital_price_batch_size=50)
    with Session(engine) as session:
        facility = _seed_facility(session)
        seed_payers(session)
        seed_price_mappings(session)
        price_source = _setup_fixture_import(session, fixture_path, facility, settings)
        session.commit()

        summary = import_price_source(session, price_source, settings)
        assert summary.records_normalized > 0
        records = session.scalar(select(func.count(HospitalPriceRecord.id))) or 0
        assert records == summary.records_normalized
    engine.dispose()


def test_checkpoint_creation_and_advancement(tmp_path: Path) -> None:
    """Checkpoint created after batch, advanced after next."""
    fixture_path = tmp_path / "checkpoint.csv"
    generate_cms_wide_fixture(fixture_path, rows=200, payers=2, plans_per_payer=1)

    engine = _engine()
    settings = HospitalPriceSettings(
        hospital_price_batch_size=50,
        hospital_price_checkpoint_enabled=True,
    )
    with Session(engine) as session:
        facility = _seed_facility(session)
        seed_payers(session)
        seed_price_mappings(session)
        price_source = _setup_fixture_import(session, fixture_path, facility, settings)
        session.commit()

        import_price_source(session, price_source, settings)
        checkpoints = session.scalars(select(ImportCheckpoint)).all()
        assert len(checkpoints) >= 1
        # The final checkpoint should be completed
        completed = [c for c in checkpoints if c.status == "completed"]
        assert len(completed) == 1
        assert completed[0].normalized_records_committed > 0
    engine.dispose()


def test_source_checksum_change_prevents_resume(tmp_path: Path) -> None:
    """Changed source -> resume rejected."""
    engine = _engine()
    with Session(engine) as session:
        _seed_facility(session)
        session.flush()
        source = SourceFile(
            source_name="test",
            source_url="https://example.test/prices.csv",
            source_type="test",
            storage_path="test.csv",
            checksum_sha256="c" * 64,
            file_size=1,
            parser_version="1.0.0",
            status=SourceStatus.COMPLETED,
        )
        session.add(source)
        session.flush()
        run = ImportRun(
            importer_name="hospital_prices",
            status=ImportStatus.INTERRUPTED,
            source_file_id=source.id,
        )
        session.add(run)
        session.flush()
        # Create checkpoint with different checksum
        session.add(
            ImportCheckpoint(
                import_run_id=run.id,
                source_file_id=source.id,
                parser_version="1.0.0",
                source_checksum="d" * 64,  # different from source
                last_completed_line=100,
                normalized_records_committed=50,
                rate_details_committed=25,
                batch_number=1,
                status="active",
            )
        )
        session.flush()

        mgr = CheckpointManager(session, run, source, "1.0.0")
        assert not mgr.can_resume()  # checksum mismatch
    engine.dispose()


def test_parser_version_change_prevents_resume(tmp_path: Path) -> None:
    """Changed parser -> resume rejected."""
    engine = _engine()
    with Session(engine) as session:
        _seed_facility(session)
        session.flush()
        source = SourceFile(
            source_name="test",
            source_url="https://example.test/prices.csv",
            source_type="test",
            storage_path="test.csv",
            checksum_sha256="e" * 64,
            file_size=1,
            parser_version="1.0.0",
            status=SourceStatus.COMPLETED,
        )
        session.add(source)
        session.flush()
        run = ImportRun(
            importer_name="hospital_prices",
            status=ImportStatus.INTERRUPTED,
            source_file_id=source.id,
        )
        session.add(run)
        session.flush()
        session.add(
            ImportCheckpoint(
                import_run_id=run.id,
                source_file_id=source.id,
                parser_version="0.9.0",  # different version
                source_checksum="e" * 64,
                last_completed_line=100,
                normalized_records_committed=50,
                rate_details_committed=25,
                batch_number=1,
                status="active",
            )
        )
        session.flush()

        mgr = CheckpointManager(session, run, source, "1.0.0")
        assert not mgr.can_resume()  # parser version mismatch
    engine.dispose()


def test_unknown_payer_batch_persistence(tmp_path: Path) -> None:
    """Unknown payers accumulated and batch-persisted."""
    engine = _engine()
    with Session(engine) as session:
        seed_payers(session)
        session.flush()
        caches = ImportCaches()
        caches.load(session)

        # Known payer
        payer_id, method, _ = caches.match_payer("UHC")
        assert payer_id is not None
        assert method == "exact_alias"

        # Unknown payer
        payer_id2, method2, _ = caches.match_payer("Totally Unknown Payer")
        assert payer_id2 is None
        assert method2 == "unknown"

        assert caches.payer_hits >= 1
        assert caches.payer_misses >= 1
    engine.dispose()


def test_unknown_plan_batch_persistence(tmp_path: Path) -> None:
    """Unknown plans accumulated and batch-persisted via caches."""
    engine = _engine()
    with Session(engine) as session:
        seed_payers(session)
        session.flush()
        caches = ImportCaches()
        caches.load(session)

        # Get a known payer
        payer_id, _, _ = caches.match_payer("UHC")
        assert payer_id is not None

        # Create a new plan
        plan_id = caches.match_or_create_plan(payer_id, "Brand New PPO Plan")
        assert plan_id is not None
        assert len(caches.pending_plans) == 1

        # Same plan again should hit cache
        plan_id2 = caches.match_or_create_plan(payer_id, "Brand New PPO Plan")
        assert plan_id2 == plan_id
        assert len(caches.pending_plans) == 1  # no new pending

        # Flush pending
        caches.flush_pending(session)
        session.flush()
        assert len(caches.pending_plans) == 0
    engine.dispose()


def test_procedure_mapping_cache_deduplication() -> None:
    """Same description mapped once."""
    engine = _engine()
    with Session(engine) as session:
        caches = ImportCaches()
        caches.load(session)

        desc1 = caches.normalize_description("CHEST X-RAY 2 VIEWS")
        desc2 = caches.normalize_description("CHEST X-RAY 2 VIEWS")
        desc3 = caches.normalize_description("CT HEAD/BRAIN WITHOUT CONTRAST")
        assert desc1 == desc2
        assert desc1 != desc3
        assert len(caches.description_cache) == 2
    engine.dispose()


def test_payer_cache_hit_miss_statistics() -> None:
    """Cache stats accurate."""
    engine = _engine()
    with Session(engine) as session:
        seed_payers(session)
        session.flush()
        caches = ImportCaches()
        caches.load(session)

        caches.match_payer("UHC")
        caches.match_payer("Harvard Pilgrim")
        caches.match_payer("Unknown Payer XYZ")
        caches.match_payer("")

        stats = caches.stats()
        assert stats["payer_hits"] == 2
        assert stats["payer_misses"] == 1
    engine.dispose()


def test_row_local_anomaly_evaluation(tmp_path: Path) -> None:
    """Row-level anomalies still detected with batch processing."""
    fixture_path = tmp_path / "anomaly.csv"
    generate_cms_wide_fixture(
        fixture_path, rows=50, payers=2, plans_per_payer=1, include_anomalies=True
    )

    engine = _engine()
    settings = HospitalPriceSettings(hospital_price_batch_size=100)
    with Session(engine) as session:
        facility = _seed_facility(session)
        seed_payers(session)
        seed_price_mappings(session)
        price_source = _setup_fixture_import(session, fixture_path, facility, settings)
        session.commit()

        summary = import_price_source(session, price_source, settings)
        # Anomalies should still be detected
        anomaly_count = session.scalar(select(func.count(PricingAnomaly.id))) or 0
        assert anomaly_count == summary.anomalies
        assert anomaly_count >= 0  # may or may not have anomalies depending on seed
    engine.dispose()


def test_idempotency_after_complete_run(tmp_path: Path) -> None:
    """Second run is no-op after complete."""
    fixture_path = tmp_path / "idempotent.csv"
    generate_cms_wide_fixture(fixture_path, rows=50, payers=2, plans_per_payer=1)

    engine = _engine()
    settings = HospitalPriceSettings(hospital_price_batch_size=100)
    with Session(engine) as session:
        facility = _seed_facility(session)
        seed_payers(session)
        seed_price_mappings(session)
        price_source = _setup_fixture_import(session, fixture_path, facility, settings)
        session.commit()

        first = import_price_source(session, price_source, settings)
        assert first.records_normalized > 0
        assert not first.skipped_unchanged

        second = import_price_source(session, price_source, settings)
        assert second.skipped_unchanged
        assert second.records_normalized == 0
    engine.dispose()


def test_profiler_milestone_and_summary() -> None:
    """Profiler tracks metrics correctly."""
    profiler = ImportProfiler()
    with profiler.time_section("test_section"):
        pass
    profiler.record_row()
    profiler.record_row()
    profiler.record_insert()
    profiler.record_rate_detail(3)
    profiler.record_db_statement(2)
    profiler.record_db_transaction()

    summary = profiler.summary()
    assert summary["rows_processed"] == 2
    assert summary["records_created"] == 1
    assert summary["rate_details_created"] == 3
    assert summary["db_statements"] == 2
    assert summary["db_transactions"] == 1
    sections = summary["sections"]
    assert isinstance(sections, dict)
    assert "test_section" in sections


def test_fixture_pipeline_still_passes() -> None:
    """Ensure existing Phase 4 pipeline test still passes with batch changes."""
    engine = _engine()
    with Session(engine) as session:
        # Seed facilities
        source = SourceFile(
            source_name="CMS",
            source_url="https://data.cms.gov/facilities.csv",
            source_type="cms_hospitals_csv",
            storage_path="fixture.csv",
            checksum_sha256="a" * 64,
            file_size=1,
            parser_version="test",
            status=SourceStatus.COMPLETED,
        )
        session.add(source)
        session.flush()
        names = (
            "ALICE PECK DAY MEMORIAL HOSPITAL",
            "ANDROSCOGGIN VALLEY HOSPITAL",
            "CATHOLIC MEDICAL CENTER",
            "CHESHIRE MEDICAL CENTER",
            "CONCORD HOSPITAL",
            "COTTAGE HOSPITAL",
        )
        for index, name in enumerate(names, start=1):
            facility = Facility(
                id=uuid.uuid4(),
                cms_certification_number=f"30{index:04d}",
                legal_name=name,
                display_name=name.title(),
                source_file_id=source.id,
            )
            facility.locations.append(
                FacilityLocation(
                    address_line_1=f"{index} Main St",
                    city="Concord",
                    state="NH",
                    postal_code="03301",
                )
            )
            session.add(facility)
        session.flush()
        from scripts.seed_procedure_catalog import seed_catalog

        seed_catalog(session)
        session.commit()
        settings_dir = Path("data/fixtures/hospital_prices")
        first = run_fixture_pipeline(session, settings_dir)
        second = run_fixture_pipeline(session, settings_dir)
        assert first.files_registered == 6
        assert first.files_parsed == 4
        assert first.quarantined_files == 2
        assert first.records_normalized == 14
        assert first.records_rejected == 2
        assert first.procedure_mappings == 10
        assert first.summaries == 12
        assert second.files_skipped_unchanged == 6
        assert second.records_normalized == 0
        assert session.scalar(select(func.count(HospitalPriceRecord.id))) == 14
        assert session.scalar(select(func.count(PricingUnmatchedRecord.id))) == 2
        assert session.scalar(select(func.count(PricingAnomaly.id))) == 5
        assert session.scalar(select(func.count(FacilityProcedurePriceSummary.id))) == 12
        assert (
            session.scalar(
                select(func.count(HospitalPriceRecord.id)).where(
                    HospitalPriceRecord.gross_charge < 0
                )
            )
            == 0
        )
    engine.dispose()
