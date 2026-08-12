"""Deterministic, state-neutral facility-image selection for the consumer API.

Only ``verified`` media is ever eligible to be shown publicly. For a given
(facility, service_location) the precedence is:

    verified photo for the exact service location
    -> verified facility-level photo (service_location_id IS NULL)
    -> None (the web renders the neutral Carevero placeholder)

The web NEVER shows a photo for the wrong physical building: a facility-level
photo is only used when no exact-location photo exists, and unrelated stock
photography is never ingested (see docs/FACILITY_MEDIA_POLICY.md).

Selection is done with a single batched query over the requested facilities to
avoid N+1 lookups on the results/comparison pages.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from packages.database import FacilityMedia
from packages.runtime import RuntimeSettings

_VERIFIED = "verified"


@dataclass(frozen=True)
class ResolvedMedia:
    """A publish-ready image reference for one facility/location context."""

    image_url: str
    alt_text: str | None
    attribution_text: str | None
    source_name: str | None
    source_type: str
    license_type: str | None


def _image_url(media: FacilityMedia, settings: RuntimeSettings) -> str | None:
    """Prefer a Carevero-controlled asset; fall back to an approved remote ref."""
    if media.cdn_url:
        return media.cdn_url
    if media.storage_key and settings.facility_media_public_base_url:
        base = settings.facility_media_public_base_url.rstrip("/")
        return f"{base}/{media.storage_key.lstrip('/')}"
    if media.source_url:
        return media.source_url
    return None


def _rank(media: FacilityMedia) -> tuple[int, int, str]:
    """Primary first, then explicit display order, then a stable id tiebreak."""
    return (0 if media.is_primary else 1, media.display_order, str(media.id))


def _to_resolved(media: FacilityMedia, settings: RuntimeSettings) -> ResolvedMedia | None:
    url = _image_url(media, settings)
    if not url:
        return None
    return ResolvedMedia(
        image_url=url,
        alt_text=media.alt_text,
        attribution_text=media.attribution_text,
        source_name=media.source_name,
        source_type=media.source_type,
        license_type=media.license_type,
    )


def resolve_facility_media(
    session: Session,
    facility_ids: list[uuid.UUID],
    settings: RuntimeSettings,
) -> dict[tuple[uuid.UUID, uuid.UUID | None], ResolvedMedia]:
    """Resolve verified imagery for a batch of facilities.

    Returns a map keyed by ``(facility_id, service_location_id)`` where the
    ``service_location_id`` key is:
      * a location id  -> the best verified photo for THAT exact location, and
      * ``None``       -> the best verified facility-level photo.

    Callers look up the exact-location key first and fall back to the ``None``
    key, matching the documented precedence. Facilities with no verified media
    simply have no entries (the web then renders the placeholder).
    """
    if not facility_ids:
        return {}
    rows = list(
        session.scalars(
            select(FacilityMedia).where(
                FacilityMedia.facility_id.in_(facility_ids),
                FacilityMedia.verification_status == _VERIFIED,
            )
        )
    )
    # Group candidates by their exact key, then pick the best per key.
    grouped: dict[tuple[uuid.UUID, uuid.UUID | None], list[FacilityMedia]] = {}
    for media in rows:
        key = (media.facility_id, media.service_location_id)
        grouped.setdefault(key, []).append(media)

    resolved: dict[tuple[uuid.UUID, uuid.UUID | None], ResolvedMedia] = {}
    for key, candidates in grouped.items():
        for media in sorted(candidates, key=_rank):
            best = _to_resolved(media, settings)
            if best is not None:
                resolved[key] = best
                break
    return resolved


def pick_media(
    resolved: dict[tuple[uuid.UUID, uuid.UUID | None], ResolvedMedia],
    facility_id: uuid.UUID,
    location_id: uuid.UUID | None,
) -> ResolvedMedia | None:
    """Apply exact-location-then-facility precedence for one context."""
    if location_id is not None:
        exact = resolved.get((facility_id, location_id))
        if exact is not None:
            return exact
    return resolved.get((facility_id, None))


def media_fields(media: ResolvedMedia | None) -> dict[str, str | None]:
    """Flatten a resolved image into the API's ``image_*`` response fields."""
    if media is None:
        return {
            "image_url": None,
            "image_alt": None,
            "image_attribution": None,
            "image_source": None,
        }
    return {
        "image_url": media.image_url,
        "image_alt": media.alt_text,
        "image_attribution": media.attribution_text,
        "image_source": media.source_name,
    }
