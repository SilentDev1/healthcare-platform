"""Bounded recovery for the verified Elliot and CMC hospital MRFs."""

import json
from pathlib import Path

from sqlalchemy import select

from collectors.hospital_prices.downloader import download_price_source
from collectors.hospital_prices.importer import import_price_source
from collectors.hospital_prices.location_association import associate_verified_locations
from collectors.hospital_prices.projections import evaluate_pricing_health, rebuild_price_summaries
from packages.database import Facility, FacilityPriceSource, session_factory
from scripts.register_verified_price_sources import load_registry, register_sources
from scripts.seed_price_mappings import seed_price_mappings

TARGET_CCNS = {"300012", "300034"}
REGISTRY = Path("data/fixtures/verified_hospital_price_sources.json")


def main() -> None:
    verified = [entry for entry in load_registry(REGISTRY) if entry["ccn"] in TARGET_CCNS]
    verified_urls = {entry["ccn"]: entry["machine_readable_file_url"] for entry in verified}
    result: dict[str, object] = {"targets": sorted(TARGET_CCNS)}
    with session_factory() as session:
        result["registration"] = register_sources(session, verified, state="NH")
        facilities = session.scalars(
            select(Facility).where(Facility.cms_certification_number.in_(TARGET_CCNS))
        ).all()
        deactivated: list[str] = []
        for facility in facilities:
            expected_url = verified_urls[facility.cms_certification_number or ""]
            for source in session.scalars(
                select(FacilityPriceSource).where(
                    FacilityPriceSource.facility_id == facility.id,
                    FacilityPriceSource.machine_readable_file_url != expected_url,
                    FacilityPriceSource.active.is_(True),
                )
            ):
                source.active = False
                deactivated.append(str(source.id))
        session.commit()
        result["deactivated_non_current_sources"] = deactivated

        location_result = associate_verified_locations(session)
        result["location_association"] = {
            "sources_associated": location_result.sources_associated,
            "unresolved_sources": location_result.unresolved_sources,
        }

        seed_price_mappings(session)
        session.commit()
        outcomes: list[dict[str, object]] = []
        for facility in facilities:
            current_source = session.scalar(
                select(FacilityPriceSource).where(
                    FacilityPriceSource.facility_id == facility.id,
                    FacilityPriceSource.machine_readable_file_url
                    == verified_urls[facility.cms_certification_number or ""],
                )
            )
            if current_source is None:
                raise RuntimeError(f"verified source missing for {facility.display_name}")
            download = download_price_source(session, current_source)
            session.commit()
            imported = import_price_source(session, current_source)
            outcomes.append(
                {
                    "ccn": facility.cms_certification_number,
                    "hospital": facility.display_name,
                    "source_id": str(current_source.id),
                    "source_file_id": str(current_source.source_file_id),
                    "checksum": download.checksum,
                    "file_size": download.size,
                    "detected_format": download.detected_format,
                    "download_skipped": download.skipped_unchanged,
                    "rows_examined": imported.rows_examined,
                    "records_normalized": imported.records_normalized,
                    "records_rejected": imported.records_rejected,
                    "rate_details": imported.rate_details,
                    "codes": imported.codes,
                    "exact_mappings": imported.exact_procedure_mappings,
                    "mapping_candidates": imported.procedure_candidates,
                    "skipped_unchanged": imported.skipped_unchanged,
                }
            )
        result["imports"] = outcomes
        result["projection"] = rebuild_price_summaries(session)
        result["health"] = evaluate_pricing_health(session)
        session.commit()
    print("CAREVERO_RECOVERY " + json.dumps(result, default=str, separators=(",", ":")))


if __name__ == "__main__":
    main()
