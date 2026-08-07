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
    PriceRecordProcedureMapping,
    PricingAnomaly,
    PricingHealthScore,
)


def rebuild_price_summaries(session: Session) -> dict[str, int]:
    session.execute(delete(FacilityProcedurePriceSummary))
    session.execute(delete(FacilityProcedurePriceObservation))
    records = session.execute(
        select(HospitalPriceRecord, PriceRecordProcedureMapping)
        .join(
            PriceRecordProcedureMapping,
            PriceRecordProcedureMapping.hospital_price_record_id == HospitalPriceRecord.id,
        )
        .where(PriceRecordProcedureMapping.reviewed.is_(True))
    ).all()
    observation_count = 0
    for record, mapping in records:
        blocked = (
            session.scalar(
                select(func.count(PricingAnomaly.id)).where(
                    PricingAnomaly.hospital_price_record_id == record.id,
                    PricingAnomaly.status == "open",
                    PricingAnomaly.severity.in_(["error", "critical"]),
                )
            )
            or 0
        )
        status = (
            "suppressed"
            if blocked
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
        for rate in session.scalars(
            select(HospitalPriceRateDetail).where(
                HospitalPriceRateDetail.hospital_price_record_id == record.id
            )
        ):
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
    for key, observations in groups.items():
        cash = [item.amount for item in observations if item.price_type == "discounted_cash"]
        negotiated = [item.amount for item in observations if item.price_type == "payer_negotiated"]
        record = session.get(HospitalPriceRecord, observations[0].hospital_price_record_id)
        if record is None:
            continue
        session.add(
            FacilityProcedurePriceSummary(
                facility_id=key[0],
                procedure_id=key[1],
                payer_entity_id=key[2],
                insurance_plan_entity_id=key[3],
                service_setting=str(key[4]),
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
    summary_count = session.scalar(select(func.count(FacilityProcedurePriceSummary.id))) or 0
    session.commit()
    return {"observations": observation_count, "summaries": summary_count}


def evaluate_pricing_health(session: Session) -> dict[str, int | float]:
    session.execute(delete(PricingHealthScore))
    scores: list[float] = []
    for facility in session.scalars(select(Facility)):
        sources = session.scalars(
            select(FacilityPriceSource).where(
                FacilityPriceSource.facility_id == facility.id, FacilityPriceSource.active.is_(True)
            )
        ).all()
        source_files = [item.source_file_id for item in sources if item.source_file_id]
        downloaded = bool(source_files)
        parsed = (
            session.scalar(
                select(func.count(HospitalPriceRecord.id)).where(
                    HospitalPriceRecord.facility_id == facility.id
                )
            )
            or 0
        )
        mapped = (
            session.scalar(
                select(func.count(PriceRecordProcedureMapping.id))
                .join(HospitalPriceRecord)
                .where(
                    HospitalPriceRecord.facility_id == facility.id,
                    PriceRecordProcedureMapping.reviewed.is_(True),
                )
            )
            or 0
        )
        rates = (
            session.scalar(
                select(func.count(HospitalPriceRateDetail.id))
                .join(HospitalPriceRecord)
                .where(HospitalPriceRecord.facility_id == facility.id)
            )
            or 0
        )
        normalized_rates = (
            session.scalar(
                select(func.count(HospitalPriceRateDetail.id))
                .join(HospitalPriceRecord)
                .where(
                    HospitalPriceRecord.facility_id == facility.id,
                    HospitalPriceRateDetail.payer_entity_id.is_not(None),
                )
            )
            or 0
        )
        anomalies = (
            session.scalar(
                select(func.count(PricingAnomaly.id))
                .join(HospitalPriceRecord)
                .where(
                    HospitalPriceRecord.facility_id == facility.id,
                    PricingAnomaly.status == "open",
                    PricingAnomaly.severity.in_(["error", "critical"]),
                )
            )
            or 0
        )
        summaries = (
            session.scalar(
                select(func.count(FacilityProcedurePriceSummary.id)).where(
                    FacilityProcedurePriceSummary.facility_id == facility.id,
                    FacilityProcedurePriceSummary.publication_status == "publishable",
                )
            )
            or 0
        )
        components = [
            100 if sources else 0,
            100 if downloaded else 0,
            100 if parsed else 0,
            round(mapped / parsed * 100, 2) if parsed else 0,
            round(normalized_rates / rates * 100, 2) if rates else (100 if parsed else 0),
            100 if anomalies == 0 else max(0, 100 - anomalies * 20),
            100 if downloaded else 0,
            min(100, summaries * 10),
        ]
        overall = round(sum(components) / len(components), 2)
        scores.append(overall)
        session.add(
            PricingHealthScore(
                facility_id=facility.id,
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
