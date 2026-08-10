"""CDM (Charge Description Master) to CPT/HCPCS crosswalk.

Provides deterministic mappings from hospital-specific CDM codes to
standard billing codes. Only verified, high-confidence mappings are used.
This module is facility-agnostic and works nationally.
"""

import json
import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CrosswalkMapping:
    cdm_pattern: str
    description_pattern: str
    target_code: str
    target_system: str
    confidence: float


_DEFAULT_FIXTURE = (
    Path(__file__).resolve().parent.parent.parent / "data" / "fixtures" / "cdm_crosswalk.json"
)

_cached_mappings: list[CrosswalkMapping] | None = None


def _load_mappings(path: Path | None = None) -> list[CrosswalkMapping]:
    global _cached_mappings
    if _cached_mappings is not None and path is None:
        return _cached_mappings

    fixture_path = path or _DEFAULT_FIXTURE
    with fixture_path.open() as f:
        data = json.load(f)

    mappings = [
        CrosswalkMapping(
            cdm_pattern=m["cdm_pattern"],
            description_pattern=m["description_pattern"],
            target_code=m["target_code"],
            target_system=m["target_system"],
            confidence=m["confidence"],
        )
        for m in data["mappings"]
    ]

    if path is None:
        _cached_mappings = mappings
    return mappings


def apply_cdm_crosswalk(
    code: str,
    code_type: str,
    description: str,
    path: Path | None = None,
) -> tuple[str, str, float] | None:
    """Attempt to resolve a CDM/unknown code to a standard billing code.

    Args:
        code: The original billing code (may be CDM-specific).
        code_type: The declared code type (CDM, UNKNOWN, etc.).
        description: The service description from the source file.

    Returns:
        (resolved_code, resolved_system, confidence) or None if no match.
        Only returns verified deterministic mappings -- never guesses.
    """
    # Only attempt crosswalk for CDM or UNKNOWN code types
    if code_type.upper() not in ("CDM", "UNKNOWN", "LOCAL", "FACILITY", "CHARGEMASTER"):
        return None

    mappings = _load_mappings(path)
    desc_lower = description.lower().strip()

    for mapping in mappings:
        try:
            if re.search(mapping.description_pattern, desc_lower):
                return (mapping.target_code, mapping.target_system, mapping.confidence)
        except re.error:
            continue

    return None
