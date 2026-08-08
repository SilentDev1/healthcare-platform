"""Benchmark runner for hospital pricing import performance."""

import sys
import time
from pathlib import Path

from sqlalchemy import create_engine, func, select
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
    PricingAnomaly,
    SourceFile,
)
from packages.database.models import SourceStatus
from scripts.seed_price_mappings import seed_price_mappings

BENCHMARK_ROWS = 10_000
BENCHMARK_PAYERS = 10
BENCHMARK_PLANS_PER_PAYER = 3


def _setup_benchmark(
    session: Session, fixture_path: Path, settings: HospitalPriceSettings
) -> FacilityPriceSource:
    """Set up a benchmark facility with a generated fixture file."""
    source = SourceFile(
        source_name="benchmark",
        source_url="file:///benchmark/fixture.csv",
        source_type="benchmark_csv",
        storage_path=str(fixture_path),
        checksum_sha256="b" * 64,
        file_size=fixture_path.stat().st_size,
        parser_version=settings.hospital_price_parser_version,
        status=SourceStatus.COMPLETED,
    )
    session.add(source)
    session.flush()

    facility = Facility(
        cms_certification_number="990001",
        legal_name="BENCHMARK HOSPITAL",
        display_name="Benchmark Hospital",
        source_file_id=source.id,
    )
    facility.locations.append(
        FacilityLocation(
            address_line_1="1 Benchmark Dr",
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


def run_benchmark(
    rows: int = BENCHMARK_ROWS,
    payers: int = BENCHMARK_PAYERS,
    plans_per_payer: int = BENCHMARK_PLANS_PER_PAYER,
) -> dict[str, object]:
    """Run a benchmark import and return performance metrics."""
    fixture_dir = Path("data/generated")
    fixture_dir.mkdir(parents=True, exist_ok=True)
    fixture_path = fixture_dir / "benchmark_fixture.csv"

    print(f"Generating fixture: {rows} rows, {payers} payers, {plans_per_payer} plans/payer...")
    generate_cms_wide_fixture(
        fixture_path, rows=rows, payers=payers, plans_per_payer=plans_per_payer
    )
    file_size_mb = fixture_path.stat().st_size / (1024 * 1024)
    print(f"Fixture: {file_size_mb:.1f} MB")

    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    settings = HospitalPriceSettings()

    with Session(engine) as session:
        seed_payers(session)
        seed_price_mappings(session)
        session.commit()

        price_source = _setup_benchmark(session, fixture_path, settings)
        session.commit()

        started = time.perf_counter()
        summary = import_price_source(session, price_source, settings)
        elapsed = time.perf_counter() - started

        records = session.scalar(select(func.count(HospitalPriceRecord.id))) or 0
        rate_details = session.scalar(select(func.count(HospitalPriceRateDetail.id))) or 0
        anomalies = session.scalar(select(func.count(PricingAnomaly.id))) or 0

    engine.dispose()

    rows_per_sec = summary.rows_examined / elapsed if elapsed > 0 else 0
    records_per_sec = records / elapsed if elapsed > 0 else 0

    report: dict[str, object] = {
        "fixture_rows": rows,
        "fixture_payers": payers,
        "fixture_plans_per_payer": plans_per_payer,
        "fixture_size_mb": round(file_size_mb, 1),
        "rows_examined": summary.rows_examined,
        "records_normalized": summary.records_normalized,
        "records_rejected": summary.records_rejected,
        "rate_details": rate_details,
        "anomalies": anomalies,
        "elapsed_sec": round(elapsed, 2),
        "rows_per_sec": round(rows_per_sec, 1),
        "records_per_sec": round(records_per_sec, 1),
    }

    print("\n=== Benchmark Results ===")
    for key, val in report.items():
        print(f"  {key}: {val}")

    target = 300
    if rows_per_sec >= target:
        print(f"\n  PASS: {rows_per_sec:.0f} rows/sec >= {target} target")
    else:
        print(f"\n  BELOW TARGET: {rows_per_sec:.0f} rows/sec < {target} target")

    return report


STATEWIDE_FACILITIES = 5
STATEWIDE_ROWS_PER_FACILITY = 1_000


def run_statewide_benchmark(
    facility_count: int = STATEWIDE_FACILITIES,
    rows_per_facility: int = STATEWIDE_ROWS_PER_FACILITY,
) -> dict[str, object]:
    """Run a statewide benchmark with multiple facilities."""
    fixture_dir = Path("data/generated")
    fixture_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n=== Statewide Benchmark: {facility_count} facilities × {rows_per_facility} rows ===")

    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    settings = HospitalPriceSettings()

    with Session(engine) as session:
        seed_payers(session)
        seed_price_mappings(session)
        session.commit()

        # Create facilities and fixtures
        facility_sources: list[FacilityPriceSource] = []
        for i in range(facility_count):
            fixture_path = fixture_dir / f"statewide_facility_{i}.csv"
            generate_cms_wide_fixture(
                fixture_path, rows=rows_per_facility, payers=3, plans_per_payer=2
            )

            source = SourceFile(
                source_name=f"statewide_{i}",
                source_url=f"file:///statewide/facility_{i}.csv",
                source_type="benchmark_csv",
                storage_path=str(fixture_path),
                checksum_sha256=f"{i:0>64}",
                file_size=fixture_path.stat().st_size,
                parser_version=settings.hospital_price_parser_version,
                status=SourceStatus.COMPLETED,
            )
            session.add(source)
            session.flush()

            facility = Facility(
                cms_certification_number=f"99{i:04d}",
                legal_name=f"STATEWIDE BENCHMARK HOSPITAL {i}",
                display_name=f"Statewide Benchmark Hospital {i}",
                source_file_id=source.id,
            )
            facility.locations.append(
                FacilityLocation(
                    address_line_1=f"{i} Benchmark Dr",
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
                source_page_url=f"https://example.test/benchmark/{i}",
                machine_readable_file_url=fixture_path.resolve().as_uri(),
                declared_format="csv",
                active=True,
                discovery_method="benchmark",
                source_file_id=source.id,
            )
            session.add(price_source)
            session.flush()
            facility_sources.append(price_source)
        session.commit()

        # Import all facilities and time each
        total_rows = 0
        total_records = 0
        per_facility: list[dict[str, object]] = []
        overall_start = time.perf_counter()

        for i, price_source in enumerate(facility_sources):
            t0 = time.perf_counter()
            summary = import_price_source(session, price_source, settings)
            elapsed = time.perf_counter() - t0
            rate = summary.rows_examined / elapsed if elapsed > 0 else 0
            total_rows += summary.rows_examined
            total_records += summary.records_normalized
            per_facility.append(
                {
                    "facility": i,
                    "rows": summary.rows_examined,
                    "records": summary.records_normalized,
                    "elapsed_sec": round(elapsed, 2),
                    "rows_per_sec": round(rate, 1),
                }
            )
            print(f"  Facility {i}: {summary.rows_examined} rows, {rate:.0f} rows/sec")

        overall_elapsed = time.perf_counter() - overall_start
        overall_rate = total_rows / overall_elapsed if overall_elapsed > 0 else 0

    engine.dispose()

    report: dict[str, object] = {
        "facility_count": facility_count,
        "rows_per_facility": rows_per_facility,
        "total_rows": total_rows,
        "total_records": total_records,
        "overall_elapsed_sec": round(overall_elapsed, 2),
        "overall_rows_per_sec": round(overall_rate, 1),
        "per_facility": per_facility,
    }

    print(f"\n  Total: {total_rows} rows in {overall_elapsed:.2f}s")
    print(f"  Overall: {overall_rate:.0f} rows/sec")

    target = 300
    if overall_rate >= target:
        print(f"\n  PASS: {overall_rate:.0f} rows/sec >= {target} target")
    else:
        print(f"\n  BELOW TARGET: {overall_rate:.0f} rows/sec < {target} target")

    return report


if __name__ == "__main__":
    rows_arg = int(sys.argv[1]) if len(sys.argv) > 1 else BENCHMARK_ROWS
    run_benchmark(rows=rows_arg)
    run_statewide_benchmark()
