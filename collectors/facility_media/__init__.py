"""State-neutral facility-media discovery + ingestion pipeline.

discover -> validate license -> download -> validate bytes -> record candidate
(as ``pending``) -> human review -> ``verified``. Discovery NEVER auto-publishes.
"""

from collectors.facility_media.pipeline import (
    MediaCandidate,
    discover_wikimedia,
    download_and_validate,
    is_free_license,
    upsert_pending_media,
)

__all__ = [
    "MediaCandidate",
    "discover_wikimedia",
    "download_and_validate",
    "is_free_license",
    "upsert_pending_media",
]
