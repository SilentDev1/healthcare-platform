"""Read-only diagnostic: where do NY HospitalPriceRecords live? (no writes)

Helps locate partial/orphan records left by an interrupted import so they can be cleaned before a
rebuild (which builds observations from HospitalPriceRecords). Prints per-NY-facility record counts,
plus records with NULL facility_id and records whose facility is NOT an NY hospital.

Run: python -m scripts.diag_ny_pricing
"""

from __future__ import annotations

# ruff: noqa: E501
import json

from sqlalchemy import func, select

from packages.database import Facility, FacilityLocation, get_session
from packages.database.pricing_models import HospitalPriceRecord


def main() -> None:
    session = next(get_session())
    ny_facilities = {
        f.id: f
        for f in session.scalars(
            select(Facility)
            .join(FacilityLocation, FacilityLocation.facility_id == Facility.id)
            .where(FacilityLocation.state == "NY")
        )
    }
    rows = session.execute(
        select(HospitalPriceRecord.facility_id, func.count(HospitalPriceRecord.id))
        .group_by(HospitalPriceRecord.facility_id)
    ).all()
    total = 0
    ny_counts = []
    non_ny = []
    null_fid = 0
    for fid, cnt in rows:
        total += cnt
        if fid is None:
            null_fid += cnt
        elif fid in ny_facilities:
            f = ny_facilities[fid]
            ny_counts.append((f.cms_certification_number, f.display_name, cnt))
        else:
            fac = session.get(Facility, fid)
            non_ny.append((str(fid), fac.cms_certification_number if fac else "?", fac.display_name if fac else "?", cnt))

    ny_counts.sort(key=lambda x: -x[2])
    print("NY_DIAG=" + json.dumps({
        "total_records_all_facilities": total,
        "ny_facility_record_count": sum(c for _, _, c in ny_counts),
        "null_facility_id_records": null_fid,
        "ny_facilities_with_records": len(ny_counts),
    }))
    print("\nNY facilities with records (CCN, name, count):")
    for ccn, name, cnt in ny_counts:
        print(f"  {ccn}  {name[:40]:40s}  {cnt}")


if __name__ == "__main__":
    main()
