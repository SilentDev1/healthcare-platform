"""Read-only production audit for major New Hampshire hospital pricing coverage."""

import json
from collections.abc import Sequence
from typing import Any

from sqlalchemy import func, select

from collectors.hospital_prices.inventory import load_inventory
from packages.database import (
    Facility,
    FacilityIdentifier,
    FacilityLocation,
    FacilityPriceSource,
    FacilityProcedurePriceObservation,
    FacilityProcedurePriceSummary,
    HospitalPriceRecord,
    ImportRun,
    ParserReview,
    PriceRecordProcedureCandidate,
    PriceServiceCode,
    PricingUnmatchedRecord,
    SourceFile,
    session_factory,
)

TARGET_CCNS = {"300012", "300034"}


def count(session: Any, statement: Any) -> int:
    return int(session.scalar(statement) or 0)


def main() -> None:
    inventory = load_inventory()
    targets: list[dict[str, object]] = []
    matrix: list[dict[str, object]] = []
    with session_factory() as session:
        facilities = session.scalars(
            select(Facility)
            .join(FacilityLocation)
            .where(Facility.active.is_(True), FacilityLocation.state == "NH")
            .distinct()
            .order_by(Facility.display_name)
        ).all()
        for facility in facilities:
            source_rows = session.execute(
                select(FacilityPriceSource, SourceFile)
                .outerjoin(SourceFile, SourceFile.id == FacilityPriceSource.source_file_id)
                .where(FacilityPriceSource.facility_id == facility.id)
                .order_by(FacilityPriceSource.last_seen_at.desc())
            ).all()
            record_count = count(
                session,
                select(func.count(HospitalPriceRecord.id)).where(
                    HospitalPriceRecord.facility_id == facility.id
                ),
            )
            published_procedures = count(
                session,
                select(func.count(func.distinct(FacilityProcedurePriceSummary.procedure_id))).where(
                    FacilityProcedurePriceSummary.facility_id == facility.id,
                    FacilityProcedurePriceSummary.publication_status == "publishable",
                ),
            )
            published_summaries = count(
                session,
                select(func.count(FacilityProcedurePriceSummary.id)).where(
                    FacilityProcedurePriceSummary.facility_id == facility.id,
                    FacilityProcedurePriceSummary.publication_status == "publishable",
                ),
            )
            matrix_row: dict[str, object] = {
                "facility_id": str(facility.id),
                "hospital": facility.display_name,
                "ccn": facility.cms_certification_number,
                "city": session.scalar(
                    select(FacilityLocation.city)
                    .where(FacilityLocation.facility_id == facility.id)
                    .order_by(FacilityLocation.created_at)
                    .limit(1)
                ),
                "active_sources": sum(1 for source, _ in source_rows if source.active),
                "normalized_records": record_count,
                "published_procedures": published_procedures,
                "published_summaries": published_summaries,
            }
            matrix.append(matrix_row)
            if facility.cms_certification_number not in TARGET_CCNS:
                continue

            source_file_ids = [
                source.source_file_id for source, _ in source_rows if source.source_file_id
            ]
            code_distribution: dict[str, int] = {
                code_system: int(code_count)
                for code_system, code_count in session.execute(
                    select(PriceServiceCode.code_system, func.count(PriceServiceCode.id))
                    .join(
                        HospitalPriceRecord,
                        HospitalPriceRecord.id == PriceServiceCode.hospital_price_record_id,
                    )
                    .where(HospitalPriceRecord.facility_id == facility.id)
                    .group_by(PriceServiceCode.code_system)
                    .order_by(func.count(PriceServiceCode.id).desc())
                ).all()
            }
            identifiers = session.execute(
                select(FacilityIdentifier.identifier_type, FacilityIdentifier.identifier_value)
                .where(FacilityIdentifier.facility_id == facility.id)
                .order_by(FacilityIdentifier.identifier_type)
            ).all()
            locations = session.scalars(
                select(FacilityLocation).where(FacilityLocation.facility_id == facility.id)
            ).all()
            imports: Sequence[ImportRun] = []
            if source_file_ids:
                imports = session.scalars(
                    select(ImportRun)
                    .where(ImportRun.source_file_id.in_(source_file_ids))
                    .order_by(ImportRun.started_at.desc())
                    .limit(10)
                ).all()
            entry = inventory.get_by_ccn(facility.cms_certification_number or "")
            targets.append(
                {
                    **matrix_row,
                    "legal_name": facility.legal_name,
                    "identifiers": [
                        {"type": identifier_type, "value": value}
                        for identifier_type, value in identifiers
                    ],
                    "health_system": entry.health_system if entry else None,
                    "locations": [
                        {
                            "id": str(location.id),
                            "name": location.location_name,
                            "type": location.location_type,
                            "address": location.address_line_1,
                            "city": location.city,
                            "postal_code": location.postal_code,
                            "active": location.active,
                        }
                        for location in locations
                    ],
                    "sources": [
                        {
                            "source_id": str(source.id),
                            "active": source.active,
                            "page_url": source.source_page_url,
                            "mrf_url": source.machine_readable_file_url,
                            "cms_hpt_url": source.cms_hpt_txt_url,
                            "discovery_method": source.discovery_method,
                            "vendor": source.vendor_name,
                            "format": source.detected_format or source.declared_format,
                            "schema_version": source.detected_schema_version
                            or source.declared_schema_version,
                            "last_successful_download_at": source.last_successful_download_at,
                            "last_failed_download_at": source.last_failed_download_at,
                            "source_file": None
                            if source_file is None
                            else {
                                "id": str(source_file.id),
                                "url": source_file.source_url,
                                "storage_path": source_file.storage_path,
                                "checksum": source_file.checksum_sha256,
                                "file_size": source_file.file_size,
                                "status": source_file.status,
                                "parser_version": source_file.parser_version,
                                "downloaded_at": source_file.downloaded_at,
                                "etag": source_file.etag,
                                "last_modified": source_file.last_modified,
                            },
                        }
                        for source, source_file in source_rows
                    ],
                    "import_runs": [
                        {
                            "id": str(run.id),
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
                        for run in imports
                    ],
                    "code_distribution": code_distribution,
                    "mapping_candidates": count(
                        session,
                        select(func.count(PriceRecordProcedureCandidate.id))
                        .join(
                            HospitalPriceRecord,
                            HospitalPriceRecord.id
                            == PriceRecordProcedureCandidate.hospital_price_record_id,
                        )
                        .where(HospitalPriceRecord.facility_id == facility.id),
                    ),
                    "unmatched_records": count(
                        session,
                        select(func.count(PricingUnmatchedRecord.id)).where(
                            PricingUnmatchedRecord.facility_id == facility.id
                        ),
                    ),
                    "published_observations": count(
                        session,
                        select(func.count(FacilityProcedurePriceObservation.id)).where(
                            FacilityProcedurePriceObservation.facility_id == facility.id,
                            FacilityProcedurePriceObservation.publication_status == "publishable",
                        ),
                    ),
                    "parser_reviews": count(
                        session,
                        select(func.count(ParserReview.id)).where(
                            ParserReview.source_file_id.in_(source_file_ids)
                        ),
                    )
                    if source_file_ids
                    else 0,
                }
            )
    for target in targets:
        print("CAREVERO_TARGET " + json.dumps(target, default=str, separators=(",", ":")))
    for row in matrix:
        print("CAREVERO_MATRIX " + json.dumps(row, default=str, separators=(",", ":")))


if __name__ == "__main__":
    main()
