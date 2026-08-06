import csv
import hashlib
import json
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

import httpx
import structlog
from sqlalchemy import select
from sqlalchemy.orm import Session

from collectors.cms_hospitals.downloader import DownloadResult, download_source
from collectors.cms_quality.config import QualityCollectorSettings, QualityDataset, quality_settings
from packages.database import (
    Facility,
    FacilityQualityMeasureObservation,
    FacilitySourceObservation,
    ImportRun,
    QualityMeasureDefinition,
    SourceFile,
    UnmatchedSourceRecord,
)
from packages.database.models import ImportStatus, SourceStatus

logger = structlog.get_logger()


@dataclass
class QualityImportSummary:
    datasets_imported: int = 0
    datasets_skipped: int = 0
    rows_read: int = 0
    facilities_matched: int = 0
    unmatched_records: int = 0
    observations_inserted: int = 0
    rows_rejected: int = 0


def _pick(row: Mapping[str, Any], *names: str) -> str:
    lowered = {str(key).strip().lower().replace("/", ""): value for key, value in row.items()}
    for name in names:
        value = lowered.get(name.lower().replace("/", ""))
        if value is not None:
            return str(value).strip()
    return ""


def _rows(path: Path) -> Iterator[dict[str, str]]:
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


def _resolve_download_url(dataset: QualityDataset, settings: QualityCollectorSettings) -> str:
    if dataset.source_url:
        return dataset.source_url
    metadata_url = (
        "https://data.cms.gov/provider-data/api/1/metastore/schemas/dataset/items/"
        f"{dataset.dataset_id}"
    )
    response = httpx.get(
        metadata_url, follow_redirects=True, timeout=settings.cms_quality_http_timeout_seconds
    )
    response.raise_for_status()
    payload = response.json()
    distributions = payload.get("distribution", [])
    for distribution in distributions:
        if distribution.get("mediaType") == "text/csv" and distribution.get("downloadURL"):
            return str(distribution["downloadURL"])
    raise ValueError(f"CMS dataset {dataset.dataset_id} has no CSV distribution")


def _parse_date(value: str) -> date | None:
    if not value:
        return None
    for pattern in ("%m/%d/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, pattern).date()
        except ValueError:
            continue
    raise ValueError(f"invalid reporting date: {value}")


def _numeric(value: str) -> Decimal | None:
    if not value or value.lower() in {"not available", "not applicable", "n/a"}:
        return None
    try:
        return Decimal(value.replace("%", "").replace(",", ""))
    except InvalidOperation:
        return None


def _normalized(row: Mapping[str, Any], dataset: QualityDataset) -> dict[str, str]:
    ccn = _pick(row, "Facility ID", "facility_id", "CMS Certification Number")
    name = _pick(row, "Facility Name", "facility_name")
    state = _pick(row, "State", "state")
    if dataset.key == "overall_rating":
        measure_id = "OVERALL_RATING"
        measure_name = "Overall hospital rating"
        score = _pick(row, "Hospital overall rating", "hospital_overall_rating")
        footnote = _pick(
            row, "Hospital overall rating footnote", "hospital_overall_rating_footnote"
        )
    elif dataset.key == "patient_experience":
        measure_id = _pick(row, "HCAHPS Measure ID", "hcahps_measure_id").upper()
        measure_name = _pick(row, "HCAHPS Question", "hcahps_question")
        score = _pick(row, "Patient Survey Star Rating", "patient_survey_star_rating")
        footnote = _pick(
            row, "Patient Survey Star Rating Footnote", "patient_survey_star_rating_footnote"
        )
    else:
        measure_id = _pick(row, "Measure ID", "measure_id").upper()
        measure_name = _pick(row, "Measure Name", "measure_name")
        score = _pick(row, "Score", "score")
        footnote = _pick(row, "Footnote", "footnote")
    category = dataset.category
    if measure_id == "MORT_30_AMI":
        category = "mortality"
    elif measure_id == "PSI_90":
        category = "patient_safety"
    return {
        "ccn": ccn,
        "name": name,
        "state": state,
        "measure_id": measure_id,
        "measure_name": measure_name or measure_id,
        "score": score,
        "footnote": footnote,
        "start": _pick(row, "Start Date", "start_date"),
        "end": _pick(row, "End Date", "end_date"),
        "category": category,
    }


def run_quality_imports(
    session: Session,
    settings: QualityCollectorSettings = quality_settings,
    fixtures: Mapping[str, Path] | None = None,
    datasets: Sequence[QualityDataset] | None = None,
) -> QualityImportSummary:
    summary = QualityImportSummary()
    for dataset in datasets or settings.datasets():
        path = fixtures.get(dataset.key) if fixtures else None
        source_url = path.resolve().as_uri() if path else _resolve_download_url(dataset, settings)
        result = (
            _local_result(path)
            if path
            else download_source(
                source_url,
                settings.cms_quality_raw_data_dir / dataset.key,
                settings.cms_quality_download_max_bytes,
                settings.cms_quality_http_timeout_seconds,
                settings.cms_quality_http_max_retries,
            )
        )
        unchanged = session.scalar(
            select(SourceFile.id).where(
                SourceFile.checksum_sha256 == result.checksum_sha256,
                SourceFile.parser_version == settings.cms_quality_parser_version,
                SourceFile.source_name == dataset.name,
                SourceFile.source_type == "cms_quality_csv",
                SourceFile.status == SourceStatus.COMPLETED,
            )
        )
        if unchanged is not None:
            summary.datasets_skipped += 1
            logger.info(
                "cms_quality_source_unchanged", dataset=dataset.key, checksum=result.checksum_sha256
            )
            continue
        _import_dataset(session, dataset, source_url, result, settings, summary)
        summary.datasets_imported += 1
    logger.info("cms_quality_import_completed", **asdict(summary))
    return summary


def _import_dataset(
    session: Session,
    dataset: QualityDataset,
    source_url: str,
    result: DownloadResult,
    settings: QualityCollectorSettings,
    summary: QualityImportSummary,
) -> None:
    source = SourceFile(
        source_name=dataset.name,
        source_url=source_url,
        source_type="cms_quality_csv",
        storage_path=str(result.path),
        checksum_sha256=result.checksum_sha256,
        etag=result.etag,
        last_modified=result.last_modified,
        downloaded_at=result.downloaded_at,
        file_size=result.size,
        parser_version=settings.cms_quality_parser_version,
        status=SourceStatus.PROCESSING,
    )
    session.add(source)
    session.flush()
    run = ImportRun(
        importer_name=f"cms_quality:{dataset.key}",
        status=ImportStatus.RUNNING,
        source_file_id=source.id,
    )
    session.add(run)
    session.flush()
    run_counts = {"read": 0, "inserted": 0, "rejected": 0, "unmatched": 0}
    rejected: list[dict[str, object]] = []
    observed_at = datetime.now(UTC)
    try:
        for row_number, row in enumerate(_rows(result.path), start=2):
            run_counts["read"] += 1
            summary.rows_read += 1
            normalized = _normalized(row, dataset)
            if normalized["state"].upper() != "NH":
                continue
            if normalized["measure_id"] not in dataset.selected_measure_ids:
                continue
            record_id = "|".join(
                (
                    normalized["ccn"],
                    normalized["measure_id"],
                    normalized["start"],
                    normalized["end"],
                )
            )
            try:
                if not normalized["ccn"] or not normalized["measure_id"]:
                    raise ValueError("missing CMS certification number or measure identifier")
                facility = session.scalar(
                    select(Facility).where(Facility.cms_certification_number == normalized["ccn"])
                )
                if facility is None:
                    session.add(
                        UnmatchedSourceRecord(
                            source_file_id=source.id,
                            import_run_id=run.id,
                            source_record_identifier=record_id,
                            supplied_cms_certification_number=normalized["ccn"],
                            supplied_facility_name=normalized["name"] or None,
                            reason_unmatched="No facility with exact CMS certification number",
                            raw_payload=dict(row),
                            review_status="pending",
                        )
                    )
                    summary.unmatched_records += 1
                    run_counts["unmatched"] += 1
                    continue
                payload = json.dumps(row, sort_keys=True, separators=(",", ":"))
                session.add(
                    FacilitySourceObservation(
                        facility_id=facility.id,
                        source_file_id=source.id,
                        import_run_id=run.id,
                        source_record_identifier=record_id,
                        source_payload_hash=hashlib.sha256(payload.encode()).hexdigest(),
                        raw_payload=dict(row),
                        observed_at=observed_at,
                    )
                )
                definition = session.scalar(
                    select(QualityMeasureDefinition).where(
                        QualityMeasureDefinition.cms_measure_id == normalized["measure_id"]
                    )
                )
                if definition is None:
                    definition = QualityMeasureDefinition(
                        cms_measure_id=normalized["measure_id"],
                        measure_name=normalized["measure_name"],
                        consumer_name=normalized["measure_name"],
                        category=normalized["category"],
                        unit="stars" if "RATING" in normalized["measure_id"] else None,
                        directionality="higher_is_better"
                        if "RATING" in normalized["measure_id"]
                        else "context_dependent",
                        data_type="numeric"
                        if _numeric(normalized["score"]) is not None
                        else "text",
                    )
                    session.add(definition)
                    session.flush()
                session.add(
                    FacilityQualityMeasureObservation(
                        facility_id=facility.id,
                        quality_measure_definition_id=definition.id,
                        source_file_id=source.id,
                        import_run_id=run.id,
                        source_record_identifier=record_id,
                        raw_value=normalized["score"] or None,
                        numeric_value=_numeric(normalized["score"]),
                        text_value=normalized["score"] or None,
                        score=normalized["score"] or None,
                        footnote_code=normalized["footnote"] or None,
                        reporting_period_start=_parse_date(normalized["start"]),
                        reporting_period_end=_parse_date(normalized["end"]),
                        observed_at=observed_at,
                    )
                )
                summary.facilities_matched += 1
                summary.observations_inserted += 1
                run_counts["inserted"] += 1
            except (ValueError, TypeError) as exc:
                summary.rows_rejected += 1
                run_counts["rejected"] += 1
                rejected.append({"row_number": row_number, "reason": str(exc), "row": row})
        if rejected:
            settings.cms_quality_rejected_data_dir.mkdir(parents=True, exist_ok=True)
            reject_path = settings.cms_quality_rejected_data_dir / f"{run.id}.jsonl"
            reject_path.write_text(
                "".join(json.dumps(item) + "\n" for item in rejected), encoding="utf-8"
            )
        run.status = (
            ImportStatus.COMPLETED_WITH_ERRORS
            if rejected or run_counts["unmatched"]
            else ImportStatus.COMPLETED
        )
        source.status = SourceStatus.COMPLETED
    except Exception as exc:
        run.status = ImportStatus.FAILED
        source.status = SourceStatus.FAILED
        run.error_summary = f"{type(exc).__name__}: {exc}"[:2000]
        raise
    finally:
        run.finished_at = datetime.now(UTC)
        run.rows_read = run_counts["read"]
        run.rows_inserted = run_counts["inserted"]
        run.rows_updated = 0
        run.rows_rejected = run_counts["rejected"] + run_counts["unmatched"]
        session.commit()
