"""Regression detector: duplicate PHYSICAL FacilityLocation rows under one facility.

A "duplicate physical location" is 2+ FacilityLocation rows (active OR inactive) belonging to
the SAME facility that share the same normalized physical address (address_line_1 + city +
state + postal_code). The provider-neutral backfill (migration 0014) created one such pair for
Parkland Medical Center (Derry) — an active priced campus with no coordinates plus an inactive
geocoded twin — which is exactly what this detector guards against recurring.

Exit code is non-zero when duplicates are found, so it can gate CI / post-backfill jobs.

Run: python -m scripts.detect_duplicate_locations
"""

from __future__ import annotations

import re
import sys
from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session

from packages.database import Facility, FacilityLocation, get_session


def normalize_address(value: str | None) -> str:
    if not value:
        return ""
    s = value.lower().strip()
    s = re.sub(r"[.,#]", " ", s)
    s = re.sub(r"\bstreet\b", "st", s)
    s = re.sub(r"\bdrive\b", "dr", s)
    s = re.sub(r"\broad\b", "rd", s)
    s = re.sub(r"\bavenue\b", "ave", s)
    s = re.sub(r"\bsuite\b", "ste", s)
    s = re.sub(r"\bunit\b", "ste", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def _key(loc: FacilityLocation) -> tuple[str, str, str, str, str]:
    return (
        str(loc.facility_id),
        normalize_address(loc.address_line_1),
        (loc.city or "").strip().upper(),
        (loc.state or "").strip().upper(),
        (loc.postal_code or "").strip(),
    )


def find_duplicate_physical_locations(session: Session) -> list[dict[str, object]]:
    """Return one entry per facility+address that has more than one location row."""
    groups: dict[tuple[str, str, str, str, str], list[FacilityLocation]] = defaultdict(list)
    for loc in session.scalars(select(FacilityLocation)):
        key = _key(loc)
        if not key[1]:  # skip rows with no address to normalize (cannot prove sameness)
            continue
        groups[key].append(loc)

    duplicates: list[dict[str, object]] = []
    for key, locs in groups.items():
        if len(locs) < 2:
            continue
        facility = session.get(Facility, locs[0].facility_id)
        duplicates.append(
            {
                "facility": facility.display_name if facility else key[0],
                "normalized_address": key[1],
                "city": key[2],
                "postal_code": key[4],
                "location_ids": [str(loc.id) for loc in locs],
                "active_flags": [loc.active for loc in locs],
            }
        )
    return duplicates


def main() -> None:
    session = next(get_session())
    dups = find_duplicate_physical_locations(session)
    if not dups:
        print("DUPLICATE_PHYSICAL_LOCATIONS=0 OK")
        return
    print(f"DUPLICATE_PHYSICAL_LOCATIONS={len(dups)} FAIL")
    for d in dups:
        print(
            f"  {d['facility']} | {d['normalized_address']} {d['city']} {d['postal_code']} "
            f"| locs={d['location_ids']} active={d['active_flags']}"
        )
    sys.exit(1)


if __name__ == "__main__":
    main()
