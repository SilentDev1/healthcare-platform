"""Pipeline: full statewide pipeline (discover → download → import → postprocess)."""

import argparse
import json
import time

from collectors.hospital_prices.discovery import discover_sources
from collectors.hospital_prices.projections import evaluate_pricing_health, rebuild_price_summaries
from collectors.hospital_prices.quality import review_open_anomalies
from packages.database import session_factory
from scripts.download_all_nh_sources import download_all_nh_sources
from scripts.import_all_nh import import_all_nh


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state", default="NH")
    args = parser.parse_args()

    started = time.perf_counter()
    results: dict[str, object] = {"state": args.state}

    with session_factory() as session:
        # Step 1: Discover
        t0 = time.perf_counter()
        try:
            discovery = discover_sources(session)
            session.commit()
            results["discover"] = {
                "sources_found": discovery.sources_found,
                "elapsed_sec": round(time.perf_counter() - t0, 2),
            }
        except Exception as exc:
            results["discover"] = {"error": str(exc)}

        # Step 2: Download
        t0 = time.perf_counter()
        try:
            download = download_all_nh_sources(session)
            session.commit()
            results["download"] = {
                **download,
                "elapsed_sec": round(time.perf_counter() - t0, 2),
            }
        except Exception as exc:
            results["download"] = {"error": str(exc)}

        # Step 3: Import
        t0 = time.perf_counter()
        try:
            import_result = import_all_nh(session)
            session.commit()
            results["import"] = {
                **import_result,
                "elapsed_sec": round(time.perf_counter() - t0, 2),
            }
        except Exception as exc:
            results["import"] = {"error": str(exc)}

        # Step 4: Postprocess
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
        except Exception as exc:
            results["postprocess"] = {"error": str(exc)}

    results["total_elapsed_sec"] = round(time.perf_counter() - started, 2)
    print(json.dumps(results, indent=2, default=str))


if __name__ == "__main__":
    main()
