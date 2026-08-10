"""Vendor detection for hospital MRF files.

Identifies the transparency data vendor/platform from URL patterns,
HTTP headers, and file content samples. Vendor knowledge is reusable
nationally -- vendors serve hospitals across all states.
"""

from collections.abc import Mapping
from typing import Any

# Vendor detection signatures: (vendor_name, url_patterns, header_markers, content_markers)
_VENDOR_SIGNATURES: list[tuple[str, list[str], list[str], list[str]]] = [
    (
        "turquoise_health",
        ["turquoise", "turquoisehealth"],
        ["x-turquoise", "turquoise"],
        ["turquoise health", "turquoisehealth"],
    ),
    (
        "cleverley",
        ["cleverley", "cleverleyassociates"],
        [],
        ["cleverley"],
    ),
    (
        "medicopy",
        ["medicopy"],
        [],
        ["medicopy"],
    ),
    (
        "hca_healthcare",
        [
            "hcahealthcare",
            "parklandmedicalcenter.com",
            "portsmouthhospital.com",
            "frisbiehospital.com",
            "catholicmc.com",
        ],
        [],
        ["hca healthcare", "healthtrust"],
    ),
    (
        "epic",
        [],
        ["epic", "x-epic"],
        ["epic systems", "mychart"],
    ),
    (
        "cerner",
        [],
        ["cerner", "x-cerner"],
        ["cerner corporation"],
    ),
    (
        "beth_israel_lahey",
        ["bilh.org"],
        [],
        ["beth israel lahey"],
    ),
    (
        "mass_general_brigham",
        ["massgeneralbrigham.org"],
        [],
        ["mass general brigham", "partners healthcare"],
    ),
    (
        "mainehealth",
        ["mainehealth.org"],
        [],
        ["mainehealth"],
    ),
]


def detect_vendor(
    url: str,
    headers: Mapping[str, str] | None = None,
    sample: str | None = None,
) -> str | None:
    """Detect the transparency data vendor from URL, headers, and content.

    Args:
        url: The MRF source URL.
        headers: HTTP response headers (optional).
        sample: First few KB of file content (optional).

    Returns:
        Vendor identifier string or None if unknown.
    """
    url_lower = url.lower()
    headers_lower = {k.lower(): v.lower() for k, v in (headers or {}).items()}
    sample_lower = (sample or "").lower()

    for vendor_name, url_patterns, header_markers, content_markers in _VENDOR_SIGNATURES:
        # Check URL patterns
        for pattern in url_patterns:
            if pattern in url_lower:
                return vendor_name

        # Check headers
        for marker in header_markers:
            if any(marker in v for v in headers_lower.values()):
                return vendor_name

        # Check content sample
        for marker in content_markers:
            if marker in sample_lower:
                return vendor_name

    return None


def detect_vendor_from_format(
    headers: list[str],
    sample_rows: list[Any] | None = None,
) -> str | None:
    """Detect vendor from CSV/JSON header structure.

    Some vendors use distinctive column naming patterns.
    """
    headers_lower = [h.lower() for h in headers]
    joined = " ".join(headers_lower)

    # HCA Healthcare uses specific column patterns
    if (
        "standard_charge|gross" in joined
        and "standard_charge|discounted_cash" in joined
        and any("healthtrust" in h for h in headers_lower)
    ):
        return "hca_healthcare"

    # CMS standard naming (not vendor-specific)
    if "standard_charge_gross" in joined or "standard_charge|gross" in joined:
        return None  # Generic CMS format

    return None


def classify_file_role(url: str, headers: list[str] | None = None) -> str:
    """Classify the role of an MRF file based on URL and content.

    Returns: standard_charges, shoppable_services, drg_schedule, chargemaster
    """
    url_lower = url.lower()

    if "shoppable" in url_lower:
        return "shoppable_services"
    if "drg" in url_lower:
        return "drg_schedule"
    if "chargemaster" in url_lower or "cdm" in url_lower:
        return "chargemaster"

    # Check headers for content clues
    if headers:
        headers_lower = [h.lower() for h in headers]
        if any("shoppable" in h for h in headers_lower):
            return "shoppable_services"

    return "standard_charges"
