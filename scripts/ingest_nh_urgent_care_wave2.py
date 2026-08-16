"""Wave 2 — NH urgent care (authoritative, verified ingestion).

Idempotent ingestion of VERIFIED NH urgent-care locations sourced from the providers'
OFFICIAL location directories (ConvenientMD: convenientmd.com/locations; ClearChoiceMD:
ccmdcenters.com/locations/new-hampshire-urgent-care). Each physical walk-in clinic is
modeled as a Facility + FacilityLocation under its Organization, with an `urgent_care`
capability and full provenance.

Modeling notes (per directive):
- `urgent_care` is a DISTINCT capability from `emergency_department`; these clinics are
  NOT emergency departments and are never conflated with hospital ERs.
- Only locations with a verified street address from the official directory are ingested.
- Coordinates are ZIP-centroid approximations (packages.geo.resolve_origin) — honest,
  same source the app uses for distance; NOT rooftop-verified.
- NO published price is asserted (price_available stays false — a valid, expected state).
- NO per-procedure service availability is asserted here: the official directory verifies
  the LOCATION and that it is an urgent-care clinic, but not a per-location priced service
  menu. Procedure-level availability/pricing is a follow-up requiring an authoritative
  per-location source; asserting it now would be an assumption, not evidence.

Run: python -m scripts.ingest_nh_urgent_care_wave2 [--dry-run]
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


@dataclass(frozen=True)
class VerifiedUrgentCare:
    organization: str
    display_name: str
    address: str
    city: str
    state: str
    postal_code: str
    phone: str
    website_url: str
    source_url: str


_CONVENIENTMD = "https://www.convenientmd.com/locations/"
_CCMD = "https://ccmdcenters.com/locations/new-hampshire-urgent-care"

# Verified from each provider's OFFICIAL location directory (2026-08-16).
VERIFIED_URGENT_CARE: tuple[VerifiedUrgentCare, ...] = (
    # --- ConvenientMD (convenientmd.com/locations) ---
    VerifiedUrgentCare("ConvenientMD", "ConvenientMD — Bedford", "3 Nashua Road", "Bedford", "NH", "03110", "(603) 472-6700", "https://www.convenientmd.com/locations/", _CONVENIENTMD),
    VerifiedUrgentCare("ConvenientMD", "ConvenientMD — Concord", "8 Loudon Road", "Concord", "NH", "03301", "(603) 226-9000", "https://www.convenientmd.com/locations/", _CONVENIENTMD),
    VerifiedUrgentCare("ConvenientMD", "ConvenientMD — Dover", "14 Webb Place", "Dover", "NH", "03820", "(603) 742-7900", "https://www.convenientmd.com/locations/", _CONVENIENTMD),
    VerifiedUrgentCare("ConvenientMD", "ConvenientMD — Stratham", "1 Portsmouth Avenue", "Stratham", "NH", "03885", "(603) 772-3600", "https://www.convenientmd.com/locations/", _CONVENIENTMD),
    VerifiedUrgentCare("ConvenientMD", "ConvenientMD — Keene", "351 Winchester Street", "Keene", "NH", "03431", "(603) 352-3406", "https://www.convenientmd.com/locations/", _CONVENIENTMD),
    VerifiedUrgentCare("ConvenientMD", "ConvenientMD — Merrimack", "2 Dobson Way", "Merrimack", "NH", "03054", "(603) 471-6069", "https://www.convenientmd.com/locations/", _CONVENIENTMD),
    VerifiedUrgentCare("ConvenientMD", "ConvenientMD — Nashua", "565 Amherst Street", "Nashua", "NH", "03063", "(603) 578-3347", "https://www.convenientmd.com/locations/", _CONVENIENTMD),
    VerifiedUrgentCare("ConvenientMD", "ConvenientMD — Portsmouth", "599 Lafayette Road, Suite 13", "Portsmouth", "NH", "03801", "(603) 942-7900", "https://www.convenientmd.com/locations/", _CONVENIENTMD),
    VerifiedUrgentCare("ConvenientMD", "ConvenientMD — Windham", "1 Sharma Way", "Windham", "NH", "03087", "(603) 890-6330", "https://www.convenientmd.com/locations/", _CONVENIENTMD),
    VerifiedUrgentCare("ConvenientMD", "ConvenientMD — Belmont", "77 Daniel Webster Hwy", "Belmont", "NH", "03220", "(603) 737-0550", "https://www.convenientmd.com/locations/", _CONVENIENTMD),
    VerifiedUrgentCare("ConvenientMD", "ConvenientMD — Littleton", "551 Meadow Street", "Littleton", "NH", "03561", "(603) 761-3660", "https://www.convenientmd.com/locations/", _CONVENIENTMD),
    VerifiedUrgentCare("ConvenientMD", "ConvenientMD — Londonderry", "42 Nashua Road", "Londonderry", "NH", "03053", "(603) 413-6800", "https://www.convenientmd.com/locations/", _CONVENIENTMD),
    VerifiedUrgentCare("ConvenientMD", "ConvenientMD — Manchester", "738 Hooksett Road", "Manchester", "NH", "03104", "(603) 384-3900", "https://www.convenientmd.com/locations/", _CONVENIENTMD),
    VerifiedUrgentCare("ConvenientMD", "ConvenientMD — Plaistow", "49 Plaistow Road", "Plaistow", "NH", "03865", "(603) 371-3229", "https://www.convenientmd.com/locations/", _CONVENIENTMD),
    VerifiedUrgentCare("ConvenientMD", "ConvenientMD — West Lebanon", "1 Interchange Drive, Unit 2", "West Lebanon", "NH", "03784", "(603) 709-0410", "https://www.convenientmd.com/locations/", _CONVENIENTMD),
    # --- ClearChoiceMD (ccmdcenters.com/locations/new-hampshire-urgent-care) ---
    VerifiedUrgentCare("ClearChoiceMD", "ClearChoiceMD — Alton", "24 Homestead Place", "Alton", "NH", "03809", "(603) 822-4713", "https://ccmdcenters.com/locations/alton-nh", _CCMD),
    VerifiedUrgentCare("ClearChoiceMD", "ClearChoiceMD — Epping", "1 Beehive Drive", "Epping", "NH", "03042", "(603) 734-9202", "https://ccmdcenters.com/locations/epping-nh", _CCMD),
    VerifiedUrgentCare("ClearChoiceMD", "ClearChoiceMD — Gilford", "9 Old Lake Shore Road", "Gilford", "NH", "03249", "(603) 556-4661", "https://ccmdcenters.com/locations/gilford-nh", _CCMD),
    VerifiedUrgentCare("ClearChoiceMD", "ClearChoiceMD — Goffstown", "558 Mast Road", "Goffstown", "NH", "03045", "(603) 232-1790", "https://ccmdcenters.com/locations/goffstown-nh", _CCMD),
    VerifiedUrgentCare("ClearChoiceMD", "ClearChoiceMD — Hooksett", "7 Cinemagic Way", "Hooksett", "NH", "03106", "(603) 782-5112", "https://ccmdcenters.com/locations/hooksett-nh", _CCMD),
    VerifiedUrgentCare("ClearChoiceMD", "ClearChoiceMD — Lebanon", "410 Miracle Mile", "Lebanon", "NH", "03766", "(603) 276-3261", "https://ccmdcenters.com/locations/lebanon-nh", _CCMD),
    VerifiedUrgentCare("ClearChoiceMD", "ClearChoiceMD — Nashua", "300 Main Street, Suite 406", "Nashua", "NH", "03060", "(603) 810-7470", "https://ccmdcenters.com/locations/nashua-nh", _CCMD),
    VerifiedUrgentCare("ClearChoiceMD", "ClearChoiceMD — Plaistow", "127 Plaistow Road", "Plaistow", "NH", "03865", "(603) 797-9289", "https://ccmdcenters.com/locations/plaistow-nh", _CCMD),
    VerifiedUrgentCare("ClearChoiceMD", "ClearChoiceMD — Rochester", "77 South Main Street", "Rochester", "NH", "03867", "(603) 509-9400", "https://ccmdcenters.com/locations/rochester-nh", _CCMD),
    VerifiedUrgentCare("ClearChoiceMD", "ClearChoiceMD — Seabrook", "636 Lafayette Road", "Seabrook", "NH", "03874", "(603) 457-7830", "https://ccmdcenters.com/locations/seabrook-nh", _CCMD),
    VerifiedUrgentCare("ClearChoiceMD", "ClearChoiceMD — Tilton", "75 Laconia Road", "Tilton", "NH", "03276", "(603) 729-0050", "https://ccmdcenters.com/locations/tilton-nh", _CCMD),
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
        parser_version="wave2-nh-urgent-care-manual",
        status=SourceStatus.COMPLETED,
    )
    session.add(source)
    session.flush()
    return source


def _organization(session: Session, name: str, source: SourceFile) -> Organization:
    existing = session.scalar(select(Organization).where(Organization.canonical_name == name))
    if existing is not None:
        return existing
    org = Organization(
        canonical_name=name,
        display_name=name,
        organization_type="urgent_care",
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
    for clinic in VERIFIED_URGENT_CARE:
        source = _source_file(session, clinic.source_url, f"{clinic.organization} location directory")
        org_before = session.scalar(
            select(Organization).where(Organization.canonical_name == clinic.organization)
        )
        org = _organization(session, clinic.organization, source)
        if org_before is None:
            created["organizations"] += 1

        facility = session.scalar(
            select(Facility).where(Facility.display_name == clinic.display_name)
        )
        if facility is None:
            facility = Facility(
                legal_name=clinic.display_name,
                display_name=clinic.display_name,
                facility_type="Urgent Care",
                phone=clinic.phone,
                website_url=clinic.website_url,
                active=True,
                organization_id=org.id,
                source_file_id=source.id,
            )
            session.add(facility)
            session.flush()
            created["facilities"] += 1

        # Coordinates are an optional enrichment (map pins); a geocode failure must not
        # abort ingestion of the verified location itself.
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
                LocationCapability.capability == "urgent_care",
            )
        )
        if capability is None:
            session.add(
                LocationCapability(
                    facility_location_id=location.id,
                    capability="urgent_care",
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
    parser = argparse.ArgumentParser(description="Ingest verified NH urgent care (Wave 2)")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    result = ingest(dry_run=args.dry_run)
    prefix = "DRY-RUN " if args.dry_run else ""
    print(f"{prefix}NH_URGENT_CARE_WAVE2_INGESTED={result}")


if __name__ == "__main__":
    main()
