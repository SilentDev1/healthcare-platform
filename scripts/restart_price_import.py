"""Restart a hospital price import from scratch, deleting existing records."""

import argparse
import uuid
from collections.abc import Sequence

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

# Records-per-chunk for the child/record delete. A large source (e.g. 97k rows)
# deleted in one un-batched statement holds a single very long-running transaction:
# the delete of the huge `hospital_price_rate_details` fan-out can run for hours
# while holding row locks and bloating the WAL, which is what previously wedged the
# refresh job. Deleting in bounded chunks (committing per chunk) keeps each
# statement's parameter count well under PostgreSQL's 65535 limit and keeps each
# transaction short so locks are released promptly.
DELETE_CHUNK_SIZE = 5000

# Child tables keyed by hospital_price_record_id, in FK-safe delete order (all
# reference HospitalPriceRecord, so they must be cleared before the records).
_RECORD_CHILDREN = (
    FacilityProcedurePriceObservation,
    PricingAnomaly,
    HospitalPriceRateDetail,
    PriceServiceCode,
    PriceRecordProcedureMapping,
    PriceRecordProcedureCandidate,
)


def _delete_records_in_chunks(
    session: Session,
    source_file_id: uuid.UUID,
    *,
    chunk_size: int = DELETE_CHUNK_SIZE,
) -> int:
    """Delete a source's price records and their children in committed chunks.

    Returns the number of records deleted. Each chunk deletes a bounded set of
    record ids' children then the records themselves and commits, so the operation
    never runs as one multi-hour, whole-source transaction.
    """
    deleted = 0
    while True:
        record_ids: Sequence[uuid.UUID] = list(
            session.scalars(
                select(HospitalPriceRecord.id)
                .where(HospitalPriceRecord.source_file_id == source_file_id)
                .limit(chunk_size)
            )
        )
        if not record_ids:
            break
        for child in _RECORD_CHILDREN:
            session.execute(delete(child).where(child.hospital_price_record_id.in_(record_ids)))
        session.execute(delete(HospitalPriceRecord).where(HospitalPriceRecord.id.in_(record_ids)))
        session.commit()
        deleted += len(record_ids)
        # flush so chunk progress is visible in Cloud Run logs in real time
        # (job stdout is block-buffered otherwise, hiding a stall).
        print(f"  ...deleted {deleted} records so far", flush=True)
    return deleted


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
        print(f"Deleting {record_count} existing records and children in chunks...", flush=True)
        _delete_records_in_chunks(session, source_file_id)

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
    print("Cleaned up. Starting fresh import...", flush=True)

    summary = import_price_source(session, price_source, hospital_price_settings)
    print(
        f"Import complete: {summary.records_normalized} records, "
        f"{summary.rate_details} rate details",
        flush=True,
    )
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Restart a price import from scratch")
    parser.add_argument("--source-file-id", type=uuid.UUID, required=True)
    args = parser.parse_args()
    restart(args.source_file_id)
