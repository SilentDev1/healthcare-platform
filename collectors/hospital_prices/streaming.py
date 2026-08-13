"""Stream rows straight out of a ZIP member without materializing the file.

Some authoritative hospital MRFs expand beyond the on-disk extraction cap
(`hospital_price_max_expanded_bytes`). Extracting them to the container's
in-memory filesystem would consume RAM proportional to the uncompressed size.

`ZipMemberSource` exposes the small subset of :class:`pathlib.Path` that the
parsers rely on (`open`, `stat`, `suffix`, `name`) while reading only the
member's compressed bytes on demand. Memory stays bounded to the parser's own
buffers regardless of how large the uncompressed member is — the durable path
for large NH files today and larger multi-state files later.

`prepare_source_inputs` keeps the existing on-disk extraction for archives that
fit under the cap (fast, unchanged behavior) and only switches to streaming for
oversized-but-bounded archives, preserving every zip-bomb / unsafe-path guard.
"""

from __future__ import annotations

import io
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import IO, Any

from collectors.hospital_prices.config import HospitalPriceSettings, hospital_price_settings
from collectors.hospital_prices.downloader import detect_container, safe_extract

# Members whose uncompressed size divided by compressed size exceeds this ratio
# are treated as potential zip bombs (mirrors the guard in ``safe_extract``).
_MAX_COMPRESSION_RATIO = 200


@dataclass(frozen=True)
class _StatResult:
    """Minimal stand-in for ``os.stat_result`` — parsers only read ``st_size``."""

    st_size: int


class ZipMemberSource:
    """Re-openable, read-only view of one member inside a ZIP archive.

    Duck-types the ``pathlib.Path`` surface the parsers use so a member can be
    parsed in place. Each :meth:`open` reads only that member's compressed bytes,
    decompressing on demand, so peak memory is independent of the uncompressed
    size.
    """

    def __init__(self, archive_path: Path, member_name: str, uncompressed_size: int) -> None:
        self._archive_path = archive_path
        self._member_name = member_name
        self._uncompressed_size = uncompressed_size
        self.name = PurePosixPath(member_name).name
        self.suffix = PurePosixPath(member_name).suffix.lower()

    def stat(self) -> _StatResult:
        return _StatResult(st_size=self._uncompressed_size)

    def open(
        self,
        mode: str = "r",
        buffering: int = -1,
        encoding: str | None = None,
        errors: str | None = None,
        newline: str | None = None,
    ) -> IO[Any]:
        """Return a fresh stream over the member that also closes the archive.

        The returned object is a genuine file-like stream (its own context
        manager); closing it — via ``with`` or ``.close()`` — also releases the
        underlying archive handle so no descriptors leak across repeated opens.
        """
        archive = zipfile.ZipFile(self._archive_path)
        try:
            member = archive.open(self._member_name)
        except Exception:
            archive.close()
            raise
        stream: IO[Any]
        if "b" in mode:
            stream = member
        else:
            stream = io.TextIOWrapper(
                member, encoding=encoding or "utf-8", errors=errors, newline=newline
            )
        original_close = stream.close

        def _close_all() -> None:
            try:
                original_close()  # closes the member (and the text wrapper's buffer)
            finally:
                archive.close()

        stream.close = _close_all  # type: ignore[method-assign]
        return stream


# A parseable input is either an on-disk path (small archives / plain files) or a
# streamed ZIP member (oversized-but-bounded archives).
SourceInput = Path | ZipMemberSource


def prepare_source_inputs(
    archive_path: Path,
    destination: Path,
    settings: HospitalPriceSettings = hospital_price_settings,
) -> list[SourceInput]:
    """Return parseable inputs, extracting to disk or streaming as appropriate.

    - Non-ZIP containers and ZIP archives whose total uncompressed size fits
      under ``hospital_price_max_expanded_bytes`` defer to ``safe_extract`` (the
      existing, well-tested on-disk path) — no behavior change.
    - ZIP archives that expand past that cap but stay within
      ``hospital_price_max_streaming_expanded_bytes`` are read member-by-member
      via :class:`ZipMemberSource`, never materializing the expanded file.
    - Anything larger, too many members, an unsafe path, or a bomb-ratio member
      raises — identical safety posture to ``safe_extract``.
    """
    if detect_container(archive_path) != "zip":
        return list(safe_extract(archive_path, destination, settings))

    with zipfile.ZipFile(archive_path) as archive:
        members = [member for member in archive.infolist() if not member.is_dir()]
        if len(members) > settings.hospital_price_max_archive_files:
            raise ValueError("ZIP contains too many files")
        total = 0
        for member in members:
            member_path = PurePosixPath(member.filename)
            if member_path.is_absolute() or ".." in member_path.parts:
                raise ValueError("unsafe ZIP path")
            if (
                member.compress_size
                and member.file_size / member.compress_size > _MAX_COMPRESSION_RATIO
            ):
                raise ValueError("ZIP compression ratio exceeds safety threshold")
            total += member.file_size

    # Fits under the on-disk cap: keep the fast, proven extraction path.
    if total <= settings.hospital_price_max_expanded_bytes:
        return list(safe_extract(archive_path, destination, settings))

    if total > settings.hospital_price_max_streaming_expanded_bytes:
        raise ValueError("ZIP expanded size exceeds streaming maximum")

    return [ZipMemberSource(archive_path, member.filename, member.file_size) for member in members]
