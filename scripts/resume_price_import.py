"""Resume an interrupted hospital price import from its last checkpoint."""

import argparse
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from collectors.hospital_prices.checkpoint import CheckpointManager
from collectors.hospital_prices.config import hospital_price_settings
from collectors.hospital_prices.importer import import_price_source
from packages.database import (
    FacilityPriceSource,
    ImportCheckpoint,
    ImportRun,
    SourceFile,
    get_session,
)
from packages.database.models import ImportStatus


def resume(import_run_id: uuid.UUID) -> None:
    session: Session = next(get_session())
    run = session.get(ImportRun, import_run_id)
    if run is None:
        raise ValueError(f"Import run {import_run_id} not found")

    if run.status not in (ImportStatus.INTERRUPTED, ImportStatus.FAILED, ImportStatus.RUNNING):
        print(f"Import run status is {run.status.value}, not resumable")
        return

    source = session.get(SourceFile, run.source_file_id)
    if source is None:
        raise ValueError("Source file not found")

    # Find the price source
    price_source = session.scalar(
        select(FacilityPriceSource).where(
            FacilityPriceSource.source_file_id == source.id,
        )
    )
    if price_source is None:
        raise ValueError("Price source not found for this source file")

    # Validate checkpoint exists
    checkpoint = session.scalar(
        select(ImportCheckpoint).where(
            ImportCheckpoint.import_run_id == import_run_id,
            ImportCheckpoint.status == "active",
        )
    )
    if checkpoint is None:
        print("No active checkpoint found. Use restart-price-import instead.")
        return

    settings = hospital_price_settings
    mgr = CheckpointManager(session, run, source, settings.hospital_price_parser_version)
    mgr.validate_resumability()

    # Reset run status so import_price_source doesn't skip it
    run.status = ImportStatus.RUNNING
    session.commit()

    print(f"Resuming from line {mgr.get_resume_position()}, batch {checkpoint.batch_number}...")
    summary = import_price_source(session, price_source, settings)
    print(
        f"Resume complete: {summary.records_normalized} records, "
        f"{summary.rate_details} rate details"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Resume an interrupted price import")
    parser.add_argument("--import-run-id", type=uuid.UUID, required=True)
    args = parser.parse_args()
    resume(args.import_run_id)
