"""Wikimedia Commons discovery + safe ingestion of facility imagery.

Only free licenses (CC0 / public domain / CC BY / CC BY-SA) pass the license
gate. Ingested rows are ``pending`` — a human must verify both the license and
that the photo depicts the correct facility before it is ever shown publicly
(see docs/FACILITY_MEDIA_POLICY.md).
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from packages.database import FacilityMedia
from packages.image_validation import ImageInfo, validate_image

COMMONS_API = "https://commons.wikimedia.org/w/api.php"
USER_AGENT = "Carevero-FacilityMedia/1.0 (healthcare price transparency; contact via app)"

# Machine-readable license codes (extmetadata.License.value) we accept as free.
_FREE_LICENSE_PREFIXES: tuple[str, ...] = (
    "cc0",
    "cc-by-sa",
    "cc-by",
    "pd",
    "public domain",
    "publicdomain",
)
_TAG_RE = re.compile(r"<[^>]+>")


@dataclass(frozen=True)
class MediaCandidate:
    title: str
    image_url: str
    description_url: str
    license_type: str | None
    license_url: str | None
    attribution_text: str | None
    copyright_owner: str | None
    width: int | None
    height: int | None
    mime_type: str | None
    is_free: bool


def _strip_html(value: str | None) -> str | None:
    if not value:
        return None
    text = _TAG_RE.sub("", value)
    return " ".join(text.split()).strip() or None


def _meta_value(meta: dict[str, object], key: str) -> str | None:
    entry = meta.get(key)
    value = entry.get("value") if isinstance(entry, dict) else None
    return value if isinstance(value, str) else None


def is_free_license(
    machine_code: str | None, short_name: str | None, copyrighted: str | None
) -> bool:
    """A license is free if it is an explicit CC0/PD/CC-BY(-SA), or the file is
    marked not copyrighted (public domain)."""
    if copyrighted is not None and copyrighted.strip().lower() == "false":
        return True
    for candidate in (machine_code, short_name):
        if not candidate:
            continue
        normalized = candidate.strip().lower()
        if any(normalized.startswith(prefix) for prefix in _FREE_LICENSE_PREFIXES):
            return True
    return False


def discover_wikimedia(http: httpx.Client, query: str, *, limit: int = 6) -> list[MediaCandidate]:
    """Search Wikimedia Commons (file namespace) for candidate imagery."""
    params = {
        "action": "query",
        "format": "json",
        "generator": "search",
        "gsrsearch": query,
        "gsrnamespace": "6",  # File:
        "gsrlimit": str(limit),
        "prop": "imageinfo",
        "iiprop": "url|size|mime|extmetadata",
        "iiurlwidth": "1280",
    }
    response = http.get(COMMONS_API, params=params)
    response.raise_for_status()
    payload = response.json()
    pages = (payload.get("query") or {}).get("pages") or {}
    candidates: list[MediaCandidate] = []
    for page in pages.values():
        info_list = page.get("imageinfo") or []
        if not info_list:
            continue
        info = info_list[0]
        meta = info.get("extmetadata") or {}
        license_code = _meta_value(meta, "License")
        short_name = _meta_value(meta, "LicenseShortName")
        copyrighted = _meta_value(meta, "Copyrighted")
        artist = _strip_html(_meta_value(meta, "Artist"))
        license_url = _meta_value(meta, "LicenseUrl")
        free = is_free_license(license_code, short_name, copyrighted)
        # Prefer a bounded thumbnail URL when available to cap file size.
        image_url = info.get("thumburl") or info.get("url")
        if not image_url:
            continue
        attribution = None
        if short_name:
            attribution = (
                f"{artist} / {short_name} via Wikimedia Commons"
                if artist
                else f"{short_name} via Wikimedia Commons"
            )
        elif artist:
            attribution = f"{artist} via Wikimedia Commons"
        candidates.append(
            MediaCandidate(
                title=str(page.get("title", "")),
                image_url=str(image_url),
                description_url=str(info.get("descriptionurl") or ""),
                license_type=short_name or license_code,
                license_url=license_url,
                attribution_text=attribution,
                copyright_owner=artist,
                width=info.get("thumbwidth") or info.get("width"),
                height=info.get("thumbheight") or info.get("height"),
                mime_type=info.get("mime"),
                is_free=free,
            )
        )
    return candidates


def download_and_validate(http: httpx.Client, url: str) -> tuple[bytes, ImageInfo]:
    """Download an image and validate its bytes. Raises on any problem."""
    response = http.get(url)
    response.raise_for_status()
    data = response.content
    return data, validate_image(data)


def upsert_pending_media(
    session: Session,
    *,
    facility_id: uuid.UUID,
    service_location_id: uuid.UUID | None,
    candidate: MediaCandidate,
    info: ImageInfo,
    cdn_url: str,
    source_type: str = "wikimedia",
    verified: bool = False,
    verified_by: str | None = None,
    review_notes: str | None = None,
) -> FacilityMedia:
    """Insert (or return an existing) facility_media row for this checksum.

    Idempotent per (facility, checksum). Defaults to ``pending``: publication
    requires an explicit human verification step.
    """
    existing = session.scalar(
        select(FacilityMedia).where(
            FacilityMedia.facility_id == facility_id,
            FacilityMedia.checksum_sha256 == info.checksum_sha256,
        )
    )
    if existing is not None:
        return existing
    media = FacilityMedia(
        facility_id=facility_id,
        service_location_id=service_location_id,
        media_type="photo",
        cdn_url=cdn_url,
        source_url=candidate.description_url or candidate.image_url,
        source_type=source_type,
        source_name="Wikimedia Commons",
        license_type=candidate.license_type,
        license_url=candidate.license_url,
        attribution_text=candidate.attribution_text,
        copyright_owner=candidate.copyright_owner,
        verification_status="verified" if verified else "pending",
        width=info.width,
        height=info.height,
        mime_type=info.mime_type,
        file_size=info.file_size,
        checksum_sha256=info.checksum_sha256,
        review_notes=review_notes,
        verified_by=verified_by if verified else None,
    )
    session.add(media)
    session.flush()
    return media
