"""Quality metrics and anomaly auto-triage for hospital pricing data."""

from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from packages.database import (
    Facility,
    HospitalPriceRecord,
    PricingAnomaly,
    PricingHealthScore,
)

# DRGs known to have legitimately high prices (>$1M)
HIGH_COST_DRGS = frozenset(
    {
        "001",
        "002",
        "003",  # Heart transplant
        "652",
        "653",  # Kidney transplant
        "480",
        "481",
        "482",  # Hip replacement revisions
    }
)


def review_open_anomalies(session: Session) -> dict[str, int]:
    """Apply auto-triage rules to open anomalies. Returns counts per action taken."""
    suppressed = 0
    downgraded = 0
    kept = 0

    anomalies = session.scalars(select(PricingAnomaly).where(PricingAnomaly.status == "open")).all()

    for anomaly in anomalies:
        record = (
            session.get(HospitalPriceRecord, anomaly.hospital_price_record_id)
            if anomaly.hospital_price_record_id
            else None
        )

        # Rule 1: suspicious_zero on lab items → auto-suppress
        if anomaly.rule_key == "suspicious_zero" and record:
            setting = (record.setting or "").lower()
            if setting in ("laboratory", "lab"):
                anomaly.status = "auto_suppressed"
                anomaly.resolution_notes = "Auto-suppressed: zero price on lab item is common"
                anomaly.reviewed_at = datetime.now(UTC)
                suppressed += 1
                continue

        # Rule 2: blank_payer with gross_charge → downgrade to warning
        if (
            anomaly.rule_key == "blank_payer"
            and record
            and record.gross_charge is not None
            and record.gross_charge > 0
        ):
            anomaly.severity = "warning"
            anomaly.resolution_notes = (
                "Downgraded: record has valid gross charge despite blank payer"
            )
            anomaly.reviewed_at = datetime.now(UTC)
            downgraded += 1
            continue

        # Rule 3: extremely_large_price on known high-cost DRGs → auto-suppress
        if anomaly.rule_key == "extremely_large_price" and record:
            raw_code = (record.raw_payload or {}).get("code", "")
            if str(raw_code) in HIGH_COST_DRGS:
                anomaly.status = "auto_suppressed"
                anomaly.resolution_notes = (
                    f"Auto-suppressed: DRG {raw_code} is a known high-cost procedure"
                )
                anomaly.reviewed_at = datetime.now(UTC)
                suppressed += 1
                continue

        kept += 1

    session.commit()
    return {"suppressed": suppressed, "downgraded": downgraded, "kept_open": kept}


def generate_quality_scores(session: Session) -> list[dict[str, object]]:
    """Generate per-facility quality scores from anomaly and coverage data."""
    results: list[dict[str, object]] = []

    health_scores = session.scalars(
        select(PricingHealthScore).order_by(PricingHealthScore.overall_score)
    ).all()

    for score in health_scores:
        facility = session.get(Facility, score.facility_id)
        if not facility:
            continue

        # Count open anomalies by severity
        anomaly_counts: dict[str, int] = {}
        for severity, count in session.execute(
            select(PricingAnomaly.severity, func.count(PricingAnomaly.id))
            .join(HospitalPriceRecord)
            .where(
                HospitalPriceRecord.facility_id == score.facility_id,
                PricingAnomaly.status == "open",
            )
            .group_by(PricingAnomaly.severity)
        ).all():
            anomaly_counts[severity] = count

        results.append(
            {
                "facility_id": str(score.facility_id),
                "facility_name": facility.display_name,
                "overall_score": float(score.overall_score),
                "source_discovery_score": float(score.source_discovery_score),
                "download_score": float(score.download_score),
                "parse_score": float(score.parse_score),
                "mapping_score": float(score.mapping_score),
                "payer_normalization_score": float(score.payer_normalization_score),
                "anomaly_score": float(score.anomaly_score),
                "freshness_score": float(score.freshness_score),
                "price_coverage_score": float(score.price_coverage_score),
                "open_anomalies": anomaly_counts,
                "details": score.details,
            }
        )

    return results
