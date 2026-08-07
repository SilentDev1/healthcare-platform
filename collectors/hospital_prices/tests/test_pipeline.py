import gzip
import uuid
import zipfile
from pathlib import Path

import httpx
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from collectors.hospital_prices.config import HospitalPriceSettings
from collectors.hospital_prices.discovery import discover_sources, extract_mrf_urls
from collectors.hospital_prices.downloader import safe_extract
from collectors.hospital_prices.importer import decimal_value
from collectors.hospital_prices.normalization import match_payer, normalize_payer_name, seed_payers
from collectors.hospital_prices.pipeline import run_fixture_pipeline
from packages.database import (
    Base,
    Facility,
    FacilityLocation,
    FacilityPriceSource,
    FacilityProcedurePriceSummary,
    HospitalPriceRecord,
    PayerEntity,
    PricingAnomaly,
    PricingUnmatchedRecord,
    SourceFile,
)
from packages.database.models import SourceStatus
from scripts.seed_procedure_catalog import seed_catalog


def _seed_facilities(session: Session, count: int = 6) -> None:
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
    for index, name in enumerate(names[:count], start=1):
        facility = Facility(
            id=uuid.uuid4(),
            cms_certification_number=f"30{index:04d}",
            legal_name=name,
            display_name=name.title(),
            source_file_id=source.id,
        )
        facility.locations.append(
            FacilityLocation(
                address_line_1=f"{index} Main St", city="Concord", state="NH", postal_code="03301"
            )
        )
        session.add(facility)
    session.flush()


def test_fixture_pipeline_is_provenance_safe_and_idempotent(tmp_path: Path) -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        _seed_facilities(session)
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


def test_decimal_and_payer_normalization_are_conservative() -> None:
    assert decimal_value("$1,234.50") is not None
    assert decimal_value("") is None
    assert normalize_payer_name("United Healthcare, Inc.") == "united healthcare"
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        seed_payers(session)
        assert match_payer(session, "UHC").method == "exact_alias"
        assert match_payer(session, "Unrecognized Regional Product").payer_id is None
        assert match_payer(session, "").method == "blank"
        assert session.scalar(select(func.count(PayerEntity.id))) == 11
    engine.dispose()


def test_cms_hpt_discovery_multiple_sources_and_idempotency() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        _seed_facilities(session, 1)
        session.commit()
        txt = Path("data/fixtures/hospital_prices/cms-hpt.txt").read_text()

        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/cms-hpt.txt":
                return httpx.Response(200, text=txt, headers={"content-type": "text/plain"})
            return httpx.Response(404)

        with httpx.Client(transport=httpx.MockTransport(handler)) as client:
            first = discover_sources(session, client)
            second = discover_sources(session, client)
        assert first.facilities_examined == 1
        assert first.facilities_with_txt == 1
        assert first.sources_found == 2
        assert second.sources_updated == 2
        assert session.scalar(select(func.count(FacilityPriceSource.id))) == 2
    engine.dispose()


def test_safe_zip_gzip_and_archive_rejections(tmp_path: Path) -> None:
    payload = Path("data/fixtures/hospital_prices/cms_standard.csv").read_bytes()
    gzip_path = tmp_path / "prices.json.gz"
    with gzip.open(gzip_path, "wb") as stream:
        stream.write(payload)
    assert safe_extract(gzip_path, tmp_path / "gzip-out")[0].read_bytes() == payload
    zip_path = tmp_path / "prices.zip"
    with zipfile.ZipFile(zip_path, "w") as archive:
        archive.writestr("prices.csv", payload)
    assert safe_extract(zip_path, tmp_path / "zip-out")[0].read_bytes() == payload
    unsafe = tmp_path / "unsafe.zip"
    with zipfile.ZipFile(unsafe, "w") as archive:
        archive.writestr("../escape.csv", payload)
    try:
        safe_extract(unsafe, tmp_path / "unsafe-out")
    except ValueError as exc:
        assert "unsafe ZIP path" in str(exc)
    else:
        raise AssertionError("unsafe archive was not rejected")
    tiny = HospitalPriceSettings(hospital_price_max_expanded_bytes=10)
    try:
        safe_extract(gzip_path, tmp_path / "tiny-out", tiny)
    except ValueError as exc:
        assert "expanded size" in str(exc)
    else:
        raise AssertionError("oversized expansion was not rejected")


def test_txt_extraction_ignores_non_mrf_urls() -> None:
    urls = extract_mrf_urls(
        Path("data/fixtures/hospital_prices/cms-hpt.txt").read_text(),
        "https://example.test/cms-hpt.txt",
    )
    assert len(urls) == 2
    assert all(url.startswith("https://example.test/") for url in urls)
