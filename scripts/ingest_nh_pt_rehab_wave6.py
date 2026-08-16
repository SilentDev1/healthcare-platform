"""Wave 6 — NH physical therapy + rehabilitation (authoritative, verified ingestion).

Idempotent ingestion of VERIFIED NH rehabilitation + physical-therapy locations from the
Northeast Rehabilitation Hospital Network OFFICIAL directory (northeastrehab.com/locations).
Northeast Rehab is a single authoritative org that operates BOTH acute inpatient
rehabilitation hospitals AND outpatient physical-therapy centers, so it cleanly exercises the
directive's "physical therapy + rehabilitation, kept distinct":

- Inpatient rehab hospitals  -> `rehabilitation` capability
- Outpatient PT centers      -> `physical_therapy` capability

`rehabilitation` and `physical_therapy` are DISTINCT capabilities and are never conflated.
Two addresses host BOTH a rehab hospital and a PT clinic (105 Corporate Dr, Portsmouth;
70 Butler St, Salem) — these are modeled as ONE physical location carrying BOTH capabilities,
NOT as duplicate rows (applying the Parkland-duplicate lesson: never create two location rows
for the same physical place).

Modeling notes (accuracy over coverage):
- Only fully address-verified locations from the official directory are ingested. This is one
  authoritative network, not an exhaustive census of all NH PT/rehab providers (a fragmented
  long tail). Other PT chains (e.g. ATI, Select) and independent clinics are a fail-forward
  follow-up once their official per-location addresses are retrievable — never fabricated.
- Coordinates are ZIP-centroid approximations (packages.geo.resolve_origin) — honest.
- NO published price and NO per-procedure availability is asserted.

Run: python -m scripts.ingest_nh_pt_rehab_wave6 [--dry-run]
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

_SRC = "https://www.northeastrehab.com/locations/"
_ORG = "Northeast Rehabilitation Hospital Network"


@dataclass(frozen=True)
class VerifiedRehab:
    display_name: str
    address: str
    city: str
    state: str
    postal_code: str
    phone: str
    capabilities: tuple[str, ...]  # DISTINCT: rehabilitation and/or physical_therapy


# Verified from northeastrehab.com/locations (2026-08-16). Same-address rehab+PT collapsed
# into one physical location carrying BOTH capabilities.
VERIFIED_REHAB: tuple[VerifiedRehab, ...] = (
    VerifiedRehab("Northeast Rehab Hospital — Nashua (SNHMC West)", "29 Northwest Boulevard", "Nashua", "NH", "03063", "(603) 689-2400", ("rehabilitation",)),
    VerifiedRehab("Northeast Rehab Hospital — Manchester", "1 Elliot Way, 7th Floor", "Manchester", "NH", "03103", "(603) 663-7700", ("rehabilitation",)),
    VerifiedRehab("Northeast Rehab — Portsmouth (Pease)", "105 Corporate Drive", "Portsmouth", "NH", "03801", "(603) 501-5500", ("rehabilitation", "physical_therapy")),
    VerifiedRehab("Northeast Rehab — Salem (Butler St)", "70 Butler Street", "Salem", "NH", "03079", "(603) 893-2900", ("rehabilitation", "physical_therapy")),
    VerifiedRehab("Northeast Rehab Physical Therapy — Plaistow", "4 Plaistow Road", "Plaistow", "NH", "03865", "(603) 382-6244", ("physical_therapy",)),
    VerifiedRehab("Northeast Rehab Physical Therapy — Salem (Stiles Rd)", "29 Stiles Road", "Salem", "NH", "03079", "(603) 893-2889", ("physical_therapy",)),
    VerifiedRehab("Northeast Rehab Physical Therapy — Windham", "125 Indian Rock Road, Suite 5", "Windham", "NH", "03087", "(603) 432-9662", ("physical_therapy",)),
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
        parser_version="wave6-nh-pt-rehab-manual",
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
        organization_type="rehabilitation",
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

    for rec in VERIFIED_REHAB:
        # facility_type reflects the primary capability at the location.
        facility_type = "Rehabilitation Hospital" if "rehabilitation" in rec.capabilities else "Physical Therapy Clinic"
        facility = session.scalar(select(Facility).where(Facility.display_name == rec.display_name))
        if facility is None:
            facility = Facility(
                legal_name=rec.display_name,
                display_name=rec.display_name,
                facility_type=facility_type,
                phone=rec.phone,
                website_url=_SRC,
                active=True,
                organization_id=org.id,
                source_file_id=source.id,
            )
            session.add(facility)
            session.flush()
            created["facilities"] += 1

        try:
            coords = resolve_origin(postal_code=rec.postal_code, state=rec.state)
        except Exception:
            coords = None
        location = session.scalar(
            select(FacilityLocation).where(
                FacilityLocation.facility_id == facility.id,
                FacilityLocation.address_line_1 == rec.address,
                FacilityLocation.postal_code == rec.postal_code,
            )
        )
        if location is None:
            location = FacilityLocation(
                facility_id=facility.id,
                location_name=rec.display_name,
                location_type="service_location",
                active=True,
                address_line_1=rec.address,
                city=rec.city,
                state=rec.state,
                postal_code=rec.postal_code,
                latitude=Decimal(str(coords[0])) if coords else None,
                longitude=Decimal(str(coords[1])) if coords else None,
            )
            session.add(location)
            session.flush()
            created["locations"] += 1

        # One physical location can carry BOTH rehabilitation and physical_therapy.
        for capability in rec.capabilities:
            existing_cap = session.scalar(
                select(LocationCapability).where(
                    LocationCapability.facility_location_id == location.id,
                    LocationCapability.capability == capability,
                )
            )
            if existing_cap is None:
                session.add(
                    LocationCapability(
                        facility_location_id=location.id,
                        capability=capability,
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
    parser = argparse.ArgumentParser(description="Ingest verified NH PT + rehabilitation (Wave 6)")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    result = ingest(dry_run=args.dry_run)
    prefix = "DRY-RUN " if args.dry_run else ""
    print(f"{prefix}NH_PT_REHAB_WAVE6_INGESTED={result}")


if __name__ == "__main__":
    main()
