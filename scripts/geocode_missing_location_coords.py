"""Backfill ZIP-centroid coordinates for active locations that are missing them.

Some FacilityLocation rows (notably the 3 hospital-affiliated freestanding ERs ingested via
the hospital pipeline) are discoverable in the directory/search but carry no coordinates, so
they never render on the map. This backfills lat/lng from the SAME authoritative ZIP-centroid
source the app already uses for every non-hospital location (packages.geo.resolve_origin).

Honest by construction: ZIP-centroid coordinates are approximate (not rooftop) — identical to
how labs/urgent care/imaging/etc. are placed. Only rows with a usable postal_code + state and
NO existing coordinates are touched; existing coordinates are never overwritten.

Run: python -m scripts.geocode_missing_location_coords \
         [--capability freestanding_emergency_department] [--apply]   (default is dry-run)
"""

from __future__ import annotations

import argparse
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from packages.database import (
    FacilityLocation,
    LocationCapability,
    get_session,
)
from packages.geo import resolve_origin


def geocode(
    session: Session | None = None,
    *,
    capability: str | None = None,
    apply: bool = False,
) -> dict[str, int]:
    if session is None:
        session = next(get_session())
    result = {"eligible": 0, "geocoded": 0, "skipped_no_zip": 0, "skipped_geocode_failed": 0}

    stmt = select(FacilityLocation).where(
        FacilityLocation.active.is_(True),
        FacilityLocation.latitude.is_(None),
    )
    candidates = list(session.scalars(stmt))

    if capability is not None:
        allowed = set(
            session.scalars(
                select(LocationCapability.facility_location_id).where(
                    LocationCapability.capability == capability
                )
            )
        )
        candidates = [loc for loc in candidates if loc.id in allowed]

    for loc in candidates:
        result["eligible"] += 1
        if not loc.postal_code or not loc.state:
            result["skipped_no_zip"] += 1
            continue
        try:
            coords = resolve_origin(postal_code=loc.postal_code, state=loc.state)
        except Exception:
            coords = None
        if not coords:
            result["skipped_geocode_failed"] += 1
            continue
        loc.latitude = Decimal(str(coords[0]))
        loc.longitude = Decimal(str(coords[1]))
        result["geocoded"] += 1
        print(
            f"  geocoded {loc.location_name!r} ({loc.city},{loc.state} {loc.postal_code}) "
            f"-> {coords[0]},{coords[1]}"
        )

    if apply:
        session.commit()
    else:
        session.rollback()
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Geocode active locations missing coordinates")
    parser.add_argument("--capability", default=None, help="only this capability (else all)")
    parser.add_argument("--apply", action="store_true", help="commit (default dry-run)")
    args = parser.parse_args()
    result = geocode(capability=args.capability, apply=args.apply)
    prefix = "" if args.apply else "DRY-RUN "
    print(f"{prefix}GEOCODE_MISSING_COORDS={result}")


if __name__ == "__main__":
    main()
