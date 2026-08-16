"""Wave 3 — NH emergency departments (capability-only, authoritative, no duplicate facilities).

NH's emergency departments are HOSPITAL-BASED — there is no freestanding/independent ED
model in New Hampshire (unlike TX/CO). So this wave creates NO new facilities. It adds an
`emergency_department` capability to the existing hospital LOCATIONS that authoritatively
operate a 24/7 general emergency department, based on the CMS facility-type designation
already on each facility:

- **Critical Access Hospitals** — 42 CFR 485.618 requires a CAH to "provide emergency care
  services 24 hours a day, 7 days a week" as a condition of its CAH designation. Every CAH
  therefore has an ED.
- **Acute Care Hospitals** — NH's short-term general acute-care hospitals all operate 24/7
  emergency departments (CMS Hospital General Information "Emergency Services = Yes").
- **Psychiatric hospitals** (New Hampshire Hospital, Hampstead Hospital) — do NOT operate a
  general emergency department and are EXCLUDED. Asserting an ER there would be unsafe.

`emergency_department` is a DISTINCT capability from `urgent_care`; the two are never
conflated. This is additive and reversible (new LocationCapability rows only); it does not
create facilities, does not touch pricing, and does not modify the audited hospital pipeline.

Run: python -m scripts.ingest_nh_emergency_departments_wave3 [--dry-run]
"""

from __future__ import annotations

import argparse
import hashlib

from sqlalchemy import select
from sqlalchemy.orm import Session

from packages.database import (
    Facility,
    FacilityLocation,
    LocationCapability,
    SourceFile,
    get_session,
)
from packages.database.models import SourceStatus

# CMS facility types that authoritatively operate a 24/7 general emergency department.
ED_FACILITY_TYPES = frozenset({"Acute Care Hospitals", "Critical Access Hospitals"})
# Documented, deliberate exclusion — no general ED at a psychiatric hospital.
EXCLUDED_FACILITY_TYPES = frozenset({"Psychiatric"})

_SOURCE_URL = "https://www.ecfr.gov/current/title-42/section-485.618"  # CAH 24/7 ED requirement
_SOURCE_NAME = (
    "CMS facility-type designation: Acute Care & Critical Access hospitals operate 24/7 EDs "
    "(42 CFR 485.618 for CAH); psychiatric hospitals excluded"
)


def _source_file(session: Session) -> SourceFile:
    existing = session.scalar(select(SourceFile).where(SourceFile.source_url == _SOURCE_URL))
    if existing is not None:
        return existing
    source = SourceFile(
        source_name=_SOURCE_NAME,
        source_url=_SOURCE_URL,
        source_type="regulatory_designation",
        storage_path=f"provenance/{hashlib.sha256(_SOURCE_URL.encode()).hexdigest()[:16]}",
        checksum_sha256=hashlib.sha256(_SOURCE_URL.encode()).hexdigest(),
        file_size=0,
        parser_version="wave3-nh-ed-cms-designation",
        status=SourceStatus.COMPLETED,
    )
    session.add(source)
    session.flush()
    return source


def ingest(
    session: Session | None = None, *, dry_run: bool = False, verbose: bool = False
) -> dict[str, int]:
    if session is None:
        session = next(get_session())
    source = _source_file(session)
    result = {"capabilities_added": 0, "facilities_with_ed": 0, "excluded_psychiatric": 0}
    audit: list[str] = []

    # Only consider locations that already hold the `hospital` capability — the ED capability
    # is layered onto the existing hospital location, never onto a non-hospital location.
    hospital_location_ids = set(
        session.scalars(
            select(LocationCapability.facility_location_id).where(
                LocationCapability.capability == "hospital"
            )
        )
    )

    for location in session.scalars(
        select(FacilityLocation).where(FacilityLocation.id.in_(hospital_location_ids))
    ):
        facility = session.get(Facility, location.facility_id)
        if facility is None:
            continue
        if facility.facility_type in EXCLUDED_FACILITY_TYPES:
            result["excluded_psychiatric"] += 1
            continue
        if facility.facility_type not in ED_FACILITY_TYPES:
            # Unknown type — do NOT assert an ED without an authoritative basis.
            continue

        result["facilities_with_ed"] += 1
        if verbose:
            audit.append(
                f"  ED-> {facility.display_name} [{facility.facility_type}] "
                f"| loc='{location.location_name}' type={location.location_type} "
                f"city={location.city}"
            )
        existing = session.scalar(
            select(LocationCapability).where(
                LocationCapability.facility_location_id == location.id,
                LocationCapability.capability == "emergency_department",
            )
        )
        if existing is None:
            session.add(
                LocationCapability(
                    facility_location_id=location.id,
                    capability="emergency_department",
                    active=True,
                    evidence_source_id=source.id,
                )
            )
            result["capabilities_added"] += 1

    if verbose:
        for line in sorted(audit):
            print(line)
    if dry_run:
        session.rollback()
    else:
        session.commit()
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Add ED capability to NH hospitals (Wave 3)")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--verbose", action="store_true", help="print each affected location")
    args = parser.parse_args()
    result = ingest(dry_run=args.dry_run, verbose=args.verbose)
    prefix = "DRY-RUN " if args.dry_run else ""
    print(f"{prefix}NH_EMERGENCY_DEPARTMENTS_WAVE3={result}")


if __name__ == "__main__":
    main()
