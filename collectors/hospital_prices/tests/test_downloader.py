"""Tests for large file streaming, .part file atomicity, and resume support."""

import hashlib
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from collectors.hospital_prices.config import HospitalPriceSettings
from collectors.hospital_prices.downloader import (
    _cleanup_part_files,
    _load_part_meta,
    _save_part_meta,
    _stream_checksum_and_size,
    detect_container,
    register_local_file,
    validate_downloaded_file,
)
from collectors.hospital_prices.parsers import inspect_format, iter_rows, normalized_record
from packages.database import Base, Facility, FacilityPriceSource, SourceFile
from packages.database.models import SourceStatus


def test_stream_checksum_matches_direct(tmp_path: Path) -> None:
    """Streaming checksum matches hashlib.sha256(content).hexdigest()."""
    content = b"A" * 500_000
    f = tmp_path / "data.csv"
    f.write_bytes(content)
    checksum, size = _stream_checksum_and_size(f, 1_000_000)
    assert size == 500_000
    assert checksum == hashlib.sha256(content).hexdigest()


def test_stream_checksum_rejects_oversized(tmp_path: Path) -> None:
    """Streaming checksum raises when file exceeds max_bytes."""
    f = tmp_path / "big.csv"
    f.write_bytes(b"X" * 200)
    try:
        _stream_checksum_and_size(f, 100)
        assert False, "should have raised"  # noqa: B011
    except ValueError as exc:
        assert "exceeds" in str(exc)


def test_part_meta_roundtrip(tmp_path: Path) -> None:
    """Save and load .part.meta produces same values."""
    meta = tmp_path / "download.part.meta"
    _save_part_meta(meta, 12345, "abc123")
    result = _load_part_meta(meta)
    assert result is not None
    assert result == (12345, "abc123")


def test_part_meta_missing(tmp_path: Path) -> None:
    """Loading non-existent .part.meta returns None."""
    meta = tmp_path / "nonexistent.meta"
    assert _load_part_meta(meta) is None


def test_part_meta_corrupt(tmp_path: Path) -> None:
    """Loading corrupt .part.meta returns None."""
    meta = tmp_path / "bad.meta"
    meta.write_text("not json", encoding="utf-8")
    assert _load_part_meta(meta) is None


def test_cleanup_part_files(tmp_path: Path) -> None:
    """Cleanup removes .part and .meta files."""
    part = tmp_path / "download.part"
    meta = tmp_path / "download.part.meta"
    part.write_bytes(b"partial")
    meta.write_text("{}", encoding="utf-8")
    _cleanup_part_files(part, meta)
    assert not part.exists()
    assert not meta.exists()


def test_cleanup_missing_files_no_error(tmp_path: Path) -> None:
    """Cleanup of non-existent files does not raise."""
    _cleanup_part_files(tmp_path / "nope.part", tmp_path / "nope.meta")


def test_validate_downloaded_file_html_error(tmp_path: Path) -> None:
    """HTML error pages are rejected."""
    f = tmp_path / "error.csv"
    f.write_bytes(b"<!DOCTYPE html><html><body>404 Not Found</body></html>" + b" " * 100)
    valid, reason = validate_downloaded_file(f)
    assert not valid
    assert reason == "html_error_page"


def test_validate_downloaded_file_valid_csv(tmp_path: Path) -> None:
    """Valid CSV passes validation."""
    f = tmp_path / "data.csv"
    f.write_bytes(b"description,code,gross_charge\nMRI Brain,70551,1500.00\n" + b"x," * 100)
    valid, reason = validate_downloaded_file(f)
    assert valid
    assert reason == "ok"


def test_validate_empty_file(tmp_path: Path) -> None:
    """Empty files are rejected."""
    f = tmp_path / "empty.csv"
    f.write_bytes(b"")
    valid, reason = validate_downloaded_file(f)
    assert not valid
    assert reason == "empty_file"


def test_detect_container_formats(tmp_path: Path) -> None:
    """Detect container identifies CSV, JSON, ZIP, GZIP, XML."""
    csv_file = tmp_path / "test.csv"
    csv_file.write_bytes(b"col1,col2\nval1,val2\n")
    assert detect_container(csv_file) == "csv"

    json_file = tmp_path / "test.json"
    json_file.write_bytes(b'{"key": "value"}')
    assert detect_container(json_file) == "json"

    bom_json_file = tmp_path / "bom.json"
    bom_json_file.write_bytes(b'\xef\xbb\xbf{"version": "3.0.0"}')
    assert detect_container(bom_json_file) == "json"

    xml_file = tmp_path / "test.xml"
    xml_file.write_bytes(b"<?xml version='1.0'?><root><item/></root>")
    assert detect_container(xml_file) == "xml"


def test_config_limits_raised() -> None:
    """Verify config defaults have been raised for large file support."""
    settings = HospitalPriceSettings()
    assert settings.hospital_price_max_bytes == 750_000_000
    assert settings.hospital_price_max_expanded_bytes == 1_500_000_000
    assert settings.hospital_price_read_timeout_seconds == 300
    assert settings.hospital_price_part_file_suffix == ".part"


def test_cms_3_csv_accepts_spaces_around_pipe_headers(tmp_path: Path) -> None:
    source = tmp_path / "cms3.csv"
    source.write_text(
        "hospital_name,last_updated_on,version,,,,\n"
        "Example Hospital,1/1/2026,3.0.0,,,,\n"
        "description,code | 1,code | 1 | type,code | 2,code | 2 | type,"
        "code | 3,code | 3 | type,standard_charge | gross,"
        "standard_charge | discounted_cash,payer_name,plan_name,"
        "standard_charge | negotiated_dollar,standard_charge | min,"
        "standard_charge | max,billing_class\n"
        "MRI BRAIN,40282170,CDM,0610,RC,70551,CPT,1500,900,Aetna,Gold,700,650,800,facility\n",
        encoding="utf-8",
    )

    match, _, _ = inspect_format(source)
    assert match is not None
    assert match.parser_name == "cms_hpt_csv"
    row = next(iter_rows(source, match))
    normalized = normalized_record(row)
    assert normalized["code"] == "70551"
    assert normalized["code_type"] == "CPT"
    assert normalized["gross_charge"] == "1500"
    assert normalized["cash_price"] == "900"
    assert normalized["minimum"] == "650"
    assert normalized["maximum"] == "800"


def test_register_local_file_rearchives_when_existing_storage_path_missing(tmp_path: Path) -> None:
    """A checksum-matched SourceFile whose staged artifact vanished must not crash.

    This reproduces the Concord-Laconia recovery case: an earlier ephemeral local
    stage left a SourceFile whose storage_path no longer exists. register_local_file
    used to call detect_container() on that dead path and raise FileNotFoundError.
    It must instead re-archive the current bytes and re-point the record.
    """
    settings = HospitalPriceSettings(hospital_price_raw_dir=tmp_path / "raw")
    src = tmp_path / "laconia.csv"
    src.write_text("description,code|1,standard_charge|discounted_cash\nWidget,1,5\n")
    checksum, _ = _stream_checksum_and_size(src, settings.hospital_price_max_bytes)

    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        facility = Facility(
            cms_certification_number="990009", legal_name="T HOSPITAL", display_name="T"
        )
        session.add(facility)
        session.flush()
        price_source = FacilityPriceSource(
            facility_id=facility.id,
            source_type="hospital_mrf",
            source_page_url="https://example.test/prices",
            machine_readable_file_url="https://example.test/f.csv",
            declared_format="csv",
            active=True,
            discovery_method="test",
        )
        session.add(price_source)
        session.flush()
        # Existing SourceFile matched by checksum, but its staged file is gone.
        dead = SourceFile(
            source_name="old",
            source_url="https://example.test/f.csv",
            source_type="hospital_price_mrf",
            storage_path="data/raw/hospital_prices/nh/gone/2026-08-07/original.csv",
            checksum_sha256=checksum,
            file_size=123,
            parser_version=settings.hospital_price_parser_version,
            status=SourceStatus.DOWNLOADED,
        )
        session.add(dead)
        session.flush()
        price_source.source_file_id = dead.id
        session.commit()

        result = register_local_file(session, price_source, src, settings)

        assert result.skipped_unchanged is False
        refreshed = session.get(SourceFile, dead.id)
        assert refreshed is not None
        assert Path(refreshed.storage_path).exists()  # re-pointed to a durable path
        assert refreshed.checksum_sha256 == checksum  # identity preserved
        assert price_source.source_file_id == dead.id
    engine.dispose()
