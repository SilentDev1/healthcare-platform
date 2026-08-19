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


def import_all_sources(
    session: Session,
    state_code: str = "NH",
    only_ccns: set[str] | None = None,
    rebuild: bool = True,
) -> dict[str, object]:
    """Import all sources in state, rebuild summaries, evaluate health.

    ``only_ccns`` optionally restricts which hospitals are *imported* (by CCN) so a wave stays
    bounded. The summary rebuild always runs across all data (it preserves NH + provider-published).
    """
    seed_price_mappings(session)
    session.commit()

    query = (
        select(Facility.id)
        .distinct()
        .join(FacilityLocation)
        .where(FacilityLocation.state == state_code.upper(), Facility.active.is_(True))
    )
    if only_ccns:
        query = query.where(Facility.cms_certification_number.in_(only_ccns))
    facility_ids = set(session.scalars(query))

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

    # Post-processing. Skippable so multi-wave scale-outs import fast and rebuild ONCE at the end
    # (the rebuild is O(all observations) and is the slow tail of each wave). MA is not consumer-
    # activated during scale-out, so deferring the rebuild has no consumer impact.
    if rebuild:
        print("\nRebuilding price summaries...")
        projection = rebuild_price_summaries(session)
        print(f"  Observations: {projection['observations']}, Summaries: {projection['summaries']}")
        print("Evaluating pricing health...")
        health = evaluate_pricing_health(session)
        avg = health["average_pricing_health"]
        print(f"  Facilities scored: {health['facilities']}, Average: {avg}")
        obs, summ = projection["observations"], projection["summaries"]
    else:
        print("\n(skipping rebuild — deferred to a final rebuild pass)")
        obs = summ = avg = None

    return {
        "sources_total": len(sources),
        "imported": imported,
        "skipped": skipped,
        "failed": failed,
        "total_rows": total_rows,
        "total_records": total_records,
        "observations": obs,
        "summaries": summ,
        "average_health": avg,
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
