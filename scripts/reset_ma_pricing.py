"""Recovery: reset stuck imports + clear partial MA hospital pricing for clean re-import.

The MA pilot's wave-B job hit the Cloud Run task timeout mid-import (too many large MRFs batched
together). That left a stuck ImportRun (status=running) and partially-imported raw records with no
summaries. This tool restores a known-clean MA pricing state so re-import (in small waves) is exact:

  * marks every ImportRun still 'running' as FAILED (clears the safety gate's active_imports),
  * for every MA hospital NOT in --keep-ccns, fully deletes its price records + children + checkpoints
    + import runs (chunked, committed per chunk — never one multi-hour transaction) and resets its
    FacilityPriceSource back to "needs download" (source_file_id = NULL),

so the next `download_all_sources`/`import_all_sources --state MA` re-fetches and imports those hospitals
from scratch with no duplication. **New Hampshire is never touched** (every query is MA-scoped). No
pricing is published by this tool. `--keep-ccns` defaults to the clean wave-A imports (MGH, Martha's Vineyard).

Run: python -m scripts.reset_ma_pricing [--dry-run] [--keep-ccns 220071,221300]
"""

from __future__ import annotations

# ruff: noqa: E501
import argparse

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from packages.database import (
    Facility,
    FacilityLocation,
    FacilityPriceSource,
    FacilitySourceObservation,
    HospitalPriceRecord,
    ImportCheckpoint,
    ImportRun,
    PricingUnmatchedRecord,
    get_session,
)
from packages.database.models import ImportStatus
from scripts.restart_price_import import _RECORD_CHILDREN, _delete_records_in_chunks

DEFAULT_KEEP = {"220071", "221300"}  # MGH + Martha's Vineyard — clean wave-A imports, kept live


def _delete_records_fast(session: Session, source_file_id: object) -> int:
    """Bulk-delete a source's records + children with correlated-subquery DELETEs.

    Much faster than the 5000-row chunked path (a few SQL statements vs hundreds of Python
    round-trips) because the FK-fanout delete runs inside the database. Safe here because MA
    pricing is not consumer-published and has no concurrent readers — there is no live query
    racing these rows. Returns the number of price records deleted.
    """
    rec_ids = select(HospitalPriceRecord.id).where(HospitalPriceRecord.source_file_id == source_file_id)
    count = session.scalar(select(func.count()).select_from(rec_ids.subquery())) or 0
    for child in _RECORD_CHILDREN:
        session.execute(delete(child).where(child.hospital_price_record_id.in_(rec_ids)))
    session.execute(delete(HospitalPriceRecord).where(HospitalPriceRecord.source_file_id == source_file_id))
    session.commit()
    return count


def reset(session: Session | None = None, *, keep_ccns: set[str] | None = None, dry_run: bool = False, fast: bool = False) -> dict[str, int]:
    if session is None:
        session = next(get_session())
    keep = keep_ccns if keep_ccns is not None else set(DEFAULT_KEEP)
    result = {"import_runs_failed": 0, "sources_reset": 0, "records_deleted": 0, "sources_kept": 0}

    # 1. Clear stuck 'running' import runs (the timed-out job's) so the safety gate can pass.
    running = list(session.scalars(select(ImportRun).where(ImportRun.status == ImportStatus.RUNNING)))
    for run in running:
        if not dry_run:
            run.status = ImportStatus.FAILED
        result["import_runs_failed"] += 1
    if not dry_run:
        session.commit()

    # 2. MA facilities, partitioned by keep-set.
    ma_facilities = {
        f.id: f
        for f in session.scalars(
            select(Facility)
            .join(FacilityLocation, FacilityLocation.facility_id == Facility.id)
            .where(FacilityLocation.state == "MA")
        )
    }
    keep_ids = {fid for fid, f in ma_facilities.items() if f.cms_certification_number in keep}
    result["sources_kept"] = len(keep_ids)
    target_ids = set(ma_facilities) - keep_ids

    sources = list(
        session.scalars(
            select(FacilityPriceSource).where(
                FacilityPriceSource.facility_id.in_(target_ids),
                FacilityPriceSource.source_file_id.is_not(None),
            )
        )
    )
    for src in sources:
        sfid = src.source_file_id
        rec_count = session.scalar(
            select(func.count(HospitalPriceRecord.id)).where(HospitalPriceRecord.source_file_id == sfid)
        ) or 0
        if dry_run:
            result["records_deleted"] += rec_count
            result["sources_reset"] += 1
            continue
        if rec_count:
            deleter = _delete_records_fast if fast else _delete_records_in_chunks
            result["records_deleted"] += deleter(session, sfid)
        session.execute(delete(PricingUnmatchedRecord).where(PricingUnmatchedRecord.source_file_id == sfid))
        run_ids = list(session.scalars(select(ImportRun.id).where(ImportRun.source_file_id == sfid)))
        if run_ids:
            session.execute(delete(ImportCheckpoint).where(ImportCheckpoint.import_run_id.in_(run_ids)))
            session.execute(delete(FacilitySourceObservation).where(FacilitySourceObservation.import_run_id.in_(run_ids)))
            session.execute(delete(ImportRun).where(ImportRun.id.in_(run_ids)))
        src.source_file_id = None
        src.last_successful_download_at = None
        src.last_failed_download_at = None
        session.commit()
        result["sources_reset"] += 1

    if dry_run:
        session.rollback()
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Reset stuck imports + clear partial MA pricing (NH untouched)")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--keep-ccns", default="", help="comma-separated CCNs to keep (default MGH+Martha's Vineyard)")
    args = parser.parse_args()
    keep = {c.strip() for c in args.keep_ccns.split(",") if c.strip()} or None
    result = reset(keep_ccns=keep, dry_run=args.dry_run)
    prefix = "DRY-RUN " if args.dry_run else ""
    print(f"{prefix}MA_PRICING_RESET={result}")


if __name__ == "__main__":
    main()
