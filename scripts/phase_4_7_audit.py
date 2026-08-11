"""Read-only statewide publication funnel and Phase 4.7 safety audit."""

from __future__ import annotations

import argparse
import json
import uuid
from collections import Counter
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select

from collectors.hospital_prices.scope import active_consumer_facility_ids
from packages.database import (
    Facility,
    FacilityLocation,
    FacilityPriceSource,
    FacilityProcedurePriceObservation,
    FacilityProcedurePriceSummary,
    HospitalPriceRateDetail,
    HospitalPriceRecord,
    ImportRun,
    PriceRecordProcedureCandidate,
    PriceRecordProcedureMapping,
    PriceServiceCode,
    ProcedureCodeMapping,
    ProcedureCodeSystem,
    SourceFile,
    session_factory,
)

STANDARD_CODE_SYSTEMS = {"CPT", "HCPCS", "MS_DRG", "APR_DRG", "APC", "REV_CODE"}


def _count(session: Any, statement: Any) -> int:
    return int(session.scalar(statement) or 0)


def _metric(row: dict[str, object], name: str) -> int:
    value = row[name]
    assert isinstance(value, int)
    return value


def _blocker(row: dict[str, object]) -> str:
    if row["official_public_summaries"]:
        return "NONE"
    if not row["official_sources_known"]:
        return "NO_SOURCE"
    if not row["source_files_downloaded"]:
        return "DOWNLOAD_FAILED"
    if not row["normalized_records"]:
        return "ZERO_NORMALIZED_ROWS"
    if row["records_missing_location"] == row["normalized_records"]:
        return "LOCATION_IDENTITY_MISMATCH"
    if not row["standard_coded_records"]:
        return "PROPRIETARY_CODES_ONLY"
    if not row["approved_mapped_records"]:
        return "MAPPING_GAP"
    if not row["publishable_observations"]:
        return "PUBLICATION_FILTER_FAILURE"
    if not row["official_public_summaries"]:
        return "SUMMARY_BUILD_FAILURE"
    return "NONE"


def _facility_row(session: Any, facility: Facility) -> dict[str, object]:
    sources = list(
        session.scalars(
            select(FacilityPriceSource)
            .where(FacilityPriceSource.facility_id == facility.id)
            .order_by(FacilityPriceSource.active.desc(), FacilityPriceSource.last_seen_at.desc())
        )
    )
    source_file_ids = {source.source_file_id for source in sources if source.source_file_id}
    official_file_ids = (
        set(
            session.scalars(
                select(SourceFile.id).where(
                    SourceFile.id.in_(source_file_ids),
                    SourceFile.source_url.not_like("file://%"),
                )
            )
        )
        if source_file_ids
        else set()
    )
    official_summary_filters = (
        FacilityProcedurePriceSummary.facility_id == facility.id,
        FacilityProcedurePriceSummary.publication_status == "publishable",
        FacilityProcedurePriceSummary.source_file_id.in_(official_file_ids),
    )
    code_distribution = {
        str(system): int(total)
        for system, total in session.execute(
            select(PriceServiceCode.code_system, func.count(PriceServiceCode.id))
            .join(HospitalPriceRecord)
            .where(HospitalPriceRecord.facility_id == facility.id)
            .group_by(PriceServiceCode.code_system)
            .order_by(func.count(PriceServiceCode.id).desc())
        )
    }
    parser_distribution = {
        str(parser_name): int(total)
        for parser_name, total in session.execute(
            select(HospitalPriceRecord.parser_name, func.count(HospitalPriceRecord.id))
            .where(HospitalPriceRecord.facility_id == facility.id)
            .group_by(HospitalPriceRecord.parser_name)
        )
    }
    source_rows: list[dict[str, object]] = []
    for source in sources:
        source_file = (
            session.get(SourceFile, source.source_file_id) if source.source_file_id else None
        )
        source_rows.append(
            {
                "active": source.active,
                "source_url": source.machine_readable_file_url,
                "page_url": source.source_page_url,
                "vendor": source.vendor_name,
                "discovery_method": source.discovery_method,
                "location_status": source.location_association_status,
                "location_id": str(source.facility_location_id)
                if source.facility_location_id
                else None,
                "source_file_id": str(source.source_file_id) if source.source_file_id else None,
                "file_url": source_file.source_url if source_file else None,
                "checksum": source_file.checksum_sha256 if source_file else None,
                "size": source_file.file_size if source_file else None,
                "status": source_file.status if source_file else None,
                "parser": source_file.parser_version if source_file else None,
                "downloaded_at": source_file.downloaded_at if source_file else None,
            }
        )
    imports = (
        [
            {
                "source_file_id": str(run.source_file_id),
                "status": run.status,
                "stage": run.stage,
                "rows_read": run.rows_read,
                "rows_inserted": run.rows_inserted,
                "rows_rejected": run.rows_rejected,
                "error": run.error_summary,
                "started_at": run.started_at,
                "finished_at": run.finished_at,
            }
            for run in session.scalars(
                select(ImportRun)
                .where(ImportRun.source_file_id.in_(source_file_ids))
                .order_by(ImportRun.started_at.desc())
                .limit(20)
            )
        ]
        if source_file_ids
        else []
    )
    row: dict[str, object] = {
        "hospital": facility.display_name,
        "facility_id": str(facility.id),
        "ccn": facility.cms_certification_number,
        "city": session.scalar(
            select(FacilityLocation.city)
            .where(
                FacilityLocation.facility_id == facility.id,
                FacilityLocation.active.is_(True),
            )
            .order_by(FacilityLocation.created_at)
            .limit(1)
        ),
        "official_sources_known": sum(source.active for source in sources),
        "source_files_downloaded": len(official_file_ids),
        "parsed_rows": max((int(item["rows_read"] or 0) for item in imports), default=0),
        "normalized_records": _count(
            session,
            select(func.count(HospitalPriceRecord.id)).where(
                HospitalPriceRecord.facility_id == facility.id
            ),
        ),
        "records_missing_location": _count(
            session,
            select(func.count(HospitalPriceRecord.id)).where(
                HospitalPriceRecord.facility_id == facility.id,
                HospitalPriceRecord.facility_location_id.is_(None),
            ),
        ),
        "standard_coded_records": _count(
            session,
            select(func.count(func.distinct(HospitalPriceRecord.id)))
            .join(PriceServiceCode)
            .where(
                HospitalPriceRecord.facility_id == facility.id,
                PriceServiceCode.code_system.in_(STANDARD_CODE_SYSTEMS),
            ),
        ),
        "approved_code_opportunities": _count(
            session,
            select(func.count(func.distinct(HospitalPriceRecord.id)))
            .join(PriceServiceCode)
            .join(
                ProcedureCodeSystem,
                ProcedureCodeSystem.code_system == PriceServiceCode.code_system,
            )
            .join(
                ProcedureCodeMapping,
                (ProcedureCodeMapping.code_system_id == ProcedureCodeSystem.id)
                & (ProcedureCodeMapping.code == PriceServiceCode.code),
            )
            .where(
                HospitalPriceRecord.facility_id == facility.id,
                ProcedureCodeMapping.mapping_status.in_(["approved", "reviewed"]),
            ),
        ),
        "approved_mapped_records": _count(
            session,
            select(func.count(func.distinct(HospitalPriceRecord.id)))
            .join(PriceRecordProcedureMapping)
            .where(
                HospitalPriceRecord.facility_id == facility.id,
                PriceRecordProcedureMapping.reviewed.is_(True),
            ),
        ),
        "mapping_candidates": _count(
            session,
            select(func.count(PriceRecordProcedureCandidate.id))
            .join(HospitalPriceRecord)
            .where(HospitalPriceRecord.facility_id == facility.id),
        ),
        "observations": _count(
            session,
            select(func.count(FacilityProcedurePriceObservation.id)).where(
                FacilityProcedurePriceObservation.facility_id == facility.id
            ),
        ),
        "publishable_observations": _count(
            session,
            select(func.count(FacilityProcedurePriceObservation.id)).where(
                FacilityProcedurePriceObservation.facility_id == facility.id,
                FacilityProcedurePriceObservation.publication_status == "publishable",
            ),
        ),
        "stored_summaries": _count(
            session,
            select(func.count(FacilityProcedurePriceSummary.id)).where(
                FacilityProcedurePriceSummary.facility_id == facility.id,
                FacilityProcedurePriceSummary.publication_status == "publishable",
            ),
        ),
        "official_public_summaries": _count(
            session,
            select(func.count(FacilityProcedurePriceSummary.id)).where(*official_summary_filters),
        ),
        "published_procedures": _count(
            session,
            select(func.count(func.distinct(FacilityProcedurePriceSummary.procedure_id))).where(
                *official_summary_filters
            ),
        ),
        "cash_coverage": _count(
            session,
            select(func.count(func.distinct(FacilityProcedurePriceSummary.procedure_id))).where(
                *official_summary_filters,
                FacilityProcedurePriceSummary.cash_price_median.is_not(None),
            ),
        ),
        "negotiated_coverage": _count(
            session,
            select(func.count(func.distinct(FacilityProcedurePriceSummary.procedure_id))).where(
                *official_summary_filters,
                FacilityProcedurePriceSummary.negotiated_price_median.is_not(None),
            ),
        ),
        "payer_rate_rows": _count(
            session,
            select(func.count(HospitalPriceRateDetail.id))
            .join(HospitalPriceRecord)
            .where(HospitalPriceRecord.facility_id == facility.id),
        ),
        "records_with_monetary_values": _count(
            session,
            select(func.count(HospitalPriceRecord.id)).where(
                HospitalPriceRecord.facility_id == facility.id,
                (HospitalPriceRecord.gross_charge.is_not(None))
                | (HospitalPriceRecord.discounted_cash_price.is_not(None))
                | (HospitalPriceRecord.deidentified_minimum_negotiated_rate.is_not(None))
                | (HospitalPriceRecord.deidentified_maximum_negotiated_rate.is_not(None)),
            ),
        ),
        "code_distribution": code_distribution,
        "parser_distribution": parser_distribution,
        "sources": source_rows,
        "imports": imports,
    }
    row["blocker"] = _blocker(row)
    return row


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state", default="NH")
    args = parser.parse_args()
    with session_factory() as session:
        facility_ids = active_consumer_facility_ids(session, args.state.upper())
        facilities = list(
            session.scalars(
                select(Facility)
                .where(Facility.id.in_(facility_ids))
                .order_by(Facility.display_name)
            )
        )
        rows = [_facility_row(session, facility) for facility in facilities]
        spread_groups: dict[
            tuple[uuid.UUID, uuid.UUID | None, uuid.UUID, str, str], list[Decimal]
        ] = {}
        for summary_row in session.scalars(
            select(FacilityProcedurePriceSummary).where(
                FacilityProcedurePriceSummary.facility_id.in_(facility_ids),
                FacilityProcedurePriceSummary.publication_status == "publishable",
                FacilityProcedurePriceSummary.negotiated_price_min.is_not(None),
            )
        ):
            spread_key = (
                summary_row.facility_id,
                summary_row.facility_location_id,
                summary_row.procedure_id,
                summary_row.service_setting,
                summary_row.included_component_scope,
            )
            spread_groups.setdefault(spread_key, []).extend(
                value
                for value in (
                    summary_row.negotiated_price_min,
                    summary_row.negotiated_price_max,
                )
                if value is not None
            )
        extreme_spreads: list[dict[str, str | float]] = []
        for spread_key, values in spread_groups.items():
            low, high = min(values), max(values)
            if low > 0 and high / low >= 10:
                extreme_spreads.append(
                    {
                        "facility_id": str(spread_key[0]),
                        "facility_location_id": str(spread_key[1]),
                        "procedure_id": str(spread_key[2]),
                        "service_setting": str(spread_key[3]),
                        "component_scope": str(spread_key[4]),
                        "minimum": str(low),
                        "maximum": str(high),
                        "spread_ratio": round(float(high / low), 2),
                    }
                )
        extreme_spreads.sort(key=lambda item: float(item["spread_ratio"]), reverse=True)
        counts = Counter(str(row["blocker"]) for row in rows)
        summary = {
            "state": args.state.upper(),
            "active_consumer_hospitals": len(rows),
            "hospitals_with_published_procedures": sum(
                _metric(row, "published_procedures") > 0 for row in rows
            ),
            "hospitals_with_zero_published_procedures": sum(
                _metric(row, "published_procedures") == 0 for row in rows
            ),
            "limited_coverage": sum(0 < _metric(row, "published_procedures") < 10 for row in rows),
            "meaningful_coverage": sum(_metric(row, "published_procedures") >= 10 for row in rows),
            "blockers": dict(sorted(counts.items())),
            "extreme_negotiated_spread_count": len(extreme_spreads),
            "extreme_negotiated_spreads_top_25": extreme_spreads[:25],
        }
    print("PHASE_4_7_SUMMARY=" + json.dumps(summary, default=str, separators=(",", ":")))
    for row in rows:
        print("PHASE_4_7_HOSPITAL=" + json.dumps(row, default=str, separators=(",", ":")))


if __name__ == "__main__":
    main()
