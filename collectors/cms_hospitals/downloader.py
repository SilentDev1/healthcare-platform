import hashlib
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import httpx

ALLOWED_CONTENT_TYPES = {
    "text/csv",
    "application/csv",
    "application/json",
    "text/plain",
    "application/octet-stream",
}


@dataclass(frozen=True)
class DownloadResult:
    path: Path
    checksum_sha256: str
    size: int
    etag: str | None
    last_modified: str | None
    downloaded_at: datetime
    content_type: str


def download_source(
    url: str, destination_dir: Path, max_bytes: int, timeout_seconds: float, retries: int
) -> DownloadResult:
    destination_dir.mkdir(parents=True, exist_ok=True)
    timeout = httpx.Timeout(timeout_seconds)
    last_error: Exception | None = None
    for attempt in range(retries + 1):
        try:
            with httpx.stream("GET", url, follow_redirects=True, timeout=timeout) as response:
                response.raise_for_status()
                content_type = response.headers.get("content-type", "").split(";", 1)[0].lower()
                if content_type not in ALLOWED_CONTENT_TYPES:
                    raise ValueError(f"unsupported content type: {content_type or 'missing'}")
                declared_size = int(response.headers.get("content-length", "0"))
                if declared_size > max_bytes:
                    raise ValueError(f"source exceeds {max_bytes} byte limit")
                suffix = ".json" if content_type == "application/json" else ".csv"
                path = destination_dir / f"cms-hospitals-{datetime.now(UTC):%Y%m%dT%H%M%SZ}{suffix}"
                digest = hashlib.sha256()
                size = 0
                with path.open("xb") as output:
                    for chunk in response.iter_bytes(64 * 1024):
                        size += len(chunk)
                        if size > max_bytes:
                            output.close()
                            path.unlink(missing_ok=True)
                            raise ValueError(f"source exceeds {max_bytes} byte limit")
                        digest.update(chunk)
                        output.write(chunk)
                return DownloadResult(
                    path=path,
                    checksum_sha256=digest.hexdigest(),
                    size=size,
                    etag=response.headers.get("etag"),
                    last_modified=response.headers.get("last-modified"),
                    downloaded_at=datetime.now(UTC),
                    content_type=content_type,
                )
        except (httpx.HTTPError, OSError) as exc:
            last_error = exc
            if attempt == retries:
                break
            time.sleep(min(2**attempt, 8))
    if last_error is not None:
        raise RuntimeError(f"CMS download failed after {retries + 1} attempts") from last_error
    raise RuntimeError("CMS download failed")
