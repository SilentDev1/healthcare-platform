"""Bounded recovery waves for authoritative Phase 4.7 hospital MRFs."""

from __future__ import annotations

import argparse
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

REGISTRY = Path("data/fixtures/verified_hospital_price_sources.json")
WAVES = {
    "dartmouth": {"301305", "300019", "300003", "301304"},
    "regional": {"301310", "301312", "301302", "301309", "300020", "301311"},
    "valley": {"301308"},
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state", default="NH")
    parser.add_argument("--wave", choices=tuple(WAVES), required=True)
    args = parser.parse_args()
    target_ccns = WAVES[args.wave]
    verified = [entry for entry in load_registry(REGISTRY) if entry["ccn"] in target_ccns]
    verified_urls = {entry["ccn"]: entry["machine_readable_file_url"] for entry in verified}
    if set(verified_urls) != target_ccns:
        missing = sorted(target_ccns - set(verified_urls))
        raise RuntimeError(f"verified source registry is missing CCNs: {missing}")

    result: dict[str, object] = {"wave": args.wave, "targets": sorted(target_ccns)}
    with session_factory() as session:
        result["registration"] = register_sources(session, verified, state=args.state.upper())
        facilities = list(
            session.scalars(
                select(Facility)
                .where(Facility.cms_certification_number.in_(target_ccns))
                .order_by(Facility.display_name)
            )
        )
        session.commit()
        location_result = associate_verified_locations(session)
        result["location_association"] = {
            "sources_associated": location_result.sources_associated,
            "unresolved_sources": location_result.unresolved_sources,
        }
        seed_price_mappings(session)
        session.commit()

        outcomes: list[dict[str, object]] = []
        for facility in facilities:
            ccn = facility.cms_certification_number or ""
            current_source = session.scalar(
                select(FacilityPriceSource).where(
                    FacilityPriceSource.facility_id == facility.id,
                    FacilityPriceSource.machine_readable_file_url == verified_urls[ccn],
                    FacilityPriceSource.active.is_(True),
                )
            )
            if current_source is None:
                raise RuntimeError(f"verified source missing for {facility.display_name}")
            download = download_price_source(session, current_source)
            session.commit()
            imported = import_price_source(session, current_source)
            outcomes.append(
                {
                    "ccn": ccn,
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
    print("PHASE_4_7_RECOVERY=" + json.dumps(result, default=str, separators=(",", ":")))


if __name__ == "__main__":
    main()
