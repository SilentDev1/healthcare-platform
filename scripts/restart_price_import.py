"""Restart a hospital price import from scratch, deleting existing records."""

import argparse
import uuid

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from collectors.hospital_prices.config import hospital_price_settings
from collectors.hospital_prices.importer import PriceImportSummary, import_price_source
from packages.database import (
    FacilityPriceSource,
    FacilityProcedurePriceObservation,
    FacilitySourceObservation,
    HospitalPriceRateDetail,
    HospitalPriceRecord,
    ImportCheckpoint,
    ImportRun,
    PriceRecordProcedureCandidate,
    PriceRecordProcedureMapping,
    PriceServiceCode,
    PricingAnomaly,
    PricingUnmatchedRecord,
    SourceFile,
    get_session,
)


def restart(source_file_id: uuid.UUID, session: Session | None = None) -> PriceImportSummary:
    if session is None:
        session = next(get_session())
    source = session.get(SourceFile, source_file_id)
    if source is None:
        raise ValueError(f"Source file {source_file_id} not found")

    price_source = session.scalar(
        select(FacilityPriceSource).where(
            FacilityPriceSource.source_file_id == source.id,
        )
    )
    if price_source is None:
        raise ValueError("No price source found for this source file")

    record_count = (
        session.scalar(
            select(func.count(HospitalPriceRecord.id)).where(
                HospitalPriceRecord.source_file_id == source_file_id
            )
        )
        or 0
    )

    if record_count:
        print(f"Deleting {record_count} existing records and children...")
        # Delete children by a SUBQUERY on source_file_id, never a materialized IN-list
        # of record ids: a large source (e.g. 97k rows) would blow past PostgreSQL's
        # 65535 bind-parameter limit. The subquery is evaluated server-side.
        record_ids_subquery = select(HospitalPriceRecord.id).where(
            HospitalPriceRecord.source_file_id == source_file_id
        )
        # Observations reference records; clear any first so the record delete's FK holds.
        session.execute(
            delete(FacilityProcedurePriceObservation).where(
                FacilityProcedurePriceObservation.hospital_price_record_id.in_(record_ids_subquery)
            )
        )
        session.execute(
            delete(PricingAnomaly).where(
                PricingAnomaly.hospital_price_record_id.in_(record_ids_subquery)
            )
        )
        session.execute(
            delete(HospitalPriceRateDetail).where(
                HospitalPriceRateDetail.hospital_price_record_id.in_(record_ids_subquery)
            )
        )
        session.execute(
            delete(PriceServiceCode).where(
                PriceServiceCode.hospital_price_record_id.in_(record_ids_subquery)
            )
        )
        session.execute(
            delete(PriceRecordProcedureMapping).where(
                PriceRecordProcedureMapping.hospital_price_record_id.in_(record_ids_subquery)
            )
        )
        session.execute(
            delete(PriceRecordProcedureCandidate).where(
                PriceRecordProcedureCandidate.hospital_price_record_id.in_(record_ids_subquery)
            )
        )
        session.execute(
            delete(HospitalPriceRecord).where(HospitalPriceRecord.source_file_id == source_file_id)
        )

    # Delete unmatched records
    session.execute(
        delete(PricingUnmatchedRecord).where(
            PricingUnmatchedRecord.source_file_id == source_file_id
        )
    )

    # Delete checkpoints
    run_ids = list(
        session.scalars(select(ImportRun.id).where(ImportRun.source_file_id == source_file_id))
    )
    if run_ids:
        session.execute(delete(ImportCheckpoint).where(ImportCheckpoint.import_run_id.in_(run_ids)))
        session.execute(
            delete(FacilitySourceObservation).where(
                FacilitySourceObservation.import_run_id.in_(run_ids)
            )
        )

    # Delete import runs
    session.execute(delete(ImportRun).where(ImportRun.source_file_id == source_file_id))

    session.commit()
    print("Cleaned up. Starting fresh import...")

    summary = import_price_source(session, price_source, hospital_price_settings)
    print(
        f"Import complete: {summary.records_normalized} records, "
        f"{summary.rate_details} rate details"
    )
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Restart a price import from scratch")
    parser.add_argument("--source-file-id", type=uuid.UUID, required=True)
    args = parser.parse_args()
    restart(args.source_file_id)
