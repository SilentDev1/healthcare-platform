"""Full verification script for Phase 4.1."""

import time
from pathlib import Path

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

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
    HospitalPriceRateDetail,
    HospitalPriceRecord,
    SourceFile,
)
from packages.database.models import SourceStatus
from scripts.seed_price_mappings import seed_price_mappings
from scripts.seed_procedure_catalog import seed_catalog


def verify_fixture_pipeline() -> None:
    """Verify existing Phase 4 fixture pipeline still passes."""
    print("\n=== Fixture Pipeline Verification ===")
    import uuid

    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
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
        for index, name in enumerate(
            [
                "ALICE PECK DAY MEMORIAL HOSPITAL",
                "ANDROSCOGGIN VALLEY HOSPITAL",
                "CATHOLIC MEDICAL CENTER",
                "CHESHIRE MEDICAL CENTER",
                "CONCORD HOSPITAL",
                "COTTAGE HOSPITAL",
            ],
            start=1,
        ):
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
        seed_catalog(session)
        session.commit()

        settings_dir = Path("data/fixtures/hospital_prices")
        first = run_fixture_pipeline(session, settings_dir)
        assert first.records_normalized == 14, f"Expected 14, got {first.records_normalized}"
        assert first.records_rejected == 2
        assert first.summaries == 12
        print(f"  Records: {first.records_normalized}")
        print(f"  Rejected: {first.records_rejected}")
        print(f"  Summaries: {first.summaries}")
        print(f"  Anomalies: {first.anomalies}")

        second = run_fixture_pipeline(session, settings_dir)
        assert second.files_skipped_unchanged == 6
        print("  Idempotency: PASS")

        # Safety invariants
        neg = (
            session.scalar(
                select(func.count(HospitalPriceRecord.id)).where(
                    HospitalPriceRecord.gross_charge < 0
                )
            )
            or 0
        )
        assert neg == 0, "Negative prices accepted!"
        print("  Safety invariants: PASS")
    engine.dispose()
    print("  Fixture pipeline: PASS")


def verify_benchmark(rows: int = 5000) -> None:
    """Run benchmark and report throughput."""
    print(f"\n=== Benchmark ({rows} rows) ===")
    from collectors.hospital_prices.config import HospitalPriceSettings

    fixture_dir = Path("data/generated")
    fixture_dir.mkdir(parents=True, exist_ok=True)
    fixture_path = fixture_dir / "verify_fixture.csv"
    generate_cms_wide_fixture(fixture_path, rows=rows, payers=5, plans_per_payer=2)

    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    settings = HospitalPriceSettings()

    with Session(engine) as session:
        seed_payers(session)
        seed_price_mappings(session)
        source = SourceFile(
            source_name="benchmark",
            source_url="file:///verify/fixture.csv",
            source_type="benchmark_csv",
            storage_path=str(fixture_path),
            checksum_sha256="v" * 64,
            file_size=fixture_path.stat().st_size,
            parser_version=settings.hospital_price_parser_version,
            status=SourceStatus.COMPLETED,
        )
        session.add(source)
        session.flush()
        facility = Facility(
            cms_certification_number="990099",
            legal_name="VERIFY HOSPITAL",
            display_name="Verify Hospital",
            source_file_id=source.id,
        )
        facility.locations.append(
            FacilityLocation(
                address_line_1="1 Verify Dr",
                city="Concord",
                state="NH",
                postal_code="03301",
            )
        )
        session.add(facility)
        session.flush()
        price_source = FacilityPriceSource(
            facility_id=facility.id,
            source_type="hospital_mrf",
            source_page_url="https://example.test/verify",
            machine_readable_file_url=fixture_path.resolve().as_uri(),
            declared_format="csv",
            active=True,
            discovery_method="verify",
            source_file_id=source.id,
        )
        session.add(price_source)
        session.commit()

        profiler = ImportProfiler()
        started = time.perf_counter()
        summary = import_price_source(session, price_source, settings, profiler)
        elapsed = time.perf_counter() - started

        records = session.scalar(select(func.count(HospitalPriceRecord.id))) or 0
        rates = session.scalar(select(func.count(HospitalPriceRateDetail.id))) or 0

    engine.dispose()

    rows_per_sec = summary.rows_examined / elapsed if elapsed > 0 else 0
    print(f"  Rows examined: {summary.rows_examined}")
    print(f"  Records: {records}")
    print(f"  Rate details: {rates}")
    print(f"  Elapsed: {elapsed:.2f}s")
    print(f"  Rows/sec: {rows_per_sec:.0f}")
    print(f"  Records/sec: {records / elapsed:.0f}")

    target = 300
    if rows_per_sec >= target:
        print(f"  PASS: {rows_per_sec:.0f} >= {target}")
    else:
        print(f"  BELOW TARGET: {rows_per_sec:.0f} < {target}")


def main() -> None:
    verify_fixture_pipeline()
    verify_benchmark()
    print("\n=== Phase 4.1 Verification Complete ===")


if __name__ == "__main__":
    main()
