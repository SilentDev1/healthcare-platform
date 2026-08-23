"""Seed the operating New York hospitals as provider-neutral IDENTITY (Phase 5).

Identity/geography ONLY — no pricing, no per-procedure availability. Creates, per hospital:
  * a get-or-create Organization (the health system, or the hospital itself when independent),
  * a get-or-create Facility keyed on ``cms_certification_number`` (DB-unique — the dedup guarantee),
  * a get-or-create FacilityLocation (one per CCN, primary campus address, ``state="NY"``,
    ``location_type="hospital_campus"``, region from the validated NY taxonomy), and
  * a ``hospital`` LocationCapability with provenance.

Source: data/ny_hospitals_seed.json (the 157 operating denominator, ccn/name/address/city/zip/
county/type/system/region, each row tagged source=cms|nysdoh). Every row carries its own street
address (CMS rows from xubh-q36u; NYSDOH additions hand-verified), so no address is fabricated.

Safety:
  * Idempotent / re-runnable / duplicate-safe (Facility dedups on CCN; FacilityLocation on the
    physical-location unique constraint; LocationCapability on (location, capability)).
  * New York only — NEVER touches NH or MA rows. Writes no pricing, asserts no availability.
  * Refuses to seed any CCN in a disposition bucket (closed/merged/superseded/specialty/rehab-LTAC)
    — a defensive guard so the active denominator can never be contaminated.
  * ``region`` is re-derived from county via the taxonomy and must equal the seed's region.

Run: python -m scripts.seed_ny_hospitals [--dry-run]
"""

from __future__ import annotations

# ruff: noqa: E501
import argparse
import hashlib
import json
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
from scripts.verify_ny_foundation import resolve_region

DATA = Path(__file__).resolve().parent.parent / "data"
SEED_PATH = DATA / "ny_hospitals_seed.json"
TAXONOMY_PATH = DATA / "ny_region_taxonomy.json"


def _disposition_ccns(meta: dict[str, Any]) -> set[str]:
    ccns: set[str] = set()
    for bucket in ("excluded_closed", "excluded_merged", "excluded_superseded", "specialty_bucket", "excluded_rehab_ltac"):
        ccns |= {e["ccn"] for e in meta.get(bucket, [])}
    return ccns


def _source_file(session: Session, url: str) -> SourceFile:
    existing = session.scalar(select(SourceFile).where(SourceFile.source_url == url))
    if existing is not None:
        return existing
    source = SourceFile(
        source_name="NY hospital identity (CMS xubh-q36u + NYSDOH vn5v-hh5r reconciliation)",
        source_url=url,
        source_type="cms_hospital_general_information",
        storage_path=f"provenance/{hashlib.sha256(url.encode()).hexdigest()[:16]}",
        checksum_sha256=hashlib.sha256(url.encode()).hexdigest(),
        file_size=0,
        parser_version="ny-hospitals-seed-phase5",
        status=SourceStatus.COMPLETED,
    )
    session.add(source)
    session.flush()
    return source


def _organization(session: Session, name: str, org_type: str, source: SourceFile) -> tuple[Organization, bool]:
    existing = session.scalar(select(Organization).where(Organization.canonical_name == name))
    if existing is not None:
        return existing, False
    org = Organization(
        canonical_name=name,
        display_name=name,
        organization_type=org_type,
        active=True,
        source_file_id=source.id,
    )
    session.add(org)
    session.flush()
    return org, True


def seed(
    session: Session | None = None,
    *,
    dry_run: bool = False,
    seed_data: dict[str, Any] | None = None,
    taxonomy: dict[str, Any] | None = None,
) -> dict[str, int]:
    if session is None:
        session = next(get_session())
    if seed_data is None:
        seed_data = json.loads(SEED_PATH.read_text())
    if taxonomy is None:
        taxonomy = json.loads(TAXONOMY_PATH.read_text())

    forbidden = _disposition_ccns(seed_data["_meta"])
    source_url = "https://data.cms.gov/provider-data/dataset/xubh-q36u + https://health.data.ny.gov/resource/vn5v-hh5r (NY identity, retrieved 2026-08-23)"

    counts = {
        "organizations": 0,
        "facilities": 0,
        "facilities_updated": 0,
        "locations": 0,
        "capabilities": 0,
        "skipped_forbidden": 0,
    }

    source = _source_file(session, source_url)

    for h in seed_data["hospitals"]:
        ccn = h["ccn"]
        if ccn in forbidden:  # disposition bucket — must never enter the active denominator
            counts["skipped_forbidden"] += 1
            continue
        if not h.get("address"):
            raise ValueError(f"CCN {ccn} ({h['name']}) has no street address — refusing to fabricate one")

        # region: trust the seed, but re-derive from county+city and require agreement
        derived = resolve_region(taxonomy, h.get("county", ""), h.get("city", ""))
        if derived != h["region"]:
            raise ValueError(f"CCN {ccn} region mismatch: seed={h['region']!r} derived={derived!r}")

        # Organization: the health system, or the hospital itself when independent/unassigned.
        if h.get("system"):
            org_name, org_type = h["system"], "hospital_system"
        else:
            org_name, org_type = h["name"], "independent_hospital"
        org, org_created = _organization(session, org_name, org_type, source)
        if org_created:
            counts["organizations"] += 1

        # Facility: get-or-create by CCN (DB-unique). Update identity fields in place on re-run.
        facility = session.scalar(select(Facility).where(Facility.cms_certification_number == ccn))
        if facility is None:
            facility = Facility(
                cms_certification_number=ccn,
                legal_name=h["name"],
                display_name=h["name"],
                facility_type=h["type"],
                ownership_type=None,
                phone=None,
                active=True,
                organization_id=org.id,
                source_file_id=source.id,
            )
            session.add(facility)
            session.flush()
            counts["facilities"] += 1
        else:
            changed = False
            for attr, val in (
                ("display_name", h["name"]),
                ("facility_type", h["type"]),
                ("organization_id", org.id),
                ("active", True),
            ):
                if getattr(facility, attr) != val:
                    setattr(facility, attr, val)
                    changed = True
            if changed:
                counts["facilities_updated"] += 1

        # FacilityLocation: one per CCN (primary campus). Dedup on the physical-location unique key.
        address = h["address"]
        postal = h["zip"]
        try:
            coords = resolve_origin(postal_code=postal, state="NY")
        except Exception:
            coords = None
        location = session.scalar(
            select(FacilityLocation).where(
                FacilityLocation.facility_id == facility.id,
                FacilityLocation.address_line_1 == address,
                FacilityLocation.city == h["city"],
                FacilityLocation.state == "NY",
                FacilityLocation.postal_code == postal,
            )
        )
        if location is None:
            location = FacilityLocation(
                facility_id=facility.id,
                location_name=h["name"],
                location_type="hospital_campus",
                active=True,
                address_line_1=address,
                city=h["city"],
                state="NY",
                postal_code=postal,
                county=h.get("county") or None,
                region=h["region"],
                latitude=Decimal(str(coords[0])) if coords else None,
                longitude=Decimal(str(coords[1])) if coords else None,
            )
            session.add(location)
            session.flush()
            counts["locations"] += 1
        else:
            if location.region != h["region"]:
                location.region = h["region"]
            if not location.county and h.get("county"):
                location.county = h["county"]

        cap = session.scalar(
            select(LocationCapability).where(
                LocationCapability.facility_location_id == location.id,
                LocationCapability.capability == "hospital",
            )
        )
        if cap is None:
            session.add(
                LocationCapability(
                    facility_location_id=location.id,
                    capability="hospital",
                    active=True,
                    evidence_source_id=source.id,
                )
            )
            counts["capabilities"] += 1

    if dry_run:
        session.rollback()
    else:
        session.commit()
    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed the operating NY hospitals (identity only, no pricing)")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    result = seed(dry_run=args.dry_run)
    prefix = "DRY-RUN " if args.dry_run else ""
    print(f"{prefix}NY_HOSPITAL_SEED={result}")


if __name__ == "__main__":
    main()
