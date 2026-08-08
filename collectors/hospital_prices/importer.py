import hashlib
import json
import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from sqlalchemy import insert, select
from sqlalchemy.orm import Session

from collectors.hospital_prices.caches import ImportCaches
from collectors.hospital_prices.checkpoint import CheckpointManager
from collectors.hospital_prices.config import HospitalPriceSettings, hospital_price_settings
from collectors.hospital_prices.downloader import safe_extract
from collectors.hospital_prices.normalization import seed_payers
from collectors.hospital_prices.parsers import inspect_format, iter_rows, normalized_record
from collectors.hospital_prices.profiler import ImportProfiler
from packages.database import (
    FacilityPriceSource,
    FacilitySourceObservation,
    HospitalPriceRateDetail,
    HospitalPriceRecord,
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
    run = ImportRun(
        importer_name="hospital_prices", status=ImportStatus.RUNNING, source_file_id=source.id
    )
    session.add(run)
    session.flush()
    observation = FacilitySourceObservation(
        facility_id=price_source.facility_id,
        source_file_id=source.id,
        import_run_id=run.id,
        source_record_identifier=f"MRF:{source.checksum_sha256}",
        source_payload_hash=source.checksum_sha256,
        raw_payload={
            "source_url": source.source_url,
            "checksum_sha256": source.checksum_sha256,
            "parser_version": settings.hospital_price_parser_version,
        },
        observed_at=datetime.now(UTC),
    )
    session.add(observation)
    session.flush()

    # Load all caches once
    with profiler.time_section("seed_payers"):
        seed_payers(session)
    caches = ImportCaches()
    with profiler.time_section("load_caches"):
        caches.load(session)

    # Checkpoint support
    checkpoint_mgr = CheckpointManager(session, run, source, settings.hospital_price_parser_version)
    run.parser_version_used = settings.hospital_price_parser_version
    run.source_checksum_used = source.checksum_sha256
    resume_line = 0
    batch_number = 0
    if settings.hospital_price_checkpoint_enabled and checkpoint_mgr.can_resume():
        resume_line = checkpoint_mgr.get_resume_position()
        prev_records, prev_rates, batch_number = checkpoint_mgr.get_resume_counters()
        summary.records_normalized = prev_records
        summary.rate_details = prev_rates
        logger.info(
            "resuming_from_checkpoint",
            extra={"resume_line": resume_line, "batch_number": batch_number},
        )

    extracted = safe_extract(
        Path(source.storage_path), Path(source.storage_path).parent / "extracted", settings
    )
    batch = _BatchAccumulator.empty()
    try:
        for input_path in extracted:
            match, headers, sample = inspect_format(input_path)
            if match is None:
                session.add(
                    ParserReview(
                        source_file_id=source.id,
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
                        facility_id=price_source.facility_id,
                        source_file_id=source.id,
                        import_run_id=run.id,
                        facility_source_observation_id=observation.id,
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
                    batch.codes.append(
                        PriceServiceCode(
                            hospital_price_record_id=rec_uuid,
                            code_system=system,
                            code=code,
                            modifier=str(row["modifier"]) if row["modifier"] else None,
                            raw_code_type=str(row["code_type"]),
                            raw_code=code,
                        )
                    )
                    summary.codes += 1

                    # Procedure mapping via in-memory cache
                    mapping = caches.lookup_code(system, code)
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
                    with profiler.time_section("rate_details"):
                        for rate_payload in row["rates"]:
                            if not isinstance(rate_payload, dict):
                                continue
                            rate = decimal_value(rate_payload.get("negotiated_rate"))
                            if rate is not None and rate < 0:
                                raise ValueError("negative negotiated rate")
                            payer_name = str(rate_payload.get("payer_name") or "").strip()
                            payer_id, _method, _conf = caches.match_payer(payer_name)
                            plan_name = str(rate_payload.get("plan_name") or "").strip() or None
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

                    # Flush batch if full
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
                        batch.clear()

                    milestone = profiler.milestone_report(
                        settings.hospital_price_profiling_milestone_rows
                    )
                    if milestone:
                        logger.info("import_milestone", extra=milestone)
                except ValueError as exc:
                    summary.records_rejected += 1
                    batch.unmatched.append(
                        PricingUnmatchedRecord(
                            source_file_id=source.id,
                            import_run_id=run.id,
                            facility_id=price_source.facility_id,
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

        # Flush remaining batch
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
            batch.clear()

        checkpoint_mgr.complete()
        run.status = (
            ImportStatus.COMPLETED_WITH_ERRORS
            if summary.records_rejected or summary.quarantined_files
            else ImportStatus.COMPLETED
        )
        run.throughput_rows_per_sec = Decimal(str(round(profiler.rows_per_sec, 2)))
        source.status = SourceStatus.COMPLETED
    except KeyboardInterrupt:
        run.status = ImportStatus.INTERRUPTED
        source.status = SourceStatus.FAILED
        run.error_summary = "Import interrupted by user"
        raise
    except Exception as exc:
        run.status = ImportStatus.FAILED
        source.status = SourceStatus.FAILED
        run.error_summary = f"{type(exc).__name__}: {exc}"[:2000]
        raise
    finally:
        run.finished_at = datetime.now(UTC)
        run.rows_read = summary.rows_examined
        run.rows_inserted = summary.records_normalized
        run.rows_rejected = summary.records_rejected
        profiler.record_db_transaction()
        with profiler.time_section("db_commit"):
            session.commit()
        logger.info("import_complete", extra=profiler.summary())
    return summary


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
