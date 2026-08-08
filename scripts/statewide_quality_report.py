"""Aggregate statewide quality metrics report."""

import json

from collectors.hospital_prices.quality import generate_quality_scores, review_open_anomalies
from packages.database import session_factory


def main() -> None:
    with session_factory() as session:
        triage = review_open_anomalies(session)
        scores = generate_quality_scores(session)

    print("\n=== Statewide Quality Report ===")
    print(f"  Anomaly triage: {json.dumps(triage)}")
    print(f"  Facilities scored: {len(scores)}")
    if scores:
        avg = sum(float(s["overall_score"]) for s in scores) / len(scores)
        print(f"  Average quality score: {avg:.1f}")
        worst = sorted(scores, key=lambda s: float(s["overall_score"]))[:5]
        print("  Lowest 5:")
        for s in worst:
            print(f"    {s['facility_name']}: {s['overall_score']:.1f}")
    print("\n  Full report:")
    print(json.dumps(scores, indent=2, default=str))


if __name__ == "__main__":
    main()
