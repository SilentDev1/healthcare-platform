"""Wave 1 — NH independent laboratories (authoritative, verified ingestion).

Idempotent ingestion of VERIFIED NH independent-lab locations sourced from the providers'
OFFICIAL location directories (Quest: locations.questdiagnostics.com; Labcorp:
locations.labcorp.com). Each physical patient service center is modeled as a Facility +
FacilityLocation under its Organization, with a `laboratory` capability and full
provenance.

Accuracy over coverage (per directive):
- Only locations with a verified street address from the official directory are ingested.
- Coordinates are ZIP-centroid approximations (packages.geo.resolve_origin) — honest,
  same source the app uses for distance; NOT rooftop-verified.
- NO published price is asserted (price_available stays false — a valid, expected state).
- NO per-procedure service availability is asserted here: the official directory verifies
  the LOCATION and that it is a laboratory, but not a per-location canonical test menu.
  Procedure-level availability is a follow-up requiring an authoritative per-location test
  menu; assigning canonical procedures without that would be an assumption, not evidence.

Run: python -m scripts.ingest_nh_labs_wave1 [--dry-run]
"""

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


@dataclass(frozen=True)
class VerifiedLab:
    organization: str
    organization_type: str
    display_name: str
    address: str
    city: str
    state: str
    postal_code: str
    phone: str
    website_url: str
    source_url: str


# Verified from each provider's OFFICIAL location directory (2026-08-16).
VERIFIED_LABS: tuple[VerifiedLab, ...] = (
    VerifiedLab(
        organization="Quest Diagnostics",
        organization_type="independent_lab",
        display_name="Quest Diagnostics — Nashua",
        address="300 Main St, Suite 301B",
        city="Nashua",
        state="NH",
        postal_code="03060",
        phone="(603) 578-0323",
        website_url="https://locations.questdiagnostics.com/nh/nashua/300-main-st",
        source_url="https://locations.questdiagnostics.com/nh/nashua/300-main-st",
    ),
    VerifiedLab(
        organization="Quest Diagnostics",
        organization_type="independent_lab",
        display_name="Quest Diagnostics — Manchester",
        address="195 McGregor Street",
        city="Manchester",
        state="NH",
        postal_code="03102",
        phone="(603) 626-1249",
        website_url="https://www.questdiagnostics.com/locations/detail.html/EWA/03102/75/1",
        source_url="https://locations.questdiagnostics.com/nh",
    ),
    VerifiedLab(
        organization="Laboratory Corporation of America",
        organization_type="independent_lab",
        display_name="Labcorp — Bedford",
        address="101 Riverway Place",
        city="Bedford",
        state="NH",
        postal_code="03110",
        phone="(603) 622-2357",
        website_url="https://locations.labcorp.com/nh/bedford/7037/",
        source_url="https://locations.labcorp.com/nh/bedford/7037/",
    ),
)


def _source_file(session: Session, source_url: str, name: str) -> SourceFile:
    existing = session.scalar(select(SourceFile).where(SourceFile.source_url == source_url))
    if existing is not None:
        return existing
    source = SourceFile(
        source_name=name,
        source_url=source_url,
        source_type="provider_directory",
        storage_path=f"provenance/{hashlib.sha256(source_url.encode()).hexdigest()[:16]}",
        checksum_sha256=hashlib.sha256(source_url.encode()).hexdigest(),
        file_size=0,
        parser_version="wave1-nh-labs-manual",
        status=SourceStatus.COMPLETED,
    )
    session.add(source)
    session.flush()
    return source


def _organization(session: Session, name: str, org_type: str, source: SourceFile) -> Organization:
    existing = session.scalar(select(Organization).where(Organization.canonical_name == name))
    if existing is not None:
        return existing
    org = Organization(
        canonical_name=name,
        display_name=name,
        organization_type=org_type,
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
    for lab in VERIFIED_LABS:
        source = _source_file(session, lab.source_url, f"{lab.organization} location directory")
        org_before = session.scalar(
            select(Organization).where(Organization.canonical_name == lab.organization)
        )
        org = _organization(session, lab.organization, lab.organization_type, source)
        if org_before is None:
            created["organizations"] += 1

        facility = session.scalar(select(Facility).where(Facility.display_name == lab.display_name))
        if facility is None:
            facility = Facility(
                legal_name=lab.display_name,
                display_name=lab.display_name,
                facility_type="Independent Laboratory",
                phone=lab.phone,
                website_url=lab.website_url,
                active=True,
                organization_id=org.id,
                source_file_id=source.id,
            )
            session.add(facility)
            session.flush()
            created["facilities"] += 1

        coords = resolve_origin(postal_code=lab.postal_code, state=lab.state)
        location = session.scalar(
            select(FacilityLocation).where(
                FacilityLocation.facility_id == facility.id,
                FacilityLocation.address_line_1 == lab.address,
                FacilityLocation.postal_code == lab.postal_code,
            )
        )
        if location is None:
            location = FacilityLocation(
                facility_id=facility.id,
                location_name=lab.display_name,
                location_type="service_location",
                active=True,
                address_line_1=lab.address,
                city=lab.city,
                state=lab.state,
                postal_code=lab.postal_code,
                latitude=Decimal(str(coords[0])) if coords else None,
                longitude=Decimal(str(coords[1])) if coords else None,
            )
            session.add(location)
            session.flush()
            created["locations"] += 1

        capability = session.scalar(
            select(LocationCapability).where(
                LocationCapability.facility_location_id == location.id,
                LocationCapability.capability == "laboratory",
            )
        )
        if capability is None:
            session.add(
                LocationCapability(
                    facility_location_id=location.id,
                    capability="laboratory",
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
    parser = argparse.ArgumentParser(description="Ingest verified NH independent labs (Wave 1)")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    result = ingest(dry_run=args.dry_run)
    prefix = "DRY-RUN " if args.dry_run else ""
    print(f"{prefix}NH_LABS_WAVE1_INGESTED={result}")


if __name__ == "__main__":
    main()
