"""Repair deterministic location/mapping projections without source reacquisition."""

import argparse
import json

from collectors.hospital_prices.location_association import associate_verified_locations
from collectors.hospital_prices.mapping_backfill import backfill_approved_code_mappings
from collectors.hospital_prices.projections import evaluate_pricing_health, rebuild_price_summaries
from collectors.hospital_prices.scope import active_consumer_facility_ids
from packages.database import session_factory
from scripts.seed_price_mappings import seed_price_mappings


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state", default="NH")
    args = parser.parse_args()
    result: dict[str, object] = {}
    with session_factory() as session:
        locations = associate_verified_locations(session)
        result["locations"] = {
            "locations_created": locations.locations_created,
            "sources_associated": locations.sources_associated,
            "records_associated": locations.records_associated,
            "unresolved_sources": locations.unresolved_sources,
        }
        result["mapping_registry_inserted"] = seed_price_mappings(session)
        session.commit()
        mapping = backfill_approved_code_mappings(
            session, active_consumer_facility_ids(session, args.state.upper())
        )
        result["mapping_backfill"] = {
            "ambiguous_registry_mappings": mapping.ambiguous_registry_mappings,
            "ambiguous_record_mappings_removed": mapping.ambiguous_record_mappings_removed,
            "records_mapped": mapping.records_mapped,
            "records_skipped_for_conflict": mapping.records_skipped_for_conflict,
        }
        session.commit()
        result["projection"] = rebuild_price_summaries(session)
        result["health"] = evaluate_pricing_health(session)
    print("PHASE_4_7_REPAIR=" + json.dumps(result, default=str, separators=(",", ":")))


if __name__ == "__main__":
    main()
