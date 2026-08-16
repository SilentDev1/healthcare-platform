"""Consolidate the duplicate Parkland Medical Center (Derry) physical location.

Migration 0014's provider-neutral backfill left Parkland Medical Center (Derry, CMS 300017)
with TWO FacilityLocation rows for the SAME physical campus (1 Parkland Dr, Derry NH 03038):

  * SURVIVOR  8d40cc8f… — active, holds ALL pricing (price sources/records/observations/
    summaries/snapshots) + capabilities, but has NO coordinates.
  * DUPLICATE ee0a7a2c… — inactive, holds ONLY capabilities, but DOES have coordinates.

This script deterministically consolidates the duplicate INTO the survivor inside one
transaction, WITHOUT losing any data:

  1. Re-verify the two rows are the same physical location (same facility, type, city, state,
     ZIP, and normalized address). Abort if not provably identical.
  2. Choose the survivor deterministically = the location with the most pricing references
     (tie-break: active, then non-null name, then smallest id).
  3. Merge unique data: copy coordinates from the duplicate onto the survivor when the
     survivor lacks them (so Parkland keeps its map pin).
  4. Re-point every child reference (all 10 facility_location FKs) duplicate → survivor.
  5. Deduplicate child rows that would collide on a unique constraint (capabilities /
     service availability) instead of violating it.
  6. Assert the duplicate has zero remaining references, then delete it.

Idempotent: if the duplicate is already gone, it is a no-op. Prints a full before/after
manifest for rollback.

Run: python -m scripts.consolidate_parkland_derry_duplicate [--apply]   (default: dry-run)
"""

from __future__ import annotations

import argparse
import json
import re
from typing import Any

from sqlalchemy import func, or_, select, update
from sqlalchemy.orm import Session

from packages.database import (
    Facility,
    FacilityLocation,
    LocationCapability,
    LocationServiceAvailability,
    get_session,
)
from packages.database.pricing_models import (
    FacilityPriceSource,
    FacilityProcedurePriceObservation,
    FacilityProcedurePriceSummary,
    HospitalPriceRecord,
    NetworkParticipationObservation,
    PriceChangeSnapshot,
    PriceSourceOverlapAnalysis,
)

try:
    from packages.database.models import FacilityMedia
except Exception:  # pragma: no cover
    FacilityMedia = None  # type: ignore

PARKLAND_CMS = "300017"

# Simple single-FK tables: (model, attr). Re-pointed with a bulk UPDATE (no location-scoped
# unique constraint that a survivor could already occupy). Typed Any so attribute access on
# the ORM models type-checks cleanly across the heterogeneous list.
SIMPLE_FK_TABLES: list[tuple[Any, str]] = [
    (FacilityPriceSource, "facility_location_id"),
    (HospitalPriceRecord, "facility_location_id"),
    (FacilityProcedurePriceObservation, "facility_location_id"),
    (FacilityProcedurePriceSummary, "facility_location_id"),
    (NetworkParticipationObservation, "facility_location_id"),
    (PriceChangeSnapshot, "facility_location_id"),
]

# Unique-constrained child tables: (model, unique_attr). Moved with collision-aware logic.
COLLISION_FK_TABLES: list[tuple[Any, str]] = [
    (LocationCapability, "capability"),
    (LocationServiceAvailability, "procedure_id"),
]


def _norm_addr(value: str | None) -> str:
    if not value:
        return ""
    s = value.lower().strip()
    s = re.sub(r"[.,#]", " ", s)
    s = re.sub(r"\bstreet\b", "st", s)
    s = re.sub(r"\bdrive\b", "dr", s)
    s = re.sub(r"\broad\b", "rd", s)
    s = re.sub(r"\bavenue\b", "ave", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def _pricing_ref_count(session: Session, loc_id: object) -> int:
    total = 0
    for model, attr in SIMPLE_FK_TABLES:
        total += (
            session.scalar(
                select(func.count()).select_from(model).where(getattr(model, attr) == loc_id)
            )
            or 0
        )
    return total


def _all_ref_count(session: Session, loc_id: object) -> dict[str, int]:
    counts: dict[str, int] = {}
    for model, attr in [
        (LocationCapability, "facility_location_id"),
        (LocationServiceAvailability, "facility_location_id"),
        *SIMPLE_FK_TABLES,
    ]:
        counts[model.__tablename__] = (
            session.scalar(
                select(func.count()).select_from(model).where(getattr(model, attr) == loc_id)
            )
            or 0
        )
    counts["price_source_overlap_analyses"] = (
        session.scalar(
            select(func.count())
            .select_from(PriceSourceOverlapAnalysis)
            .where(
                or_(
                    PriceSourceOverlapAnalysis.left_location_id == loc_id,
                    PriceSourceOverlapAnalysis.right_location_id == loc_id,
                )
            )
        )
        or 0
    )
    if FacilityMedia is not None:
        counts["facility_media"] = (
            session.scalar(
                select(func.count())
                .select_from(FacilityMedia)
                .where(FacilityMedia.service_location_id == loc_id)
            )
            or 0
        )
    return counts


def _same_physical_location(a: FacilityLocation, b: FacilityLocation) -> bool:
    return (
        a.facility_id == b.facility_id
        and a.location_type == b.location_type
        and (a.city or "").strip().upper() == (b.city or "").strip().upper()
        and (a.state or "").strip().upper() == (b.state or "").strip().upper()
        and (a.postal_code or "").strip() == (b.postal_code or "").strip()
        and _norm_addr(a.address_line_1) == _norm_addr(b.address_line_1)
    )


def _pick_survivor(session: Session, locs: list[FacilityLocation]) -> FacilityLocation:
    def sort_key(loc: FacilityLocation) -> tuple[int, int, int]:
        return (
            _pricing_ref_count(session, loc.id),  # most pricing wins
            1 if loc.active else 0,  # then active
            1 if loc.location_name else 0,  # then has a name
            # tie-break stable/deterministic: smallest id string last (negate by using str)
        )

    ranked = sorted(locs, key=sort_key, reverse=True)
    # Final deterministic tie-break on id.
    top = ranked[0]
    top_key = sort_key(top)
    tied = [loc for loc in ranked if sort_key(loc) == top_key]
    return min(tied, key=lambda loc: str(loc.id))


def consolidate(session: Session | None = None, *, apply: bool = False) -> dict[str, Any]:
    if session is None:
        session = next(get_session())

    facility = session.scalar(
        select(Facility).where(Facility.cms_certification_number == PARKLAND_CMS)
    )
    if facility is None:
        return {"status": "facility_not_found", "cms": PARKLAND_CMS}

    # Same-physical-location group among this facility's hospital campuses in Derry.
    campuses = list(
        session.scalars(
            select(FacilityLocation).where(
                FacilityLocation.facility_id == facility.id,
                FacilityLocation.location_type == "hospital_campus",
            )
        )
    )
    # Group by physical sameness.
    if len(campuses) < 2:
        return {"status": "no_duplicate", "campus_count": len(campuses)}

    survivor = _pick_survivor(session, campuses)
    duplicates = [loc for loc in campuses if loc.id != survivor.id]

    # Every candidate duplicate MUST be provably the same physical place as the survivor.
    for dup in duplicates:
        if not _same_physical_location(survivor, dup):
            return {
                "status": "not_provably_identical",
                "survivor": str(survivor.id),
                "duplicate": str(dup.id),
                "survivor_addr": survivor.address_line_1,
                "duplicate_addr": dup.address_line_1,
            }

    actions: list[str] = []
    dup_manifests: list[dict[str, Any]] = []
    manifest: dict[str, Any] = {
        "status": "dry_run" if not apply else "applied",
        "facility": facility.display_name,
        "survivor": {
            "id": str(survivor.id),
            "name": survivor.location_name,
            "addr": survivor.address_line_1,
            "coords_before": [str(survivor.latitude), str(survivor.longitude)],
            "refs_before": _all_ref_count(session, survivor.id),
        },
        "duplicates": dup_manifests,
        "actions": actions,
    }

    for dup in duplicates:
        dup_manifest: dict[str, Any] = {
            "id": str(dup.id),
            "name": dup.location_name,
            "addr": dup.address_line_1,
            "active": dup.active,
            "coords": [str(dup.latitude), str(dup.longitude)],
            "refs_before": _all_ref_count(session, dup.id),
        }
        dup_manifests.append(dup_manifest)

        # (3) Merge coordinates: survivor keeps its own if present, else inherit duplicate's.
        if (survivor.latitude is None or survivor.longitude is None) and (
            dup.latitude is not None and dup.longitude is not None
        ):
            survivor.latitude = dup.latitude
            survivor.longitude = dup.longitude
            actions.append(f"copied coords {dup.latitude},{dup.longitude} -> survivor")

        # (4/5) Collision-aware move for unique-constrained child tables.
        for model, uniq_attr in COLLISION_FK_TABLES:
            survivor_keys = set(
                session.scalars(
                    select(getattr(model, uniq_attr)).where(
                        model.facility_location_id == survivor.id
                    )
                )
            )
            for child in session.scalars(
                select(model).where(model.facility_location_id == dup.id)
            ):
                key = getattr(child, uniq_attr)
                if key in survivor_keys:
                    session.delete(child)  # survivor already has it -> drop redundant dup row
                    actions.append(
                        f"deleted redundant {model.__tablename__}.{key} from duplicate"
                    )
                else:
                    child.facility_location_id = survivor.id
                    survivor_keys.add(key)
                    actions.append(
                        f"repointed {model.__tablename__}.{key} -> survivor"
                    )

        # (4) Bulk re-point for simple FK tables (no location-scoped unique constraint).
        for model, attr in SIMPLE_FK_TABLES:
            moved = session.execute(
                update(model)
                .where(getattr(model, attr) == dup.id)
                .values(**{attr: survivor.id})
            ).rowcount
            if moved:
                actions.append(f"repointed {moved} {model.__tablename__} -> survivor")

        # Overlap analysis (left/right) and media.
        for col in ("left_location_id", "right_location_id"):
            moved = session.execute(
                update(PriceSourceOverlapAnalysis)
                .where(getattr(PriceSourceOverlapAnalysis, col) == dup.id)
                .values(**{col: survivor.id})
            ).rowcount
            if moved:
                actions.append(f"repointed {moved} overlap.{col} -> survivor")
        if FacilityMedia is not None:
            moved = session.execute(
                update(FacilityMedia)
                .where(FacilityMedia.service_location_id == dup.id)
                .values(service_location_id=survivor.id)
            ).rowcount
            if moved:
                actions.append(f"repointed {moved} facility_media -> survivor")

        session.flush()

        # (6) Assert zero remaining references, then delete.
        remaining = _all_ref_count(session, dup.id)
        dup_manifest["refs_after"] = remaining
        if any(remaining.values()):
            session.rollback()
            manifest["status"] = "aborted_refs_remaining"
            manifest["remaining"] = remaining
            return manifest
        session.delete(dup)
        actions.append(f"deleted duplicate location {dup.id}")

    manifest["survivor"]["coords_after"] = [str(survivor.latitude), str(survivor.longitude)]
    manifest["survivor"]["refs_after"] = _all_ref_count(session, survivor.id)

    if apply:
        session.commit()
    else:
        session.rollback()
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Consolidate Parkland Derry duplicate location")
    parser.add_argument("--apply", action="store_true", help="commit (default is dry-run)")
    args = parser.parse_args()
    result = consolidate(apply=args.apply)
    print("PARKLAND_CONSOLIDATION=" + json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
