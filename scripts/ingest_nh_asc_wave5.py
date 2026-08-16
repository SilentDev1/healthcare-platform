"""Wave 5 — NH ambulatory surgery centers (authoritative, verified ingestion).

Idempotent ingestion of VERIFIED NH ambulatory surgery centers (ASCs), each verified from an
authoritative source (the ASC's own official website / NH DHHS licensure). Each center is
modeled as a Facility + FacilityLocation under its Organization, with an `ambulatory_surgery`
capability and full provenance.

Coverage note (accuracy over coverage): this ships the ASCs whose street address + ZIP were
fully verified from an authoritative source. NH's complete ASC enumeration lives in the NH
DHHS Health Facilities licensed-facilities list; that document was not machine-fetchable at
ingest time (HTTP 403). Remaining licensed ASCs (e.g. Capital Orthopedic Surgery Center; the
Dartmouth-Hitchcock hospital-affiliated ASC in Manchester) are a fail-forward follow-up once
the authoritative roster is retrievable — never fabricate a location to inflate coverage.

Modeling notes:
- Only fully address-verified locations are ingested.
- Coordinates are ZIP-centroid approximations (packages.geo.resolve_origin) — honest.
- NO published price and NO per-procedure availability is asserted (needs a priced menu).

Run: python -m scripts.ingest_nh_asc_wave5 [--dry-run]
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
class VerifiedASC:
    organization: str
    display_name: str
    address: str
    city: str
    state: str
    postal_code: str
    phone: str
    website_url: str
    source_url: str


# Verified from each ASC's OFFICIAL website (2026-08-16).
VERIFIED_ASCS: tuple[VerifiedASC, ...] = (
    VerifiedASC("Bedford Ambulatory Surgical Center", "Bedford Ambulatory Surgical Center", "11 Washington Place", "Bedford", "NH", "03110", "(603) 622-3670", "https://bascnh.com/", "https://bascnh.com/"),
    VerifiedASC("Nashua Ambulatory Surgical Center", "Nashua Ambulatory Surgical Center", "15 Riverside Street", "Nashua", "NH", "03062", "(603) 882-0950", "https://nascnh.com/", "https://nascnh.com/about/"),
    VerifiedASC("Orthopaedic Surgery Center", "Orthopaedic Surgery Center — Concord", "116 Langley Parkway", "Concord", "NH", "03301", "(603) 228-7211", "https://www.copaosc.com/", "https://www.copaosc.com/locations"),
)


def _source_file(session: Session, source_url: str, name: str) -> SourceFile:
    existing = session.scalar(select(SourceFile).where(SourceFile.source_url == source_url))
    if existing is not None:
        return existing
    source = SourceFile(
        source_name=name,
        source_url=source_url,
        source_type="provider_website",
        storage_path=f"provenance/{hashlib.sha256(source_url.encode()).hexdigest()[:16]}",
        checksum_sha256=hashlib.sha256(source_url.encode()).hexdigest(),
        file_size=0,
        parser_version="wave5-nh-asc-manual",
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
        organization_type="ambulatory_surgery_center",
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
    for asc in VERIFIED_ASCS:
        source = _source_file(session, asc.source_url, f"{asc.organization} official website")
        org_before = session.scalar(
            select(Organization).where(Organization.canonical_name == asc.organization)
        )
        org = _organization(session, asc.organization, source)
        if org_before is None:
            created["organizations"] += 1

        facility = session.scalar(
            select(Facility).where(Facility.display_name == asc.display_name)
        )
        if facility is None:
            facility = Facility(
                legal_name=asc.display_name,
                display_name=asc.display_name,
                facility_type="Ambulatory Surgery Center",
                phone=asc.phone,
                website_url=asc.website_url,
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
            coords = resolve_origin(postal_code=asc.postal_code, state=asc.state)
        except Exception:
            coords = None
        location = session.scalar(
            select(FacilityLocation).where(
                FacilityLocation.facility_id == facility.id,
                FacilityLocation.address_line_1 == asc.address,
                FacilityLocation.postal_code == asc.postal_code,
            )
        )
        if location is None:
            location = FacilityLocation(
                facility_id=facility.id,
                location_name=asc.display_name,
                location_type="service_location",
                active=True,
                address_line_1=asc.address,
                city=asc.city,
                state=asc.state,
                postal_code=asc.postal_code,
                latitude=Decimal(str(coords[0])) if coords else None,
                longitude=Decimal(str(coords[1])) if coords else None,
            )
            session.add(location)
            session.flush()
            created["locations"] += 1

        capability = session.scalar(
            select(LocationCapability).where(
                LocationCapability.facility_location_id == location.id,
                LocationCapability.capability == "ambulatory_surgery",
            )
        )
        if capability is None:
            session.add(
                LocationCapability(
                    facility_location_id=location.id,
                    capability="ambulatory_surgery",
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
    parser = argparse.ArgumentParser(description="Ingest verified NH ambulatory surgery centers (Wave 5)")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    result = ingest(dry_run=args.dry_run)
    prefix = "DRY-RUN " if args.dry_run else ""
    print(f"{prefix}NH_ASC_WAVE5_INGESTED={result}")


if __name__ == "__main__":
    main()
