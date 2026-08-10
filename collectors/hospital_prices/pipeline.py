import logging
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from collectors.hospital_prices.downloader import (
    download_price_source,
    register_local_file,
)
from collectors.hospital_prices.importer import PriceImportSummary, import_price_source
from collectors.hospital_prices.projections import evaluate_pricing_health, rebuild_price_summaries
from collectors.hospital_prices.self_healing import check_source_health
from packages.database import Facility, FacilityLocation, FacilityPriceSource
from scripts.seed_price_mappings import seed_price_mappings

logger = logging.getLogger(__name__)


@dataclass
class PricingPipelineSummary:
    files_registered: int = 0
    files_skipped_unchanged: int = 0
    files_parsed: int = 0
    quarantined_files: int = 0
    rows_examined: int = 0
    records_normalized: int = 0
    records_rejected: int = 0
    rate_details: int = 0
    procedure_mappings: int = 0
    procedure_candidates: int = 0
    anomalies: int = 0
    observations: int = 0
    summaries: int = 0


def run_fixture_pipeline(
    session: Session, fixtures_dir: Path = Path("data/fixtures/hospital_prices")
) -> PricingPipelineSummary:
    seed_price_mappings(session)
    session.commit()
    summary = PricingPipelineSummary()
    facilities = session.scalars(
        select(Facility).where(Facility.active.is_(True)).order_by(Facility.display_name)
    ).all()
    fixture_names = (
        "cms_standard.csv",
        "cms_standard.json",
        "legacy.csv",
        "legacy.json",
        "unknown.csv",
        "malformed.json",
    )
    for facility, fixture_name in zip(facilities, fixture_names, strict=False):
        path = fixtures_dir / fixture_name
        url = path.resolve().as_uri()
        price_source = session.scalar(
            select(FacilityPriceSource).where(
                FacilityPriceSource.facility_id == facility.id,
                FacilityPriceSource.machine_readable_file_url == url,
            )
        )
        if price_source is None:
            price_source = FacilityPriceSource(
                facility_id=facility.id,
                source_type="hospital_mrf",
                source_page_url="https://example.test/pricing",
                machine_readable_file_url=url,
                declared_format=path.suffix.lstrip("."),
                active=True,
                discovery_method="manually_seeded",
            )
            session.add(price_source)
            session.flush()
        downloaded = register_local_file(session, price_source, path)
        summary.files_skipped_unchanged += int(downloaded.skipped_unchanged)
        summary.files_registered += int(not downloaded.skipped_unchanged)
        imported: PriceImportSummary = import_price_source(session, price_source)
        summary.files_parsed += imported.files_parsed
        summary.quarantined_files += imported.quarantined_files
        summary.rows_examined += imported.rows_examined
        summary.records_normalized += imported.records_normalized
        summary.records_rejected += imported.records_rejected
        summary.rate_details += imported.rate_details
        summary.procedure_mappings += imported.exact_procedure_mappings
        summary.procedure_candidates += imported.procedure_candidates
        summary.anomalies += imported.anomalies
    projection = rebuild_price_summaries(session)
    summary.observations = projection["observations"]
    summary.summaries = projection["summaries"]
    evaluate_pricing_health(session)
    return summary


@dataclass
class StatewidePipelineResult:
    sources_processed: int = 0
    imported: int = 0
    skipped: int = 0
    failed: int = 0
    total_rows: int = 0
    total_records: int = 0
    observations: int = 0
    summaries: int = 0
    average_health: float = 0.0


def run_statewide_pipeline(session: Session, state_code: str = "NH") -> StatewidePipelineResult:
    """Discover → download → import → rebuild → evaluate for all facilities in a state."""
    seed_price_mappings(session)
    session.commit()
    result = StatewidePipelineResult()

    facility_ids = set(
        session.scalars(
            select(Facility.id)
            .join(FacilityLocation)
            .where(FacilityLocation.state == state_code.upper(), Facility.active.is_(True))
        )
    )

    sources = session.scalars(
        select(FacilityPriceSource).where(
            FacilityPriceSource.active.is_(True),
            FacilityPriceSource.source_file_id.is_not(None),
            FacilityPriceSource.facility_id.in_(facility_ids),
        )
    ).all()
    result.sources_processed = len(sources)

    for source in sources:
        try:
            summary = import_price_source(session, source)
            if summary.skipped_unchanged:
                result.skipped += 1
            else:
                result.imported += 1
                result.total_rows += summary.rows_examined
                result.total_records += summary.records_normalized
        except Exception as exc:
            result.failed += 1
            logger.warning(
                "statewide_import_failed",
                extra={"facility_id": str(source.facility_id), "error": str(exc)},
            )

    projection = rebuild_price_summaries(session)
    result.observations = projection["observations"]
    result.summaries = projection["summaries"]

    health = evaluate_pricing_health(session)
    result.average_health = health["average_pricing_health"]

    return result


@dataclass
class DownloadRetryResult:
    attempted: int = 0
    succeeded: int = 0
    failed: int = 0
    skipped_ok: int = 0
    errors: list[str] = field(default_factory=list)


def run_download_retry(
    session: Session, state_code: str = "NH"
) -> DownloadRetryResult:
    """Re-attempt downloads for sources with previous failures.

    Pre-checks source health via HEAD request, follows redirects,
    then re-downloads with raised limits.
    """
    import httpx

    result = DownloadRetryResult()
    facility_ids = set(
        session.scalars(
            select(Facility.id)
            .join(FacilityLocation)
            .where(FacilityLocation.state == state_code.upper(), Facility.active.is_(True))
        )
    )

    sources = session.scalars(
        select(FacilityPriceSource).where(
            FacilityPriceSource.active.is_(True),
            FacilityPriceSource.facility_id.in_(facility_ids),
            FacilityPriceSource.last_failed_download_at.is_not(None),
        )
    ).all()

    http = httpx.Client(
        timeout=15,
        follow_redirects=False,
        headers={"User-Agent": "CareCompare-HPT-Research/1.0"},
    )
    try:
        for source in sources:
            result.attempted += 1
            # Pre-check health and follow redirects
            status = check_source_health(session, source, http)
            if status == "broken":
                result.failed += 1
                result.errors.append(
                    f"{source.facility_id}: broken URL {source.machine_readable_file_url}"
                )
                continue

            try:
                downloaded = download_price_source(session, source)
                if downloaded.skipped_unchanged:
                    result.skipped_ok += 1
                else:
                    result.succeeded += 1
                    logger.info(
                        "download_retry_success",
                        extra={
                            "facility_id": str(source.facility_id),
                            "size": downloaded.size,
                        },
                    )
            except Exception as exc:
                result.failed += 1
                result.errors.append(f"{source.facility_id}: {exc}")
                logger.warning(
                    "download_retry_failed",
                    extra={
                        "facility_id": str(source.facility_id),
                        "error": str(exc),
                    },
                )
    finally:
        http.close()

    return result
