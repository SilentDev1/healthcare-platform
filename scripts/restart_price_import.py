"""Restart a hospital price import from scratch, deleting existing records."""

import argparse
import uuid

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from collectors.hospital_prices.config import hospital_price_settings
from collectors.hospital_prices.importer import import_price_source
from packages.database import (
    FacilityPriceSource,
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


def restart(source_file_id: uuid.UUID) -> None:
    session: Session = next(get_session())
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

    # Get all record IDs for this source file
    record_ids = list(
        session.scalars(
            select(HospitalPriceRecord.id).where(
                HospitalPriceRecord.source_file_id == source_file_id
            )
        )
    )

    if record_ids:
        print(f"Deleting {len(record_ids)} existing records and children...")
        # Delete children first (FK constraints)
        session.execute(
            delete(PricingAnomaly).where(PricingAnomaly.hospital_price_record_id.in_(record_ids))
        )
        session.execute(
            delete(HospitalPriceRateDetail).where(
                HospitalPriceRateDetail.hospital_price_record_id.in_(record_ids)
            )
        )
        session.execute(
            delete(PriceServiceCode).where(
                PriceServiceCode.hospital_price_record_id.in_(record_ids)
            )
        )
        session.execute(
            delete(PriceRecordProcedureMapping).where(
                PriceRecordProcedureMapping.hospital_price_record_id.in_(record_ids)
            )
        )
        session.execute(
            delete(PriceRecordProcedureCandidate).where(
                PriceRecordProcedureCandidate.hospital_price_record_id.in_(record_ids)
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


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Restart a price import from scratch")
    parser.add_argument("--source-file-id", type=uuid.UUID, required=True)
    args = parser.parse_args()
    restart(args.source_file_id)
