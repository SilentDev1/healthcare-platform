import csv
import io
import json
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ParserMatch:
    parser_name: str
    parser_version: str
    schema_version: str | None
    confidence: float
    detected_format: str


CSV_DESCRIPTION = ("description", "general_description", "service_description", "item_description")
CSV_CODES = ("code", "billing_code", "billing/accounting_code", "cpt_hcpcs")
CMS_FIELDS = {"description", "setting", "code", "gross_charge", "discounted_cash_price"}


def _normalized_key(value: str) -> str:
    return value.strip().lower().replace(" ", "_").replace("-", "_")


def inspect_format(path: Path) -> tuple[ParserMatch | None, list[str], list[object]]:
    with path.open("rb") as stream:
        sample_bytes = stream.read(128 * 1024)
    text = sample_bytes.decode("utf-8-sig", errors="replace")
    stripped = text.lstrip()
    if stripped.startswith(("{", "[")):
        try:
            payload = json.loads(text) if path.stat().st_size <= len(sample_bytes) else None
        except json.JSONDecodeError:
            payload = None
        headers: list[str] = []
        sample: list[object] = []
        if isinstance(payload, list) and payload:
            headers = list(payload[0]) if isinstance(payload[0], dict) else []
            sample = payload[:3]
        elif isinstance(payload, dict):
            records = payload.get("standard_charge_information") or payload.get("records")
            if isinstance(records, list) and records:
                headers = list(records[0]) if isinstance(records[0], dict) else []
                sample = records[:3]
            else:
                headers = list(payload)
        normalized = {_normalized_key(item) for item in headers}
        if normalized & {"description", "general_description"} and normalized & {
            "code",
            "billing_code",
            "billing_code_information",
        }:
            return (
                ParserMatch("cms_hpt_json", "1.0.0", _json_version(payload), 1.0, "json"),
                headers,
                sample,
            )
        if normalized & {"service_description", "item_description"}:
            return ParserMatch("legacy_hospital_json", "1.0.0", None, 0.8, "json"), headers, sample
        return None, headers, sample
    lines = text.splitlines()
    header_index = next(
        (index for index, line in enumerate(lines) if line.lower().startswith("description,")), 0
    )
    csv_text = "\n".join(lines[header_index:])
    delimiter = csv.Sniffer().sniff(csv_text[:8192], delimiters=",|\t;").delimiter
    reader = csv.DictReader(io.StringIO(csv_text), delimiter=delimiter)
    headers = list(reader.fieldnames or [])
    sample_rows: list[object] = [dict(row) for _, row in zip(range(3), reader, strict=False)]
    normalized = {_normalized_key(item) for item in headers}
    has_code = bool(normalized & set(CSV_CODES)) or "code|1" in normalized
    if normalized & set(CSV_DESCRIPTION) and has_code:
        cms_overlap = len(normalized & CMS_FIELDS)
        name = (
            "cms_hpt_csv"
            if cms_overlap >= 3
            or "cms_template_version" in normalized
            or "standard_charge|gross" in normalized
            else "legacy_hospital_csv"
        )
        return (
            ParserMatch(name, "1.0.0", None, 1.0 if name == "cms_hpt_csv" else 0.8, "csv"),
            headers,
            sample_rows,
        )
    return None, headers, sample_rows


def _json_version(payload: object) -> str | None:
    if isinstance(payload, dict):
        value = payload.get("version") or payload.get("cms_template_version")
        return str(value) if value is not None else None
    return None


def _stream_json_array(path: Path, key: str | None = None) -> Iterator[dict[str, Any]]:
    decoder = json.JSONDecoder()
    buffer = ""
    started = False
    with path.open(encoding="utf-8-sig") as stream:
        while chunk := stream.read(64 * 1024):
            buffer += chunk
            if not started:
                if key:
                    marker = f'"{key}"'
                    marker_index = buffer.find(marker)
                    if marker_index < 0:
                        buffer = buffer[-len(marker) :]
                        continue
                    array_index = buffer.find("[", marker_index + len(marker))
                else:
                    array_index = buffer.find("[")
                if array_index < 0:
                    continue
                buffer = buffer[array_index + 1 :]
                started = True
            while True:
                buffer = buffer.lstrip(" \r\n\t,")
                if buffer.startswith("]"):
                    return
                try:
                    value, offset = decoder.raw_decode(buffer)
                except json.JSONDecodeError:
                    break
                if isinstance(value, dict):
                    yield value
                buffer = buffer[offset:]
            if len(buffer) > 10_000_000:
                raise ValueError("JSON record exceeds bounded parser buffer")
    if not started:
        raise ValueError("JSON record array not found")


def iter_rows(path: Path, match: ParserMatch) -> Iterator[dict[str, Any]]:
    if match.detected_format == "csv":
        with path.open(encoding="utf-8-sig", errors="replace", newline="") as stream:
            metadata_lines: list[str] = []
            while line := stream.readline():
                metadata_lines.append(line)
                lowered = line.lower()
                if any(
                    token in lowered
                    for token in ("description,", "item_description,", "service_description,")
                ):
                    break
                if len(metadata_lines) >= 10:
                    raise ValueError("CSV header not found within bounded metadata rows")
            sample = metadata_lines[-1]
            delimiter = csv.Sniffer().sniff(sample, delimiters=",|\t;").delimiter
            fieldnames = next(csv.reader([sample], delimiter=delimiter))
            for row in csv.DictReader(stream, fieldnames=fieldnames, delimiter=delimiter):
                yield {_normalized_key(str(key)): value for key, value in row.items() if key}
        return
    with path.open(encoding="utf-8-sig") as stream:
        prefix = stream.read(64 * 1024)
    key = (
        "standard_charge_information"
        if '"standard_charge_information"' in prefix
        else "records"
        if '"records"' in prefix
        else None
    )
    for row in _stream_json_array(path, key):
        yield {_normalized_key(str(key_name)): value for key_name, value in row.items()}


def value(row: Mapping[str, Any], *names: str) -> Any:
    for name in names:
        candidate = row.get(_normalized_key(name))
        if candidate not in (None, ""):
            return candidate
    return None


def normalized_record(row: Mapping[str, Any]) -> dict[str, Any]:
    description = value(row, *CSV_DESCRIPTION)
    code = value(row, *CSV_CODES)
    code_type = value(row, "code_type", "billing_code_type", "billing/accounting_code_type")
    code = code or value(row, "code|1", "code_1")
    code_type = code_type or value(row, "code|1|type", "code_1_type")
    rates = value(row, "payer_rates", "rates")
    if not isinstance(rates, list):
        payer = value(row, "payer_name", "payer")
        negotiated = value(
            row, "negotiated_rate", "standard_charge_dollar", "payer_specific_negotiated_charge"
        )
        rates = (
            [
                {
                    "payer_name": payer,
                    "plan_name": value(row, "plan_name", "plan"),
                    "negotiated_rate": negotiated,
                    "negotiated_rate_type": value(
                        row, "negotiated_rate_type", "standard_charge_method"
                    ),
                }
            ]
            if payer or negotiated is not None
            else []
        )
        for key, negotiated in row.items():
            parts = key.split("|")
            if (
                len(parts) >= 4
                and parts[0] == "standard_charge"
                and parts[-1] == "negotiated_dollar"
                and negotiated not in (None, "")
            ):
                rates.append(
                    {
                        "payer_name": parts[1] or "other/unknown",
                        "plan_name": parts[2] or None,
                        "negotiated_rate": negotiated,
                        "negotiated_rate_type": "dollar",
                    }
                )
    return {
        "description": description,
        "code": code,
        "code_type": code_type or "UNKNOWN",
        "modifier": value(row, "modifier", "modifiers"),
        "setting": value(row, "setting") or "unknown",
        "billing_class": value(row, "billing_class") or "facility",
        "gross_charge": value(
            row, "gross_charge", "gross", "standard_charge_gross", "standard_charge|gross"
        ),
        "cash_price": value(
            row,
            "discounted_cash_price",
            "cash_price",
            "standard_charge_discounted_cash",
            "standard_charge|discounted_cash",
        ),
        "minimum": value(
            row,
            "deidentified_minimum_negotiated_rate",
            "minimum_negotiated_charge",
            "min_rate",
            "standard_charge|min",
        ),
        "maximum": value(
            row,
            "deidentified_maximum_negotiated_rate",
            "maximum_negotiated_charge",
            "max_rate",
            "standard_charge|max",
        ),
        "rates": rates,
    }
