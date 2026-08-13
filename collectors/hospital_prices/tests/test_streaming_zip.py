"""Streaming-from-ZIP importer path for oversized machine-readable files.

Covers the CCN 301308 (Valley Regional) class of MRF whose uncompressed size
expands past the on-disk extraction cap. These archives are parsed straight from
the ZIP member without ever materializing the expanded file on disk.
"""

import zipfile
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import Engine, create_engine, func, select
from sqlalchemy.orm import Session

from collectors.hospital_prices.config import HospitalPriceSettings
from collectors.hospital_prices.fixture_generator import generate_cms_wide_fixture
from collectors.hospital_prices.importer import import_price_source
from collectors.hospital_prices.normalization import seed_payers
from collectors.hospital_prices.parsers import inspect_format, iter_rows
from collectors.hospital_prices.streaming import (
    ZipMemberSource,
    prepare_source_inputs,
)
from packages.database import (
    Base,
    Facility,
    FacilityLocation,
    FacilityPriceSource,
    HospitalPriceRecord,
    SourceFile,
)
from packages.database.models import SourceStatus
from scripts.seed_price_mappings import seed_price_mappings


def _zip_of(csv_path: Path, zip_path: Path, arcname: str = "standardcharges.csv") -> Path:
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.write(csv_path, arcname=arcname)
    return zip_path


# --------------------------------------------------------------------------- #
# ZipMemberSource duck-types the Path surface the parsers rely on.
# --------------------------------------------------------------------------- #


def test_zip_member_source_reads_without_extraction(tmp_path: Path) -> None:
    csv_path = generate_cms_wide_fixture(tmp_path / "src.csv", rows=40, payers=2, plans_per_payer=1)
    zip_path = _zip_of(csv_path, tmp_path / "src.zip")

    member = ZipMemberSource(zip_path, "standardcharges.csv", csv_path.stat().st_size)

    assert member.name == "standardcharges.csv"
    assert member.suffix == ".csv"
    assert member.stat().st_size == csv_path.stat().st_size

    # Binary read yields the exact member bytes; text read yields the header line.
    with member.open("rb") as binary:
        assert binary.read() == csv_path.read_bytes()
    with member.open(encoding="utf-8-sig", newline="") as text:
        assert text.readline().startswith("description,")


def test_streamed_member_parses_identically_to_on_disk(tmp_path: Path) -> None:
    csv_path = generate_cms_wide_fixture(tmp_path / "src.csv", rows=50, payers=2, plans_per_payer=1)
    zip_path = _zip_of(csv_path, tmp_path / "src.zip")
    member = ZipMemberSource(zip_path, "standardcharges.csv", csv_path.stat().st_size)

    disk_match, _, _ = inspect_format(csv_path)
    stream_match, _, _ = inspect_format(member)
    assert disk_match is not None and stream_match is not None
    assert stream_match.parser_name == disk_match.parser_name

    disk_rows = list(iter_rows(csv_path, disk_match))
    stream_rows = list(iter_rows(member, stream_match))
    assert stream_rows == disk_rows
    assert len(stream_rows) == 50


def test_zip_member_source_open_releases_archive_handle(tmp_path: Path) -> None:
    csv_path = generate_cms_wide_fixture(tmp_path / "src.csv", rows=10, payers=1, plans_per_payer=1)
    zip_path = _zip_of(csv_path, tmp_path / "src.zip")
    member = ZipMemberSource(zip_path, "standardcharges.csv", csv_path.stat().st_size)

    # Repeated opens must not leak descriptors or fail — each open re-reads.
    for _ in range(5):
        with member.open(encoding="utf-8-sig") as text:
            assert "description" in text.readline()


# --------------------------------------------------------------------------- #
# prepare_source_inputs: extract-to-disk vs. stream vs. reject.
# --------------------------------------------------------------------------- #


def test_small_zip_extracts_to_disk(tmp_path: Path) -> None:
    csv_path = generate_cms_wide_fixture(tmp_path / "src.csv", rows=20, payers=1, plans_per_payer=1)
    zip_path = _zip_of(csv_path, tmp_path / "src.zip")
    dest = tmp_path / "out"

    inputs = prepare_source_inputs(zip_path, dest, HospitalPriceSettings())

    # Under the cap: proven on-disk path, materialized inside the destination.
    assert inputs
    first = inputs[0]
    assert isinstance(first, Path)
    assert dest in first.parents


def test_oversized_zip_streams_members(tmp_path: Path) -> None:
    csv_path = generate_cms_wide_fixture(tmp_path / "src.csv", rows=60, payers=2, plans_per_payer=1)
    zip_path = _zip_of(csv_path, tmp_path / "src.zip")
    dest = tmp_path / "out"
    # Force the streaming branch: cap far below the member's uncompressed size,
    # ceiling well above it.
    settings = HospitalPriceSettings(
        hospital_price_max_expanded_bytes=100,
        hospital_price_max_streaming_expanded_bytes=8_000_000_000,
    )

    inputs = prepare_source_inputs(zip_path, dest, settings)

    assert inputs and all(isinstance(i, ZipMemberSource) for i in inputs)
    # Nothing was written to the extraction destination.
    assert not dest.exists() or not any(dest.iterdir())


def test_zip_beyond_streaming_ceiling_is_rejected(tmp_path: Path) -> None:
    csv_path = generate_cms_wide_fixture(tmp_path / "src.csv", rows=20, payers=1, plans_per_payer=1)
    zip_path = _zip_of(csv_path, tmp_path / "src.zip")
    settings = HospitalPriceSettings(
        hospital_price_max_expanded_bytes=100,
        hospital_price_max_streaming_expanded_bytes=101,
    )

    with pytest.raises(ValueError, match="streaming maximum"):
        prepare_source_inputs(zip_path, tmp_path / "out", settings)


def test_streaming_decision_preserves_bomb_guard(tmp_path: Path) -> None:
    # Highly compressible member → compression ratio well above the threshold.
    bomb = tmp_path / "bomb.csv"
    bomb.write_bytes(b"A" * 2_000_000)
    zip_path = _zip_of(bomb, tmp_path / "bomb.zip", arcname="bomb.csv")

    with pytest.raises(ValueError, match="compression ratio"):
        prepare_source_inputs(zip_path, tmp_path / "out", HospitalPriceSettings())


def test_streaming_decision_preserves_unsafe_path_guard(tmp_path: Path) -> None:
    payload = tmp_path / "x.csv"
    payload.write_text("description,code\nA,1\n", encoding="utf-8")
    zip_path = tmp_path / "unsafe.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.write(payload, arcname="../escape.csv")

    with pytest.raises(ValueError, match="unsafe ZIP path"):
        prepare_source_inputs(zip_path, tmp_path / "out", HospitalPriceSettings())


def test_streaming_decision_preserves_file_count_guard(tmp_path: Path) -> None:
    a = tmp_path / "a.csv"
    b = tmp_path / "b.csv"
    a.write_text("description,code\nA,1\n", encoding="utf-8")
    b.write_text("description,code\nB,2\n", encoding="utf-8")
    zip_path = tmp_path / "many.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.write(a, arcname="a.csv")
        archive.write(b, arcname="b.csv")
    settings = HospitalPriceSettings(hospital_price_max_archive_files=1)

    with pytest.raises(ValueError, match="too many files"):
        prepare_source_inputs(zip_path, tmp_path / "out", settings)


# --------------------------------------------------------------------------- #
# End-to-end: a streamed import produces the same records as an on-disk import.
# --------------------------------------------------------------------------- #


def _engine() -> Engine:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    return engine


def _seed_facility(session: Session, ccn: str) -> Facility:
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


def _price_source(session: Session, facility: Facility, storage_path: Path, fmt: str) -> Any:  # noqa: ANN401
    source = SourceFile(
        source_name="mrf",
        source_url=storage_path.resolve().as_uri(),
        source_type="hospital_price_mrf",
        storage_path=str(storage_path),
        checksum_sha256=storage_path.name.ljust(64, "0")[:64],
        file_size=storage_path.stat().st_size,
        parser_version="1.0.0",
        status=SourceStatus.DOWNLOADED,
    )
    session.add(source)
    session.flush()
    price_source = FacilityPriceSource(
        facility_id=facility.id,
        source_type="hospital_mrf",
        source_page_url="https://example.test/prices",
        machine_readable_file_url=storage_path.resolve().as_uri(),
        declared_format=fmt,
        active=True,
        discovery_method="test",
        source_file_id=source.id,
    )
    session.add(price_source)
    session.flush()
    return price_source


def test_streamed_import_matches_on_disk_import(tmp_path: Path) -> None:
    csv_path = generate_cms_wide_fixture(
        tmp_path / "mrf.csv", rows=120, payers=2, plans_per_payer=1
    )
    zip_path = _zip_of(csv_path, tmp_path / "mrf.zip")

    # Baseline: import the plain CSV on the standard on-disk path.
    baseline_settings = HospitalPriceSettings()
    engine_a = _engine()
    with Session(engine_a) as session:
        facility = _seed_facility(session, ccn="990101")
        seed_payers(session)
        seed_price_mappings(session)
        ps = _price_source(session, facility, csv_path, "csv")
        session.commit()
        baseline = import_price_source(session, ps, baseline_settings)
        baseline_records = session.scalar(select(func.count(HospitalPriceRecord.id))) or 0
    engine_a.dispose()

    # Streamed: import the ZIP with the on-disk cap forced below the member size,
    # so prepare_source_inputs must stream instead of extract.
    streaming_settings = HospitalPriceSettings(
        hospital_price_max_expanded_bytes=100,
        hospital_price_max_streaming_expanded_bytes=8_000_000_000,
    )
    engine_b = _engine()
    with Session(engine_b) as session:
        facility = _seed_facility(session, ccn="990102")
        seed_payers(session)
        seed_price_mappings(session)
        ps = _price_source(session, facility, zip_path, "zip")
        session.commit()
        streamed = import_price_source(session, ps, streaming_settings)
        streamed_records = session.scalar(select(func.count(HospitalPriceRecord.id))) or 0
    engine_b.dispose()

    assert baseline.records_normalized == 120
    assert streamed.records_normalized == baseline.records_normalized
    assert streamed.rate_details == baseline.rate_details
    assert streamed.records_rejected == baseline.records_rejected
    assert streamed.exact_procedure_mappings == baseline.exact_procedure_mappings
    assert streamed_records == baseline_records == 120
