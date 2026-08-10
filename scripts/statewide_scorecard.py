"""Statewide readiness scorecard targeting 90%+ composite score.

Accepts geographic scope (state code, defaults to NH).
All calculations are state-agnostic -- the same engine works for any state.
"""

import json

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from collectors.hospital_prices.inventory import load_inventory
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
from packages.database.pricing_models import ParserReview


def calculate_scorecard(session: Session, state_code: str = "NH") -> dict[str, object]:
    """Calculate composite readiness score from 12+ metrics."""
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

    # Load inventory for exclusion awareness
    try:
        inventory = load_inventory()
        excluded_count = len(inventory.excluded_hospitals)
        active_target = total_facilities - excluded_count
    except Exception:
        excluded_count = 0
        active_target = total_facilities

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

    # Component 2: Download — % sources successfully downloaded
    total_sources = (
        session.scalar(
            select(func.count(FacilityPriceSource.id)).where(
                FacilityPriceSource.active.is_(True),
                FacilityPriceSource.facility_id.in_(nh_ids),
            )
        )
        or 1
    )
    downloaded_sources = (
        session.scalar(
            select(func.count(FacilityPriceSource.id)).where(
                FacilityPriceSource.active.is_(True),
                FacilityPriceSource.facility_id.in_(nh_ids),
                FacilityPriceSource.source_file_id.isnot(None),
            )
        )
        or 0
    )
    download_pct = round(downloaded_sources / total_sources * 100, 1)

    # Component 3: Parsing — % facilities with at least one parsed record
    with_records = (
        session.scalar(
            select(func.count(func.distinct(HospitalPriceRecord.facility_id))).where(
                HospitalPriceRecord.facility_id.in_(nh_ids)
            )
        )
        or 0
    )
    parsing_pct = round(with_records / total_facilities * 100, 1)

    # Component 4: Publishable — % facilities with publishable pricing
    publishable_facilities = (
        session.scalar(
            select(func.count(func.distinct(FacilityProcedurePriceSummary.facility_id))).where(
                FacilityProcedurePriceSummary.publication_status == "publishable",
                FacilityProcedurePriceSummary.facility_id.in_(nh_ids),
            )
        )
        or 0
    )
    publishable_pct = round(publishable_facilities / total_facilities * 100, 1)

    # Component 5: Mapping — avg mapping_score across facilities with health scores
    health_scores = session.scalars(
        select(PricingHealthScore).where(PricingHealthScore.facility_id.in_(nh_ids))
    ).all()
    mapping_pct = (
        round(sum(float(s.mapping_score) for s in health_scores) / len(health_scores), 1)
        if health_scores
        else 0
    )

    # Component 6: Quality — avg anomaly_score
    quality_pct = (
        round(sum(float(s.anomaly_score) for s in health_scores) / len(health_scores), 1)
        if health_scores
        else 0
    )

    # Component 7: Freshness — avg freshness_score
    freshness_pct = (
        round(sum(float(s.freshness_score) for s in health_scores) / len(health_scores), 1)
        if health_scores
        else 0
    )

    # Component 8: Coverage — total procedures with publishable prices / total procedures
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

    # Component 9: Parser health
    quarantined_files = (
        session.scalar(
            select(func.count(ParserReview.id)).where(
                ParserReview.status == "unsupported_pending_review"
            )
        )
        or 0
    )

    # Component 10: Vendor distribution
    vendor_counts: dict[str, int] = {}
    for row in session.execute(
        select(FacilityPriceSource.vendor_name, func.count(FacilityPriceSource.id))
        .where(
            FacilityPriceSource.active.is_(True),
            FacilityPriceSource.facility_id.in_(nh_ids),
            FacilityPriceSource.vendor_name.isnot(None),
        )
        .group_by(FacilityPriceSource.vendor_name)
    ).all():
        vendor_counts[str(row[0])] = row[1]

    # Component 11: Broken links
    broken_count = (
        session.scalar(
            select(func.count(FacilityPriceSource.id)).where(
                FacilityPriceSource.active.is_(True),
                FacilityPriceSource.facility_id.in_(nh_ids),
                FacilityPriceSource.last_failed_download_at.isnot(None),
                FacilityPriceSource.source_file_id.is_(None),
            )
        )
        or 0
    )

    # Component 12: Missing procedures
    mapped_procedure_ids = set(
        session.scalars(
            select(func.distinct(FacilityProcedurePriceSummary.procedure_id)).where(
                FacilityProcedurePriceSummary.publication_status == "publishable",
                FacilityProcedurePriceSummary.facility_id.in_(nh_ids),
            )
        )
    )
    all_procedure_ids = set(session.scalars(select(Procedure.id).where(Procedure.active.is_(True))))
    missing_procedure_ids = all_procedure_ids - mapped_procedure_ids
    missing_procedures = (
        list(session.scalars(select(Procedure.slug).where(Procedure.id.in_(missing_procedure_ids))))
        if missing_procedure_ids
        else []
    )

    # Per-facility status
    per_facility: list[dict[str, object]] = []
    for fid in nh_ids:
        f = session.get(Facility, fid)
        if not f:
            continue
        has_source = (
            session.scalar(
                select(FacilityPriceSource.id).where(
                    FacilityPriceSource.facility_id == fid,
                    FacilityPriceSource.active.is_(True),
                )
            )
            is not None
        )
        has_records = (
            session.scalar(
                select(HospitalPriceRecord.id).where(HospitalPriceRecord.facility_id == fid)
            )
            is not None
        )
        is_publishable = (
            session.scalar(
                select(FacilityProcedurePriceSummary.id).where(
                    FacilityProcedurePriceSummary.facility_id == fid,
                    FacilityProcedurePriceSummary.publication_status == "publishable",
                )
            )
            is not None
        )
        per_facility.append(
            {
                "facility_id": str(fid),
                "name": f.display_name,
                "has_source": has_source,
                "has_records": has_records,
                "is_publishable": is_publishable,
            }
        )

    # Composite: equally weighted across first 8 components
    components = [
        discovery_pct,
        download_pct,
        parsing_pct,
        publishable_pct,
        mapping_pct,
        quality_pct,
        freshness_pct,
        coverage_pct,
    ]
    overall = round(sum(components) / len(components), 1)

    return {
        "state": state_code,
        "total_facilities": total_facilities,
        "excluded_facilities": excluded_count,
        "active_target": active_target,
        "component_scores": {
            "discovery": discovery_pct,
            "download": download_pct,
            "parsing": parsing_pct,
            "publishable": publishable_pct,
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
            "downloaded_sources": downloaded_sources,
            "total_sources": total_sources,
            "facilities_with_records": with_records,
            "publishable_facilities": publishable_facilities,
            "priced_procedures": priced_procedures,
            "total_procedures": total_procedures,
            "health_scores_count": len(health_scores),
            "quarantined_files": quarantined_files,
            "broken_links": broken_count,
            "vendor_distribution": vendor_counts,
            "missing_procedures": missing_procedures[:20],
            "per_facility_status": per_facility,
        },
    }


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--state", default="NH")
    args = parser.parse_args()

    with session_factory() as session:
        scorecard = calculate_scorecard(session, args.state)

    print(f"\n=== Statewide Readiness Scorecard ({scorecard['state']}) ===")
    print(f"  Total facilities: {scorecard['total_facilities']}")
    print(f"  Excluded (psychiatric): {scorecard['excluded_facilities']}")
    print(f"  Active target: {scorecard['active_target']}")
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
