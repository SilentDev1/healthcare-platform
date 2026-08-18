"""Read-only audit of raw hospital price records for an exact billing code.

Answers the go/no-go question for a candidate canonical procedure: do NH hospitals
actually publish this exact code, and what do the records look like? Never writes.

Run (Cloud Run job):
  python -m scripts.audit_raw_code --code 82306 --system CPT --state NH
"""

from __future__ import annotations

# ruff: noqa: E501
import argparse
import json
import statistics
from collections import defaultdict
from typing import Any

from sqlalchemy import func, select

from collectors.hospital_prices.scope import active_consumer_facility_ids
from packages.database import Facility, get_session
from packages.database.pricing_models import HospitalPriceRecord, PriceServiceCode


def run(code: str, system: str, state: str) -> dict[str, Any]:
    session = next(get_session())
    consumer_ids = active_consumer_facility_ids(session, state)

    rows = session.execute(
        select(
            HospitalPriceRecord.facility_id,
            Facility.display_name,
            HospitalPriceRecord.raw_description,
            HospitalPriceRecord.setting,
            HospitalPriceRecord.discounted_cash_price,
            HospitalPriceRecord.deidentified_minimum_negotiated_rate,
            HospitalPriceRecord.deidentified_maximum_negotiated_rate,
        )
        .join(PriceServiceCode, PriceServiceCode.hospital_price_record_id == HospitalPriceRecord.id)
        .join(Facility, Facility.id == HospitalPriceRecord.facility_id)
        .where(
            PriceServiceCode.code_system == system,
            PriceServiceCode.code == code,
            HospitalPriceRecord.facility_id.in_(consumer_ids),
        )
    ).all()

    by_fac: dict[Any, dict[str, Any]] = defaultdict(
        lambda: {"name": "", "records": 0, "cash": [], "neg": [], "descs": set(), "settings": set()}
    )
    cash_all: list[float] = []
    for fid, name, desc, setting, cash, neg_min, neg_max in rows:
        f = by_fac[fid]
        f["name"] = name
        f["records"] += 1
        if cash is not None:
            f["cash"].append(float(cash))
            cash_all.append(float(cash))
        if neg_min is not None:
            f["neg"].append(float(neg_min))
        if desc:
            f["descs"].add(desc.strip()[:80])
        if setting:
            f["settings"].add(setting)

    facilities = [
        {
            "facility": v["name"],
            "records": v["records"],
            "has_cash": bool(v["cash"]),
            "has_negotiated": bool(v["neg"]),
            "cash_min": round(min(v["cash"]), 2) if v["cash"] else None,
            "cash_max": round(max(v["cash"]), 2) if v["cash"] else None,
            "settings": sorted(v["settings"]),
            "sample_descriptions": sorted(v["descs"])[:3],
        }
        for v in sorted(by_fac.values(), key=lambda x: -x["records"])
    ]
    result = {
        "code": f"{system}:{code}",
        "state": state,
        "consumer_hospitals": len(consumer_ids),
        "hospitals_with_raw_records": len(by_fac),
        "hospitals_with_cash": sum(1 for f in facilities if f["has_cash"]),
        "hospitals_with_negotiated": sum(1 for f in facilities if f["has_negotiated"]),
        "total_raw_records": len(rows),
        "cash_min": round(min(cash_all), 2) if cash_all else None,
        "cash_median": round(statistics.median(cash_all), 2) if cash_all else None,
        "cash_max": round(max(cash_all), 2) if cash_all else None,
        "facilities": facilities,
    }
    return result


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--code", required=True)
    ap.add_argument("--system", default="CPT")
    ap.add_argument("--state", default="NH")
    args = ap.parse_args()
    result = run(args.code, args.system, args.state)
    slim = {k: v for k, v in result.items() if k != "facilities"}
    print("RAW_CODE_AUDIT=" + json.dumps(slim))
    for f in result["facilities"]:
        print(f"  {f['facility'][:34]:34} records={f['records']:3} cash={f['cash_min']}-{f['cash_max']} settings={f['settings']} desc={f['sample_descriptions'][:1]}")


if __name__ == "__main__":
    main()
