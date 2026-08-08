from collections import defaultdict
from datetime import UTC, datetime
from decimal import Decimal
from statistics import median

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from packages.database import (
    Facility,
    FacilityPriceSource,
    FacilityProcedurePriceObservation,
    FacilityProcedurePriceSummary,
    HospitalPriceRateDetail,
    HospitalPriceRecord,
    PriceChangeSnapshot,
    PriceRecordProcedureMapping,
    PricingAnomaly,
    PricingHealthScore,
)


def freshness_score(last_download: datetime | None) -> float:
    """Calculate freshness score based on days since last download."""
    if last_download is None:
        return 0.0
    now = datetime.now(UTC)
    # Handle timezone-naive datetimes (e.g., from SQLite)
    if last_download.tzinfo is None:
        last_download = last_download.replace(tzinfo=UTC)
    days = (now - last_download).days
    if days <= 30:
        return 100.0
    if days <= 60:
        return 80.0
    if days <= 90:
        return 50.0
    if days <= 180:
        return 20.0
    return 0.0


def rebuild_price_summaries(session: Session) -> dict[str, int]:
    # Snapshot current summaries before deleting (for historical price tracking)
    existing_summaries = session.scalars(
        select(FacilityProcedurePriceSummary).where(
            FacilityProcedurePriceSummary.publication_status == "publishable"
        )
    ).all()
    previous_prices: dict[
        tuple[object, object, object, str], tuple[Decimal | None, Decimal | None]
    ] = {}
    for s in existing_summaries:
        key = (s.facility_id, s.procedure_id, s.payer_entity_id, s.service_setting)
        previous_prices[key] = (s.cash_price_median, s.negotiated_price_median)

    session.execute(delete(FacilityProcedurePriceSummary))
    session.execute(delete(FacilityProcedurePriceObservation))

    # Pre-load blocked record IDs in one query (O(1) set lookup per record)
    blocked_ids: set[object] = set(
        session.scalars(
            select(PricingAnomaly.hospital_price_record_id)
            .where(
                PricingAnomaly.status == "open",
                PricingAnomaly.severity.in_(["error", "critical"]),
                PricingAnomaly.hospital_price_record_id.is_not(None),
            )
            .distinct()
        )
    )

    records = session.execute(
        select(HospitalPriceRecord, PriceRecordProcedureMapping)
        .join(
            PriceRecordProcedureMapping,
            PriceRecordProcedureMapping.hospital_price_record_id == HospitalPriceRecord.id,
        )
        .where(PriceRecordProcedureMapping.reviewed.is_(True))
    ).all()

    # Pre-load all rate details for matched records in one query
    matched_record_ids = [record.id for record, _mapping in records]
    rate_details_by_record: dict[object, list[HospitalPriceRateDetail]] = defaultdict(list)
    if matched_record_ids:
        for rate in session.scalars(
            select(HospitalPriceRateDetail).where(
                HospitalPriceRateDetail.hospital_price_record_id.in_(matched_record_ids)
            )
        ):
            rate_details_by_record[rate.hospital_price_record_id].append(rate)

    observation_count = 0
    for record, mapping in records:
        is_blocked = record.id in blocked_ids
        status = (
            "suppressed"
            if is_blocked
            else "publishable"
            if record.parser_name.startswith("cms_hpt")
            else "review_required"
        )
        values = (
            ("gross", record.gross_charge),
            ("discounted_cash", record.discounted_cash_price),
            ("deidentified_min", record.deidentified_minimum_negotiated_rate),
            ("deidentified_max", record.deidentified_maximum_negotiated_rate),
        )
        for price_type, amount in values:
            if amount is not None:
                session.add(
                    FacilityProcedurePriceObservation(
                        facility_id=record.facility_id,
                        procedure_id=mapping.procedure_id,
                        hospital_price_record_id=record.id,
                        price_type=price_type,
                        amount=amount,
                        service_setting=record.setting or "unknown",
                        included_component_scope=record.billing_class or "unknown",
                        source_confidence=1
                        if record.parser_name.startswith("cms_hpt")
                        else Decimal("0.8"),
                        mapping_confidence=mapping.confidence_score,
                        publication_status=status,
                    )
                )
                observation_count += 1
        # Use pre-loaded rate details instead of per-record query
        for rate in rate_details_by_record.get(record.id, []):
            if rate.negotiated_rate is not None:
                session.add(
                    FacilityProcedurePriceObservation(
                        facility_id=record.facility_id,
                        procedure_id=mapping.procedure_id,
                        hospital_price_record_id=record.id,
                        hospital_price_rate_detail_id=rate.id,
                        payer_entity_id=rate.payer_entity_id,
                        insurance_plan_entity_id=rate.insurance_plan_entity_id,
                        price_type="payer_negotiated",
                        amount=rate.negotiated_rate,
                        service_setting=record.setting or "unknown",
                        included_component_scope=record.billing_class or "unknown",
                        source_confidence=1
                        if record.parser_name.startswith("cms_hpt")
                        else Decimal("0.8"),
                        mapping_confidence=mapping.confidence_score,
                        publication_status=status if rate.payer_entity_id else "review_required",
                    )
                )
                observation_count += 1
    session.flush()
    groups: dict[tuple[object, ...], list[FacilityProcedurePriceObservation]] = defaultdict(list)
    for observation in session.scalars(
        select(FacilityProcedurePriceObservation).where(
            FacilityProcedurePriceObservation.publication_status == "publishable"
        )
    ):
        groups[
            (
                observation.facility_id,
                observation.procedure_id,
                observation.payer_entity_id,
                observation.insurance_plan_entity_id,
                observation.service_setting,
            )
        ].append(observation)
    for group_key, observations in groups.items():
        cash = [item.amount for item in observations if item.price_type == "discounted_cash"]
        negotiated = [item.amount for item in observations if item.price_type == "payer_negotiated"]
        record = session.get(HospitalPriceRecord, observations[0].hospital_price_record_id)
        if record is None:
            continue
        session.add(
            FacilityProcedurePriceSummary(
                facility_id=group_key[0],
                procedure_id=group_key[1],
                payer_entity_id=group_key[2],
                insurance_plan_entity_id=group_key[3],
                service_setting=str(group_key[4]),
                cash_price_min=min(cash) if cash else None,
                cash_price_max=max(cash) if cash else None,
                cash_price_median=Decimal(median(cash)) if cash else None,
                negotiated_price_min=min(negotiated) if negotiated else None,
                negotiated_price_max=max(negotiated) if negotiated else None,
                negotiated_price_median=Decimal(median(negotiated)) if negotiated else None,
                record_count=len({item.hospital_price_record_id for item in observations}),
                source_file_id=record.source_file_id,
                calculated_at=datetime.now(UTC),
                publication_status="publishable",
                completeness_score=100 if cash or negotiated else 50,
                notes=(
                    "Facility/professional scope follows the source billing class; "
                    "other charges may be separate."
                ),
            )
        )
    session.flush()

    # Create change snapshots for any prices that changed
    if previous_prices:
        for new_summary in session.scalars(
            select(FacilityProcedurePriceSummary).where(
                FacilityProcedurePriceSummary.publication_status == "publishable"
            )
        ):
            snap_key = (
                new_summary.facility_id,
                new_summary.procedure_id,
                new_summary.payer_entity_id,
                new_summary.service_setting,
            )
            prev = previous_prices.get(snap_key)
            if prev is None:
                continue
            prev_cash, prev_neg = prev
            curr_cash = new_summary.cash_price_median
            curr_neg = new_summary.negotiated_price_median
            if prev_cash == curr_cash and prev_neg == curr_neg:
                continue

            def _pct(old: Decimal | None, new: Decimal | None) -> Decimal | None:
                if old and new and old != 0:
                    return Decimal(str(round(float((new - old) / old * 100), 4)))
                return None

            session.add(
                PriceChangeSnapshot(
                    facility_id=new_summary.facility_id,
                    procedure_id=new_summary.procedure_id,
                    payer_entity_id=new_summary.payer_entity_id,
                    service_setting=new_summary.service_setting,
                    previous_cash_median=prev_cash,
                    current_cash_median=curr_cash,
                    cash_change_pct=_pct(prev_cash, curr_cash),
                    previous_negotiated_median=prev_neg,
                    current_negotiated_median=curr_neg,
                    negotiated_change_pct=_pct(prev_neg, curr_neg),
                    snapshot_at=datetime.now(UTC),
                )
            )
        session.flush()

    summary_count = session.scalar(select(func.count(FacilityProcedurePriceSummary.id))) or 0
    session.commit()
    return {"observations": observation_count, "summaries": summary_count}


def evaluate_pricing_health(session: Session) -> dict[str, int | float]:
    session.execute(delete(PricingHealthScore))

    # Pre-load all counts in batch queries instead of per-facility N+1
    facility_ids = list(session.scalars(select(Facility.id)))

    # Per-facility record counts
    record_counts: dict[object, int] = {
        row[0]: row[1]
        for row in session.execute(
            select(HospitalPriceRecord.facility_id, func.count(HospitalPriceRecord.id)).group_by(
                HospitalPriceRecord.facility_id
            )
        ).all()
    }

    # Per-facility reviewed mapping counts
    mapping_counts: dict[object, int] = {
        row[0]: row[1]
        for row in session.execute(
            select(HospitalPriceRecord.facility_id, func.count(PriceRecordProcedureMapping.id))
            .join(HospitalPriceRecord)
            .where(PriceRecordProcedureMapping.reviewed.is_(True))
            .group_by(HospitalPriceRecord.facility_id)
        ).all()
    }

    # Per-facility total rate counts
    rate_counts: dict[object, int] = {
        row[0]: row[1]
        for row in session.execute(
            select(HospitalPriceRecord.facility_id, func.count(HospitalPriceRateDetail.id))
            .join(HospitalPriceRecord)
            .group_by(HospitalPriceRecord.facility_id)
        ).all()
    }

    # Per-facility normalized rate counts (payer matched)
    normalized_rate_counts: dict[object, int] = {
        row[0]: row[1]
        for row in session.execute(
            select(HospitalPriceRecord.facility_id, func.count(HospitalPriceRateDetail.id))
            .join(HospitalPriceRecord)
            .where(HospitalPriceRateDetail.payer_entity_id.is_not(None))
            .group_by(HospitalPriceRecord.facility_id)
        ).all()
    }

    # Per-facility open high-severity anomaly counts
    anomaly_counts: dict[object, int] = {
        row[0]: row[1]
        for row in session.execute(
            select(HospitalPriceRecord.facility_id, func.count(PricingAnomaly.id))
            .join(HospitalPriceRecord)
            .where(
                PricingAnomaly.status == "open",
                PricingAnomaly.severity.in_(["error", "critical"]),
            )
            .group_by(HospitalPriceRecord.facility_id)
        ).all()
    }

    # Per-facility publishable summary counts
    summary_counts: dict[object, int] = {
        row[0]: row[1]
        for row in session.execute(
            select(
                FacilityProcedurePriceSummary.facility_id,
                func.count(FacilityProcedurePriceSummary.id),
            )
            .where(FacilityProcedurePriceSummary.publication_status == "publishable")
            .group_by(FacilityProcedurePriceSummary.facility_id)
        ).all()
    }

    # Per-facility source info
    facility_sources: dict[object, list[FacilityPriceSource]] = defaultdict(list)
    for source in session.scalars(
        select(FacilityPriceSource).where(FacilityPriceSource.active.is_(True))
    ):
        facility_sources[source.facility_id].append(source)

    scores: list[float] = []
    for facility_id in facility_ids:
        sources = facility_sources.get(facility_id, [])
        source_files = [s.source_file_id for s in sources if s.source_file_id]
        downloaded = bool(source_files)
        parsed = record_counts.get(facility_id, 0)
        mapped = mapping_counts.get(facility_id, 0)
        rates = rate_counts.get(facility_id, 0)
        normalized_rates = normalized_rate_counts.get(facility_id, 0)
        anomalies = anomaly_counts.get(facility_id, 0)
        summaries = summary_counts.get(facility_id, 0)
        # Calculate actual freshness from most recent download
        latest_download = max(
            (s.last_successful_download_at for s in sources if s.last_successful_download_at),
            default=None,
        )
        components = [
            100 if sources else 0,
            100 if downloaded else 0,
            100 if parsed else 0,
            round(mapped / parsed * 100, 2) if parsed else 0,
            round(normalized_rates / rates * 100, 2) if rates else (100 if parsed else 0),
            100 if anomalies == 0 else max(0, 100 - anomalies * 20),
            freshness_score(latest_download),
            min(100, summaries * 10),
        ]
        overall = round(sum(components) / len(components), 2)
        scores.append(overall)
        session.add(
            PricingHealthScore(
                facility_id=facility_id,
                source_discovery_score=components[0],
                download_score=components[1],
                parse_score=components[2],
                mapping_score=components[3],
                payer_normalization_score=components[4],
                anomaly_score=components[5],
                freshness_score=components[6],
                price_coverage_score=components[7],
                overall_score=overall,
                details={
                    "records": parsed,
                    "reviewed_mappings": mapped,
                    "publishable_summaries": summaries,
                    "open_high_anomalies": anomalies,
                },
            )
        )
    session.commit()
    return {
        "facilities": len(scores),
        "average_pricing_health": round(sum(scores) / len(scores), 2) if scores else 0,
    }
