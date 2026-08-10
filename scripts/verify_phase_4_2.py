"""Automated verification for Phase 4.2 deliverables."""

import json
import sys

from sqlalchemy import func, select

from collectors.hospital_prices.projections import evaluate_pricing_health
from collectors.hospital_prices.quality import review_open_anomalies
from packages.database import (
    Facility,
    FacilityLocation,
    HospitalPriceRecord,
    PriceChangeSnapshot,
    Procedure,
    session_factory,
)
from scripts.statewide_scorecard import calculate_scorecard


def verify() -> dict[str, object]:
    """Run Phase 4.2 verification checks and return results."""
    checks: list[dict[str, object]] = []
    all_pass = True

    with session_factory() as session:
        # Check 1: Scorecard calculation works
        try:
            scorecard = calculate_scorecard(session)
            checks.append(
                {
                    "check": "scorecard_calculation",
                    "passed": True,
                    "overall_readiness": scorecard["overall_readiness"],
                }
            )
        except Exception as exc:
            checks.append({"check": "scorecard_calculation", "passed": False, "error": str(exc)})
            all_pass = False

        # Check 2: NH facilities exist
        nh_count = (
            session.scalar(
                select(func.count(func.distinct(Facility.id)))
                .join(FacilityLocation)
                .where(FacilityLocation.state == "NH", Facility.active.is_(True))
            )
            or 0
        )
        passed = nh_count > 0
        checks.append({"check": "nh_facilities_exist", "passed": passed, "count": nh_count})
        if not passed:
            all_pass = False

        # Check 3: Procedure catalog populated
        procedure_count = (
            session.scalar(select(func.count(Procedure.id)).where(Procedure.active.is_(True))) or 0
        )
        passed = procedure_count >= 10
        checks.append({"check": "procedure_catalog", "passed": passed, "count": procedure_count})
        if not passed:
            all_pass = False

        # Check 4: PricingHealthScore model works
        try:
            health = evaluate_pricing_health(session)
            checks.append(
                {
                    "check": "pricing_health_evaluation",
                    "passed": True,
                    "facilities": health["facilities"],
                }
            )
        except Exception as exc:
            checks.append(
                {"check": "pricing_health_evaluation", "passed": False, "error": str(exc)}
            )
            all_pass = False

        # Check 5: Quality review works
        try:
            triage = review_open_anomalies(session)
            checks.append({"check": "anomaly_triage", "passed": True, "results": triage})
        except Exception as exc:
            checks.append({"check": "anomaly_triage", "passed": False, "error": str(exc)})
            all_pass = False

        # Check 6: PriceChangeSnapshot table exists
        try:
            snapshot_count = session.scalar(select(func.count(PriceChangeSnapshot.id))) or 0
            checks.append(
                {
                    "check": "price_change_snapshots_table",
                    "passed": True,
                    "count": snapshot_count,
                }
            )
        except Exception as exc:
            checks.append(
                {"check": "price_change_snapshots_table", "passed": False, "error": str(exc)}
            )
            all_pass = False

        # Check 7: No negative prices
        negative = (
            session.scalar(
                select(func.count(HospitalPriceRecord.id)).where(
                    HospitalPriceRecord.gross_charge < 0
                )
            )
            or 0
        )
        passed = negative == 0
        checks.append({"check": "no_negative_prices", "passed": passed, "negative_count": negative})
        if not passed:
            all_pass = False

    results = {
        "phase": "4.2",
        "all_passed": all_pass,
        "checks": checks,
        "total_checks": len(checks),
        "passed_checks": sum(1 for c in checks if c["passed"]),
    }

    return results


def main() -> None:
    results = verify()
    print(json.dumps(results, indent=2, default=str))

    print("\n=== Phase 4.2 Verification ===")
    checks = results["checks"]
    assert isinstance(checks, list)
    for check in checks:
        assert isinstance(check, dict)
        status = "PASS" if check["passed"] else "FAIL"
        print(f"  [{status}] {check['check']}")

    print(f"\n  {results['passed_checks']}/{results['total_checks']} checks passed")
    if results["all_passed"]:
        print("  Phase 4.2 verification: ALL PASSED")
    else:
        print("  Phase 4.2 verification: SOME CHECKS FAILED")
        sys.exit(1)


if __name__ == "__main__":
    main()
