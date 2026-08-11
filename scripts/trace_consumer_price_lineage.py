"""Export exact consumer-price lineage for a bounded procedure/facility set."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

from sqlalchemy import select

from packages.database import (
    Facility,
    FacilityLocation,
    FacilityProcedurePriceObservation,
    HospitalPriceRateDetail,
    HospitalPriceRecord,
    InsurancePlanEntity,
    PayerEntity,
    PriceRecordProcedureMapping,
    PriceServiceCode,
    Procedure,
    SourceFile,
    session_factory,
)

DEFAULT_CCNS = ("300034", "300001", "301306")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--procedure", default="mri-knee-without-contrast")
    parser.add_argument("--ccn", action="append", dest="ccns")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    ccns = tuple(args.ccns or DEFAULT_CCNS)

    with session_factory() as session:
        procedure = session.scalar(select(Procedure).where(Procedure.slug == args.procedure))
        if procedure is None:
            raise SystemExit(f"procedure not found: {args.procedure}")
        statement = (
            select(
                FacilityProcedurePriceObservation,
                HospitalPriceRecord,
                HospitalPriceRateDetail,
                PriceRecordProcedureMapping,
                Facility,
                FacilityLocation,
                SourceFile,
                PayerEntity,
                InsurancePlanEntity,
            )
            .join(
                HospitalPriceRecord,
                HospitalPriceRecord.id
                == FacilityProcedurePriceObservation.hospital_price_record_id,
            )
            .outerjoin(
                HospitalPriceRateDetail,
                HospitalPriceRateDetail.id
                == FacilityProcedurePriceObservation.hospital_price_rate_detail_id,
            )
            .join(
                PriceRecordProcedureMapping,
                (PriceRecordProcedureMapping.hospital_price_record_id == HospitalPriceRecord.id)
                & (PriceRecordProcedureMapping.procedure_id == procedure.id),
            )
            .join(Facility, Facility.id == FacilityProcedurePriceObservation.facility_id)
            .join(
                FacilityLocation,
                FacilityLocation.id == FacilityProcedurePriceObservation.facility_location_id,
            )
            .join(SourceFile, SourceFile.id == HospitalPriceRecord.source_file_id)
            .outerjoin(PayerEntity, PayerEntity.id == HospitalPriceRateDetail.payer_entity_id)
            .outerjoin(
                InsurancePlanEntity,
                InsurancePlanEntity.id == HospitalPriceRateDetail.insurance_plan_entity_id,
            )
            .where(
                Facility.cms_certification_number.in_(ccns),
                FacilityProcedurePriceObservation.procedure_id == procedure.id,
                FacilityProcedurePriceObservation.publication_status == "publishable",
                SourceFile.source_url.not_like("file://%"),
            )
            .order_by(
                Facility.display_name,
                FacilityLocation.city,
                HospitalPriceRecord.source_record_identifier,
                FacilityProcedurePriceObservation.price_type,
            )
        )
        rows = session.execute(statement).all()
        record_ids = {record.id for _obs, record, *_rest in rows}
        codes_by_record: dict[object, list[dict[str, object]]] = defaultdict(list)
        if record_ids:
            for code in session.scalars(
                select(PriceServiceCode)
                .where(PriceServiceCode.hospital_price_record_id.in_(record_ids))
                .order_by(PriceServiceCode.code_system, PriceServiceCode.code)
            ):
                codes_by_record[code.hospital_price_record_id].append(
                    {
                        "system": code.code_system,
                        "code": code.code,
                        "modifier": code.modifier,
                        "raw_type": code.raw_code_type,
                        "raw_code": code.raw_code,
                    }
                )

        details: list[dict[str, object]] = []
        for observation, record, rate, mapping, facility, location, source, payer, plan in rows:
            details.append(
                {
                    "facility": facility.display_name,
                    "ccn": facility.cms_certification_number,
                    "physical_location": location.location_name or location.city,
                    "location_id": str(location.id),
                    "source_file_id": str(source.id),
                    "source_url": source.source_url,
                    "source_checksum": source.checksum_sha256,
                    "source_published_at": source.source_published_at,
                    "source_last_modified": source.last_modified,
                    "downloaded_at": source.downloaded_at,
                    "procedure": procedure.consumer_name,
                    "procedure_slug": procedure.slug,
                    "mapping_method": mapping.mapping_method,
                    "mapping_confidence": mapping.confidence_score,
                    "mapping_reviewed": mapping.reviewed,
                    "original_description": record.raw_description,
                    "codes": codes_by_record.get(record.id, []),
                    "service_setting": record.setting or "unknown",
                    "billing_class": record.billing_class or "unknown",
                    "cash_price": record.discounted_cash_price,
                    "gross_charge": record.gross_charge,
                    "payer_raw": None if rate is None else rate.source_payer_name,
                    "payer_normalized": None if payer is None else payer.canonical_name,
                    "payer_slug": None if payer is None else payer.slug,
                    "plan_raw": None if rate is None else rate.source_plan_name,
                    "plan_normalized": None if plan is None else plan.canonical_name,
                    "negotiated_rate": None if rate is None else rate.negotiated_rate,
                    "negotiated_rate_type": (None if rate is None else rate.negotiated_rate_type),
                    "price_type": observation.price_type,
                    "published_amount": observation.amount,
                    "source_record_identifier": record.source_record_identifier,
                    "source_line_number": record.source_line_number,
                    "source_payload_hash": record.source_payload_hash,
                    "observation_id": str(observation.id),
                }
            )

    facility_counts = Counter(str(item["facility"]) for item in details)
    cash_by_facility: dict[str, set[str]] = defaultdict(set)
    semantic_groups: Counter[tuple[str, str, str, str]] = Counter()
    for item in details:
        facility_name = str(item["facility"])
        if item["price_type"] == "discounted_cash":
            cash_by_facility[facility_name].add(str(item["published_amount"]))
        semantic_groups[
            (
                facility_name,
                str(item["service_setting"]),
                str(item["billing_class"]),
                str(item["price_type"]),
            )
        ] += 1
    report = {
        "read_only": True,
        "procedure": args.procedure,
        "ccns": ccns,
        "observation_count": len(details),
        "facility_observation_counts": dict(sorted(facility_counts.items())),
        "cash_values_by_facility": {
            key: sorted(values) for key, values in sorted(cash_by_facility.items())
        },
        "semantic_group_counts": [
            {
                "facility": key[0],
                "setting": key[1],
                "billing_class": key[2],
                "price_type": key[3],
                "count": count,
            }
            for key, count in sorted(semantic_groups.items())
        ],
        "details": details,
    }
    payload = json.dumps(report, default=str, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload)
    print(
        "PRICE_LINEAGE_SUMMARY="
        + json.dumps(
            {key: value for key, value in report.items() if key != "details"},
            default=str,
            separators=(",", ":"),
        )
    )


if __name__ == "__main__":
    main()
