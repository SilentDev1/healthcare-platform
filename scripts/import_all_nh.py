"""Import all supported hospital price sources.

Accepts a state_code parameter for geographic scope (defaults to NH).
"""

import argparse
import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from collectors.hospital_prices.importer import import_price_source
from collectors.hospital_prices.projections import evaluate_pricing_health, rebuild_price_summaries
from packages.database import Facility, FacilityLocation, FacilityPriceSource, session_factory
from scripts.seed_price_mappings import seed_price_mappings


def import_all_sources(session: Session, state_code: str = "NH") -> dict[str, object]:
    """Import all sources in state, rebuild summaries, evaluate health."""
    seed_price_mappings(session)
    session.commit()

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

    imported = 0
    skipped = 0
    failed = 0
    total_rows = 0
    total_records = 0
    errors: list[dict[str, str]] = []

    for source in sources:
        facility = session.get(Facility, source.facility_id)
        name = facility.display_name if facility else str(source.facility_id)
        try:
            summary = import_price_source(session, source)
            if summary.skipped_unchanged:
                skipped += 1
                print(f"  Skipped (already imported): {name}")
            else:
                imported += 1
                total_rows += summary.rows_examined
                total_records += summary.records_normalized
                print(
                    f"  Imported: {name} — "
                    f"{summary.records_normalized} records, "
                    f"{summary.rate_details} rates"
                )
        except Exception as exc:
            failed += 1
            errors.append({"facility": name, "error": f"{type(exc).__name__}: {exc}"})
            print(f"  Failed: {name} — {type(exc).__name__}: {exc}")

    # Post-processing
    print("\nRebuilding price summaries...")
    projection = rebuild_price_summaries(session)
    print(f"  Observations: {projection['observations']}, Summaries: {projection['summaries']}")

    print("Evaluating pricing health...")
    health = evaluate_pricing_health(session)
    print(
        f"  Facilities scored: {health['facilities']}, Average: {health['average_pricing_health']}"
    )

    return {
        "sources_total": len(sources),
        "imported": imported,
        "skipped": skipped,
        "failed": failed,
        "total_rows": total_rows,
        "total_records": total_records,
        "observations": projection["observations"],
        "summaries": projection["summaries"],
        "average_health": health["average_pricing_health"],
        "errors": errors,
    }


def import_all_nh(session: Session) -> dict[str, object]:
    """Backward-compatible alias."""
    return import_all_sources(session, "NH")


def main() -> None:
    parser = argparse.ArgumentParser(description="Import all price sources")
    parser.add_argument("--state", default="NH")
    args = parser.parse_args()
    with session_factory() as session:
        result = import_all_sources(session, args.state)
    print(f"\n=== Statewide Import Results ({args.state}) ===")
    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
