"""Download from all active price sources that lack a source_file_id.

Accepts a state_code parameter for geographic scope (defaults to NH).
"""

import argparse
import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from collectors.hospital_prices.downloader import download_price_source
from packages.database import Facility, FacilityLocation, FacilityPriceSource, session_factory


def download_all_sources(
    session: Session, state_code: str = "NH", only_ccns: set[str] | None = None
) -> dict[str, int]:
    """Download all sources missing source_file_id for facilities in state.

    ``only_ccns`` optionally restricts to specific hospitals (by CMS CCN) so a wave can
    be bounded — e.g. to keep a large-MRF ingestion within the Cloud Run job timeout.
    """
    query = (
        select(Facility.id)
        .distinct()
        .join(FacilityLocation)
        .where(FacilityLocation.state == state_code.upper(), Facility.active.is_(True))
    )
    if only_ccns:
        query = query.where(Facility.cms_certification_number.in_(only_ccns))
    facility_ids = set(session.scalars(query))

    sources = session.scalars(
        select(FacilityPriceSource).where(
            FacilityPriceSource.active.is_(True),
            FacilityPriceSource.source_file_id.is_(None),
            FacilityPriceSource.facility_id.in_(facility_ids),
        )
    ).all()

    downloaded = 0
    skipped = 0
    failed = 0

    for source in sources:
        facility = session.get(Facility, source.facility_id)
        name = facility.display_name if facility else str(source.facility_id)
        try:
            result = download_price_source(session, source)
            if result.skipped_unchanged:
                skipped += 1
                print(f"  Skipped (unchanged): {name}")
            else:
                downloaded += 1
                print(f"  Downloaded: {name} ({result.size} bytes)")
        except Exception as exc:
            failed += 1
            print(f"  Failed: {name} — {type(exc).__name__}: {exc}")

    return {"downloaded": downloaded, "skipped": skipped, "failed": failed, "total": len(sources)}


def download_all_nh_sources(session: Session) -> dict[str, int]:
    """Backward-compatible alias."""
    return download_all_sources(session, "NH")


def main() -> None:
    parser = argparse.ArgumentParser(description="Download all price sources")
    parser.add_argument("--state", default="NH")
    args = parser.parse_args()
    with session_factory() as session:
        result = download_all_sources(session, args.state)
    print(f"\n=== Download All {args.state} Sources ===")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
