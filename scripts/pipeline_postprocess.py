"""Pipeline step: post-process (rebuild summaries, evaluate health, quality review)."""

import argparse
import json
import time

from collectors.hospital_prices.projections import evaluate_pricing_health, rebuild_price_summaries
from collectors.hospital_prices.quality import review_open_anomalies
from packages.database import session_factory


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state", default="NH")
    args = parser.parse_args()

    started = time.perf_counter()
    with session_factory() as session:
        projections = rebuild_price_summaries(session)
        triage = review_open_anomalies(session)
        health = evaluate_pricing_health(session)
    elapsed = round(time.perf_counter() - started, 2)

    output = {
        "step": "postprocess",
        "state": args.state,
        "observations": projections["observations"],
        "summaries": projections["summaries"],
        "anomaly_triage": triage,
        "average_health": health["average_pricing_health"],
        "elapsed_sec": elapsed,
    }
    print(json.dumps(output, indent=2, default=str))


if __name__ == "__main__":
    main()
