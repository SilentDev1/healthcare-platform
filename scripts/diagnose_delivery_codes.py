"""Read-only: report which delivery codes actually appear in NH hospital records.

Verifies, from the imported raw data, which MS-DRG / CPT delivery codes are present
(and their descriptions, settings, billing classes, and hospital spread) so the
reviewed registry additions are grounded in the source data rather than assumed.
The full delivery code universe is listed — including sterilization/D&C variants —
so the billing-component decision (which codes are a clean vaginal/cesarean
delivery vs a bundled sterilization) is evidence-based. Never mutates anything.
"""

import argparse
import json
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from collectors.hospital_prices.scope import active_consumer_facility_ids
from packages.database import (
    Facility,
    HospitalPriceRecord,
    PriceServiceCode,
    get_session,
)

# The full delivery code universe (verify meaning before mapping any of them).
DELIVERY_CODES: dict[str, dict[str, str]] = {
    "MS_DRG": {
        "768": "Vaginal delivery w/ O.R. proc except steril/D&C",
        "774": "Vaginal delivery w/ complicating dx (RETIRED)",
        "775": "Vaginal delivery w/o complicating dx (RETIRED)",
        "796": "Vaginal delivery w/ sterilization/D&C w/ MCC",
        "797": "Vaginal delivery w/ sterilization/D&C w/ CC",
        "798": "Vaginal delivery w/ sterilization/D&C w/o CC/MCC",
        "805": "Vaginal delivery w/o sterilization/D&C w/ MCC",
        "806": "Vaginal delivery w/o sterilization/D&C w/ CC",
        "807": "Vaginal delivery w/o sterilization/D&C w/o CC/MCC",
        "765": "Cesarean section w/ CC (RETIRED numbering)",
        "766": "Cesarean section w/o CC/MCC (RETIRED numbering)",
        "767": "Cesarean w/ sterilization? (RETIRED numbering)",
        "783": "Cesarean section w/ sterilization w/ MCC",
        "784": "Cesarean section w/ sterilization w/ CC",
        "785": "Cesarean section w/ sterilization w/o CC/MCC",
        "786": "Cesarean section w/o sterilization w/ MCC",
        "787": "Cesarean section w/o sterilization w/ CC",
        "788": "Cesarean section w/o sterilization w/o CC/MCC",
    },
    "CPT": {
        "59400": "Routine OB care incl vaginal delivery (global)",
        "59409": "Vaginal delivery only",
        "59410": "Vaginal delivery incl postpartum",
        "59510": "Routine OB care incl cesarean (global)",
        "59514": "Cesarean delivery only",
        "59515": "Cesarean delivery incl postpartum",
        "59610": "VBAC routine care (global)",
        "59612": "VBAC delivery only",
        "59618": "Cesarean after attempted VBAC (global)",
        "59620": "Cesarean delivery only after attempted VBAC",
    },
}


def diagnose(session: Session | None = None, state: str = "NH") -> dict[str, Any]:
    if session is None:
        session = next(get_session())
    facility_ids = set(active_consumer_facility_ids(session, state.upper()))
    ccn = {
        f.id: f.cms_certification_number
        for f in session.scalars(select(Facility).where(Facility.id.in_(facility_ids)))
    }

    out: list[dict[str, Any]] = []
    for system, codes in DELIVERY_CODES.items():
        for code, meaning in codes.items():
            rows = session.execute(
                select(
                    HospitalPriceRecord.facility_id,
                    func.min(HospitalPriceRecord.raw_description),
                    func.count(PriceServiceCode.id),
                )
                .join(
                    HospitalPriceRecord,
                    HospitalPriceRecord.id == PriceServiceCode.hospital_price_record_id,
                )
                .where(
                    HospitalPriceRecord.facility_id.in_(facility_ids),
                    PriceServiceCode.code_system == system,
                    PriceServiceCode.code == code,
                )
                .group_by(HospitalPriceRecord.facility_id)
            ).all()
            if not rows:
                continue
            hospitals = sorted({str(ccn.get(fid) or "?") for fid, _d, _c in rows})
            out.append(
                {
                    "system": system,
                    "code": code,
                    "meaning": meaning,
                    "hospitals": len(hospitals),
                    "ccns": hospitals,
                    "total_records": sum(c for _f, _d, c in rows),
                    "sample_descriptions": sorted({str(d) for _f, d, _c in rows})[:4],
                }
            )
    out.sort(key=lambda r: (r["system"], r["code"]))
    return {"state": state.upper(), "present_codes": out}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Report delivery codes present in NH records")
    parser.add_argument("--state", default="NH")
    args = parser.parse_args()
    print(
        "DELIVERY_CODES="
        + json.dumps(diagnose(state=args.state), default=str, separators=(",", ":"))
    )
