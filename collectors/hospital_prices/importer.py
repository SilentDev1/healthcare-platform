import hashlib
import json
import logging
import shutil
import tempfile
import time
import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from sqlalchemy import insert, select
from sqlalchemy.orm import Session

from collectors.hospital_prices.caches import ImportCaches
from collectors.hospital_prices.cdm_crosswalk import apply_cdm_crosswalk
from collectors.hospital_prices.checkpoint import CheckpointManager
from collectors.hospital_prices.config import HospitalPriceSettings, hospital_price_settings
from collectors.hospital_prices.normalization import seed_payers
from collectors.hospital_prices.parsers import inspect_format, iter_rows, normalized_record
from collectors.hospital_prices.profiler import ImportProfiler
from collectors.hospital_prices.streaming import (
    SourceInput,
    ZipMemberSource,
    prepare_source_inputs,
)
from packages.database import (
    FacilityPriceSource,
    FacilitySourceObservation,
    HospitalPriceRateDetail,
    HospitalPriceRecord,
    ImportCheckpoint,
    ImportRun,
    ParserReview,
    PriceRecordProcedureCandidate,
    PriceRecordProcedureMapping,
    PriceServiceCode,
    PricingAnomaly,
    PricingUnmatchedRecord,
    SourceFile,
)
from packages.database.models import ImportStatus, SourceStatus

logger = logging.getLogger(__name__)

# Fields to keep in raw_payload (bounded subset of wide-CSV columns)
_RAW_PAYLOAD_KEYS = frozenset(
    {
        "description",
        "general_description",
        "service_description",
        "item_description",
        "code",
        "code|1",
        "billing_code",
        "cpt_hcpcs",
        "code_type",
        "code|1|type",
        "billing_code_type",
        "setting",
        "billing_class",
        "modifier",
        "modifiers",
        "gross_charge",
        "standard_charge|gross",
        "discounted_cash_price",
        "standard_charge|discounted_cash",
        "deidentified_minimum_negotiated_rate",
        "standard_charge|min",
        "deidentified_maximum_negotiated_rate",
        "standard_charge|max",
        "cms_template_version",
    }
)


@dataclass
class PriceImportSummary:
    files_parsed: int = 0
    cms_csv_files: int = 0
    cms_json_files: int = 0
    legacy_files: int = 0
    quarantined_files: int = 0
    rows_examined: int = 0
    records_normalized: int = 0
    records_rejected: int = 0
    rate_details: int = 0
    codes: int = 0
    exact_procedure_mappings: int = 0
    procedure_candidates: int = 0
    anomalies: int = 0
    skipped_unchanged: bool = False
    # True when the import stopped at the soft deadline with work still remaining;
    # the run is INTERRUPTED and resumable from its active checkpoint.
    interrupted: bool = False


def decimal_value(value: object) -> Decimal | None:
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    if isinstance(value, bool):
        raise ValueError("boolean is not a valid price")
    text = str(value).strip().replace("$", "").replace(",", "")
    try:
        result = Decimal(text)
    except InvalidOperation as exc:
        raise ValueError(f"non-numeric price: {value}") from exc
    if not result.is_finite():
        raise ValueError("price must be finite")
    return result


def rate_identity(payload: Mapping[str, object]) -> tuple[str, str | None, Decimal | None]:
    """Return the database uniqueness identity for one source rate payload."""
    payer_name = str(payload.get("payer_name") or "").strip()
    plan_name = str(payload.get("plan_name") or "").strip() or None
    return payer_name, plan_name, decimal_value(payload.get("negotiated_rate"))


def _code_system(raw: object) -> str:
    normalized = str(raw or "UNKNOWN").upper().replace("-", "").replace(" ", "")
    return {
        "CPT": "CPT",
        "HCPCS": "HCPCS",
        "CPT/HCPCS": "HCPCS",
        "MSDRG": "MS_DRG",
        "DRG": "MS_DRG",
        "REVENUECODE": "REV_CODE",
        "REV": "REV_CODE",
        "ICD10PCS": "ICD10PCS",
        "CDM": "CDM",
        "CHARGEMASTER": "CDM",
        "LOCAL": "CDM",
        "FACILITY": "CDM",
    }.get(normalized, "UNKNOWN")


def _bounded_payload(raw_row: dict[str, object]) -> dict[str, object]:
    """Extract only the bounded fields for raw_payload storage."""
    return {k: v for k, v in raw_row.items() if k in _RAW_PAYLOAD_KEYS}


@dataclass
class _BatchAccumulator:
    """Accumulates records for batch flush."""

    records: list[HospitalPriceRecord]
    codes: list[PriceServiceCode]
    rate_dicts: list[dict[str, object]]  # Core bulk insert dicts
    mappings: list[PriceRecordProcedureMapping]
    candidates: list[PriceRecordProcedureCandidate]
    anomalies: list[PricingAnomaly]
    unmatched: list[PricingUnmatchedRecord]

    @staticmethod
    def empty() -> "_BatchAccumulator":
        return _BatchAccumulator([], [], [], [], [], [], [])

    def __len__(self) -> int:
        return len(self.records)

    def clear(self) -> None:
        self.records.clear()
        self.codes.clear()
        self.rate_dicts.clear()
        self.mappings.clear()
        self.candidates.clear()
        self.anomalies.clear()
        self.unmatched.clear()


def _flush_batch(
    session: Session,
    batch: _BatchAccumulator,
    caches: ImportCaches,
    profiler: ImportProfiler,
) -> None:
    """Persist all accumulated records in one batch."""
    with profiler.time_section("db_flush"):
        # Flush pending payer/plan entities first (FK parents for rate details)
        caches.flush_pending(session)
        session.add_all(batch.records)
        session.add_all(batch.codes)
        session.add_all(batch.mappings)
        session.add_all(batch.candidates)
        session.add_all(batch.anomalies)
        session.add_all(batch.unmatched)
        session.flush()
        # Core bulk insert for rate details (highest volume — bypasses ORM overhead)
        if batch.rate_dicts:
            session.execute(insert(HospitalPriceRateDetail), batch.rate_dicts)
        profiler.record_db_statement()


def import_price_source(
    session: Session,
    price_source: FacilityPriceSource,
    settings: HospitalPriceSettings = hospital_price_settings,
    profiler: ImportProfiler | None = None,
) -> PriceImportSummary:
    summary = PriceImportSummary()
    if profiler is None:
        profiler = ImportProfiler()
    if price_source.source_file_id is None:
        raise ValueError("price source has no downloaded source file")
    source = session.get(SourceFile, price_source.source_file_id)
    if source is None:
        raise ValueError("downloaded source file is missing")
    existing_run = session.scalar(
        select(ImportRun).where(
            ImportRun.source_file_id == source.id,
            ImportRun.importer_name == "hospital_prices",
            ImportRun.status.in_([ImportStatus.COMPLETED, ImportStatus.COMPLETED_WITH_ERRORS]),
        )
    )
    if existing_run:
        summary.skipped_unchanged = True
        return summary

    parser_version = settings.hospital_price_parser_version
    resume_line = 0
    batch_number = 0

    # Resume a prior interrupted/killed import instead of starting a second run for
    # the same source file. Prefer the run that owns an active checkpoint (matched on
    # source-file identity + checksum + parser version, so a changed file or parser
    # never silently resumes onto stale progress). Because a changed checksum/parser
    # yields a *different* source_file_id (download dedups on both), an active
    # checkpoint always matches when committed rows exist for this source file — so
    # "no active checkpoint" means zero committed rows and a safe restart at line 0.
    active_checkpoint: ImportCheckpoint | None = None
    run: ImportRun | None = None
    if settings.hospital_price_checkpoint_enabled:
        active_checkpoint = session.scalar(
            select(ImportCheckpoint)
            .where(
                ImportCheckpoint.source_file_id == source.id,
                ImportCheckpoint.status == "active",
                ImportCheckpoint.source_checksum == source.checksum_sha256,
                ImportCheckpoint.parser_version == parser_version,
            )
            .order_by(ImportCheckpoint.checkpoint_at.desc())
            .limit(1)
        )
        if active_checkpoint is not None:
            run = session.get(ImportRun, active_checkpoint.import_run_id)
            if run is None:
                active_checkpoint = None  # orphaned checkpoint → treat as no progress

    if run is None:
        # Reuse any prior non-terminal run for this source (e.g. one killed before its
        # first committed batch) rather than orphaning a fresh RUNNING run/observation.
        run = session.scalar(
            select(ImportRun)
            .where(
                ImportRun.source_file_id == source.id,
                ImportRun.importer_name == "hospital_prices",
                ImportRun.status.in_([ImportStatus.RUNNING, ImportStatus.INTERRUPTED]),
            )
            .order_by(ImportRun.started_at.desc())
            .limit(1)
        )

    observation: FacilitySourceObservation | None = None
    if run is not None:
        run.status = ImportStatus.RUNNING
        observation = session.scalar(
            select(FacilitySourceObservation).where(
                FacilitySourceObservation.import_run_id == run.id,
                FacilitySourceObservation.source_file_id == source.id,
            )
        )
        if active_checkpoint is not None:
            resume_line = active_checkpoint.last_completed_line
            summary.records_normalized = active_checkpoint.normalized_records_committed
            summary.rate_details = active_checkpoint.rate_details_committed
            batch_number = active_checkpoint.batch_number
            logger.info(
                "resuming_from_checkpoint",
                extra={"resume_line": resume_line, "batch_number": batch_number},
            )
        else:
            logger.info("restarting_incomplete_run", extra={"run_id": str(run.id)})
    else:
        run = ImportRun(
            importer_name="hospital_prices", status=ImportStatus.RUNNING, source_file_id=source.id
        )
        session.add(run)
        session.flush()

    if observation is None:
        observation = FacilitySourceObservation(
            facility_id=price_source.facility_id,
            source_file_id=source.id,
            import_run_id=run.id,
            source_record_identifier=f"MRF:{source.checksum_sha256}",
            source_payload_hash=source.checksum_sha256,
            raw_payload={
                "source_url": source.source_url,
                "checksum_sha256": source.checksum_sha256,
                "parser_version": parser_version,
            },
            observed_at=datetime.now(UTC),
        )
        session.add(observation)
        session.flush()

    checkpoint_mgr = CheckpointManager(session, run, source, parser_version)
    if active_checkpoint is not None:
        checkpoint_mgr.resume_existing(active_checkpoint.id)
    run.parser_version_used = parser_version
    run.source_checksum_used = source.checksum_sha256
    # Persist the RUNNING run + observation up front so a hard kill still leaves a
    # resumable anchor. Also fixes the identifiers below against expiry across the
    # per-batch commits that follow.
    session.commit()

    # Stable identifiers reused across per-batch commits (avoids re-querying expired
    # ORM attributes after each commit).
    source_id = source.id
    run_id = run.id
    observation_id = observation.id
    facility_id = price_source.facility_id
    location_id = price_source.facility_location_id
    soft_deadline = settings.hospital_price_import_soft_deadline_seconds
    started_monotonic = time.monotonic()

    # Load all caches once
    with profiler.time_section("seed_payers"):
        seed_payers(session)
    caches = ImportCaches()
    with profiler.time_section("load_caches"):
        caches.load(session)

    # Stage extraction and parsing on local container disk instead of the gcsfuse
    # source mount. Reading/writing multi-GB machine-readable files directly over
    # gcsfuse stalls the import before the first row; local disk keeps it fast. The
    # staging directory is always removed in the finally clause below.
    #
    # Archives that expand past the on-disk cap are parsed straight from the ZIP
    # member (ZipMemberSource) — constant memory, nothing materialized on disk.
    local_extract_root = Path(tempfile.mkdtemp(prefix="carevero-extract-"))
    logger.info("import_extract_start", extra={"source_file_id": str(source.id)})
    staged_inputs: list[SourceInput] = []
    for candidate in prepare_source_inputs(Path(source.storage_path), local_extract_root, settings):
        if isinstance(candidate, ZipMemberSource):
            # Streamed from the archive on demand; nothing to stage on disk.
            staged_inputs.append(candidate)
        elif local_extract_root in candidate.parents:
            staged_inputs.append(candidate)
        else:
            local_copy = local_extract_root / candidate.name
            shutil.copyfile(candidate, local_copy)
            staged_inputs.append(local_copy)
    extracted = staged_inputs
    logger.info(
        "import_extract_complete",
        extra={"source_file_id": str(source.id), "files": len(extracted)},
    )
    batch = _BatchAccumulator.empty()
    try:
        for input_path in extracted:
            match, headers, sample = inspect_format(input_path)
            if match is None:
                session.add(
                    ParserReview(
                        source_file_id=source_id,
                        detected_format=input_path.suffix.lower().lstrip(".") or "unknown",
                        detected_headers=headers,
                        bounded_sample=sample,
                        status="unsupported_pending_review",
                        reason="No deterministic parser matched the bounded schema sample",
                    )
                )
                summary.quarantined_files += 1
                continue
            summary.files_parsed += 1
            summary.cms_csv_files += int(match.parser_name == "cms_hpt_csv")
            summary.cms_json_files += int(match.parser_name == "cms_hpt_json")
            summary.legacy_files += int(match.parser_name.startswith("legacy"))
            price_source.detected_format = match.detected_format
            price_source.detected_schema_version = match.schema_version
            now = datetime.now(UTC)
            for line_number, raw_row in enumerate(iter_rows(input_path, match), start=2):
                if line_number <= resume_line:
                    summary.rows_examined += 1
                    continue
                summary.rows_examined += 1
                profiler.record_row()
                with profiler.time_section("normalize"):
                    row = normalized_record(raw_row)
                record_id = str(
                    raw_row.get("source_record_identifier") or raw_row.get("id") or line_number
                )
                bounded = _bounded_payload(raw_row)
                payload_json = json.dumps(
                    bounded, sort_keys=True, default=str, separators=(",", ":")
                )
                try:
                    description = str(row["description"] or "").strip()
                    code = str(row["code"] or "").strip()
                    if not description or not code:
                        raise ValueError("missing description or billing code")
                    gross, cash = (
                        decimal_value(row["gross_charge"]),
                        decimal_value(row["cash_price"]),
                    )
                    minimum, maximum = decimal_value(row["minimum"]), decimal_value(row["maximum"])
                    values = [
                        value for value in (gross, cash, minimum, maximum) if value is not None
                    ]
                    if any(value < 0 for value in values):
                        raise ValueError("negative price")

                    # Pre-assign UUID so children can reference it without flush
                    rec_uuid = uuid.uuid4()
                    normalized_desc = caches.normalize_description(description)
                    record = HospitalPriceRecord(
                        id=rec_uuid,
                        facility_id=facility_id,
                        facility_location_id=location_id,
                        source_file_id=source_id,
                        import_run_id=run_id,
                        facility_source_observation_id=observation_id,
                        source_record_identifier=record_id,
                        source_line_number=line_number,
                        source_payload_hash=hashlib.sha256(payload_json.encode()).hexdigest(),
                        raw_description=description,
                        service_description_normalized=normalized_desc,
                        setting=str(row["setting"]),
                        billing_class=str(row["billing_class"]),
                        gross_charge=gross,
                        discounted_cash_price=cash,
                        deidentified_minimum_negotiated_rate=minimum,
                        deidentified_maximum_negotiated_rate=maximum,
                        raw_payload=bounded,
                        parser_name=match.parser_name,
                        parser_version=match.parser_version,
                        observed_at=now,
                    )
                    batch.records.append(record)
                    summary.records_normalized += 1
                    profiler.record_insert()

                    system = _code_system(row["code_type"])
                    resolved_code = code
                    # CDM crosswalk: attempt to resolve CDM/UNKNOWN codes
                    if system in ("CDM", "UNKNOWN"):
                        crosswalk_result = apply_cdm_crosswalk(code, system, description)
                        if crosswalk_result:
                            resolved_code, system, _cdm_conf = crosswalk_result

                    batch.codes.append(
                        PriceServiceCode(
                            hospital_price_record_id=rec_uuid,
                            code_system=system,
                            # code/raw_code are String(100). Some vendor CDM/local "codes"
                            # are long concatenated description blobs (e.g. Craneware exports)
                            # that overflow the column. Cap at the column width — canonical
                            # billing codes (CPT/HCPCS/MS-DRG) are short and never truncated,
                            # so procedure mapping is unaffected; only junk local codes get cut.
                            code=resolved_code[:100],
                            modifier=str(row["modifier"]) if row["modifier"] else None,
                            raw_code_type=str(row["code_type"]),
                            raw_code=code[:100],
                        )
                    )
                    summary.codes += 1

                    # Procedure mapping via in-memory cache
                    mapping = caches.lookup_code(system, resolved_code)
                    if mapping:
                        procedure_id, mapping_id = mapping
                        batch.mappings.append(
                            PriceRecordProcedureMapping(
                                hospital_price_record_id=rec_uuid,
                                procedure_id=procedure_id,
                                mapping_method="exact_approved_code",
                                confidence_score=1,
                                reviewed=True,
                                reviewed_by="approved-code-registry",
                                reviewed_at=now,
                                source_code_mapping_id=mapping_id,
                            )
                        )
                        summary.exact_procedure_mappings += 1
                    else:
                        alias_procedure = caches.lookup_procedure_alias(normalized_desc)
                        batch.candidates.append(
                            PriceRecordProcedureCandidate(
                                hospital_price_record_id=rec_uuid,
                                procedure_id=alias_procedure,
                                match_method="exact_reviewed_alias"
                                if alias_procedure
                                else "conservative_similarity",
                                score=Decimal("0.80") if alias_procedure else Decimal("0"),
                                reason=(
                                    "Description requires human review; no approved code mapping"
                                ),
                                status="pending",
                            )
                        )
                        summary.procedure_candidates += 1

                    # Row-local anomaly evaluation
                    if cash is not None and gross is not None and cash > gross:
                        _batch_anomaly(
                            batch,
                            summary,
                            rec_uuid,
                            None,
                            "cash_above_gross",
                            "error",
                            "Discounted cash price exceeds gross charge",
                            {"cash": str(cash), "gross": str(gross)},
                        )
                    if minimum is not None and maximum is not None and minimum > maximum:
                        _batch_anomaly(
                            batch,
                            summary,
                            rec_uuid,
                            None,
                            "minimum_above_maximum",
                            "error",
                            "De-identified minimum exceeds maximum",
                            {"minimum": str(minimum), "maximum": str(maximum)},
                        )
                    if any(value == 0 for value in values):
                        _batch_anomaly(
                            batch,
                            summary,
                            rec_uuid,
                            None,
                            "suspicious_zero",
                            "warning",
                            "Source explicitly reports a zero price",
                            {},
                        )
                    if any(value > 1_000_000 for value in values):
                        _batch_anomaly(
                            batch,
                            summary,
                            rec_uuid,
                            None,
                            "extremely_large_price",
                            "warning",
                            "Price exceeds review threshold",
                            {},
                        )

                    # Rate details — payer/plan via in-memory cache (dict for Core insert)
                    row_rate_count = 0
                    seen_rate_identities: set[tuple[str, str | None, Decimal | None]] = set()
                    with profiler.time_section("rate_details"):
                        for rate_payload in row["rates"]:
                            if not isinstance(rate_payload, dict):
                                continue
                            payer_name, plan_name, rate = rate_identity(rate_payload)
                            rate_key = (payer_name, plan_name, rate)
                            if rate_key in seen_rate_identities:
                                continue
                            seen_rate_identities.add(rate_key)
                            if rate is not None and rate < 0:
                                raise ValueError("negative negotiated rate")
                            payer_id, _method, _conf = caches.match_payer(payer_name)
                            plan_id = caches.match_or_create_plan(payer_id, plan_name)
                            detail_uuid = uuid.uuid4()
                            batch.rate_dicts.append(
                                {
                                    "id": detail_uuid,
                                    "hospital_price_record_id": rec_uuid,
                                    "payer_entity_id": payer_id,
                                    "insurance_plan_entity_id": plan_id,
                                    "source_payer_name": payer_name,
                                    "source_plan_name": plan_name,
                                    "negotiated_rate": rate,
                                    "negotiated_rate_type": str(
                                        rate_payload.get("negotiated_rate_type") or "unknown"
                                    ),
                                    "negotiated_rate_algorithm": (
                                        str(rate_payload.get("algorithm"))
                                        if rate_payload.get("algorithm")
                                        else None
                                    ),
                                    "source_payload": rate_payload,
                                }
                            )
                            row_rate_count += 1
                            if not payer_name:
                                _batch_anomaly(
                                    batch,
                                    summary,
                                    rec_uuid,
                                    detail_uuid,
                                    "blank_payer",
                                    "error",
                                    "Payer-specific rate has no payer name",
                                    {},
                                )
                    summary.rate_details += row_rate_count
                    profiler.record_rate_detail(row_rate_count)

                    # Flush the batch and COMMIT it together with its checkpoint, so
                    # the committed rows + resume position are durable. A later run
                    # resumes at exactly this line, never re-importing committed work.
                    if len(batch) >= settings.hospital_price_batch_size:
                        _flush_batch(session, batch, caches, profiler)
                        batch_number += 1
                        if settings.hospital_price_checkpoint_enabled:
                            checkpoint_mgr.save(
                                line_number,
                                summary.records_normalized,
                                summary.rate_details,
                                batch_number,
                            )
                        session.commit()
                        batch.clear()
                        # Soft wall-clock budget: stop cleanly at this committed
                        # boundary so the platform never hard-kills mid-batch.
                        if soft_deadline and time.monotonic() - started_monotonic >= soft_deadline:
                            summary.interrupted = True
                            break

                    milestone = profiler.milestone_report(
                        settings.hospital_price_profiling_milestone_rows
                    )
                    if milestone:
                        logger.info("import_milestone", extra=milestone)
                except ValueError as exc:
                    summary.records_rejected += 1
                    batch.unmatched.append(
                        PricingUnmatchedRecord(
                            source_file_id=source_id,
                            import_run_id=run_id,
                            facility_id=facility_id,
                            source_record_identifier=record_id,
                            reason=str(exc),
                            raw_description=str(row.get("description") or "") or None,
                            supplied_codes={
                                "code": row.get("code"),
                                "code_type": row.get("code_type"),
                            },
                            raw_payload=_bounded_payload(raw_row),
                            review_status="pending",
                        )
                    )
                    if "negative" in str(exc):
                        _batch_anomaly(
                            batch,
                            summary,
                            None,
                            None,
                            "negative_price",
                            "critical",
                            "Negative source price rejected from normalized facts",
                            {"record_id": record_id},
                        )

            if summary.interrupted:
                break  # soft deadline reached; leave the rest for a resume

        if summary.interrupted:
            # Stopped cleanly at the soft deadline. Committed batches and the active
            # checkpoint remain; mark the run resumable and return without completing.
            interrupted_run = session.get(ImportRun, run_id)
            if interrupted_run is not None:
                interrupted_run.status = ImportStatus.INTERRUPTED
                interrupted_run.throughput_rows_per_sec = Decimal(
                    str(round(profiler.rows_per_sec, 2))
                )
                interrupted_run.finished_at = datetime.now(UTC)
                interrupted_run.rows_read = summary.rows_examined
                interrupted_run.rows_inserted = summary.records_normalized
                interrupted_run.rows_rejected = summary.records_rejected
            session.commit()
            logger.info(
                "import_interrupted_soft_deadline",
                extra={"records": summary.records_normalized, "line": resume_line},
            )
            return summary

        # Flush remaining batch and commit it with its checkpoint.
        if len(batch) > 0 or batch.unmatched or batch.anomalies:
            _flush_batch(session, batch, caches, profiler)
            batch_number += 1
            if settings.hospital_price_checkpoint_enabled:
                checkpoint_mgr.save(
                    summary.rows_examined + 1,  # past last line
                    summary.records_normalized,
                    summary.rate_details,
                    batch_number,
                )
            session.commit()
            batch.clear()

        checkpoint_mgr.complete()
        completed_run = session.get(ImportRun, run_id)
        assert completed_run is not None
        completed_run.status = (
            ImportStatus.COMPLETED_WITH_ERRORS
            if summary.records_rejected or summary.quarantined_files
            else ImportStatus.COMPLETED
        )
        completed_run.throughput_rows_per_sec = Decimal(str(round(profiler.rows_per_sec, 2)))
        completed_run.finished_at = datetime.now(UTC)
        completed_run.rows_read = summary.rows_examined
        completed_run.rows_inserted = summary.records_normalized
        completed_run.rows_rejected = summary.records_rejected
        completed_source = session.get(SourceFile, source_id)
        assert completed_source is not None
        completed_source.status = SourceStatus.COMPLETED
    except KeyboardInterrupt:
        _persist_interrupted_import(session, run_id, source_id, summary)
        raise
    except Exception as exc:
        _persist_interrupted_import(
            session, run_id, source_id, summary, error=f"{type(exc).__name__}: {exc}"[:2000]
        )
        raise
    finally:
        shutil.rmtree(local_extract_root, ignore_errors=True)
    profiler.record_db_transaction()
    with profiler.time_section("db_commit"):
        session.commit()
    logger.info("import_complete", extra=profiler.summary())
    return summary


def _persist_interrupted_import(
    session: Session,
    run_id: uuid.UUID,
    source_id: uuid.UUID,
    summary: PriceImportSummary,
    error: str | None = None,
) -> None:
    """Roll back only the uncommitted partial batch and leave the import resumable.

    With per-batch commits, batches already written are durable and correct; only the
    in-flight batch (never committed) is discarded by the rollback. The run is marked
    INTERRUPTED and its active checkpoint is preserved (never abandoned), so the next
    invocation resumes from the last committed line rather than re-importing. The
    source is returned to DOWNLOADED so a retry is permitted. Committed rows are never
    thrown away — that is what makes very large MRFs completable across runs.
    """
    session.rollback()
    interrupted_run = session.get(ImportRun, run_id)
    if interrupted_run is not None:
        interrupted_run.status = ImportStatus.INTERRUPTED
        if error is not None:
            interrupted_run.error_summary = error
        interrupted_run.finished_at = datetime.now(UTC)
        interrupted_run.rows_read = summary.rows_examined
        interrupted_run.rows_inserted = summary.records_normalized
        interrupted_run.rows_rejected = summary.records_rejected
    interrupted_source = session.get(SourceFile, source_id)
    if interrupted_source is not None:
        interrupted_source.status = SourceStatus.DOWNLOADED
    session.commit()


def _batch_anomaly(
    batch: _BatchAccumulator,
    summary: PriceImportSummary,
    record_id: uuid.UUID | None,
    rate_id: uuid.UUID | None,
    rule: str,
    severity: str,
    message: str,
    details: dict[str, object],
) -> None:
    batch.anomalies.append(
        PricingAnomaly(
            hospital_price_record_id=record_id,
            hospital_price_rate_detail_id=rate_id,
            anomaly_type=rule,
            severity=severity,
            rule_key=rule,
            rule_version="1.0",
            message=message,
            details=details,
            status="open",
        )
    )
    summary.anomalies += 1
