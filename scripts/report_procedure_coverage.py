"""Report procedure coverage per facility: procedures with prices / total procedures."""

import json

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from collectors.hospital_prices.scope import active_consumer_facility_ids
from packages.database import (
    Facility,
    FacilityLocation,
    FacilityProcedurePriceSummary,
    Procedure,
    session_factory,
)


def report_procedure_coverage(session: Session, state_code: str = "NH") -> dict[str, object]:
    """Per-facility and statewide procedure coverage."""
    total_procedures = (
        session.scalar(select(func.count(Procedure.id)).where(Procedure.active.is_(True))) or 0
    )
    facility_ids = active_consumer_facility_ids(session, state_code)

    facilities = session.scalars(
        select(Facility).where(Facility.id.in_(facility_ids)).order_by(Facility.display_name)
    ).all()

    # Publishable procedure counts per facility
    coverage_counts: dict[object, int] = {
        row[0]: row[1]
        for row in session.execute(
            select(
                FacilityProcedurePriceSummary.facility_id,
                func.count(func.distinct(FacilityProcedurePriceSummary.procedure_id)),
            )
            .where(
                FacilityProcedurePriceSummary.publication_status == "publishable",
                FacilityProcedurePriceSummary.facility_id.in_(facility_ids),
            )
            .group_by(FacilityProcedurePriceSummary.facility_id)
        ).all()
    }

    # All procedures with at least one publishable price anywhere
    all_priced_procedures = set(
        session.scalars(
            select(func.distinct(FacilityProcedurePriceSummary.procedure_id)).where(
                FacilityProcedurePriceSummary.publication_status == "publishable",
                FacilityProcedurePriceSummary.facility_id.in_(facility_ids),
            )
        )
    )

    # All procedures (for missing list)
    all_procedures = {
        p.id: p.consumer_name
        for p in session.scalars(select(Procedure).where(Procedure.active.is_(True)))
    }

    facility_reports = []
    for facility in facilities:
        location = session.scalar(
            select(FacilityLocation)
            .where(FacilityLocation.facility_id == facility.id)
            .order_by(FacilityLocation.id)
            .limit(1)
        )
        mapped = coverage_counts.get(facility.id, 0)
        pct = round(mapped / total_procedures * 100, 1) if total_procedures else 0

        # Procedures this facility has
        facility_procedure_ids = set(
            session.scalars(
                select(func.distinct(FacilityProcedurePriceSummary.procedure_id)).where(
                    FacilityProcedurePriceSummary.facility_id == facility.id,
                    FacilityProcedurePriceSummary.publication_status == "publishable",
                )
            )
        )
        missing = [
            name
            for pid, name in sorted(all_procedures.items(), key=lambda x: x[1])
            if pid not in facility_procedure_ids
        ]

        facility_reports.append(
            {
                "facility_name": facility.display_name,
                "city": location.city if location else None,
                "procedures_mapped": mapped,
                "total_procedures": total_procedures,
                "coverage_pct": pct,
                "missing_procedures": missing[:20],
            }
        )

    statewide_pct = (
        round(len(all_priced_procedures) / total_procedures * 100, 1) if total_procedures else 0
    )

    return {
        "state": state_code,
        "total_procedures_in_catalog": total_procedures,
        "statewide_procedures_with_prices": len(all_priced_procedures),
        "statewide_coverage_pct": statewide_pct,
        "facility_count": len(facilities),
        "facilities": facility_reports,
    }


def main() -> None:
    with session_factory() as session:
        report = report_procedure_coverage(session)

    print("\n=== Procedure Coverage Report ===")
    print(f"  State: {report['state']}")
    print(f"  Total procedures: {report['total_procedures_in_catalog']}")
    print(f"  Statewide with prices: {report['statewide_procedures_with_prices']}")
    print(f"  Statewide coverage: {report['statewide_coverage_pct']}%")
    print("\n  Per-facility:")
    facilities = report["facilities"]
    assert isinstance(facilities, list)
    for f in facilities:
        assert isinstance(f, dict)
        nm = f["facility_name"]
        mp = f["procedures_mapped"]
        tp = f["total_procedures"]
        cp = f["coverage_pct"]
        print(f"    {nm}: {mp}/{tp} ({cp}%)")
    print("\n  Full report:")
    print(json.dumps(report, indent=2, default=str))


if __name__ == "__main__":
    main()
