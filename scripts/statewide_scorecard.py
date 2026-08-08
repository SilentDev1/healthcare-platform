"""Statewide readiness scorecard targeting 90%+ composite score."""

import json

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from packages.database import (
    Facility,
    FacilityLocation,
    FacilityPriceSource,
    FacilityProcedurePriceSummary,
    HospitalPriceRecord,
    PricingHealthScore,
    Procedure,
    session_factory,
)


def calculate_scorecard(session: Session, state_code: str = "NH") -> dict[str, object]:
    """Calculate composite readiness score from 6 equally weighted components."""
    nh_ids = set(
        session.scalars(
            select(Facility.id)
            .join(FacilityLocation)
            .where(FacilityLocation.state == state_code.upper(), Facility.active.is_(True))
        )
    )
    total_facilities = len(nh_ids)
    if total_facilities == 0:
        return {"total_facilities": 0, "overall_readiness": 0}

    # Component 1: Discovery — % facilities with at least one active source
    with_sources = (
        session.scalar(
            select(func.count(func.distinct(FacilityPriceSource.facility_id))).where(
                FacilityPriceSource.active.is_(True),
                FacilityPriceSource.facility_id.in_(nh_ids),
            )
        )
        or 0
    )
    discovery_pct = round(with_sources / total_facilities * 100, 1)

    # Component 2: Parsing — % facilities with at least one parsed record
    with_records = (
        session.scalar(
            select(func.count(func.distinct(HospitalPriceRecord.facility_id))).where(
                HospitalPriceRecord.facility_id.in_(nh_ids)
            )
        )
        or 0
    )
    parsing_pct = round(with_records / total_facilities * 100, 1)

    # Component 3: Mapping — avg mapping_score across facilities with health scores
    health_scores = session.scalars(
        select(PricingHealthScore).where(PricingHealthScore.facility_id.in_(nh_ids))
    ).all()
    mapping_pct = (
        round(sum(float(s.mapping_score) for s in health_scores) / len(health_scores), 1)
        if health_scores
        else 0
    )

    # Component 4: Quality — avg anomaly_score
    quality_pct = (
        round(sum(float(s.anomaly_score) for s in health_scores) / len(health_scores), 1)
        if health_scores
        else 0
    )

    # Component 5: Freshness — avg freshness_score
    freshness_pct = (
        round(sum(float(s.freshness_score) for s in health_scores) / len(health_scores), 1)
        if health_scores
        else 0
    )

    # Component 6: Coverage — total procedures with publishable prices / total procedures
    total_procedures = (
        session.scalar(select(func.count(Procedure.id)).where(Procedure.active.is_(True))) or 1
    )
    priced_procedures = (
        session.scalar(
            select(func.count(func.distinct(FacilityProcedurePriceSummary.procedure_id))).where(
                FacilityProcedurePriceSummary.publication_status == "publishable",
                FacilityProcedurePriceSummary.facility_id.in_(nh_ids),
            )
        )
        or 0
    )
    coverage_pct = round(priced_procedures / total_procedures * 100, 1)

    # Composite: equally weighted
    components = [discovery_pct, parsing_pct, mapping_pct, quality_pct, freshness_pct, coverage_pct]
    overall = round(sum(components) / len(components), 1)

    return {
        "state": state_code,
        "total_facilities": total_facilities,
        "component_scores": {
            "discovery": discovery_pct,
            "parsing": parsing_pct,
            "mapping": mapping_pct,
            "quality": quality_pct,
            "freshness": freshness_pct,
            "coverage": coverage_pct,
        },
        "overall_readiness": overall,
        "target": 90.0,
        "meets_target": overall >= 90.0,
        "details": {
            "facilities_with_sources": with_sources,
            "facilities_with_records": with_records,
            "priced_procedures": priced_procedures,
            "total_procedures": total_procedures,
            "health_scores_count": len(health_scores),
        },
    }


def main() -> None:
    with session_factory() as session:
        scorecard = calculate_scorecard(session)

    print("\n=== Statewide Readiness Scorecard ===")
    print(f"  State: {scorecard['state']}")
    print(f"  Total facilities: {scorecard['total_facilities']}")
    print("\n  Component scores:")
    components = scorecard["component_scores"]
    assert isinstance(components, dict)
    for name, score in components.items():
        print(f"    {name}: {score}%")
    print(f"\n  Overall readiness: {scorecard['overall_readiness']}%")
    print(f"  Target: {scorecard['target']}%")
    print(f"  Meets target: {'YES' if scorecard['meets_target'] else 'NO'}")
    print("\n  Full scorecard:")
    print(json.dumps(scorecard, indent=2, default=str))


if __name__ == "__main__":
    main()
