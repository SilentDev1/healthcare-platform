"""Seed the 53 operating Massachusetts hospitals as provider-neutral IDENTITY (Phase 2).

Identity/geography ONLY — no pricing, no per-procedure availability. Creates, per hospital:
  * a get-or-create Organization (the health system, or the hospital itself when independent),
  * a get-or-create Facility keyed on ``cms_certification_number`` (DB-unique — the dedup guarantee),
  * a get-or-create FacilityLocation (one per CCN, primary CMS campus address, ``state="MA"``,
    ``location_type="hospital_campus"``, region from the validated MA taxonomy), and
  * a ``hospital`` LocationCapability with provenance.

Data sources (both identity-only, no prices):
  * data/ma_hospitals_seed.json          — the 53 operating acute+CAH denominator (ccn, name, city, zip, region, system, type)
  * data/ma_cms_hospital_snapshot.json    — authoritative CMS identity (address, county, ownership, phone) keyed by CCN

Safety:
  * Idempotent / re-runnable / duplicate-safe: Facility dedups on CCN (DB unique), FacilityLocation on
    the physical-location unique constraint, LocationCapability on (location, capability). A second run
    creates nothing.
  * Massachusetts only — this NEVER touches NH rows. It writes no pricing and asserts no availability.
  * Refuses to seed any CCN listed as closed (Carney/Nashoba/Norwood) or as a separately-bucketed
    specialty-acute hospital — a defensive guard so the active denominator can never be contaminated.
  * ``region`` is taken from the seed (already proven derivable from (county, city) by
    scripts/verify_ma_foundation.py); it is re-checked here against the CMS county via the taxonomy.

Run: python -m scripts.seed_ma_hospitals [--dry-run]
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
from scripts.verify_ma_foundation import resolve_region

DATA = Path(__file__).resolve().parent.parent / "data"
SEED_PATH = DATA / "ma_hospitals_seed.json"
CMS_PATH = DATA / "ma_cms_hospital_snapshot.json"
TAXONOMY_PATH = DATA / "ma_region_taxonomy.json"


def _source_file(session: Session, url: str) -> SourceFile:
    existing = session.scalar(select(SourceFile).where(SourceFile.source_url == url))
    if existing is not None:
        return existing
    source = SourceFile(
        source_name="CMS Hospital General Information (MA identity snapshot)",
        source_url=url,
        source_type="cms_hospital_general_information",
        storage_path=f"provenance/{hashlib.sha256(url.encode()).hexdigest()[:16]}",
        checksum_sha256=hashlib.sha256(url.encode()).hexdigest(),
        file_size=0,
        parser_version="ma-hospitals-seed-phase2",
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
    cms_data: dict[str, Any] | None = None,
    taxonomy: dict[str, Any] | None = None,
) -> dict[str, int]:
    if session is None:
        session = next(get_session())
    if seed_data is None:
        seed_data = json.loads(SEED_PATH.read_text())
    if cms_data is None:
        cms_data = json.loads(CMS_PATH.read_text())
    if taxonomy is None:
        taxonomy = json.loads(TAXONOMY_PATH.read_text())

    cms = {r["facility_id"]: r for r in cms_data["hospitals"]}
    forbidden = {e["ccn"] for e in seed_data["_meta"]["excluded_closed"]}
    forbidden |= {s.split()[0] for s in seed_data["_meta"]["specialty_acute_bucket_separately"]}
    source_url = cms_data["_meta"]["endpoint"]

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
        if ccn in forbidden:  # closed or specialty — must never enter the active denominator
            counts["skipped_forbidden"] += 1
            continue
        rec = cms.get(ccn)
        if rec is None or not rec.get("address"):
            raise ValueError(f"CCN {ccn} ({h['name']}) missing an authoritative CMS address — refusing to fabricate one")

        # region: trust the seed, but re-derive from CMS county+city and require agreement
        derived = resolve_region(taxonomy, rec.get("countyparish", ""), rec.get("citytown", h["city"]))
        if derived != h["region"]:
            raise ValueError(f"CCN {ccn} region mismatch: seed={h['region']!r} derived={derived!r}")

        # Organization: the health system, or the hospital itself when independent.
        if h["system"] == "Independent":
            org_name, org_type = h["name"], "independent_hospital"
        else:
            org_name, org_type = h["system"], "hospital_system"
        org, org_created = _organization(session, org_name, org_type, source)
        if org_created:
            counts["organizations"] += 1

        # Facility: get-or-create by CCN (DB-unique). Update identity fields in place on re-run.
        facility = session.scalar(
            select(Facility).where(Facility.cms_certification_number == ccn)
        )
        if facility is None:
            facility = Facility(
                cms_certification_number=ccn,
                legal_name=rec["facility_name"],
                display_name=h["name"],
                facility_type=h["type"],
                ownership_type=rec.get("hospital_ownership") or None,
                phone=rec.get("telephone_number") or None,
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
                ("legal_name", rec["facility_name"]),
                ("facility_type", h["type"]),
                ("ownership_type", rec.get("hospital_ownership") or None),
                ("phone", rec.get("telephone_number") or None),
                ("organization_id", org.id),
                ("active", True),
            ):
                if getattr(facility, attr) != val:
                    setattr(facility, attr, val)
                    changed = True
            if changed:
                counts["facilities_updated"] += 1

        # FacilityLocation: one per CCN (primary campus). Dedup on the physical-location unique key.
        address = rec["address"]
        postal = rec.get("zip_code") or h["zip"]
        try:
            coords = resolve_origin(postal_code=postal, state="MA")
        except Exception:
            coords = None
        location = session.scalar(
            select(FacilityLocation).where(
                FacilityLocation.facility_id == facility.id,
                FacilityLocation.address_line_1 == address,
                FacilityLocation.city == rec["citytown"],
                FacilityLocation.state == "MA",
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
                city=rec["citytown"],
                state="MA",
                postal_code=postal,
                county=rec.get("countyparish") or None,
                region=h["region"],
                latitude=Decimal(str(coords[0])) if coords else None,
                longitude=Decimal(str(coords[1])) if coords else None,
            )
            session.add(location)
            session.flush()
            counts["locations"] += 1
        else:
            # keep region/county current without duplicating
            if location.region != h["region"]:
                location.region = h["region"]
            if not location.county and rec.get("countyparish"):
                location.county = rec["countyparish"]

        # hospital capability (offered != priced) with provenance
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
    parser = argparse.ArgumentParser(description="Seed the 53 operating MA hospitals (identity only, no pricing)")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    result = seed(dry_run=args.dry_run)
    prefix = "DRY-RUN " if args.dry_run else ""
    print(f"{prefix}MA_HOSPITAL_SEED={result}")


if __name__ == "__main__":
    main()
