"""Facility-media: image validation, license gating, and selection precedence."""

from __future__ import annotations

import struct
import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from collectors.facility_media.pipeline import is_free_license
from packages.database import Base, Facility, FacilityLocation, FacilityMedia
from packages.image_validation import ImageValidationError, validate_image
from packages.runtime import RuntimeSettings
from services.api.app.facility_media import (
    media_fields,
    pick_media,
    resolve_facility_media,
)

_SETTINGS = RuntimeSettings(facility_media_public_base_url="https://cdn.test/media")


def _png(width: int, height: int) -> bytes:
    header = b"\x89PNG\r\n\x1a\n" + struct.pack(">I", 13) + b"IHDR"
    header += struct.pack(">II", width, height) + b"\x08\x02\x00\x00\x00"
    return header + b"\x00" * 4096  # pad above the min-size floor


def _jpeg(width: int, height: int) -> bytes:
    body = b"\xff\xd8" + b"\xff\xc0\x00\x11\x08"
    body += struct.pack(">H", height) + struct.pack(">H", width)
    return body + b"\x00" * 4096


# --- validation ------------------------------------------------------------


def test_validate_png_and_jpeg_dimensions() -> None:
    png = validate_image(_png(400, 300))
    assert png.mime_type == "image/png"
    assert (png.width, png.height) == (400, 300)
    assert len(png.checksum_sha256) == 64
    jpeg = validate_image(_jpeg(640, 480))
    assert jpeg.mime_type == "image/jpeg"
    assert (jpeg.width, jpeg.height) == (640, 480)


def test_validate_rejects_svg_and_markup() -> None:
    with pytest.raises(ImageValidationError):
        validate_image(b"<svg xmlns='...'>" + b" " * 4096)
    with pytest.raises(ImageValidationError):
        validate_image(b"<!DOCTYPE html>" + b" " * 4096)


def test_validate_rejects_tiny_and_low_resolution() -> None:
    with pytest.raises(ImageValidationError):
        validate_image(b"\x89PNG\r\n\x1a\n")  # too small
    with pytest.raises(ImageValidationError):
        validate_image(_png(100, 80))  # below min resolution


def test_validate_rejects_unknown_type() -> None:
    with pytest.raises(ImageValidationError):
        validate_image(b"NOTIMAGE" + b"\x00" * 4096)


# --- license gate ----------------------------------------------------------


def test_is_free_license() -> None:
    assert is_free_license("cc-by-sa-4.0", "CC BY-SA 4.0", "True")
    assert is_free_license("cc0", "CC0", None)
    assert is_free_license(None, None, "False")  # public domain (not copyrighted)
    assert not is_free_license("all rights reserved", "© Owner", "True")
    assert not is_free_license(None, None, None)


# --- selection precedence --------------------------------------------------

_engine = create_engine(
    "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
)
_Session = sessionmaker(bind=_engine, expire_on_commit=False)


def _seed() -> tuple[uuid.UUID, uuid.UUID]:
    Base.metadata.drop_all(_engine)
    Base.metadata.create_all(_engine)
    facility_id = uuid.uuid4()
    location_id = uuid.uuid4()
    with _Session.begin() as session:
        session.add(Facility(id=facility_id, legal_name="Test", display_name="Test Hospital"))
        session.add(
            FacilityLocation(
                id=location_id,
                facility_id=facility_id,
                address_line_1="1 Rd",
                city="Keene",
                state="NH",
                postal_code="03431",
            )
        )
    return facility_id, location_id


def _add_media(session: Session, **kwargs: object) -> FacilityMedia:
    media = FacilityMedia(source_type="wikimedia", **kwargs)
    session.add(media)
    session.flush()
    return media


def test_only_verified_media_is_selected() -> None:
    facility_id, _ = _seed()
    with _Session.begin() as session:
        _add_media(
            session,
            facility_id=facility_id,
            cdn_url="https://cdn.test/pending.jpg",
            verification_status="pending",
        )
    with _Session() as session:
        resolved = resolve_facility_media(session, [facility_id], _SETTINGS)
    assert pick_media(resolved, facility_id, None) is None  # pending is never shown


def test_location_photo_preferred_then_facility_then_fallback() -> None:
    facility_id, location_id = _seed()
    other_location = uuid.uuid4()
    with _Session.begin() as session:
        _add_media(
            session,
            facility_id=facility_id,
            service_location_id=None,
            cdn_url="https://cdn.test/facility.jpg",
            verification_status="verified",
        )
        _add_media(
            session,
            facility_id=facility_id,
            service_location_id=location_id,
            cdn_url="https://cdn.test/location.jpg",
            verification_status="verified",
        )
    with _Session() as session:
        resolved = resolve_facility_media(session, [facility_id], _SETTINGS)
    # Exact location wins.
    exact = pick_media(resolved, facility_id, location_id)
    assert exact is not None and exact.image_url == "https://cdn.test/location.jpg"
    # A different location with no exact photo falls back to the facility photo.
    other = pick_media(resolved, facility_id, other_location)
    assert other is not None and other.image_url == "https://cdn.test/facility.jpg"


def test_storage_key_builds_public_url_and_fields() -> None:
    facility_id, _ = _seed()
    with _Session.begin() as session:
        _add_media(
            session,
            facility_id=facility_id,
            storage_key="facility-media/x.jpg",
            verification_status="verified",
            attribution_text="Author / CC BY-SA 4.0 via Wikimedia Commons",
            source_name="Wikimedia Commons",
        )
    with _Session() as session:
        resolved = resolve_facility_media(session, [facility_id], _SETTINGS)
    picked = pick_media(resolved, facility_id, None)
    assert picked is not None
    assert picked.image_url == "https://cdn.test/media/facility-media/x.jpg"
    fields = media_fields(picked)
    assert fields["image_url"] == "https://cdn.test/media/facility-media/x.jpg"
    assert fields["image_attribution"] == "Author / CC BY-SA 4.0 via Wikimedia Commons"
    assert fields["image_source"] == "Wikimedia Commons"
    assert media_fields(None)["image_url"] is None
