"""Analyze unmapped codes per facility and identify compound codes.

Produces a diagnostic report of the most frequent codes that don't map
to any procedure in the catalog. NO automatic mapping — suggestions only.
"""

import json
import re
import sys
from collections import Counter
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from packages.database import (
    Facility,
    FacilityLocation,
    HospitalPriceRecord,
    PriceServiceCode,
    PricingUnmatchedRecord,
    session_factory,
)


def rank_unmapped_codes(
    session: Session, state_code: str = "NH", limit: int = 50
) -> list[dict[str, object]]:
    """Query unmapped codes grouped by (code, code_type, description), ranked by frequency."""
    facility_ids = set(
        session.scalars(
            select(Facility.id)
            .join(FacilityLocation)
            .where(FacilityLocation.state == state_code.upper(), Facility.active.is_(True))
        )
    )

    rows = session.execute(
        select(
            PricingUnmatchedRecord.supplied_codes,
            PricingUnmatchedRecord.raw_description,
            PricingUnmatchedRecord.reason,
            func.count(PricingUnmatchedRecord.id).label("count"),
        )
        .where(PricingUnmatchedRecord.facility_id.in_(facility_ids))
        .group_by(
            PricingUnmatchedRecord.supplied_codes,
            PricingUnmatchedRecord.raw_description,
            PricingUnmatchedRecord.reason,
        )
        .order_by(func.count(PricingUnmatchedRecord.id).desc())
        .limit(limit)
    ).all()

    return [
        {
            "codes": row[0],
            "description": row[1],
            "reason": row[2],
            "count": row[3],
        }
        for row in rows
    ]


def identify_compound_codes(session: Session, state_code: str = "NH") -> list[dict[str, object]]:
    """Detect compound codes like '85025+85027' or '85025/85027'."""
    facility_ids = set(
        session.scalars(
            select(Facility.id)
            .join(FacilityLocation)
            .where(FacilityLocation.state == state_code.upper(), Facility.active.is_(True))
        )
    )

    codes = session.scalars(
        select(PriceServiceCode.code)
        .join(HospitalPriceRecord)
        .where(HospitalPriceRecord.facility_id.in_(facility_ids))
        .distinct()
    ).all()

    compound_pattern = re.compile(r"^(\d{4,5})\s*[+/,]\s*(\d{4,5})")
    compounds: list[dict[str, object]] = []
    for code in codes:
        match = compound_pattern.match(str(code))
        if match:
            compounds.append({
                "compound_code": str(code),
                "component_1": match.group(1),
                "component_2": match.group(2),
            })
    return compounds


def code_system_distribution(
    session: Session, state_code: str = "NH"
) -> dict[str, int]:
    """Count records by code_system for the state."""
    facility_ids = set(
        session.scalars(
            select(Facility.id)
            .join(FacilityLocation)
            .where(FacilityLocation.state == state_code.upper(), Facility.active.is_(True))
        )
    )

    rows = session.execute(
        select(PriceServiceCode.code_system, func.count(PriceServiceCode.id))
        .join(HospitalPriceRecord)
        .where(HospitalPriceRecord.facility_id.in_(facility_ids))
        .group_by(PriceServiceCode.code_system)
    ).all()

    return {str(row[0]): row[1] for row in rows}


def per_facility_unmapped(
    session: Session, state_code: str = "NH"
) -> list[dict[str, Any]]:
    """Top unmapped codes per facility."""
    facility_ids = set(
        session.scalars(
            select(Facility.id)
            .join(FacilityLocation)
            .where(FacilityLocation.state == state_code.upper(), Facility.active.is_(True))
        )
    )

    results: list[dict[str, Any]] = []
    for fid in facility_ids:
        facility = session.get(Facility, fid)
        if not facility:
            continue
        total_unmatched = session.scalar(
            select(func.count(PricingUnmatchedRecord.id)).where(
                PricingUnmatchedRecord.facility_id == fid
            )
        ) or 0
        total_records = session.scalar(
            select(func.count(HospitalPriceRecord.id)).where(
                HospitalPriceRecord.facility_id == fid
            )
        ) or 0

        # Get top 5 rejection reasons
        reasons = Counter[str]()
        for row in session.execute(
            select(PricingUnmatchedRecord.reason, func.count(PricingUnmatchedRecord.id))
            .where(PricingUnmatchedRecord.facility_id == fid)
            .group_by(PricingUnmatchedRecord.reason)
            .order_by(func.count(PricingUnmatchedRecord.id).desc())
            .limit(5)
        ):
            reasons[row[0]] = row[1]

        if total_records > 0 or total_unmatched > 0:
            results.append({
                "facility": facility.legal_name,
                "total_records": total_records,
                "unmatched": total_unmatched,
                "rejection_pct": round(
                    total_unmatched / (total_records + total_unmatched) * 100, 1
                )
                if (total_records + total_unmatched) > 0
                else 0,
                "top_reasons": dict(reasons),
            })
    results.sort(key=lambda x: x.get("unmatched", 0), reverse=True)
    return results


def main() -> None:
    state = sys.argv[1] if len(sys.argv) > 1 else "NH"
    with session_factory() as session:
        report = {
            "generated_at": datetime.now(UTC).isoformat(),
            "state": state,
            "code_system_distribution": code_system_distribution(session, state),
            "compound_codes": identify_compound_codes(session, state),
            "top_unmapped_codes": rank_unmapped_codes(session, state),
            "per_facility_unmapped": per_facility_unmapped(session, state),
        }
    print(json.dumps(report, indent=2, default=str))


if __name__ == "__main__":
    main()
