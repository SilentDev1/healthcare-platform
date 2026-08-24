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
from collectors.hospital_prices.importer import (
    PriceImportSummary,
    _persist_interrupted_import,
    decimal_value,
    rate_identity,
)
from collectors.hospital_prices.normalization import match_payer, normalize_payer_name, seed_payers
from collectors.hospital_prices.pipeline import run_fixture_pipeline
from packages.database import (
    Base,
    Facility,
    FacilityLocation,
    FacilityPriceSource,
    FacilityProcedurePriceSummary,
    HospitalPriceRecord,
    ImportRun,
    PayerEntity,
    PricingAnomaly,
    PricingUnmatchedRecord,
    SourceFile,
)
from packages.database.models import ImportStatus, SourceStatus
from scripts.seed_price_mappings import MAPPINGS
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
        assert first.summaries == 0
        assert second.files_skipped_unchanged == 6
        assert second.records_normalized == 0
        assert session.scalar(select(func.count(HospitalPriceRecord.id))) == 14
        assert session.scalar(select(func.count(PricingUnmatchedRecord.id))) == 2
        assert session.scalar(select(func.count(PricingAnomaly.id))) == 5
        assert session.scalar(select(func.count(FacilityProcedurePriceSummary.id))) == 0
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


def test_rate_identity_deduplicates_equivalent_decimal_source_rates() -> None:
    first = {"payer_name": "Bcbs", "plan_name": "Anthem Ppo", "negotiated_rate": "0.02"}
    repeated = {
        "payer_name": "Bcbs",
        "plan_name": "Anthem Ppo",
        "negotiated_rate": "0.0200",
    }
    assert rate_identity(first) == rate_identity(repeated)


def test_interrupted_import_run_stays_resumable_after_rollback() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        source = SourceFile(
            source_name="Hospital MRF",
            source_url="https://hospital.example/prices.csv",
            source_type="hospital_mrf",
            storage_path="prices.csv",
            checksum_sha256="b" * 64,
            file_size=1,
            parser_version="test",
            status=SourceStatus.COMPLETED,
        )
        session.add(source)
        session.commit()
        run = ImportRun(
            importer_name="hospital_prices",
            status=ImportStatus.RUNNING,
            source_file_id=source.id,
        )
        session.add(run)
        session.commit()

        _persist_interrupted_import(
            session,
            run.id,
            source.id,
            PriceImportSummary(rows_examined=12, records_normalized=10, records_rejected=2),
            error="parser failed",
        )

        resumed = session.get(ImportRun, run.id)
        assert resumed is not None
        # Marked resumable — committed rows are preserved, not zeroed.
        assert resumed.status == ImportStatus.INTERRUPTED
        assert resumed.rows_read == 12
        assert resumed.rows_inserted == 10
        assert resumed.rows_rejected == 2
        assert resumed.error_summary == "parser failed"
        resumed_source = session.get(SourceFile, source.id)
        assert resumed_source is not None
        # Source returns to DOWNLOADED so a later run may resume the import.
        assert resumed_source.status == SourceStatus.DOWNLOADED
    engine.dispose()


def test_approved_code_registry_has_no_ambiguous_consumer_procedure_codes() -> None:
    procedures_by_code: dict[tuple[str, str], set[str]] = {}
    for slug, system, code in MAPPINGS:
        procedures_by_code.setdefault((system, code), set()).add(slug)
    assert all(len(slugs) == 1 for slugs in procedures_by_code.values())


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

def test_import_mapped_only_drops_unmapped_rows_but_preserves_published_prices(
    monkeypatch,
) -> None:
    """mapped_only import must skip rows with no canonical mapping (huge volume win)
    while publishing the EXACT same summaries — rebuild only ever used mapped rows."""
    from collectors.hospital_prices.config import hospital_price_settings
    from packages.database import PriceRecordProcedureMapping

    settings_dir = Path("data/fixtures/hospital_prices")

    def _run() -> tuple[int, int, int]:
        engine = create_engine("sqlite://")
        Base.metadata.create_all(engine)
        with Session(engine) as session:
            _seed_facilities(session)
            seed_catalog(session)
            session.commit()
            summary = run_fixture_pipeline(session, settings_dir)
            recs = session.scalar(select(func.count(HospitalPriceRecord.id)))
            # Reviewed exact-approved-code mappings are exactly what rebuild publishes from.
            maps = session.scalar(
                select(func.count(PriceRecordProcedureMapping.id)).where(
                    PriceRecordProcedureMapping.reviewed.is_(True)
                )
            )
            norm = summary.records_normalized
        engine.dispose()
        return norm, recs, maps

    full_norm, full_recs, full_maps = _run()
    monkeypatch.setattr(hospital_price_settings, "hospital_price_import_mapped_only", True)
    mo_norm, mo_recs, mo_maps = _run()

    # Unmapped rows are skipped entirely at import (huge volume reduction).
    assert mo_recs < full_recs
    assert mo_norm < full_norm
    # But every publishable mapping survives — no price is lost.
    assert mo_maps == full_maps
    assert full_maps > 0
    # In mapped-only mode every persisted record carries a publishable mapping.
    assert mo_recs == mo_maps
