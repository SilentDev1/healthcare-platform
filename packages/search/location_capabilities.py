"""Consumer location-capability registry + capability-aware location resolution.

Capability resolution is deterministic and evidence-based: a consumer term ("urgent
care", "ER", "imaging") maps to a canonical capability id via a reviewed registry, and
matching locations come ONLY from the `location_capabilities` table (real, verified
data) — never inferred from an organization's name or type, and never fabricated. If no
verified location holds the capability yet, the resolver returns nothing for it, so the
consumer never sees provider categories Carevero has no data for.

Display labels live here for 5 locales; canonical capability ids are language-independent.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import structlog
from sqlalchemy import select
from sqlalchemy.orm import Session

from packages.database import (
    Facility,
    FacilityLocation,
    LocationCapability,
    Organization,
)
from packages.identity import normalize_name
from packages.search.service import SearchResult

logger = structlog.get_logger(service="location_capabilities")

SUPPORTED_LOCALES = ("en", "es", "vi", "zh-TW", "zh-CN")


@dataclass(frozen=True)
class ConsumerCapability:
    capability: str
    i18n_key: str
    labels: dict[str, str]
    aliases: tuple[str, ...]

    def label(self, locale: str) -> str:
        return self.labels.get(locale, self.labels["en"])


@lru_cache(maxsize=1)
def consumer_location_capabilities() -> dict[str, ConsumerCapability]:
    path = Path(__file__).resolve().parents[2] / "data" / "consumer_location_capabilities.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    registry: dict[str, ConsumerCapability] = {}
    for item in payload:
        labels = item["labels"]
        if set(labels) != set(SUPPORTED_LOCALES):
            raise ValueError(f"capability {item['capability']} must define every supported locale")
        capability = ConsumerCapability(
            capability=item["capability"],
            i18n_key=item["i18n_key"],
            labels=labels,
            aliases=tuple(item["aliases"]),
        )
        if capability.capability in registry:
            raise ValueError(f"duplicate capability: {capability.capability}")
        registry[capability.capability] = capability
    return registry


@lru_cache(maxsize=1)
def _term_to_capability() -> dict[str, str]:
    """Normalized consumer term -> canonical capability id (labels + reviewed aliases)."""
    mapping: dict[str, str] = {}
    for capability in consumer_location_capabilities().values():
        terms = [*capability.labels.values(), *capability.aliases, capability.capability]
        for term in terms:
            normalized = normalize_name(term) or " ".join(term.casefold().split())
            if normalized:
                mapping.setdefault(normalized, capability.capability)
    return mapping


def match_capability(query: str) -> str | None:
    """Return the canonical capability id a query names, or None. Exact/alias match only.

    Defensive: capability resolution is an optional enrichment layer. If the registry
    cannot be loaded (e.g. the data file is absent from an image), degrade to "no
    capability match" so core deterministic search is never taken down by it.
    """
    normalized = normalize_name(query) or " ".join(query.casefold().split())
    try:
        return _term_to_capability().get(normalized)
    except Exception:
        logger.warning("capability_registry_unavailable")
        return None


def resolve_capability_locations(
    session: Session,
    capability: str,
    *,
    state: str | None = None,
    limit: int = 25,
) -> list[SearchResult]:
    """Verified locations that actually hold `capability`, as facility SearchResults.

    Real data only: joins `location_capabilities` to active facilities/locations. Empty
    when no verified location has the capability (no fabrication). One result per
    (facility, location) that holds the capability.
    """
    conditions = [
        LocationCapability.capability == capability,
        LocationCapability.active.is_(True),
        FacilityLocation.active.is_(True),
        Facility.active.is_(True),
    ]
    if state:
        conditions.append(FacilityLocation.state == state.upper())

    rows = session.execute(
        select(Facility, FacilityLocation, Organization)
        .join(FacilityLocation, FacilityLocation.facility_id == Facility.id)
        .join(LocationCapability, LocationCapability.facility_location_id == FacilityLocation.id)
        .outerjoin(Organization, Organization.id == Facility.organization_id)
        .where(*conditions)
        .order_by(Facility.display_name, FacilityLocation.id)
        .limit(limit)
    ).all()

    results: list[SearchResult] = []
    for facility, location, organization in rows:
        location_text = (
            " · ".join(filter(None, [location.city, location.state, location.postal_code])) or None
        )
        results.append(
            SearchResult(
                entity_type="facility",
                entity_id=facility.id,
                title=facility.display_name,
                subtitle=location.city or "",
                location=location_text,
                score=70.0,
                match_reason="capability_match",
                matched_term=capability,
                metadata={
                    "capability": capability,
                    "facility_location_id": str(location.id),
                    "location_type": location.location_type,
                    "organization_name": organization.display_name if organization else None,
                    "organization_type": organization.organization_type if organization else None,
                    "region": location.region,
                },
            )
        )
    return results
