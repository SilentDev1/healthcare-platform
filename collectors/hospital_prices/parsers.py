"""Format detection and row-level parsing for hospital price files.

Parser selection depends on file format, schema, CMS version, vendor,
and content structure -- NEVER on hospital location. A CMS 3.0 file in
any state uses the same parser as one from any other state.
"""

import csv
import io
import json
import re
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from xml.etree import ElementTree


@dataclass(frozen=True)
class ParserMatch:
    parser_name: str
    parser_version: str
    schema_version: str | None
    confidence: float
    detected_format: str


# Expanded header synonyms for description fields
CSV_DESCRIPTION = (
    "description",
    "general_description",
    "service_description",
    "item_description",
    "item/service",
    "item_service",
    "procedure",
    "charge_description",
    "service_name",
    "procedure_description",
    "line_item_description",
    "cdm_description",
    "charge_desc",
    "svc_description",
    "service_desc",
    "line_description",
    "item_name",
    "chg_desc",
    "chg_description",
    "procedure_name",
    "proc_description",
    "proc_desc",
    "code_desc",
    "code_description",
)

# Expanded header synonyms for code fields
CSV_CODES = (
    "code",
    "billing_code",
    "billing/accounting_code",
    "cpt_hcpcs",
    "procedure_code",
    "hcpcs_code",
    "cpt_code",
    "cpt",
    "hcpcs",
    "billing_code_value",
    "cdm_code",
    "charge_code",
    "service_code",
    "item_code",
    "rev_code",
    "revenue_code",
    "drg",
    "drg_code",
    "ms_drg",
    "charge_number",
    "chg_code",
    "proc_code",
    "cpt_hcpcs_code",
    "billing_code_1",
    "hcpc_code",
)

CMS_FIELDS = {"description", "setting", "code", "gross_charge", "discounted_cash_price"}

# Maximum metadata lines to skip before finding header
MAX_METADATA_LINES = 20


def _normalized_key(value: str) -> str:
    compact_pipes = re.sub(r"\s*\|\s*", "|", value.strip().lower())
    return compact_pipes.replace(" ", "_").replace("-", "_")


@dataclass(frozen=True)
class _ParserDefinition:
    """Registry entry for a parser with its match function."""

    name: str
    format_type: str
    match_fn_name: str  # method name on module level
    confidence: float
    version: str


def inspect_format(path: Path) -> tuple[ParserMatch | None, list[str], list[object]]:
    """Detect file format and return (ParserMatch, headers, sample_rows)."""
    with path.open("rb") as stream:
        sample_bytes = stream.read(128 * 1024)

    text = sample_bytes.decode("utf-8-sig", errors="replace")
    stripped = text.lstrip()

    # XML detection
    if stripped.startswith("<?xml") or (stripped.startswith("<") and not stripped.startswith("<!")):
        return _inspect_xml(path, text)

    # JSON detection
    if stripped.startswith(("{", "[")):
        return _inspect_json(path, text, sample_bytes)

    # CSV/TSV/pipe-delimited detection
    return _inspect_csv(path, text)


def _inspect_json(
    path: Path, text: str, sample_bytes: bytes
) -> tuple[ParserMatch | None, list[str], list[object]]:
    """Inspect JSON files."""
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
    if normalized & {"service_description", "item_description", "charge_description"}:
        return ParserMatch("legacy_hospital_json", "1.0.0", None, 0.8, "json"), headers, sample

    # Large JSON file: can't parse full payload, detect format from text markers
    if payload is None and path.stat().st_size > len(text.encode("utf-8", errors="replace")):
        text_lower = text.lower()
        if '"standard_charge_information"' in text_lower:
            version = None
            if '"version"' in text_lower:
                # Extract version from text
                import re as _re

                ver_match = _re.search(r'"version"\s*:\s*"([^"]+)"', text)
                version = ver_match.group(1) if ver_match else None
            return (
                ParserMatch("cms_hpt_json", "1.0.0", version, 0.95, "json"),
                ["standard_charge_information"],
                [],
            )
        if '"description"' in text_lower and (
            '"code"' in text_lower or '"billing_code"' in text_lower
        ):
            return (
                ParserMatch("legacy_hospital_json", "1.0.0", None, 0.7, "json"),
                [],
                [],
            )

    return None, headers, sample


def _inspect_csv(path: Path, text: str) -> tuple[ParserMatch | None, list[str], list[object]]:
    """Inspect CSV/TSV/pipe-delimited files."""
    lines = text.splitlines()

    # Expanded header search: skip up to MAX_METADATA_LINES of metadata
    # Generate tokens with both underscores and spaces for raw-text matching
    _desc_variants = set(CSV_DESCRIPTION) | {d.replace("_", " ") for d in CSV_DESCRIPTION}
    description_tokens = tuple(d + sep for d in _desc_variants for sep in (",", "|", "\t"))

    header_index = 0
    for index, line in enumerate(lines):
        if index >= MAX_METADATA_LINES:
            break
        lowered = line.lower().strip()
        if any(lowered.startswith(token) for token in description_tokens):
            header_index = index
            break
        # Check if any description token appears anywhere in the line (not just start)
        if any(token in lowered for token in description_tokens):
            header_index = index
            break
        # Also check for CMS 3.0 wide-format markers
        compact_pipes = re.sub(r"\s*\|\s*", "|", lowered)
        if "standard_charge|" in compact_pipes or "billing_code_value" in lowered:
            header_index = index
            break

    csv_text = "\n".join(lines[header_index:])
    try:
        delimiter = csv.Sniffer().sniff(csv_text[:8192], delimiters=",|\t;").delimiter
    except csv.Error:
        delimiter = ","
    reader = csv.DictReader(io.StringIO(csv_text), delimiter=delimiter)
    headers = list(reader.fieldnames or [])
    sample_rows: list[object] = [dict(row) for _, row in zip(range(3), reader, strict=False)]
    normalized = {_normalized_key(item) for item in headers}
    has_code = bool(normalized & set(CSV_CODES)) or "code|1" in normalized
    has_desc = bool(normalized & set(CSV_DESCRIPTION))

    # CMS 3.0 wide-format detection
    has_wide_format = any("standard_charge|" in _normalized_key(h) for h in headers)

    if has_desc and (has_code or has_wide_format):
        cms_overlap = len(normalized & CMS_FIELDS)
        name = (
            "cms_hpt_csv"
            if cms_overlap >= 3 or "cms_template_version" in normalized or has_wide_format
            else "legacy_hospital_csv"
        )
        return (
            ParserMatch(name, "1.0.0", None, 1.0 if name == "cms_hpt_csv" else 0.8, "csv"),
            headers,
            sample_rows,
        )

    # Chargemaster-wide CSV with payer columns as headers
    if has_desc and len(headers) > 6:
        # Many columns likely indicate payer-specific rates as headers
        return (
            ParserMatch("chargemaster_wide_csv", "1.0.0", None, 0.7, "csv"),
            headers,
            sample_rows,
        )

    # Fallback: CSV with description but no recognized code column
    # May still contain embedded codes in description or other columns
    if has_desc:
        return (
            ParserMatch("legacy_hospital_csv", "1.0.0", None, 0.6, "csv"),
            headers,
            sample_rows,
        )

    return None, headers, sample_rows


def _inspect_xml(path: Path, text: str) -> tuple[ParserMatch | None, list[str], list[object]]:
    """Inspect XML standard charges files."""
    try:
        tree = ElementTree.fromstring(text[:500_000])  # noqa: S314
        root_tag = tree.tag.lower()
        # Remove XML namespace prefix for matching
        if "}" in root_tag:
            root_tag = root_tag.split("}")[-1]
        xml_keywords = (
            "charge",
            "price",
            "standard",
            "hospital",
            "transparency",
            "mrf",
            "services",
            "billing",
            "rate",
            "fee",
        )
        if any(kw in root_tag for kw in xml_keywords) or len(tree) > 0:
            child_tags = [child.tag for child in tree[:5]]
            return (
                ParserMatch("xml_standard_charges", "1.0.0", None, 0.8, "xml"),
                child_tags,
                [],
            )
    except ElementTree.ParseError:
        pass
    return None, [], []


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
    """Stream normalized rows from a parsed file."""
    if match.detected_format == "xml":
        yield from _iter_xml_rows(path)
        return

    if match.detected_format == "csv":
        with path.open(encoding="utf-8-sig", errors="replace", newline="") as stream:
            metadata_lines: list[str] = []
            while line := stream.readline():
                metadata_lines.append(line)
                lowered = line.lower()
                # Expanded header detection (both underscore and space variants)
                _variants = set(CSV_DESCRIPTION) | {d.replace("_", " ") for d in CSV_DESCRIPTION}
                desc_tokens = tuple(d + sep for d in _variants for sep in (",", "|", "\t")) + (
                    "billing_code_value",
                    "standard_charge|",
                )
                compact_pipes = re.sub(r"\s*\|\s*", "|", lowered)
                if (
                    any(token in lowered for token in desc_tokens)
                    or "standard_charge|" in compact_pipes
                ):
                    break
                if len(metadata_lines) >= MAX_METADATA_LINES:
                    raise ValueError("CSV header not found within bounded metadata rows")
            sample = metadata_lines[-1]
            try:
                delimiter = csv.Sniffer().sniff(sample, delimiters=",|\t;").delimiter
            except csv.Error:
                delimiter = ","
            fieldnames = next(csv.reader([sample], delimiter=delimiter))
            for row in csv.DictReader(stream, fieldnames=fieldnames, delimiter=delimiter):
                yield {_normalized_key(str(key)): value for key, value in row.items() if key}
        return

    # JSON
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


def _iter_xml_rows(path: Path) -> Iterator[dict[str, Any]]:
    """Basic XPath extraction for XML standard charges."""
    try:
        tree = ElementTree.parse(path)  # noqa: S314
        root = tree.getroot()
        for item in root:
            row: dict[str, Any] = {}
            for child in item:
                tag = child.tag.lower().replace("{", "").split("}")[-1]
                row[_normalized_key(tag)] = child.text
            if row:
                yield row
    except ElementTree.ParseError:
        return


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
    if not code:
        source_codes = [
            (
                value(row, f"code|{index}", f"code_{index}"),
                value(row, f"code|{index}|type", f"code_{index}_type"),
            )
            for index in range(1, 7)
        ]
        preferred_types = {"CPT", "HCPCS", "MS-DRG", "MS_DRG", "APC"}
        preferred = next(
            (
                (candidate_code, candidate_type)
                for candidate_code, candidate_type in source_codes
                if candidate_code and str(candidate_type or "").strip().upper() in preferred_types
            ),
            None,
        )
        fallback = next(
            (
                (candidate_code, candidate_type)
                for candidate_code, candidate_type in source_codes
                if candidate_code
            ),
            (None, None),
        )
        code, code_type = preferred or fallback

    # CMS HPT JSON 3.0: extract code from code_information array
    code_info = row.get("code_information") or row.get("billing_code_information")
    if not code and isinstance(code_info, list) and code_info:
        for ci in code_info:
            if isinstance(ci, dict):
                ci_type = str(ci.get("type", "") or "").upper()
                if ci_type in ("CPT", "HCPCS", "MS-DRG", "MS_DRG"):
                    code = ci.get("code")
                    code_type = ci_type.replace("-", "_")
                    break
        # Fallback: use first code if no preferred type found
        if not code and isinstance(code_info[0], dict):
            code = code_info[0].get("code")
            code_type = str(code_info[0].get("type", "UNKNOWN") or "UNKNOWN").upper()

    rates = value(row, "payer_rates", "rates")

    # CMS HPT JSON 3.0: extract rates and charges from standard_charges array
    std_charges = row.get("standard_charges")
    setting_from_charges = None
    gross_from_charges = None
    cash_from_charges = None
    min_from_charges = None
    max_from_charges = None
    if isinstance(std_charges, list) and std_charges and not isinstance(rates, list):
        rates = []
        for sc in std_charges:
            if not isinstance(sc, dict):
                continue
            setting_from_charges = setting_from_charges or sc.get("setting")
            gross_from_charges = gross_from_charges or sc.get("gross_charge")
            cash_from_charges = cash_from_charges or sc.get("discounted_cash")
            min_from_charges = min_from_charges or sc.get("minimum")
            max_from_charges = max_from_charges or sc.get("maximum")
            payers_info = sc.get("payers_information")
            if isinstance(payers_info, list):
                for pi in payers_info:
                    if isinstance(pi, dict):
                        methodology = str(pi.get("methodology") or "dollar")[:30]
                        rates.append(
                            {
                                "payer_name": pi.get("payer_name"),
                                "plan_name": pi.get("plan_name"),
                                "negotiated_rate": pi.get("standard_charge_dollar"),
                                "negotiated_rate_type": methodology,
                            }
                        )

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
        "setting": value(row, "setting") or setting_from_charges or "unknown",
        "billing_class": value(row, "billing_class") or "facility",
        "gross_charge": value(
            row, "gross_charge", "gross", "standard_charge_gross", "standard_charge|gross"
        )
        or gross_from_charges,
        "cash_price": value(
            row,
            "discounted_cash_price",
            "cash_price",
            "standard_charge_discounted_cash",
            "standard_charge|discounted_cash",
        )
        or cash_from_charges,
        "minimum": value(
            row,
            "deidentified_minimum_negotiated_rate",
            "minimum_negotiated_charge",
            "min_rate",
            "standard_charge|min",
        )
        or min_from_charges,
        "maximum": value(
            row,
            "deidentified_maximum_negotiated_rate",
            "maximum_negotiated_charge",
            "max_rate",
            "standard_charge|max",
        )
        or max_from_charges,
        "rates": rates,
    }
