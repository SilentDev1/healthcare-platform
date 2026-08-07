import gzip
import hashlib
import json
import shutil
import tempfile
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

ALLOWED_CONTENT_TYPES = (
    "text/csv",
    "application/json",
    "text/json",
    "application/zip",
    "application/gzip",
    "application/octet-stream",
    "text/plain",
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
    with path.open("rb") as stream:
        magic = stream.read(4)
    if magic.startswith(b"PK\x03\x04"):
        return "zip"
    if magic.startswith(b"\x1f\x8b"):
        return "gzip"
    if magic[:1] in {b"{", b"["}:
        return "json"
    return "csv"


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


def register_local_file(
    session: Session,
    price_source: FacilityPriceSource,
    path: Path,
    settings: HospitalPriceSettings = hospital_price_settings,
) -> DownloadedPriceFile:
    content = path.read_bytes()
    if len(content) > settings.hospital_price_max_bytes:
        raise ValueError("source exceeds configured maximum")
    checksum = hashlib.sha256(content).hexdigest()
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
    archived = _archive_bytes(content, str(price_source.id), path.suffix or ".dat", settings)
    detected = detect_container(archived)
    source = SourceFile(
        source_name=f"Hospital MRF: {price_source.id}",
        source_url=price_source.machine_readable_file_url,
        source_type="hospital_price_mrf",
        storage_path=str(archived),
        checksum_sha256=checksum,
        file_size=len(content),
        parser_version=settings.hospital_price_parser_version,
        status=SourceStatus.DOWNLOADED,
    )
    session.add(source)
    session.flush()
    price_source.source_file_id = source.id
    price_source.detected_format = detected
    price_source.last_successful_download_at = datetime.now(UTC)
    session.commit()
    return DownloadedPriceFile(source.id, archived, checksum, len(content), detected, False)


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
    error: Exception | None = None
    for attempt in range(settings.hospital_price_http_retries + 1):
        try:
            digest = hashlib.sha256()
            size = 0
            with tempfile.NamedTemporaryFile(delete=False) as temporary:
                temporary_path = Path(temporary.name)
                with (
                    httpx.Client(
                        headers={"User-Agent": settings.hospital_price_user_agent},
                        timeout=timeout,
                        follow_redirects=True,
                        max_redirects=settings.hospital_price_max_redirects,
                    ) as client,
                    client.stream("GET", price_source.machine_readable_file_url) as response,
                ):
                    response.raise_for_status()
                    declared = int(response.headers.get("content-length", "0") or 0)
                    if declared > settings.hospital_price_max_bytes:
                        raise ValueError("declared source size exceeds configured maximum")
                    content_type = response.headers.get("content-type", "").split(";")[0].lower()
                    if content_type and content_type not in ALLOWED_CONTENT_TYPES:
                        raise ValueError(f"unsupported content type: {content_type}")
                    for chunk in response.iter_bytes(64 * 1024):
                        size += len(chunk)
                        if size > settings.hospital_price_max_bytes:
                            raise ValueError("streamed source size exceeds configured maximum")
                        digest.update(chunk)
                        temporary.write(chunk)
                    headers = response.headers
            checksum = digest.hexdigest()
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
            suffix = Path(parsed.path).suffix.lower() or ".dat"
            archived = _archive_file(temporary_path, str(price_source.id), suffix, settings)
            detected = detect_container(archived)
            source = SourceFile(
                source_name=f"Hospital MRF: {price_source.id}",
                source_url=price_source.machine_readable_file_url,
                source_type="hospital_price_mrf",
                storage_path=str(archived),
                checksum_sha256=checksum,
                etag=headers.get("etag"),
                last_modified=headers.get("last-modified"),
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
                "etag": headers.get("etag"),
                "last_modified": headers.get("last-modified"),
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
