"""Wave 4 — NH independent imaging centers (authoritative, verified ingestion).

Idempotent ingestion of VERIFIED NH independent diagnostic-imaging locations sourced from
each provider's OFFICIAL location directory (Derry Imaging: derryimaging.com/locations;
Shields: shields.com/locations). Each physical imaging center is modeled as a Facility +
FacilityLocation under its Organization, with an `imaging` capability and full provenance.

Modeling notes (per directive):
- Only locations with a verified street address from the official directory are ingested.
- Coordinates are ZIP-centroid approximations (packages.geo.resolve_origin) — honest,
  same source the app uses for distance; NOT rooftop-verified.
- NO published price is asserted (price_available stays false). NOTE: Derry Imaging is a
  price-transparency leader ("40-70% less than hospitals") — a FUTURE wave could ingest its
  published cash prices from an authoritative machine-readable source and attach real
  LocationServiceAvailability + price records. Until then, price-not-available is the honest,
  expected state (never $0, never fabricated).
- NO per-procedure service availability is asserted here (needs a per-location priced menu).

Run: python -m scripts.ingest_nh_imaging_wave4 [--dry-run]
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
class VerifiedImaging:
    organization: str
    display_name: str
    address: str
    city: str
    state: str
    postal_code: str
    phone: str
    website_url: str
    source_url: str


_DERRY = "https://www.derryimaging.com/derry-imaging-2/locations/"
_SHIELDS = "https://shields.com/locations/shields-mri-at-portsmouth/"

# Verified from each provider's OFFICIAL location directory (2026-08-16).
VERIFIED_IMAGING: tuple[VerifiedImaging, ...] = (
    # --- Derry Imaging (derryimaging.com/locations) ---
    VerifiedImaging("Derry Imaging", "Derry Imaging — Derry", "6 Tsienneto Road", "Derry", "NH", "03038", "(603) 537-1363", "https://www.derryimaging.com/", _DERRY),
    VerifiedImaging("Derry Imaging", "Derry Imaging — Bedford", "160 South River Road, Suite 2100", "Bedford", "NH", "03110", "(603) 537-1363", "https://www.derryimaging.com/", _DERRY),
    VerifiedImaging("Derry Imaging", "Derry Imaging — Concord", "81 Hall Street", "Concord", "NH", "03301", "(603) 537-1363", "https://www.derryimaging.com/", _DERRY),
    VerifiedImaging("Derry Imaging", "Derry Imaging — Dover", "15 Durham Road", "Dover", "NH", "03820", "(603) 537-1350", "https://www.derryimaging.com/", _DERRY),
    VerifiedImaging("Derry Imaging", "Derry Imaging — Londonderry", "50 Michels Way", "Londonderry", "NH", "03053", "(603) 537-1363", "https://www.derryimaging.com/", _DERRY),
    VerifiedImaging("Derry Imaging", "Derry Imaging — Raymond", "6 Old Fremont Road, Suite 104", "Raymond", "NH", "03077", "(603) 537-1363", "https://www.derryimaging.com/", _DERRY),
    VerifiedImaging("Derry Imaging", "Derry Imaging — Windham", "49 Range Road, Suite 103", "Windham", "NH", "03087", "(603) 537-1363", "https://www.derryimaging.com/", _DERRY),
    # --- Shields Health Care Group (shields.com/locations) ---
    VerifiedImaging("Shields Health Care Group", "Shields MRI — Portsmouth", "1900 Lafayette Road", "Portsmouth", "NH", "03801", "(800) 258-4674", "https://shields.com/locations/shields-mri-at-portsmouth/", _SHIELDS),
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
        parser_version="wave4-nh-imaging-manual",
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
        organization_type="imaging_center",
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
    for center in VERIFIED_IMAGING:
        source = _source_file(session, center.source_url, f"{center.organization} location directory")
        org_before = session.scalar(
            select(Organization).where(Organization.canonical_name == center.organization)
        )
        org = _organization(session, center.organization, source)
        if org_before is None:
            created["organizations"] += 1

        facility = session.scalar(
            select(Facility).where(Facility.display_name == center.display_name)
        )
        if facility is None:
            facility = Facility(
                legal_name=center.display_name,
                display_name=center.display_name,
                facility_type="Imaging Center",
                phone=center.phone,
                website_url=center.website_url,
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
            coords = resolve_origin(postal_code=center.postal_code, state=center.state)
        except Exception:
            coords = None
        location = session.scalar(
            select(FacilityLocation).where(
                FacilityLocation.facility_id == facility.id,
                FacilityLocation.address_line_1 == center.address,
                FacilityLocation.postal_code == center.postal_code,
            )
        )
        if location is None:
            location = FacilityLocation(
                facility_id=facility.id,
                location_name=center.display_name,
                location_type="service_location",
                active=True,
                address_line_1=center.address,
                city=center.city,
                state=center.state,
                postal_code=center.postal_code,
                latitude=Decimal(str(coords[0])) if coords else None,
                longitude=Decimal(str(coords[1])) if coords else None,
            )
            session.add(location)
            session.flush()
            created["locations"] += 1

        capability = session.scalar(
            select(LocationCapability).where(
                LocationCapability.facility_location_id == location.id,
                LocationCapability.capability == "imaging",
            )
        )
        if capability is None:
            session.add(
                LocationCapability(
                    facility_location_id=location.id,
                    capability="imaging",
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
    parser = argparse.ArgumentParser(description="Ingest verified NH imaging centers (Wave 4)")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    result = ingest(dry_run=args.dry_run)
    prefix = "DRY-RUN " if args.dry_run else ""
    print(f"{prefix}NH_IMAGING_WAVE4_INGESTED={result}")


if __name__ == "__main__":
    main()
