import csv
import hashlib
import json
from collections.abc import Iterator, Mapping
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.orm import Session

from collectors.cms_hospitals.config import CollectorSettings, collector_settings
from collectors.cms_hospitals.downloader import DownloadResult, download_source
from packages.database import Facility, FacilityLocation, ImportRun, SourceFile
from packages.database.models import ImportStatus, SourceStatus

logger = structlog.get_logger()

FIELD_ALIASES = {
    "ccn": ("Facility ID", "facility_id", "facility id"),
    "name": ("Facility Name", "facility_name", "facility name"),
    "address": ("Address", "address", "address_line_1"),
    "city": ("City/Town", "city_town", "city"),
    "state": ("State", "state"),
    "zip": ("ZIP Code", "zip_code", "zip code"),
    "county": ("County/Parish", "county_parish", "county"),
    "phone": ("Telephone Number", "telephone_number", "phone"),
    "type": ("Hospital Type", "hospital_type", "facility_type"),
    "ownership": ("Hospital Ownership", "hospital_ownership", "ownership_type"),
}


@dataclass
class ImportSummary:
    source_file_id: str
    import_run_id: str
    rows_read: int = 0
    rows_inserted: int = 0
    rows_updated: int = 0
    rows_rejected: int = 0


def _value(row: Mapping[str, Any], key: str) -> str:
    for alias in FIELD_ALIASES[key]:
        value = row.get(alias)
        if value is not None:
            return str(value).strip()
    return ""


def _rows(path: Path) -> Iterator[dict[str, Any]]:
    if path.suffix.lower() == ".json":
        payload = json.loads(path.read_text(encoding="utf-8"))
        records = payload.get("results", payload) if isinstance(payload, dict) else payload
        if not isinstance(records, list):
            raise ValueError("CMS JSON response does not contain a results list")
        yield from records
        return
    with path.open(encoding="utf-8-sig", newline="") as stream:
        yield from csv.DictReader(stream)


def _local_result(path: Path) -> DownloadResult:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(64 * 1024), b""):
            size += len(chunk)
            digest.update(chunk)
    return DownloadResult(path, digest.hexdigest(), size, None, None, datetime.now(UTC), "text/csv")


def run_import(
    session: Session,
    settings: CollectorSettings = collector_settings,
    source_path: Path | None = None,
    source_url: str | None = None,
) -> ImportSummary:
    url = source_url or (
        source_path.resolve().as_uri() if source_path else settings.cms_hospitals_source_url
    )
    result = (
        _local_result(source_path)
        if source_path
        else download_source(
            url,
            settings.cms_raw_data_dir,
            settings.cms_download_max_bytes,
            settings.cms_http_timeout_seconds,
            settings.cms_http_max_retries,
        )
    )
    source = SourceFile(
        source_name="CMS Hospital General Information",
        source_url=url,
        source_type=result.path.suffix.removeprefix("."),
        storage_path=str(result.path),
        checksum_sha256=result.checksum_sha256,
        etag=result.etag,
        last_modified=result.last_modified,
        downloaded_at=result.downloaded_at,
        file_size=result.size,
        parser_version=settings.cms_parser_version,
        status=SourceStatus.PROCESSING,
    )
    session.add(source)
    session.flush()
    run = ImportRun(
        importer_name="cms_hospitals", status=ImportStatus.RUNNING, source_file_id=source.id
    )
    session.add(run)
    session.flush()
    summary = ImportSummary(str(source.id), str(run.id))
    rejected: list[dict[str, Any]] = []
    try:
        for row_number, row in enumerate(_rows(result.path), start=2):
            summary.rows_read += 1
            if _value(row, "state").upper() != "NH":
                continue
            try:
                _upsert_row(session, row, source)
                existing = session.scalar(
                    select(Facility.id).where(
                        Facility.cms_certification_number == _value(row, "ccn")
                    )
                )
                # The object is present; provenance equality identifies updates on repeat runs.
                if existing is None:  # pragma: no cover - guarded inside _upsert_row
                    raise RuntimeError("facility upsert did not persist")
                action = session.info.pop("last_upsert_action")
                setattr(summary, f"rows_{action}", getattr(summary, f"rows_{action}") + 1)
            except (ValueError, TypeError) as exc:
                summary.rows_rejected += 1
                rejected.append({"row_number": row_number, "reason": str(exc), "row": row})
                logger.warning("cms_row_rejected", row_number=row_number, reason=str(exc))
        if rejected:
            settings.cms_rejected_data_dir.mkdir(parents=True, exist_ok=True)
            reject_path = settings.cms_rejected_data_dir / f"{run.id}.jsonl"
            reject_path.write_text(
                "".join(json.dumps(item) + "\n" for item in rejected), encoding="utf-8"
            )
        run.status = ImportStatus.COMPLETED_WITH_ERRORS if rejected else ImportStatus.COMPLETED
        source.status = SourceStatus.COMPLETED
    except Exception as exc:
        run.status = ImportStatus.FAILED
        source.status = SourceStatus.FAILED
        run.error_summary = f"{type(exc).__name__}: {exc}"[:2000]
        raise
    finally:
        run.finished_at = datetime.now(UTC)
        run.rows_read = summary.rows_read
        run.rows_inserted = summary.rows_inserted
        run.rows_updated = summary.rows_updated
        run.rows_rejected = summary.rows_rejected
        session.commit()
    logger.info("cms_import_completed", **asdict(summary))
    return summary


def _upsert_row(session: Session, row: Mapping[str, Any], source: SourceFile) -> None:
    ccn, name = _value(row, "ccn"), _value(row, "name")
    address, city, postal = _value(row, "address"), _value(row, "city"), _value(row, "zip")
    if not (ccn and name and address and city and postal):
        raise ValueError("missing one or more required facility fields")
    if len(ccn) > 20:
        raise ValueError("CMS certification number exceeds 20 characters")
    facility = session.scalar(select(Facility).where(Facility.cms_certification_number == ccn))
    action = "updated"
    if facility is None:
        action = "inserted"
        facility = Facility(
            cms_certification_number=ccn,
            legal_name=name,
            display_name=name,
            source_file_id=source.id,
        )
        session.add(facility)
    facility.legal_name = name
    facility.display_name = name
    facility.facility_type = _value(row, "type") or None
    facility.ownership_type = _value(row, "ownership") or None
    facility.phone = _value(row, "phone") or None
    facility.active = True
    facility.source_file_id = source.id
    if facility.locations:
        location = facility.locations[0]
    else:
        location = FacilityLocation(
            facility=facility, address_line_1=address, city=city, state="NH", postal_code=postal
        )
        session.add(location)
    location.address_line_1 = address
    location.city = city
    location.state = "NH"
    location.postal_code = postal
    location.county = _value(row, "county") or None
    session.flush()
    session.info["last_upsert_action"] = action
