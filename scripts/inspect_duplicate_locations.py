"""Read-only inspector for duplicate physical FacilityLocation rows.

Prints, for every group of locations under the same facility that plausibly represent the
SAME physical place, the full detail of each row plus a reference count across EVERY table
that carries a facility_location FK. Used to PROVE (before any write) whether two rows are
the same physical location and which one is canonical (carries the pricing/provenance).

Read-only: performs no writes.

Run: python -m scripts.inspect_duplicate_locations [--facility "PARKLAND MEDICAL CENTER"]
"""

from __future__ import annotations

# ruff: noqa: E501  -- diagnostic print lines are kept readable
import argparse
import re
from collections import defaultdict

from sqlalchemy import func, or_, select
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

try:  # FacilityMedia may live in either module depending on version
    from packages.database.models import FacilityMedia
except Exception:  # pragma: no cover
    FacilityMedia = None  # type: ignore[assignment]

# (label, model, attribute) for every single-location FK.
LOC_FK_TABLES = [
    ("location_capabilities", LocationCapability, "facility_location_id"),
    ("location_service_availability", LocationServiceAvailability, "facility_location_id"),
    ("facility_price_sources", FacilityPriceSource, "facility_location_id"),
    ("hospital_price_records", HospitalPriceRecord, "facility_location_id"),
    ("facility_procedure_price_observations", FacilityProcedurePriceObservation, "facility_location_id"),
    ("facility_procedure_price_summaries", FacilityProcedurePriceSummary, "facility_location_id"),
    ("network_participation_observations", NetworkParticipationObservation, "facility_location_id"),
    ("price_change_snapshots", PriceChangeSnapshot, "facility_location_id"),
]


def _norm_addr(value: str | None) -> str:
    if not value:
        return ""
    s = value.lower().strip()
    s = re.sub(r"[.,#]", " ", s)
    s = re.sub(r"\bstreet\b", "st", s)
    s = re.sub(r"\broad\b", "rd", s)
    s = re.sub(r"\bavenue\b", "ave", s)
    s = re.sub(r"\bsuite\b", "ste", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def _ref_counts(session: Session, loc_id: object) -> dict[str, int]:
    counts: dict[str, int] = {}
    for label, model, attr in LOC_FK_TABLES:
        counts[label] = (
            session.scalar(
                select(func.count()).select_from(model).where(getattr(model, attr) == loc_id)
            )
            or 0
        )
    counts["price_source_overlap_analyses(l/r)"] = (
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
        counts["facility_media(service_location_id)"] = (
            session.scalar(
                select(func.count())
                .select_from(FacilityMedia)
                .where(FacilityMedia.service_location_id == loc_id)
            )
            or 0
        )
    return counts


def dump_facility(session: Session, name_substr: str) -> None:
    """Dump EVERY facility matching the name and ALL its locations (active or not)."""
    facilities = list(
        session.scalars(
            select(Facility).where(Facility.display_name.ilike(f"%{name_substr}%"))
        )
    )
    print(f"FACILITIES_MATCHING={len(facilities)} for {name_substr!r}")
    for f in facilities:
        print(f"\n### FACILITY id={f.id} name={f.display_name!r} type={f.facility_type} "
              f"cms={f.cms_certification_number} org={f.organization_id} active={f.active}")
        locs = list(
            session.scalars(
                select(FacilityLocation).where(FacilityLocation.facility_id == f.id)
            )
        )
        print(f"    locations={len(locs)}")
        for loc in locs:
            print(f"    LOC id={loc.id} name={loc.location_name!r} type={loc.location_type} "
                  f"addr={loc.address_line_1!r} city={loc.city} zip={loc.postal_code} "
                  f"lat={loc.latitude} lng={loc.longitude} active={loc.active}")
            counts = _ref_counts(session, loc.id)
            nonzero = {k: v for k, v in counts.items() if v}
            print(f"        refs={nonzero if nonzero else 'NONE'}")


def inspect(session: Session | None = None, *, facility_filter: str | None = None) -> None:
    if session is None:
        session = next(get_session())

    if facility_filter:
        dump_facility(session, facility_filter)
        print()

    # Group active locations by (facility_id, city, state, location_type) to find same-place candidates.
    groups: dict[tuple, list[FacilityLocation]] = defaultdict(list)
    for loc in session.scalars(select(FacilityLocation).where(FacilityLocation.active.is_(True))):
        key = (loc.facility_id, (loc.city or "").upper(), (loc.state or "").upper(), loc.location_type)
        groups[key].append(loc)

    dup_groups = {k: v for k, v in groups.items() if len(v) > 1}
    print(f"DUP_LOCATION_GROUPS_FOUND={len(dup_groups)}")
    for key, locs in dup_groups.items():
        facility = session.get(Facility, key[0])
        fname = facility.display_name if facility else "?"
        if facility_filter and facility_filter.upper() not in (fname or "").upper():
            continue
        print(f"\n=== {fname} [{facility.facility_type if facility else '?'}] "
              f"| city={key[1]} state={key[2]} type={key[3]} | {len(locs)} locations ===")
        norm_addrs = {_norm_addr(loc.address_line_1) for loc in locs}
        print(f"  normalized_addresses={sorted(norm_addrs)}  "
              f"same_physical_place={'YES' if len(norm_addrs - {''}) <= 1 else 'AMBIGUOUS'}")
        for loc in locs:
            print(f"  LOC id={loc.id}")
            print(f"      name={loc.location_name!r} addr={loc.address_line_1!r} zip={loc.postal_code} "
                  f"lat={loc.latitude} lng={loc.longitude} active={loc.active}")
            counts = _ref_counts(session, loc.id)
            nonzero = {k: v for k, v in counts.items() if v}
            print(f"      refs={nonzero if nonzero else 'NONE'}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect duplicate physical locations (read-only)")
    parser.add_argument("--facility", default=None, help="only show groups for this facility name substring")
    args = parser.parse_args()
    inspect(facility_filter=args.facility)


if __name__ == "__main__":
    main()
