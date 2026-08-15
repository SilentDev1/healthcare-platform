"""CDM (Charge Description Master) to CPT/HCPCS crosswalk.

Provides deterministic mappings from hospital-specific CDM codes to
standard billing codes. Only verified, high-confidence mappings are used.
This module is facility-agnostic and works nationally.
"""

import json
import re
from dataclasses import dataclass
from pathlib import Path

# A procedure crosswalk must never resolve a drug/supply line to a procedure code.
# Dosage-form / supply words are strong, procedure-free signals — a bone-density
# scan is never a "tablet" and an EGD is never a "suspension". This guard prevents
# drug-name collisions the description patterns cannot otherwise distinguish (e.g.
# "DEXA 4MG TAB" dexamethasone vs a DEXA scan, "TOBRA/DEXAMETH OPTH SUSP").
_DRUG_SUPPLY_PATTERN = re.compile(
    # Unambiguous dosage-form / supply words (procedures are never these). 'inj',
    # 'enema', 'patch' are deliberately excluded — they collide with real procedures
    # (EGD injection of varices, barium enema); injectable drugs are still caught by
    # the numeric strength below.
    r"\b(tabs?|tablet|caps?|capsule|susp|suspension|soln|solution|ointment|oint|"
    r"cream|drops|lozenge|supp|suppository|vial|elixir|syrup|inhaler|nebul|"
    r"otic|ophth|opth|troche)\b"
    r"|\b\d+\s?(mg|mcg|meq|units?)\b"  # numeric drug strength (not ml/contrast volume)
)


def _looks_like_drug_or_supply(description_lower: str) -> bool:
    """True if the description is a drug/supply line (dosage form or strength)."""
    return bool(_DRUG_SUPPLY_PATTERN.search(description_lower))


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

    desc_lower = description.lower().strip()

    # A drug/supply line is never a procedure — refuse it before any pattern match.
    if _looks_like_drug_or_supply(desc_lower):
        return None

    mappings = _load_mappings(path)

    for mapping in mappings:
        try:
            if re.search(mapping.description_pattern, desc_lower):
                return (mapping.target_code, mapping.target_system, mapping.confidence)
        except re.error:
            continue

    return None
