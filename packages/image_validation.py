"""Dependency-free image validation for the facility-media pipeline.

Validates candidate hospital imagery WITHOUT Pillow (keeps the job image lean):
magic-byte MIME sniffing, header-based dimension parsing for JPEG/PNG/WebP, size
limits, an SVG/markup guard (no script-injection surface), and a SHA-256 checksum
for de-duplication and provenance. An image that fails validation must never
become a public primary; the web falls back to the neutral placeholder.
"""

from __future__ import annotations

import hashlib
import struct
from dataclasses import dataclass

ALLOWED_MIME_TYPES: frozenset[str] = frozenset({"image/jpeg", "image/png", "image/webp"})
DEFAULT_MIN_WIDTH = 320
DEFAULT_MIN_HEIGHT = 240
DEFAULT_MAX_FILE_SIZE = 8 * 1024 * 1024  # 8 MB
DEFAULT_MIN_FILE_SIZE = 2 * 1024  # 2 KB — reject tracking pixels / error stubs


class ImageValidationError(ValueError):
    """Raised when a candidate image is not safe/usable as facility media."""


@dataclass(frozen=True)
class ImageInfo:
    mime_type: str
    width: int | None
    height: int | None
    file_size: int
    checksum_sha256: str


def sniff_mime(data: bytes) -> str | None:
    if data[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None


def _looks_like_markup(data: bytes) -> bool:
    head = data[:512].lstrip().lower()
    return head.startswith(b"<") or b"<svg" in head or b"<?xml" in head


def _png_dimensions(data: bytes) -> tuple[int, int] | None:
    # IHDR is the first chunk: bytes 16..24 are width, height (big-endian uint32).
    if len(data) < 24 or data[12:16] != b"IHDR":
        return None
    width, height = struct.unpack(">II", data[16:24])
    return int(width), int(height)


def _jpeg_dimensions(data: bytes) -> tuple[int, int] | None:
    # Walk JPEG segments to the first Start-Of-Frame marker.
    index = 2
    length = len(data)
    while index + 9 < length:
        if data[index] != 0xFF:
            index += 1
            continue
        marker = data[index + 1]
        if 0xC0 <= marker <= 0xCF and marker not in (0xC4, 0xC8, 0xCC):
            height = struct.unpack(">H", data[index + 5 : index + 7])[0]
            width = struct.unpack(">H", data[index + 7 : index + 9])[0]
            return int(width), int(height)
        segment_length = struct.unpack(">H", data[index + 2 : index + 4])[0]
        index += 2 + segment_length
    return None


def _webp_dimensions(data: bytes) -> tuple[int, int] | None:
    fourcc = data[12:16]
    try:
        if fourcc == b"VP8X" and len(data) >= 30:
            w = 1 + int.from_bytes(data[24:27], "little")
            h = 1 + int.from_bytes(data[27:30], "little")
            return w, h
        if fourcc == b"VP8 " and len(data) >= 30:
            w = struct.unpack("<H", data[26:28])[0] & 0x3FFF
            h = struct.unpack("<H", data[28:30])[0] & 0x3FFF
            return int(w), int(h)
        if fourcc == b"VP8L" and len(data) >= 25:
            bits = int.from_bytes(data[21:25], "little")
            w = (bits & 0x3FFF) + 1
            h = ((bits >> 14) & 0x3FFF) + 1
            return int(w), int(h)
    except (struct.error, IndexError):
        return None
    return None


def dimensions(data: bytes, mime_type: str) -> tuple[int, int] | None:
    if mime_type == "image/png":
        return _png_dimensions(data)
    if mime_type == "image/jpeg":
        return _jpeg_dimensions(data)
    if mime_type == "image/webp":
        return _webp_dimensions(data)
    return None


def validate_image(
    data: bytes,
    *,
    min_width: int = DEFAULT_MIN_WIDTH,
    min_height: int = DEFAULT_MIN_HEIGHT,
    max_file_size: int = DEFAULT_MAX_FILE_SIZE,
    min_file_size: int = DEFAULT_MIN_FILE_SIZE,
    allowed_mime: frozenset[str] = ALLOWED_MIME_TYPES,
) -> ImageInfo:
    """Validate raw image bytes. Raises ImageValidationError on any failure."""
    size = len(data)
    if size < min_file_size:
        raise ImageValidationError(f"image too small ({size} bytes)")
    if size > max_file_size:
        raise ImageValidationError(f"image too large ({size} bytes)")
    if _looks_like_markup(data):
        raise ImageValidationError("payload looks like markup/SVG, not a raster image")
    mime = sniff_mime(data)
    if mime is None or mime not in allowed_mime:
        raise ImageValidationError(f"unsupported or unrecognized image type: {mime!r}")
    dims = dimensions(data, mime)
    width = height = None
    if dims is not None:
        width, height = dims
        if width < min_width or height < min_height:
            raise ImageValidationError(f"image below minimum resolution ({width}x{height})")
    checksum = hashlib.sha256(data).hexdigest()
    return ImageInfo(
        mime_type=mime,
        width=width,
        height=height,
        file_size=size,
        checksum_sha256=checksum,
    )
