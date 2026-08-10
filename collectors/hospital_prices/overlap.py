import itertools
import uuid
from collections import Counter
from dataclasses import dataclass

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from packages.database import (
    FacilityPriceSource,
    HospitalPriceRateDetail,
    HospitalPriceRecord,
    PriceServiceCode,
    PriceSourceOverlapAnalysis,
    SourceFile,
)


@dataclass(frozen=True)
class SourceProfile:
    source_file_id: uuid.UUID
    location_id: uuid.UUID | None
    checksum: str
    record_count: int
    code_systems: dict[str, int]
    codes: set[tuple[str, str]]
    descriptions: set[str]
    price_tuples: set[tuple[str | None, ...]]
    payer_plans: set[tuple[uuid.UUID | None, uuid.UUID | None]]


def _ratio(left: set[object], right: set[object]) -> float:
    if not left or not right:
        return 0.0
    return round(len(left & right) / min(len(left), len(right)), 6)


def profile_source(session: Session, source: FacilityPriceSource) -> SourceProfile:
    if source.source_file_id is None:
        raise ValueError("source must have a downloaded source file")
    source_file = session.get(SourceFile, source.source_file_id)
    if source_file is None:
        raise ValueError("source file not found")
    records = session.execute(
        select(
            HospitalPriceRecord.service_description_normalized,
            HospitalPriceRecord.gross_charge,
            HospitalPriceRecord.discounted_cash_price,
            HospitalPriceRecord.deidentified_minimum_negotiated_rate,
            HospitalPriceRecord.deidentified_maximum_negotiated_rate,
            HospitalPriceRecord.setting,
            HospitalPriceRecord.billing_class,
        ).where(HospitalPriceRecord.source_file_id == source.source_file_id)
    ).all()
    codes: set[tuple[str, str]] = set()
    code_systems: Counter[str] = Counter()
    for code_system, code in session.execute(
        select(PriceServiceCode.code_system, PriceServiceCode.code)
        .join(HospitalPriceRecord)
        .where(HospitalPriceRecord.source_file_id == source.source_file_id)
    ):
        codes.add((code_system, code))
        code_systems[code_system] += 1
    payer_plans: set[tuple[uuid.UUID | None, uuid.UUID | None]] = set()
    for payer_id, plan_id in session.execute(
        select(
            HospitalPriceRateDetail.payer_entity_id,
            HospitalPriceRateDetail.insurance_plan_entity_id,
        )
        .join(HospitalPriceRecord)
        .where(HospitalPriceRecord.source_file_id == source.source_file_id)
        .distinct()
    ):
        payer_plans.add((payer_id, plan_id))
    return SourceProfile(
        source_file_id=source.source_file_id,
        location_id=source.facility_location_id,
        checksum=source_file.checksum_sha256,
        record_count=len(records),
        code_systems=dict(code_systems),
        codes=codes,
        descriptions={
            record.service_description_normalized
            for record in records
            if record.service_description_normalized
        },
        price_tuples={
            (
                str(record.gross_charge) if record.gross_charge is not None else None,
                str(record.discounted_cash_price)
                if record.discounted_cash_price is not None
                else None,
                str(record.deidentified_minimum_negotiated_rate)
                if record.deidentified_minimum_negotiated_rate is not None
                else None,
                str(record.deidentified_maximum_negotiated_rate)
                if record.deidentified_maximum_negotiated_rate is not None
                else None,
                record.setting,
                record.billing_class,
            )
            for record in records
        },
        payer_plans=payer_plans,
    )


def classify_profiles(left: SourceProfile, right: SourceProfile) -> tuple[str, dict[str, object]]:
    code_overlap = _ratio(set(left.codes), set(right.codes))
    description_overlap = _ratio(set(left.descriptions), set(right.descriptions))
    price_overlap = _ratio(set(left.price_tuples), set(right.price_tuples))
    payer_overlap = _ratio(set(left.payer_plans), set(right.payer_plans))
    metrics: dict[str, object] = {
        "left_record_count": left.record_count,
        "right_record_count": right.record_count,
        "left_code_systems": left.code_systems,
        "right_code_systems": right.code_systems,
        "exact_code_overlap": code_overlap,
        "normalized_description_overlap": description_overlap,
        "price_tuple_overlap": price_overlap,
        "payer_plan_overlap": payer_overlap,
        "same_checksum": left.checksum == right.checksum,
        "same_location": left.location_id == right.location_id and left.location_id is not None,
    }
    if left.checksum == right.checksum:
        classification = "DUPLICATE_SOURCE_VERSION"
    elif (
        left.location_id is not None
        and right.location_id is not None
        and left.location_id != right.location_id
        and code_overlap >= 0.9
        and description_overlap >= 0.9
    ):
        classification = "DISTINCT_LOCATION_OVERLAPPING_SCHEDULE"
    elif metrics["same_location"] and price_overlap >= 0.95:
        classification = "DUPLICATE_SOURCE_VERSION"
    elif code_overlap >= 0.9 and price_overlap < 0.5:
        classification = "DISTINCT_PRICE_SCHEDULE"
    elif code_overlap >= 0.25:
        classification = "PARTIAL_OVERLAP"
    else:
        classification = "UNKNOWN_REVIEW_REQUIRED"
    return classification, metrics


def analyze_facility_sources(session: Session, facility_id: uuid.UUID) -> int:
    sources = list(
        session.scalars(
            select(FacilityPriceSource).where(
                FacilityPriceSource.facility_id == facility_id,
                FacilityPriceSource.active.is_(True),
                FacilityPriceSource.source_file_id.is_not(None),
            )
        )
    )
    profiles = {source.id: profile_source(session, source) for source in sources}
    session.execute(
        delete(PriceSourceOverlapAnalysis).where(
            PriceSourceOverlapAnalysis.facility_id == facility_id
        )
    )
    count = 0
    for left_source, right_source in itertools.combinations(sources, 2):
        left = profiles[left_source.id]
        right = profiles[right_source.id]
        if str(left.source_file_id) > str(right.source_file_id):
            left, right = right, left
        classification, metrics = classify_profiles(left, right)
        session.add(
            PriceSourceOverlapAnalysis(
                facility_id=facility_id,
                left_source_file_id=left.source_file_id,
                right_source_file_id=right.source_file_id,
                left_location_id=left.location_id,
                right_location_id=right.location_id,
                classification=classification,
                metrics=metrics,
                evidence={
                    "method": "deterministic_source_profile_v1",
                    "location_association_required": True,
                },
            )
        )
        count += 1
    session.commit()
    return count
