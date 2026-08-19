"""Read-only diagnostic: where do MA HospitalPriceRecords live? (no writes)

Helps locate partial/orphan records left by an interrupted import so they can be cleaned before a
rebuild (which builds observations from HospitalPriceRecords). Prints per-MA-facility record counts,
plus records with NULL facility_id and records whose facility is NOT an MA hospital.

Run: python -m scripts.diag_ma_pricing
"""

from __future__ import annotations

# ruff: noqa: E501
import json

from sqlalchemy import func, select

from packages.database import Facility, FacilityLocation, get_session
from packages.database.pricing_models import HospitalPriceRecord


def main() -> None:
    session = next(get_session())
    ma_facilities = {
        f.id: f
        for f in session.scalars(
            select(Facility)
            .join(FacilityLocation, FacilityLocation.facility_id == Facility.id)
            .where(FacilityLocation.state == "MA")
        )
    }
    # per-facility record counts across ALL facilities (to catch mis-stamped rows)
    rows = session.execute(
        select(HospitalPriceRecord.facility_id, func.count(HospitalPriceRecord.id))
        .group_by(HospitalPriceRecord.facility_id)
    ).all()
    total = 0
    ma_counts = []
    non_ma = []
    null_fid = 0
    for fid, cnt in rows:
        total += cnt
        if fid is None:
            null_fid += cnt
        elif fid in ma_facilities:
            f = ma_facilities[fid]
            ma_counts.append((f.cms_certification_number, f.display_name, cnt))
        else:
            fac = session.get(Facility, fid)
            non_ma.append((str(fid), fac.cms_certification_number if fac else "?", fac.display_name if fac else "?", cnt))

    ma_counts.sort(key=lambda x: -x[2])
    print("MA_DIAG=" + json.dumps({
        "total_records_all_facilities": total,
        "ma_facility_record_count": sum(c for _, _, c in ma_counts),
        "null_facility_id_records": null_fid,
        "ma_facilities_with_records": len(ma_counts),
    }))
    print("\nMA facilities with records (CCN, name, count):")
    for ccn, name, cnt in ma_counts:
        print(f"  {ccn}  {name[:40]:40s}  {cnt}")
    if non_ma:
        print(f"\nNON-MA facilities with records that... (should be NH — {len(non_ma)} facilities):")
        for fid, ccn, name, cnt in sorted(non_ma, key=lambda x: -x[3])[:8]:
            print(f"  {ccn}  {name[:40]:40s}  {cnt}")


if __name__ == "__main__":
    main()
