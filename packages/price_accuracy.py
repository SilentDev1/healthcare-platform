"""Deterministic evidence checks for consumer-published hospital prices."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from statistics import median
from typing import Any

AUDIT_VERSION = "4.7.0"
PUBLIC_PRICE_TYPES = {
    "gross",
    "discounted_cash",
    "deidentified_min",
    "deidentified_max",
    "payer_negotiated",
}


def parse_source_decimal(value: object) -> Decimal | None:
    """Normalize formatting only; never round, estimate, or alter magnitude."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, Decimal):
        return value
    if isinstance(value, int | float):
        return Decimal(str(value))
    text = str(value).strip()
    negative = text.startswith("(") and text.endswith(")")
    normalized = re.sub(r"[$,\s]", "", text.strip("()"))
    try:
        amount = Decimal(normalized)
    except InvalidOperation:
        return None
    return -amount if negative else amount


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def source_amount_for(
    price_type: str,
    record: Any,
    rate_detail: Any | None,
) -> Decimal | None:
    fields = {
        "gross": "gross_charge",
        "discounted_cash": "discounted_cash_price",
        "deidentified_min": "deidentified_minimum_negotiated_rate",
        "deidentified_max": "deidentified_maximum_negotiated_rate",
    }
    if price_type == "payer_negotiated":
        return None if rate_detail is None else parse_source_decimal(rate_detail.negotiated_rate)
    field = fields.get(price_type)
    return None if field is None else parse_source_decimal(getattr(record, field))


@dataclass(frozen=True)
class AuditOutcome:
    status: str
    source_amount: Decimal | None
    normalized_amount: Decimal
    difference: Decimal | None
    semantic_checks: dict[str, bool]
    provenance_checks: dict[str, bool]
    evidence: dict[str, object]

    def serializable(self) -> dict[str, object]:
        result = asdict(self)
        for key in ("source_amount", "normalized_amount", "difference"):
            value = result[key]
            result[key] = None if value is None else str(value)
        return result


def audit_observation(
    observation: Any,
    record: Any,
    rate_detail: Any | None,
    mapping: Any | None,
    source_file: Any,
    *,
    raw_checksum_verified: bool = False,
    raw_source_available: bool = False,
    source_location_id: object | None = None,
) -> AuditOutcome:
    source_amount = source_amount_for(observation.price_type, record, rate_detail)
    normalized = Decimal(observation.amount)
    difference = None if source_amount is None else normalized - source_amount
    semantic = {
        "price_type_known": observation.price_type in PUBLIC_PRICE_TYPES,
        "procedure_mapping_present": mapping is not None,
        "procedure_matches_mapping": mapping is not None
        and mapping.procedure_id == observation.procedure_id,
        "mapping_publishable": mapping is not None
        and (mapping.mapping_method == "exact_approved_code" or bool(mapping.reviewed)),
        "facility_matches": observation.facility_id == record.facility_id,
        "location_matches": observation.facility_location_id
        == (record.facility_location_id or source_location_id),
        "setting_matches": observation.service_setting == (record.setting or "unknown"),
        "payer_matches": observation.price_type != "payer_negotiated"
        or (rate_detail is not None and observation.payer_entity_id == rate_detail.payer_entity_id),
        "plan_matches": observation.price_type != "payer_negotiated"
        or (
            rate_detail is not None
            and observation.insurance_plan_entity_id == rate_detail.insurance_plan_entity_id
        ),
    }
    provenance = {
        "source_file_present": source_file is not None,
        "source_url_present": bool(getattr(source_file, "source_url", None)),
        "source_checksum_present": len(getattr(source_file, "checksum_sha256", "")) == 64,
        "source_record_identifier_present": bool(record.source_record_identifier),
        "source_payload_hash_present": len(record.source_payload_hash or "") == 64,
        "bounded_source_payload_present": bool(record.raw_payload),
        "parser_version_present": bool(record.parser_version),
        "raw_source_available": raw_source_available,
        "raw_checksum_verified": raw_checksum_verified,
    }
    if source_amount is None or difference != 0:
        status = "VALUE_MISMATCH"
    elif not semantic["procedure_mapping_present"] or not semantic["mapping_publishable"]:
        status = "MAPPING_REVIEW_REQUIRED"
    elif not all(semantic.values()):
        status = "SEMANTIC_MISMATCH"
    elif raw_source_available and raw_checksum_verified:
        status = "FULL_SOURCE_VERIFIED"
    elif all(
        provenance[key]
        for key in (
            "source_file_present",
            "source_url_present",
            "source_checksum_present",
            "source_record_identifier_present",
            "source_payload_hash_present",
            "bounded_source_payload_present",
            "parser_version_present",
        )
    ):
        status = "PROVENANCE_VERIFIED"
    else:
        status = "SOURCE_FILE_UNAVAILABLE"
    return AuditOutcome(
        status=status,
        source_amount=source_amount,
        normalized_amount=normalized,
        difference=difference,
        semantic_checks=semantic,
        provenance_checks=provenance,
        evidence={
            "record_locator": record.source_record_identifier,
            "source_line_number": record.source_line_number,
            "source_payload_hash": record.source_payload_hash,
            "source_url": getattr(source_file, "source_url", None),
            "checksum_sha256": getattr(source_file, "checksum_sha256", None),
            "parser_name": record.parser_name,
            "parser_version": record.parser_version,
            "mapping_method": None if mapping is None else mapping.mapping_method,
        },
    )


def reproduce_range(values: Iterable[Decimal]) -> dict[str, Decimal] | None:
    ordered = sorted(values)
    if not ordered:
        return None
    return {"min": ordered[0], "max": ordered[-1], "median": Decimal(median(ordered))}
