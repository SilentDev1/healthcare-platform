"""Publication blocker analytics with deterministic reason codes.

Classifies why each facility with records has zero publishable summaries,
producing both per-facility and aggregate reports.
"""

import json
import sys
from collections import Counter
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from packages.database import (
    Facility,
    FacilityLocation,
    FacilityPriceSource,
    FacilityProcedurePriceSummary,
    HospitalPriceRecord,
    PriceRecordProcedureMapping,
    PriceServiceCode,
    PricingAnomaly,
    PricingUnmatchedRecord,
    session_factory,
)


def _classify_facility(session: Session, facility_id: object) -> list[str]:
    """Classify publication blockers for a single facility.

    Returns a list of deterministic reason codes.
    """
    blockers: list[str] = []

    # Check for any price sources
    source_count = session.scalar(
        select(func.count(FacilityPriceSource.id)).where(
            FacilityPriceSource.facility_id == facility_id,
            FacilityPriceSource.active.is_(True),
        )
    ) or 0
    if source_count == 0:
        blockers.append("no_sources")
        return blockers

    # Check for downloaded sources
    downloaded = session.scalar(
        select(func.count(FacilityPriceSource.id)).where(
            FacilityPriceSource.facility_id == facility_id,
            FacilityPriceSource.active.is_(True),
            FacilityPriceSource.source_file_id.is_not(None),
        )
    ) or 0
    if downloaded == 0:
        blockers.append("download_failed")
        return blockers

    # Check for parsed records
    record_count = session.scalar(
        select(func.count(HospitalPriceRecord.id)).where(
            HospitalPriceRecord.facility_id == facility_id
        )
    ) or 0
    if record_count == 0:
        blockers.append("parse_failed")
        return blockers

    # Check parser names used
    parser_names = list(
        session.scalars(
            select(HospitalPriceRecord.parser_name)
            .where(HospitalPriceRecord.facility_id == facility_id)
            .distinct()
        )
    )
    cms_parsers = [p for p in parser_names if p and p.startswith("cms_hpt")]
    if not cms_parsers:
        blockers.append("parser_not_cms")

    # Check code system distribution
    code_counts: dict[str, int] = {
        str(row[0]): int(row[1])
        for row in session.execute(
            select(PriceServiceCode.code_system, func.count(PriceServiceCode.id))
            .join(HospitalPriceRecord)
            .where(HospitalPriceRecord.facility_id == facility_id)
            .group_by(PriceServiceCode.code_system)
        ).all()
    }
    total_codes = sum(code_counts.values())
    unresolved = code_counts.get("CDM", 0) + code_counts.get("UNKNOWN", 0)
    if total_codes > 0 and unresolved / total_codes > 0.5:
        blockers.append("cdm_codes_unresolved")

    # Check for open critical/error anomalies
    anomaly_count = session.scalar(
        select(func.count(PricingAnomaly.id))
        .join(HospitalPriceRecord)
        .where(
            HospitalPriceRecord.facility_id == facility_id,
            PricingAnomaly.status == "open",
            PricingAnomaly.severity.in_(["error", "critical"]),
        )
    ) or 0
    if anomaly_count > 0:
        blockers.append("open_critical_anomalies")

    # Check for procedure mappings
    mapping_count = session.scalar(
        select(func.count(PriceRecordProcedureMapping.id))
        .join(HospitalPriceRecord)
        .where(
            HospitalPriceRecord.facility_id == facility_id,
            PriceRecordProcedureMapping.reviewed.is_(True),
        )
    ) or 0
    if mapping_count == 0:
        blockers.append("no_procedure_match")

    # Check for rejection rate
    unmatched_count = session.scalar(
        select(func.count(PricingUnmatchedRecord.id)).where(
            PricingUnmatchedRecord.facility_id == facility_id
        )
    ) or 0
    if unmatched_count > record_count:
        blockers.append("high_rejection_rate")

    if not blockers:
        blockers.append("unknown")

    return blockers


def analyze_blockers(
    session: Session, state_code: str = "NH"
) -> dict[str, object]:
    """Analyze publication blockers for all facilities in a state."""
    facility_ids = list(
        session.scalars(
            select(Facility.id)
            .join(FacilityLocation)
            .where(FacilityLocation.state == state_code.upper(), Facility.active.is_(True))
        )
    )

    per_facility: list[dict[str, object]] = []
    blocker_counts = Counter[str]()

    for fid in facility_ids:
        facility = session.get(Facility, fid)
        if not facility:
            continue

        # Check if already publishable
        pub_count = session.scalar(
            select(func.count(FacilityProcedurePriceSummary.id)).where(
                FacilityProcedurePriceSummary.facility_id == fid,
                FacilityProcedurePriceSummary.publication_status == "publishable",
            )
        ) or 0

        if pub_count > 0:
            per_facility.append({
                "facility": facility.legal_name,
                "ccn": facility.cms_certification_number,
                "status": "publishable",
                "publishable_summaries": pub_count,
                "blockers": [],
            })
            continue

        blockers = _classify_facility(session, fid)
        for b in blockers:
            blocker_counts[b] += 1

        record_count = session.scalar(
            select(func.count(HospitalPriceRecord.id)).where(
                HospitalPriceRecord.facility_id == fid
            )
        ) or 0

        per_facility.append({
            "facility": facility.legal_name,
            "ccn": facility.cms_certification_number,
            "status": "blocked",
            "records": record_count,
            "blockers": blockers,
        })

    per_facility.sort(
        key=lambda x: len(x.get("blockers") or []),  # type: ignore[arg-type]
        reverse=True,
    )

    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "state": state_code,
        "total_facilities": len(facility_ids),
        "publishable": sum(1 for f in per_facility if f["status"] == "publishable"),
        "blocked": sum(1 for f in per_facility if f["status"] == "blocked"),
        "blocker_summary": dict(blocker_counts.most_common()),
        "per_facility": per_facility,
    }


def main() -> None:
    state = sys.argv[1] if len(sys.argv) > 1 else "NH"
    with session_factory() as session:
        report = analyze_blockers(session, state)
    print(json.dumps(report, indent=2, default=str))


if __name__ == "__main__":
    main()
