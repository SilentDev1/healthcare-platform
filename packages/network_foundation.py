"""Semantics and conservative validation for official provider-directory evidence."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

NETWORK_STATUSES = {
    "IN_NETWORK_VERIFIED",
    "OUT_OF_NETWORK_VERIFIED",
    "NETWORK_STATUS_UNKNOWN",
    "DIRECTORY_LISTED",
    "DIRECTORY_NOT_LISTED",
    "STALE_DIRECTORY_DATA",
    "CONFLICT_REVIEW_REQUIRED",
}
STRONG_IDENTIFIER_TYPES = {"npi", "ccn", "organization_id"}


@dataclass(frozen=True)
class FacilityMatch:
    facility_id: str | None
    location_id: str | None
    status: str
    evidence: dict[str, object]


def match_facility_by_identifiers(
    source_identifiers: dict[str, str], candidates: list[dict[str, Any]]
) -> FacilityMatch:
    """Match only unique strong identifiers; names/addresses remain review evidence."""
    matches: list[dict[str, Any]] = []
    for candidate in candidates:
        identifiers = candidate.get("identifiers", {})
        if any(
            source_identifiers.get(kind) and source_identifiers[kind] == identifiers.get(kind)
            for kind in STRONG_IDENTIFIER_TYPES
        ):
            matches.append(candidate)
    if len(matches) == 1:
        item = matches[0]
        return FacilityMatch(
            str(item["facility_id"]),
            None if item.get("location_id") is None else str(item["location_id"]),
            "matched",
            {"method": "strong_identifier", "source_identifiers": source_identifiers},
        )
    return FacilityMatch(
        None,
        None,
        "ambiguous_review_required" if len(matches) > 1 else "unmatched_review_required",
        {"method": "no_unique_strong_identifier", "candidate_count": len(matches)},
    )


def freshness_status(
    observed_at: datetime, freshness_days: int, *, now: datetime | None = None
) -> str:
    reference = now or datetime.now(UTC)
    observed = observed_at if observed_at.tzinfo else observed_at.replace(tzinfo=UTC)
    age = (reference - observed).days
    if age <= freshness_days:
        return "fresh"
    if age <= freshness_days * 2:
        return "aging"
    return "stale"


def conservative_network_status(statuses: set[str]) -> str:
    known = statuses & NETWORK_STATUSES
    if "IN_NETWORK_VERIFIED" in known and "OUT_OF_NETWORK_VERIFIED" in known:
        return "CONFLICT_REVIEW_REQUIRED"
    if len(known) == 1:
        return next(iter(known))
    return "NETWORK_STATUS_UNKNOWN"


class ProviderDirectoryConnector(ABC):
    """Generic boundary; payer-specific connectors can be added only when justified."""

    @abstractmethod
    def discover(self) -> list[dict[str, object]]: ...

    @abstractmethod
    def fetch(self, source: dict[str, object]) -> bytes: ...

    @abstractmethod
    def normalize(self, content: bytes) -> list[dict[str, object]]: ...

    def match_facility(
        self, record: dict[str, object], candidates: list[dict[str, Any]]
    ) -> FacilityMatch:
        identifiers = record.get("identifiers", {})
        return match_facility_by_identifiers(
            identifiers if isinstance(identifiers, dict) else {}, candidates
        )

    @abstractmethod
    def record_observation(self, record: dict[str, object], match: FacilityMatch) -> None: ...
