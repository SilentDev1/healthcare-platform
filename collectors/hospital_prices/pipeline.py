from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from collectors.hospital_prices.downloader import register_local_file
from collectors.hospital_prices.importer import PriceImportSummary, import_price_source
from collectors.hospital_prices.projections import evaluate_pricing_health, rebuild_price_summaries
from packages.database import Facility, FacilityPriceSource
from scripts.seed_price_mappings import seed_price_mappings


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
