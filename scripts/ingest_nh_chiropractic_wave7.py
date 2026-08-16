"""Wave 7 — NH chiropractic (authoritative, verified ingestion).

Idempotent ingestion of VERIFIED NH chiropractic locations sourced from the operator's
OFFICIAL directory (The Joint Chiropractic NH group: thejointnh.com). Each clinic is modeled
as a Facility + FacilityLocation under its Organization, with a `chiropractic` capability and
full provenance.

Modeling notes (accuracy over coverage):
- Chiropractic is the most fragmented provider type in NH (largely solo/small practices).
  This ships one authoritative multi-location operator with verified addresses, NOT an
  exhaustive census. Independent chiropractors are a fail-forward follow-up once authoritative
  per-location addresses are retrievable — never fabricated.
- Coordinates are ZIP-centroid approximations (packages.geo.resolve_origin) — honest.
- NO published price is asserted (price_available stays false). NOTE: The Joint uses a
  transparent membership/cash model — a future wave could ingest published cash prices from an
  authoritative source. Until then, price-not-available is the honest, expected state.
- NO per-procedure service availability is asserted here.

Run: python -m scripts.ingest_nh_chiropractic_wave7 [--dry-run]
"""
# ruff: noqa: E501  -- verified location records are kept one-per-line for auditability

from __future__ import annotations

import argparse
import hashlib
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from packages.database import (
    Facility,
    FacilityLocation,
    LocationCapability,
    Organization,
    SourceFile,
    get_session,
)
from packages.database.models import SourceStatus
from packages.geo import resolve_origin

_SRC = "https://thejointnh.com/"
_ORG = "The Joint Chiropractic"


@dataclass(frozen=True)
class VerifiedChiro:
    display_name: str
    address: str
    city: str
    state: str
    postal_code: str
    phone: str


# Verified from thejointnh.com (2026-08-16).
VERIFIED_CHIRO: tuple[VerifiedChiro, ...] = (
    VerifiedChiro("The Joint Chiropractic — Nashua", "219 Daniel Webster Highway, C2", "Nashua", "NH", "03060", "(855) 603-0055"),
    VerifiedChiro("The Joint Chiropractic — Manchester", "655 South Willow Street, Suite 102", "Manchester", "NH", "03103", "(603) 244-3672"),
    VerifiedChiro("The Joint Chiropractic — Salem", "236 North Broadway", "Salem", "NH", "03079", "(603) 873-4356"),
)


def _source_file(session: Session) -> SourceFile:
    existing = session.scalar(select(SourceFile).where(SourceFile.source_url == _SRC))
    if existing is not None:
        return existing
    source = SourceFile(
        source_name=f"{_ORG} location directory",
        source_url=_SRC,
        source_type="provider_directory",
        storage_path=f"provenance/{hashlib.sha256(_SRC.encode()).hexdigest()[:16]}",
        checksum_sha256=hashlib.sha256(_SRC.encode()).hexdigest(),
        file_size=0,
        parser_version="wave7-nh-chiropractic-manual",
        status=SourceStatus.COMPLETED,
    )
    session.add(source)
    session.flush()
    return source


def _organization(session: Session, source: SourceFile) -> Organization:
    existing = session.scalar(select(Organization).where(Organization.canonical_name == _ORG))
    if existing is not None:
        return existing
    org = Organization(
        canonical_name=_ORG,
        display_name=_ORG,
        organization_type="chiropractic",
        active=True,
        source_file_id=source.id,
    )
    session.add(org)
    session.flush()
    return org


def ingest(session: Session | None = None, *, dry_run: bool = False) -> dict[str, int]:
    if session is None:
        session = next(get_session())
    created = {"organizations": 0, "facilities": 0, "locations": 0, "capabilities": 0}
    source = _source_file(session)
    org_before = session.scalar(select(Organization).where(Organization.canonical_name == _ORG))
    org = _organization(session, source)
    if org_before is None:
        created["organizations"] += 1

    for clinic in VERIFIED_CHIRO:
        facility = session.scalar(select(Facility).where(Facility.display_name == clinic.display_name))
        if facility is None:
            facility = Facility(
                legal_name=clinic.display_name,
                display_name=clinic.display_name,
                facility_type="Chiropractic Clinic",
                phone=clinic.phone,
                website_url=_SRC,
                active=True,
                organization_id=org.id,
                source_file_id=source.id,
            )
            session.add(facility)
            session.flush()
            created["facilities"] += 1

        try:
            coords = resolve_origin(postal_code=clinic.postal_code, state=clinic.state)
        except Exception:
            coords = None
        location = session.scalar(
            select(FacilityLocation).where(
                FacilityLocation.facility_id == facility.id,
                FacilityLocation.address_line_1 == clinic.address,
                FacilityLocation.postal_code == clinic.postal_code,
            )
        )
        if location is None:
            location = FacilityLocation(
                facility_id=facility.id,
                location_name=clinic.display_name,
                location_type="service_location",
                active=True,
                address_line_1=clinic.address,
                city=clinic.city,
                state=clinic.state,
                postal_code=clinic.postal_code,
                latitude=Decimal(str(coords[0])) if coords else None,
                longitude=Decimal(str(coords[1])) if coords else None,
            )
            session.add(location)
            session.flush()
            created["locations"] += 1

        capability = session.scalar(
            select(LocationCapability).where(
                LocationCapability.facility_location_id == location.id,
                LocationCapability.capability == "chiropractic",
            )
        )
        if capability is None:
            session.add(
                LocationCapability(
                    facility_location_id=location.id,
                    capability="chiropractic",
                    active=True,
                    evidence_source_id=source.id,
                )
            )
            created["capabilities"] += 1

    if dry_run:
        session.rollback()
    else:
        session.commit()
    return created


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest verified NH chiropractic (Wave 7)")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    result = ingest(dry_run=args.dry_run)
    prefix = "DRY-RUN " if args.dry_run else ""
    print(f"{prefix}NH_CHIROPRACTIC_WAVE7_INGESTED={result}")


if __name__ == "__main__":
    main()
