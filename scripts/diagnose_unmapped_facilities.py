"""Pinpoint the 'parsed-but-unmapped' NH coverage gap (read-only).

A facility becomes consumer-publishable only when its imported price records
carry a reviewed, approved-code procedure mapping (see
``collectors/hospital_prices/projections.py``). Some facilities parse cleanly but
publish nothing because their billing codes have no approved
``ProcedureCodeMapping`` — the "parsed-but-unmapped" gap the handoff calls out.

This diagnostic finds those facilities (records > 0, publishable summaries == 0)
and ranks the most frequent unmapped ``(code_system, code)`` on their records so a
human can author *reviewed* mappings — either approved ``ProcedureCodeMapping``
rows (``scripts/seed_price_mappings.py``) for standard codes, or reviewed
``data/fixtures/cdm_crosswalk.json`` entries for local/CDM codes.

It is strictly read-only and proposes NOTHING automatically: no fuzzy matching,
no writes. Run it against prod via the read-only price-audit job:

    gcloud run jobs execute carevero-beta-price-audit --region=us-east4 \
        --args="-m,scripts.diagnose_unmapped_facilities,--state,NH"
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime

from sqlalchemy import and_, exists, func, select
from sqlalchemy.orm import Session

from packages.database import (
    Facility,
    FacilityLocation,
    FacilityProcedurePriceSummary,
    HospitalPriceRecord,
    PriceRecordProcedureMapping,
    PriceServiceCode,
    session_factory,
)


def _state_facility_ids(session: Session, state: str) -> set[object]:
    return set(
        session.scalars(
            select(Facility.id)
            .distinct()
            .join(FacilityLocation)
            .where(FacilityLocation.state == state.upper(), Facility.active.is_(True))
        )
    )


def _record_counts(session: Session, facility_ids: set[object]) -> dict[object, int]:
    return {
        row[0]: row[1]
        for row in session.execute(
            select(HospitalPriceRecord.facility_id, func.count(HospitalPriceRecord.id))
            .where(HospitalPriceRecord.facility_id.in_(facility_ids))
            .group_by(HospitalPriceRecord.facility_id)
        ).all()
    }


def _reviewed_mapping_counts(session: Session, facility_ids: set[object]) -> dict[object, int]:
    return {
        row[0]: row[1]
        for row in session.execute(
            select(HospitalPriceRecord.facility_id, func.count(PriceRecordProcedureMapping.id))
            .join(
                PriceRecordProcedureMapping,
                PriceRecordProcedureMapping.hospital_price_record_id == HospitalPriceRecord.id,
            )
            .where(
                HospitalPriceRecord.facility_id.in_(facility_ids),
                PriceRecordProcedureMapping.reviewed.is_(True),
            )
            .group_by(HospitalPriceRecord.facility_id)
        ).all()
    }


def _publishable_summary_counts(session: Session, facility_ids: set[object]) -> dict[object, int]:
    return {
        row[0]: row[1]
        for row in session.execute(
            select(
                FacilityProcedurePriceSummary.facility_id,
                func.count(FacilityProcedurePriceSummary.id),
            )
            .where(
                FacilityProcedurePriceSummary.facility_id.in_(facility_ids),
                FacilityProcedurePriceSummary.publication_status == "publishable",
            )
            .group_by(FacilityProcedurePriceSummary.facility_id)
        ).all()
    }


def _code_system_distribution(session: Session, facility_id: object) -> dict[str, int]:
    rows = session.execute(
        select(PriceServiceCode.code_system, func.count(PriceServiceCode.id))
        .join(
            HospitalPriceRecord, PriceServiceCode.hospital_price_record_id == HospitalPriceRecord.id
        )
        .where(HospitalPriceRecord.facility_id == facility_id)
        .group_by(PriceServiceCode.code_system)
    ).all()
    return {str(row[0]): row[1] for row in rows}


def _top_unmapped_codes(
    session: Session, facility_id: object, limit: int
) -> list[dict[str, object]]:
    """Most frequent codes on records that have NO reviewed procedure mapping."""
    reviewed_for_record = exists().where(
        and_(
            PriceRecordProcedureMapping.hospital_price_record_id == HospitalPriceRecord.id,
            PriceRecordProcedureMapping.reviewed.is_(True),
        )
    )
    rows = session.execute(
        select(
            PriceServiceCode.code_system,
            PriceServiceCode.code,
            func.count(PriceServiceCode.id).label("count"),
            func.min(HospitalPriceRecord.raw_description).label("sample_description"),
            # The raw (pre-normalization) type label the source used. A code is
            # UNKNOWN when this label isn't one _code_system() recognizes — seeing
            # it tells us whether the fix is code-type recognition vs. a crosswalk.
            func.min(PriceServiceCode.raw_code_type).label("raw_code_type"),
        )
        .join(
            HospitalPriceRecord, PriceServiceCode.hospital_price_record_id == HospitalPriceRecord.id
        )
        .where(HospitalPriceRecord.facility_id == facility_id, ~reviewed_for_record)
        .group_by(PriceServiceCode.code_system, PriceServiceCode.code)
        .order_by(func.count(PriceServiceCode.id).desc())
        .limit(limit)
    ).all()
    return [
        {
            "code_system": str(row[0]),
            "code": str(row[1]),
            "count": row[2],
            "sample_description": row[3],
            "raw_code_type": row[4],
        }
        for row in rows
    ]


def _unmapped_code_type_distribution(session: Session, facility_id: object) -> dict[str, int]:
    """Counts by the raw source code-type label, over records lacking a reviewed mapping.

    This is the single most useful signal for a MAPPING_GAP: if the dominant label
    is a recognized standard system that merely isn't in `_code_system()`'s map, the
    fix is code-type recognition; if it's a proprietary/blank label, it's a
    chargemaster that needs a reviewed crosswalk (or a standard column we're not
    reading — see the raw payload samples).
    """
    reviewed_for_record = exists().where(
        and_(
            PriceRecordProcedureMapping.hospital_price_record_id == HospitalPriceRecord.id,
            PriceRecordProcedureMapping.reviewed.is_(True),
        )
    )
    rows = session.execute(
        select(PriceServiceCode.raw_code_type, func.count(PriceServiceCode.id))
        .join(
            HospitalPriceRecord, PriceServiceCode.hospital_price_record_id == HospitalPriceRecord.id
        )
        .where(HospitalPriceRecord.facility_id == facility_id, ~reviewed_for_record)
        .group_by(PriceServiceCode.raw_code_type)
        .order_by(func.count(PriceServiceCode.id).desc())
    ).all()
    return {str(row[0]): row[1] for row in rows}


def _raw_payload_samples(
    session: Session, facility_id: object, limit: int
) -> list[dict[str, object]]:
    """A few full raw records lacking a reviewed mapping, to eyeball the columns.

    The bounded `raw_payload` shows every source column the importer retained — the
    definitive way to tell whether a standard CPT/HCPCS code sits in a column the
    parser didn't prefer (→ a small normalization fix) rather than being absent
    (→ a reviewed crosswalk).
    """
    reviewed_for_record = exists().where(
        and_(
            PriceRecordProcedureMapping.hospital_price_record_id == HospitalPriceRecord.id,
            PriceRecordProcedureMapping.reviewed.is_(True),
        )
    )
    rows = session.execute(
        select(
            PriceServiceCode.code_system,
            PriceServiceCode.code,
            PriceServiceCode.raw_code_type,
            PriceServiceCode.raw_code,
            HospitalPriceRecord.raw_description,
            HospitalPriceRecord.raw_payload,
        )
        .join(
            HospitalPriceRecord, PriceServiceCode.hospital_price_record_id == HospitalPriceRecord.id
        )
        .where(HospitalPriceRecord.facility_id == facility_id, ~reviewed_for_record)
        .limit(limit)
    ).all()
    return [
        {
            "code_system": str(row[0]),
            "code": str(row[1]),
            "raw_code_type": row[2],
            "raw_code": row[3],
            "raw_description": row[4],
            "raw_payload": row[5],
        }
        for row in rows
    ]


# Shoppable-procedure keywords → how we'd expect the description to read. Used only
# to SAMPLE a facility's actual wording for these procedures so a human can author
# precise, reviewed crosswalk patterns. NOT itself a mapping — never auto-applied.
_SHOPPABLE_KEYWORDS = (
    "mri",
    "ct ",
    "cat scan",
    "mammogram",
    "mammo",
    "ultrasound",
    "echocardiogram",
    "echo ",
    "electrocardiogram",
    "ekg",
    "ecg",
    "colonoscopy",
    "endoscopy",
    "dexa",
    "bone density",
    "blood count",
    "cbc",
    "metabolic panel",
    "lipid",
    "a1c",
    "hemoglobin a1c",
    "thyroid",
    "tsh",
    "urinalysis",
    "x-ray",
    "xray",
)


def _shoppable_description_probe(
    session: Session, facility_id: object, per_keyword_limit: int = 6
) -> dict[str, list[str]]:
    """Sample a facility's own descriptions for shoppable procedures.

    For each shoppable keyword, return up to N distinct raw descriptions from
    records lacking a reviewed mapping. This reveals exactly how the facility words
    each procedure so precise, reviewed crosswalk patterns can be authored to match
    THEIR wording (the standard-phrase patterns already in cdm_crosswalk.json did
    not match). Read-only; proposes nothing.
    """
    reviewed_for_record = exists().where(
        and_(
            PriceRecordProcedureMapping.hospital_price_record_id == HospitalPriceRecord.id,
            PriceRecordProcedureMapping.reviewed.is_(True),
        )
    )
    probe: dict[str, list[str]] = {}
    for keyword in _SHOPPABLE_KEYWORDS:
        descriptions = session.scalars(
            select(HospitalPriceRecord.raw_description)
            .where(
                HospitalPriceRecord.facility_id == facility_id,
                func.lower(HospitalPriceRecord.raw_description).like(f"%{keyword}%"),
                ~reviewed_for_record,
            )
            .distinct()
            .limit(per_keyword_limit)
        ).all()
        if descriptions:
            probe[keyword.strip()] = [str(description) for description in descriptions]
    return probe


def diagnose(session: Session, state: str = "NH", top_codes: int = 25) -> dict[str, object]:
    facility_ids = _state_facility_ids(session, state)
    records = _record_counts(session, facility_ids)
    mappings = _reviewed_mapping_counts(session, facility_ids)
    summaries = _publishable_summary_counts(session, facility_ids)

    unmapped: list[dict[str, object]] = []
    for facility_id in facility_ids:
        record_count = records.get(facility_id, 0)
        summary_count = summaries.get(facility_id, 0)
        # Parsed-but-unmapped: real records, nothing publishable.
        if record_count == 0 or summary_count > 0:
            continue
        facility = session.get(Facility, facility_id)
        reviewed = mappings.get(facility_id, 0)
        # If there ARE reviewed mappings but still no summaries, the cause is NOT
        # missing code mappings (likely location association, anomalies, or a
        # conditionally-publishable legacy parser) — flag it so it isn't mis-fixed.
        cause = (
            "no_approved_code_mappings"
            if reviewed == 0
            else "mapped_but_not_publishable_investigate"
        )
        unmapped.append(
            {
                "facility_id": str(facility_id),
                "ccn": facility.cms_certification_number if facility else None,
                "legal_name": facility.legal_name if facility else None,
                "records": record_count,
                "reviewed_mappings": reviewed,
                "publishable_summaries": summary_count,
                "likely_cause": cause,
                "code_system_distribution": _code_system_distribution(session, facility_id),
                "raw_code_type_distribution": _unmapped_code_type_distribution(
                    session, facility_id
                ),
                "top_unmapped_codes": _top_unmapped_codes(session, facility_id, top_codes),
                "raw_payload_samples": _raw_payload_samples(session, facility_id, 8),
                "shoppable_description_probe": _shoppable_description_probe(session, facility_id),
            }
        )

    unmapped.sort(key=lambda item: item["records"], reverse=True)  # type: ignore[arg-type,return-value]
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "state": state.upper(),
        "facilities_examined": len(facility_ids),
        "parsed_but_unmapped_count": len(unmapped),
        "parsed_but_unmapped": unmapped,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state", default="NH")
    parser.add_argument("--top-codes", type=int, default=25)
    args = parser.parse_args()
    with session_factory() as session:
        report = diagnose(session, args.state, args.top_codes)
    print(json.dumps(report, indent=2, default=str))


if __name__ == "__main__":
    main()
