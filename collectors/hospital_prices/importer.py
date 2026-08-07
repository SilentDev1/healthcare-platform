import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from collectors.hospital_prices.config import HospitalPriceSettings, hospital_price_settings
from collectors.hospital_prices.downloader import safe_extract
from collectors.hospital_prices.normalization import match_or_create_plan, match_payer, seed_payers
from collectors.hospital_prices.parsers import inspect_format, iter_rows, normalized_record
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
    ProcedureAlias,
    ProcedureCodeMapping,
    ProcedureCodeSystem,
    SourceFile,
)
from packages.database.models import ImportStatus, SourceStatus
from packages.identity import normalize_name


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


def _approved_code_map(session: Session) -> dict[tuple[str, str], tuple[uuid.UUID, uuid.UUID]]:
    rows = session.execute(
        select(ProcedureCodeMapping, ProcedureCodeSystem)
        .join(ProcedureCodeSystem)
        .where(ProcedureCodeMapping.mapping_status.in_(["reviewed", "approved"]))
    ).all()
    return {
        (system.code_system, mapping.code): (mapping.procedure_id, mapping.id)
        for mapping, system in rows
    }


def import_price_source(
    session: Session,
    price_source: FacilityPriceSource,
    settings: HospitalPriceSettings = hospital_price_settings,
) -> PriceImportSummary:
    summary = PriceImportSummary()
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
    seed_payers(session)
    code_map = _approved_code_map(session)
    aliases = {
        alias.normalized_alias: alias.procedure_id
        for alias in session.scalars(select(ProcedureAlias).where(ProcedureAlias.active.is_(True)))
    }
    extracted = safe_extract(
        Path(source.storage_path), Path(source.storage_path).parent / "extracted", settings
    )
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
            for line_number, raw_row in enumerate(iter_rows(input_path, match), start=2):
                summary.rows_examined += 1
                row = normalized_record(raw_row)
                record_id = str(
                    raw_row.get("source_record_identifier") or raw_row.get("id") or line_number
                )
                raw_json = json.dumps(raw_row, sort_keys=True, default=str, separators=(",", ":"))
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
                    record = HospitalPriceRecord(
                        facility_id=price_source.facility_id,
                        source_file_id=source.id,
                        import_run_id=run.id,
                        facility_source_observation_id=observation.id,
                        source_record_identifier=record_id,
                        source_line_number=line_number,
                        source_payload_hash=hashlib.sha256(raw_json.encode()).hexdigest(),
                        raw_description=description,
                        service_description_normalized=normalize_name(description),
                        setting=str(row["setting"]),
                        billing_class=str(row["billing_class"]),
                        gross_charge=gross,
                        discounted_cash_price=cash,
                        deidentified_minimum_negotiated_rate=minimum,
                        deidentified_maximum_negotiated_rate=maximum,
                        raw_payload=dict(raw_row),
                        parser_name=match.parser_name,
                        parser_version=match.parser_version,
                        observed_at=datetime.now(UTC),
                    )
                    session.add(record)
                    session.flush()
                    summary.records_normalized += 1
                    system = _code_system(row["code_type"])
                    session.add(
                        PriceServiceCode(
                            hospital_price_record_id=record.id,
                            code_system=system,
                            code=code,
                            modifier=str(row["modifier"]) if row["modifier"] else None,
                            raw_code_type=str(row["code_type"]),
                            raw_code=code,
                        )
                    )
                    summary.codes += 1
                    mapping = code_map.get((system, code))
                    if mapping:
                        procedure_id, mapping_id = mapping
                        session.add(
                            PriceRecordProcedureMapping(
                                hospital_price_record_id=record.id,
                                procedure_id=procedure_id,
                                mapping_method="exact_approved_code",
                                confidence_score=1,
                                reviewed=True,
                                reviewed_by="approved-code-registry",
                                reviewed_at=datetime.now(UTC),
                                source_code_mapping_id=mapping_id,
                            )
                        )
                        summary.exact_procedure_mappings += 1
                    else:
                        alias_procedure = aliases.get(normalize_name(description))
                        session.add(
                            PriceRecordProcedureCandidate(
                                hospital_price_record_id=record.id,
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
                    blocking = False
                    if cash is not None and gross is not None and cash > gross:
                        _anomaly(
                            session,
                            summary,
                            record.id,
                            "cash_above_gross",
                            "error",
                            "Discounted cash price exceeds gross charge",
                            {"cash": str(cash), "gross": str(gross)},
                        )
                        blocking = True
                    if minimum is not None and maximum is not None and minimum > maximum:
                        _anomaly(
                            session,
                            summary,
                            record.id,
                            "minimum_above_maximum",
                            "error",
                            "De-identified minimum exceeds maximum",
                            {"minimum": str(minimum), "maximum": str(maximum)},
                        )
                        blocking = True
                    if any(value == 0 for value in values):
                        _anomaly(
                            session,
                            summary,
                            record.id,
                            "suspicious_zero",
                            "warning",
                            "Source explicitly reports a zero price",
                            {},
                        )
                    if any(value > 1_000_000 for value in values):
                        _anomaly(
                            session,
                            summary,
                            record.id,
                            "extremely_large_price",
                            "warning",
                            "Price exceeds review threshold",
                            {},
                        )
                    for rate_payload in row["rates"]:
                        if not isinstance(rate_payload, dict):
                            continue
                        rate = decimal_value(rate_payload.get("negotiated_rate"))
                        if rate is not None and rate < 0:
                            raise ValueError("negative negotiated rate")
                        payer_name = str(rate_payload.get("payer_name") or "").strip()
                        payer_match = match_payer(session, payer_name)
                        plan_name = str(rate_payload.get("plan_name") or "").strip() or None
                        plan_id = match_or_create_plan(session, payer_match.payer_id, plan_name)
                        detail = HospitalPriceRateDetail(
                            hospital_price_record_id=record.id,
                            payer_entity_id=payer_match.payer_id,
                            insurance_plan_entity_id=plan_id,
                            source_payer_name=payer_name,
                            source_plan_name=plan_name,
                            negotiated_rate=rate,
                            negotiated_rate_type=str(
                                rate_payload.get("negotiated_rate_type") or "unknown"
                            ),
                            negotiated_rate_algorithm=str(rate_payload.get("algorithm"))
                            if rate_payload.get("algorithm")
                            else None,
                            source_payload=rate_payload,
                        )
                        session.add(detail)
                        session.flush()
                        summary.rate_details += 1
                        if not payer_name:
                            _anomaly(
                                session,
                                summary,
                                record.id,
                                "blank_payer",
                                "error",
                                "Payer-specific rate has no payer name",
                                {},
                                detail.id,
                            )
                            blocking = True
                    if blocking:
                        session.flush()
                    if summary.rows_examined % settings.hospital_price_batch_size == 0:
                        session.flush()
                except ValueError as exc:
                    summary.records_rejected += 1
                    session.add(
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
                            raw_payload=dict(raw_row),
                            review_status="pending",
                        )
                    )
                    if "negative" in str(exc):
                        _anomaly(
                            session,
                            summary,
                            None,
                            "negative_price",
                            "critical",
                            "Negative source price rejected from normalized facts",
                            {"record_id": record_id},
                        )
        run.status = (
            ImportStatus.COMPLETED_WITH_ERRORS
            if summary.records_rejected or summary.quarantined_files
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
        run.rows_read = summary.rows_examined
        run.rows_inserted = summary.records_normalized
        run.rows_rejected = summary.records_rejected
        session.commit()
    return summary


def _anomaly(
    session: Session,
    summary: PriceImportSummary,
    record_id: uuid.UUID | None,
    rule: str,
    severity: str,
    message: str,
    details: dict[str, object],
    rate_id: uuid.UUID | None = None,
) -> None:
    session.add(
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
