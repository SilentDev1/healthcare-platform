"""Wave 8 — NH provider-roster completeness (authoritative, verified, dedup-by-location).

Ingests the verified additional NH locations in data/nh_roster_expansion.json (labs, imaging,
ambulatory surgery, urgent care, physical therapy) discovered in a 2026-08-16 authoritative
research sweep. Every record carries a per-location official source URL; nothing is fabricated.

Key modeling rules (per directive):
- DEDUP BY PHYSICAL LOCATION. Records are grouped by (organization, normalized address, city,
  state, ZIP); a single physical site under one organization becomes ONE FacilityLocation
  carrying the UNION of its capabilities (e.g. Wentworth-Douglass Lee = urgent_care +
  physical_therapy at 65 Calef Highway). Never two rows for the same physical place.
- Organizations are reused by canonical_name — the 21 new Quest/Labcorp draw stations join
  their existing Wave-1 organizations; BASC Imaging joins the existing Bedford ASC org.
- Coordinates are ZIP-centroid approximations (packages.geo.resolve_origin) — honest.
- NO price and NO per-procedure availability is asserted (offered != priced).

Cross-ORG shared-building near-duplicates (e.g. a lab and an imaging center in the same medical
building under different organizations) are intentionally kept as separate locations here and
surfaced by scripts/detect_duplicate_locations.py for human review — never auto-merged.

Run: python -m scripts.ingest_nh_roster_expansion [--dry-run]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import OrderedDict
from decimal import Decimal
from pathlib import Path
from typing import Any

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

DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "nh_roster_expansion.json"


def _norm_addr(value: str | None) -> str:
    if not value:
        return ""
    s = value.lower().strip()
    s = re.sub(r"[.,#]", " ", s)
    s = re.sub(r"\bstreet\b", "st", s)
    s = re.sub(r"\bdrive\b", "dr", s)
    s = re.sub(r"\broad\b", "rd", s)
    s = re.sub(r"\bavenue\b", "ave", s)
    s = re.sub(r"\bhighway\b", "hwy", s)
    s = re.sub(r"\bboulevard\b", "blvd", s)
    s = re.sub(r"\bsuite\b", "ste", s)
    s = re.sub(r"\bunit\b", "ste", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def _source_file(session: Session, url: str, name: str) -> SourceFile:
    existing = session.scalar(select(SourceFile).where(SourceFile.source_url == url))
    if existing is not None:
        return existing
    source = SourceFile(
        source_name=name,
        source_url=url,
        source_type="provider_directory",
        storage_path=f"provenance/{hashlib.sha256(url.encode()).hexdigest()[:16]}",
        checksum_sha256=hashlib.sha256(url.encode()).hexdigest(),
        file_size=0,
        parser_version="wave8-nh-roster-expansion",
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


def _load_records(path: Path | None = None) -> list[dict[str, Any]]:
    data = json.loads((path or DATA_PATH).read_text())
    return list(data["records"])


def ingest(
    session: Session | None = None,
    *,
    dry_run: bool = False,
    records: list[dict[str, Any]] | None = None,
) -> dict[str, int]:
    if session is None:
        session = next(get_session())
    if records is None:
        records = _load_records()

    created = {"organizations": 0, "facilities": 0, "locations": 0, "capabilities": 0}

    # Group records into physical locations: one site under one org -> union of capabilities.
    groups: OrderedDict[tuple[str, str, str], dict[str, Any]] = OrderedDict()
    for rec in records:
        key = (rec["organization"], _norm_addr(rec["address"]), rec["postal_code"])
        grp = groups.get(key)
        if grp is None:
            groups[key] = {"rec": rec, "capabilities": [rec["capability"]]}
        elif rec["capability"] not in grp["capabilities"]:
            grp["capabilities"].append(rec["capability"])

    for grp in groups.values():
        rec = grp["rec"]
        prov_name = f"{rec['organization']} — {rec['display_name']}"
        source = _source_file(session, rec["source_url"], prov_name)
        org_before = session.scalar(
            select(Organization).where(Organization.canonical_name == rec["organization"])
        )
        org = _organization(session, rec["organization"], rec["organization_type"], source)
        if org_before is None:
            created["organizations"] += 1

        facility = session.scalar(
            select(Facility).where(Facility.display_name == rec["display_name"])
        )
        if facility is None:
            facility = Facility(
                legal_name=rec["display_name"],
                display_name=rec["display_name"],
                facility_type=rec["facility_type"],
                phone=rec.get("phone"),
                website_url=rec["source_url"],
                active=True,
                organization_id=org.id,
                source_file_id=source.id,
            )
            session.add(facility)
            session.flush()
            created["facilities"] += 1

        try:
            coords = resolve_origin(postal_code=rec["postal_code"], state="NH")
        except Exception:
            coords = None
        location = session.scalar(
            select(FacilityLocation).where(
                FacilityLocation.facility_id == facility.id,
                FacilityLocation.address_line_1 == rec["address"],
                FacilityLocation.postal_code == rec["postal_code"],
            )
        )
        if location is None:
            location = FacilityLocation(
                facility_id=facility.id,
                location_name=rec["display_name"],
                location_type="service_location",
                active=True,
                address_line_1=rec["address"],
                city=rec["city"],
                state="NH",
                postal_code=rec["postal_code"],
                latitude=Decimal(str(coords[0])) if coords else None,
                longitude=Decimal(str(coords[1])) if coords else None,
            )
            session.add(location)
            session.flush()
            created["locations"] += 1

        for capability in grp["capabilities"]:
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
    parser = argparse.ArgumentParser(description="Ingest NH roster expansion (Wave 8)")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    result = ingest(dry_run=args.dry_run)
    prefix = "DRY-RUN " if args.dry_run else ""
    print(f"{prefix}NH_ROSTER_EXPANSION_INGESTED={result}")


if __name__ == "__main__":
    main()
