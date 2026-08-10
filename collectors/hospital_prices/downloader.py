import gzip
import hashlib
import json
import logging
import re
import shutil
import time
import zipfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from urllib.parse import urlparse

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from collectors.hospital_prices.config import HospitalPriceSettings, hospital_price_settings
from packages.database import FacilityPriceSource, SourceFile
from packages.database.models import SourceStatus

logger = logging.getLogger(__name__)

ALLOWED_CONTENT_TYPES = (
    "text/csv",
    "application/json",
    "text/json",
    "application/zip",
    "application/gzip",
    "application/octet-stream",
    "text/plain",
    "application/xml",
    "text/xml",
    "application/fhir+json",
    "application/x-zip-compressed",
    "application/x-gzip",
    "application/vnd.ms-excel",
    "text/tab-separated-values",
)


@dataclass(frozen=True)
class DownloadedPriceFile:
    source_file_id: object
    path: Path
    checksum: str
    size: int
    detected_format: str
    skipped_unchanged: bool


def detect_container(path: Path) -> str:
    """Detect file format using magic bytes and content inspection."""
    with path.open("rb") as stream:
        magic = stream.read(8)
    # ZIP magic bytes
    if magic.startswith(b"PK\x03\x04"):
        return "zip"
    # GZIP magic bytes
    if magic.startswith(b"\x1f\x8b"):
        return "gzip"
    # XML detection (with optional BOM)
    content_start = magic
    # Strip BOM markers
    if content_start.startswith(b"\xef\xbb\xbf"):
        content_start = content_start[3:]
    elif content_start.startswith(b"\xff\xfe") or content_start.startswith(b"\xfe\xff"):
        content_start = content_start[2:]
    if content_start.lstrip().startswith(b"<?xml") or content_start.lstrip().startswith(b"<"):
        # Read more to confirm it's XML vs HTML
        with path.open("rb") as stream:
            head = stream.read(1024).lower()
        if b"<!doctype html" in head or b"<html" in head:
            return "html"
        return "xml"
    # JSON detection
    if magic[:1] in {b"{", b"["}:
        return "json"
    # Default to CSV
    return "csv"


def validate_downloaded_file(path: Path) -> tuple[bool, str]:
    """Pre-import validation of downloaded file.

    Returns (is_valid, reason). Invalid files should skip import.
    """
    size = path.stat().st_size
    if size == 0:
        return False, "empty_file"
    if size < 100:
        return False, "suspiciously_small"

    # Check for HTML error pages masquerading as data files
    with path.open("rb") as f:
        head = f.read(2048).lower()
    if (b"<!doctype html" in head or b"<html" in head) and (
        b"standard" not in head and b"charge" not in head
    ):
        return False, "html_error_page"

    # Check for redirect/login pages
    if b"<!doctype html" in head or b"<html" in head:
        if b"login" in head or b"sign in" in head or b"authenticate" in head:
            return False, "login_page"
        if b"meta http-equiv" in head and b"refresh" in head:
            return False, "redirect_page"

    # Check for obviously non-data binary content
    with path.open("rb") as f:
        sample = f.read(512)
    # If more than 30% null bytes, likely binary garbage
    null_count = sample.count(b"\x00")
    if null_count > len(sample) * 0.3 and not sample.startswith((b"PK", b"\x1f\x8b")):
        return False, "binary_content"

    return True, "ok"


def extract_mrf_link_from_html(path: Path) -> str | None:
    """If a downloaded file is HTML, try to extract an embedded MRF download link.

    Looks for iframe src, direct download links, or meta-refresh URLs
    pointing to MRF files.
    """
    try:
        with path.open("r", encoding="utf-8", errors="replace") as f:
            html = f.read(50_000).lower()
    except Exception:
        return None

    mrf_extensions = (".csv", ".json", ".zip", ".gz", ".xml")

    # Check iframe src
    for match in re.finditer(r'<iframe[^>]+src=["\']([^"\']+)["\']', html):
        url = match.group(1)
        if any(ext in url for ext in mrf_extensions):
            return url

    # Check direct download links
    for match in re.finditer(r'<a[^>]+href=["\']([^"\']+)["\']', html):
        url = match.group(1)
        url_lower = url.lower()
        if any(ext in url_lower for ext in mrf_extensions) and any(
            kw in url_lower
            for kw in ("charge", "price", "transparency", "mrf", "standard")
        ):
            return url

    # Check meta-refresh
    meta_match = re.search(
        r'<meta[^>]+http-equiv=["\']refresh["\'][^>]+url=([^"\';\s>]+)', html
    )
    if meta_match:
        url = meta_match.group(1)
        if any(ext in url.lower() for ext in mrf_extensions):
            return url

    return None


def _parse_content_disposition(header: str) -> str | None:
    """Extract filename from Content-Disposition header."""
    match = re.search(r'filename[*]?=["\']?([^"\';]+)', header, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return None


def safe_extract(
    path: Path, destination: Path, settings: HospitalPriceSettings = hospital_price_settings
) -> list[Path]:
    container = detect_container(path)
    destination.mkdir(parents=True, exist_ok=True)
    if container == "gzip":
        output = destination / path.stem
        expanded = 0
        with gzip.open(path, "rb") as source, output.open("wb") as target:
            while chunk := source.read(64 * 1024):
                expanded += len(chunk)
                if expanded > settings.hospital_price_max_expanded_bytes:
                    raise ValueError("gzip expanded size exceeds configured maximum")
                target.write(chunk)
        return [output]
    if container != "zip":
        return [path]
    outputs: list[Path] = []
    total = 0
    with zipfile.ZipFile(path) as archive:
        members = archive.infolist()
        if len(members) > settings.hospital_price_max_archive_files:
            raise ValueError("ZIP contains too many files")
        for member in members:
            member_path = PurePosixPath(member.filename)
            if member.is_dir():
                continue
            if member_path.is_absolute() or ".." in member_path.parts:
                raise ValueError("unsafe ZIP path")
            total += member.file_size
            if total > settings.hospital_price_max_expanded_bytes:
                raise ValueError("ZIP expanded size exceeds configured maximum")
            if member.compress_size and member.file_size / member.compress_size > 200:
                raise ValueError("ZIP compression ratio exceeds safety threshold")
            output = destination / member_path.name
            with archive.open(member) as source, output.open("wb") as target:
                while chunk := source.read(64 * 1024):
                    target.write(chunk)
            outputs.append(output)
    return outputs


def _archive_bytes(
    content: bytes, source_id: str, suffix: str, settings: HospitalPriceSettings
) -> Path:
    day = datetime.now(UTC).date().isoformat()
    directory = settings.hospital_price_raw_dir / source_id / day
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"original{suffix}"
    if path.exists():
        path = directory / f"original-{int(time.time() * 1000)}{suffix}"
    path.write_bytes(content)
    return path


def _archive_file(
    source: Path, source_id: str, suffix: str, settings: HospitalPriceSettings
) -> Path:
    day = datetime.now(UTC).date().isoformat()
    directory = settings.hospital_price_raw_dir / source_id / day
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"original{suffix}"
    if path.exists():
        path = directory / f"original-{int(time.time() * 1000)}{suffix}"
    shutil.move(str(source), path)
    return path


def _stream_checksum_and_size(path: Path, max_bytes: int) -> tuple[str, int]:
    """Compute SHA-256 and file size by streaming, bounded by max_bytes."""
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as f:
        while chunk := f.read(64 * 1024):
            size += len(chunk)
            if size > max_bytes:
                raise ValueError("source exceeds configured maximum")
            digest.update(chunk)
    return digest.hexdigest(), size


def _archive_stream(
    source_path: Path, source_id: str, suffix: str, settings: HospitalPriceSettings
) -> Path:
    """Archive a file by streaming copy (no full read into memory)."""
    day = datetime.now(UTC).date().isoformat()
    directory = settings.hospital_price_raw_dir / source_id / day
    directory.mkdir(parents=True, exist_ok=True)
    dest = directory / f"original{suffix}"
    if dest.exists():
        dest = directory / f"original-{int(time.time() * 1000)}{suffix}"
    shutil.copy2(str(source_path), dest)
    return dest


def register_local_file(
    session: Session,
    price_source: FacilityPriceSource,
    path: Path,
    settings: HospitalPriceSettings = hospital_price_settings,
) -> DownloadedPriceFile:
    checksum, file_size = _stream_checksum_and_size(path, settings.hospital_price_max_bytes)
    existing = session.scalar(
        select(SourceFile).where(
            SourceFile.source_type == "hospital_price_mrf",
            SourceFile.checksum_sha256 == checksum,
            SourceFile.parser_version == settings.hospital_price_parser_version,
        )
    )
    if existing:
        return DownloadedPriceFile(
            existing.id,
            Path(existing.storage_path),
            checksum,
            existing.file_size,
            detect_container(Path(existing.storage_path)),
            True,
        )
    archived = _archive_stream(
        path, str(price_source.id), path.suffix or ".dat", settings
    )

    detected = detect_container(archived)
    source = SourceFile(
        source_name=f"Hospital MRF: {price_source.id}",
        source_url=price_source.machine_readable_file_url,
        source_type="hospital_price_mrf",
        storage_path=str(archived),
        checksum_sha256=checksum,
        file_size=file_size,
        parser_version=settings.hospital_price_parser_version,
        status=SourceStatus.DOWNLOADED,
    )
    session.add(source)
    session.flush()
    price_source.source_file_id = source.id
    price_source.detected_format = detected
    price_source.last_successful_download_at = datetime.now(UTC)
    session.commit()
    return DownloadedPriceFile(source.id, archived, checksum, file_size, detected, False)


def _load_part_meta(meta_path: Path) -> tuple[int, str] | None:
    """Load partial download state from .part.meta file.

    Returns (bytes_downloaded, partial_hex_digest) or None.
    """
    if not meta_path.exists():
        return None
    try:
        data = json.loads(meta_path.read_text(encoding="utf-8"))
        return int(data["bytes_downloaded"]), str(data["partial_checksum"])
    except (json.JSONDecodeError, KeyError, ValueError):
        return None


def _save_part_meta(meta_path: Path, bytes_downloaded: int, partial_checksum: str) -> None:
    """Save partial download state for resume."""
    meta_path.write_text(
        json.dumps(
            {
                "bytes_downloaded": bytes_downloaded,
                "partial_checksum": partial_checksum,
                "timestamp": datetime.now(UTC).isoformat(),
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def _cleanup_part_files(*paths: Path) -> None:
    """Remove .part and .part.meta files."""
    for p in paths:
        if p.exists():
            p.unlink(missing_ok=True)


def download_price_source(
    session: Session,
    price_source: FacilityPriceSource,
    settings: HospitalPriceSettings = hospital_price_settings,
) -> DownloadedPriceFile:
    parsed = urlparse(price_source.machine_readable_file_url)
    if parsed.scheme != "https" and not price_source.machine_readable_file_url.startswith(
        "file://"
    ):
        raise ValueError("non-HTTPS source requires manual review")
    timeout = httpx.Timeout(
        settings.hospital_price_read_timeout_seconds,
        connect=settings.hospital_price_connection_timeout_seconds,
    )

    # Determine .part file path for atomic download
    suffix = Path(parsed.path).suffix.lower() or ".dat"
    day = datetime.now(UTC).date().isoformat()
    part_dir = settings.hospital_price_raw_dir / str(price_source.id) / day
    part_dir.mkdir(parents=True, exist_ok=True)
    part_path = part_dir / f"download{settings.hospital_price_part_file_suffix}"
    meta_path = Path(f"{part_path}.meta")

    error: Exception | None = None
    for attempt in range(settings.hospital_price_http_retries + 1):
        try:
            # Check for resumable partial download
            resume_bytes = 0
            digest = hashlib.sha256()
            request_headers: dict[str, str] = {
                "User-Agent": settings.hospital_price_user_agent,
            }
            saved = _load_part_meta(meta_path)
            if saved and part_path.exists():
                resume_bytes = saved[0]
                actual_part_size = part_path.stat().st_size
                if actual_part_size == resume_bytes:
                    # Rebuild digest from existing part file
                    with part_path.open("rb") as f:
                        while chunk := f.read(64 * 1024):
                            digest.update(chunk)
                    request_headers["Range"] = f"bytes={resume_bytes}-"
                    logger.info(
                        "resuming_download",
                        extra={
                            "source_id": str(price_source.id),
                            "resume_bytes": resume_bytes,
                        },
                    )
                else:
                    # Part file size mismatch — restart
                    _cleanup_part_files(part_path, meta_path)
                    resume_bytes = 0

            size = resume_bytes
            with (
                httpx.Client(
                    headers=request_headers,
                    timeout=timeout,
                    follow_redirects=True,
                    max_redirects=settings.hospital_price_max_redirects,
                ) as client,
                client.stream("GET", price_source.machine_readable_file_url) as response,
            ):
                # Server may ignore Range header — check response code
                if resume_bytes > 0 and response.status_code != 206:
                    # Server didn't support Range; restart from scratch
                    _cleanup_part_files(part_path, meta_path)
                    digest = hashlib.sha256()
                    size = 0
                    resume_bytes = 0

                response.raise_for_status()
                declared = int(response.headers.get("content-length", "0") or 0)
                total_expected = declared + resume_bytes
                if total_expected > settings.hospital_price_max_bytes:
                    raise ValueError("declared source size exceeds configured maximum")
                content_type = response.headers.get("content-type", "").split(";")[0].lower()
                if content_type and content_type not in ALLOWED_CONTENT_TYPES:
                    raise ValueError(f"unsupported content type: {content_type}")

                # Parse Content-Disposition for filename hints
                disposition = response.headers.get("content-disposition", "")
                if disposition:
                    _parse_content_disposition(disposition)

                mode = "ab" if resume_bytes > 0 else "wb"
                with part_path.open(mode) as f:
                    for chunk in response.iter_bytes(64 * 1024):
                        size += len(chunk)
                        if size > settings.hospital_price_max_bytes:
                            raise ValueError(
                                "streamed source size exceeds configured maximum"
                            )
                        digest.update(chunk)
                        f.write(chunk)
                resp_headers = response.headers

            # Save resume state in case of later failure
            _save_part_meta(meta_path, size, digest.hexdigest())

            checksum = digest.hexdigest()

            # Duplicate checksum detection
            existing = session.scalar(
                select(SourceFile).where(
                    SourceFile.source_type == "hospital_price_mrf",
                    SourceFile.checksum_sha256 == checksum,
                    SourceFile.parser_version == settings.hospital_price_parser_version,
                )
            )
            if existing:
                _cleanup_part_files(part_path, meta_path)
                return DownloadedPriceFile(
                    existing.id,
                    Path(existing.storage_path),
                    checksum,
                    existing.file_size,
                    detect_container(Path(existing.storage_path)),
                    True,
                )

            # Atomic rename: .part → final
            final_path = part_dir / f"original{suffix}"
            if final_path.exists():
                final_path = part_dir / f"original-{int(time.time() * 1000)}{suffix}"
            part_path.rename(final_path)
            _cleanup_part_files(meta_path)
            archived = final_path

            # Pre-import validation
            is_valid, reason = validate_downloaded_file(archived)
            if not is_valid:
                price_source.last_failed_download_at = datetime.now(UTC)
                session.commit()
                raise ValueError(f"downloaded file failed validation: {reason}")

            detected = detect_container(archived)
            source = SourceFile(
                source_name=f"Hospital MRF: {price_source.id}",
                source_url=price_source.machine_readable_file_url,
                source_type="hospital_price_mrf",
                storage_path=str(archived),
                checksum_sha256=checksum,
                etag=resp_headers.get("etag"),
                last_modified=resp_headers.get("last-modified"),
                file_size=size,
                parser_version=settings.hospital_price_parser_version,
                status=SourceStatus.DOWNLOADED,
            )
            session.add(source)
            session.flush()
            price_source.source_file_id = source.id
            price_source.detected_format = detected
            price_source.last_successful_download_at = datetime.now(UTC)
            metadata = {
                "source_url": price_source.machine_readable_file_url,
                "checksum_sha256": checksum,
                "size": size,
                "etag": resp_headers.get("etag"),
                "last_modified": resp_headers.get("last-modified"),
                "detected_format": detected,
                "downloaded_at": datetime.now(UTC).isoformat(),
            }
            (archived.parent / "metadata.json").write_text(
                json.dumps(metadata, indent=2), encoding="utf-8"
            )
            session.commit()
            return DownloadedPriceFile(source.id, archived, checksum, size, detected, False)
        except (httpx.HTTPError, ValueError) as exc:
            error = exc
            if attempt < settings.hospital_price_http_retries:
                time.sleep(0.25 * (2**attempt))
    price_source.last_failed_download_at = datetime.now(UTC)
    session.commit()
    raise RuntimeError(f"price source download failed: {error}")
