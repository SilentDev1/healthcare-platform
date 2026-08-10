"""Benchmark coverage: full enhanced pipeline run with report.

Runs: inventory load → discovery → health system propagation → download →
import → CDM crosswalk → quality triage → rebuild summaries → health scores →
enhanced scorecard. Saves JSON report. Accepts --state for geographic scope.
"""

import argparse
import json
import time
from datetime import UTC, datetime
from pathlib import Path

from collectors.hospital_prices.discovery import discover_sources
from collectors.hospital_prices.health_systems import (
    populate_facility_relationships,
    propagate_system_sources,
)
from collectors.hospital_prices.inventory import load_inventory, validate_inventory
from collectors.hospital_prices.projections import evaluate_pricing_health, rebuild_price_summaries
from collectors.hospital_prices.quality import review_open_anomalies
from collectors.hospital_prices.self_healing import check_all_sources
from packages.database import session_factory
from scripts.download_all_nh_sources import download_all_sources
from scripts.import_all_nh import import_all_sources
from scripts.statewide_scorecard import calculate_scorecard


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark statewide coverage")
    parser.add_argument("--state", default="NH", help="State code to benchmark")
    args = parser.parse_args()

    started = time.perf_counter()
    results: dict[str, object] = {
        "state": args.state,
        "benchmark_started_at": datetime.now(UTC).isoformat(),
    }

    # Step 0: Validate inventory
    print(f"=== Benchmarking coverage for {args.state} ===")
    try:
        inventory = load_inventory()
        errors = validate_inventory(inventory)
        results["inventory"] = {
            "total_hospitals": len(inventory.hospitals),
            "active_hospitals": len(inventory.active_hospitals),
            "excluded_hospitals": len(inventory.excluded_hospitals),
            "health_systems": len(inventory.health_systems),
            "validation_errors": errors,
        }
        print(
            f"  Inventory: {len(inventory.active_hospitals)} active, "
            f"{len(inventory.excluded_hospitals)} excluded"
        )
    except Exception as exc:
        results["inventory"] = {"error": str(exc)}
        print(f"  Inventory error: {exc}")

    with session_factory() as session:
        # Step 1: Populate health system relationships
        t0 = time.perf_counter()
        try:
            relationships = populate_facility_relationships(session)
            session.commit()
            results["health_systems"] = {
                "relationships_created": relationships,
                "elapsed_sec": round(time.perf_counter() - t0, 2),
            }
            print(f"  Health systems: {sum(relationships.values())} relationships")
        except Exception as exc:
            results["health_systems"] = {"error": str(exc)}

        # Step 2: Discover sources
        t0 = time.perf_counter()
        try:
            discovery = discover_sources(session)
            session.commit()
            results["discover"] = {
                "facilities_examined": discovery.facilities_examined,
                "facilities_with_txt": discovery.facilities_with_txt,
                "facilities_with_sources": discovery.facilities_with_sources,
                "sources_found": discovery.sources_found,
                "sources_updated": discovery.sources_updated,
                "facilities_missing": discovery.facilities_missing,
                "failed": discovery.failed,
                "strategies_used": discovery.strategies_used,
                "elapsed_sec": round(time.perf_counter() - t0, 2),
            }
            print(
                f"  Discovery: {discovery.facilities_with_sources}"
                f"/{discovery.facilities_examined}"
                f" facilities, {discovery.sources_found} new sources"
            )
        except Exception as exc:
            results["discover"] = {"error": str(exc)}

        # Step 3: Propagate health system sources
        t0 = time.perf_counter()
        try:
            propagated = propagate_system_sources(session)
            results["propagation"] = {
                "sources_propagated": propagated,
                "elapsed_sec": round(time.perf_counter() - t0, 2),
            }
            print(f"  Propagation: {sum(propagated.values())} sources propagated")
        except Exception as exc:
            results["propagation"] = {"error": str(exc)}

        # Step 4: Self-healing check
        t0 = time.perf_counter()
        try:
            health_check = check_all_sources(session)
            results["self_healing"] = {
                **health_check,
                "elapsed_sec": round(time.perf_counter() - t0, 2),
            }
            print(f"  Self-healing: {health_check}")
        except Exception as exc:
            results["self_healing"] = {"error": str(exc)}

        # Step 5: Download
        t0 = time.perf_counter()
        try:
            download = download_all_sources(session, args.state)
            session.commit()
            results["download"] = {
                **download,
                "elapsed_sec": round(time.perf_counter() - t0, 2),
            }
            print(f"  Download: {download}")
        except Exception as exc:
            results["download"] = {"error": str(exc)}

        # Step 6: Import
        t0 = time.perf_counter()
        try:
            import_result = import_all_sources(session, args.state)
            session.commit()
            results["import"] = {
                **import_result,
                "elapsed_sec": round(time.perf_counter() - t0, 2),
            }
            print(f"  Import: {import_result}")
        except Exception as exc:
            results["import"] = {"error": str(exc)}

        # Step 7: Postprocess
        t0 = time.perf_counter()
        try:
            projections = rebuild_price_summaries(session)
            triage = review_open_anomalies(session)
            health = evaluate_pricing_health(session)
            results["postprocess"] = {
                "observations": projections["observations"],
                "summaries": projections["summaries"],
                "anomaly_triage": triage,
                "average_health": health["average_pricing_health"],
                "elapsed_sec": round(time.perf_counter() - t0, 2),
            }
            print(f"  Postprocess: triage={triage}, health={health['average_pricing_health']}")
        except Exception as exc:
            results["postprocess"] = {"error": str(exc)}

        # Step 8: Enhanced scorecard
        t0 = time.perf_counter()
        try:
            scorecard = calculate_scorecard(session, args.state)
            results["scorecard"] = scorecard
            print(f"  Scorecard: {scorecard['overall_readiness']}% (target {scorecard['target']}%)")
        except Exception as exc:
            results["scorecard"] = {"error": str(exc)}

    results["total_elapsed_sec"] = round(time.perf_counter() - started, 2)

    # Save report
    output_dir = Path("data/generated")
    output_dir.mkdir(parents=True, exist_ok=True)
    date_str = datetime.now(UTC).date().isoformat()
    output_path = output_dir / f"coverage_benchmark_{args.state}_{date_str}.json"
    output_path.write_text(json.dumps(results, indent=2, default=str))
    print(f"\n  Report saved: {output_path}")
    print(json.dumps(results, indent=2, default=str))


if __name__ == "__main__":
    main()
