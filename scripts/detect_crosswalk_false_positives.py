"""Read-only detector for CDM-crosswalk false-positive mappings in production.

The importer resolves a CDM/UNKNOWN code to a standard code via apply_cdm_crosswalk,
stores the resolved (code_system, code) on PriceServiceCode while preserving the
original as (raw_code_type, raw_code), then creates an approved procedure mapping
from the resolved code. A too-broad crosswalk description pattern therefore attaches
a real record to the WRONG procedure (e.g. a penile prosthesis "700CXR" -> chest
x-ray). After tightening the patterns, this pass finds records whose stored
crosswalk resolution would NO LONGER be produced by the current crosswalk — i.e.
suspected false positives that predate the fix.

Deterministic and read-only: it re-applies the current crosswalk to each stored
raw description and flags mismatches. It NEVER edits mappings; it classifies each
facility CLEAN / REVIEW_REQUIRED / REIMPORT_RECOMMENDED so a human can decide.
"""

import argparse
import json
from collections import defaultdict
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from collectors.hospital_prices.cdm_crosswalk import apply_cdm_crosswalk
from collectors.hospital_prices.scope import active_consumer_facility_ids
from packages.database import (
    Facility,
    FacilityProcedurePriceSummary,
    HospitalPriceRecord,
    PriceServiceCode,
    Procedure,
    ProcedureCodeMapping,
    ProcedureCodeSystem,
    get_session,
)

# raw_code_type values the crosswalk is allowed to resolve (mirrors apply_cdm_crosswalk).
_LOCAL_TYPES = ("CDM", "UNKNOWN", "LOCAL", "FACILITY", "CHARGEMASTER")
# Standard systems a crosswalk resolution lands on (never a local system).
_STANDARD_SYSTEMS = ("CPT", "HCPCS", "MS_DRG", "MS-DRG", "APC", "DRG", "ICD10", "ICD-10")


def _resolved_code_to_procedure(session: Session) -> dict[tuple[str, str], tuple[Any, str]]:
    """{(code_system, code): (procedure_id, procedure_slug)} for approved/reviewed codes."""
    rows = session.execute(
        select(
            ProcedureCodeSystem.code_system,
            ProcedureCodeMapping.code,
            ProcedureCodeMapping.procedure_id,
            Procedure.slug,
        )
        .join(ProcedureCodeSystem, ProcedureCodeSystem.id == ProcedureCodeMapping.code_system_id)
        .join(Procedure, Procedure.id == ProcedureCodeMapping.procedure_id)
        .where(ProcedureCodeMapping.mapping_status.in_(["approved", "reviewed"]))
    ).all()
    out: dict[tuple[str, str], tuple[Any, str]] = {}
    for system, code, proc_id, slug in rows:
        out[(str(system).upper(), str(code))] = (proc_id, str(slug))
    return out


def detect(session: Session | None = None, state: str = "NH", sample: int = 8) -> dict[str, Any]:
    if session is None:
        session = next(get_session())
    facility_ids = set(active_consumer_facility_ids(session, state.upper()))
    facilities = {
        f.id: {"ccn": f.cms_certification_number, "name": f.display_name}
        for f in session.scalars(select(Facility).where(Facility.id.in_(facility_ids)))
    }
    code_to_proc = _resolved_code_to_procedure(session)

    # Publishable (facility, procedure) cells — does a suspect feed a public price?
    publishable = {
        (fid, pid)
        for fid, pid in session.execute(
            select(
                FacilityProcedurePriceSummary.facility_id,
                FacilityProcedurePriceSummary.procedure_id,
            )
            .where(
                FacilityProcedurePriceSummary.facility_id.in_(facility_ids),
                FacilityProcedurePriceSummary.publication_status == "publishable",
            )
            .distinct()
        ).all()
    }

    # Distinct crosswalk-resolved codes: local raw_code_type resolved to a standard system.
    rows = session.execute(
        select(
            HospitalPriceRecord.facility_id,
            HospitalPriceRecord.raw_description,
            PriceServiceCode.raw_code,
            PriceServiceCode.raw_code_type,
            PriceServiceCode.code_system,
            PriceServiceCode.code,
            func.count(PriceServiceCode.id),
        )
        .join(
            HospitalPriceRecord,
            HospitalPriceRecord.id == PriceServiceCode.hospital_price_record_id,
        )
        .where(
            HospitalPriceRecord.facility_id.in_(facility_ids),
            PriceServiceCode.raw_code_type.in_(_LOCAL_TYPES),
            PriceServiceCode.code_system.in_(_STANDARD_SYSTEMS),
        )
        .group_by(
            HospitalPriceRecord.facility_id,
            HospitalPriceRecord.raw_description,
            PriceServiceCode.raw_code,
            PriceServiceCode.raw_code_type,
            PriceServiceCode.code_system,
            PriceServiceCode.code,
        )
    ).all()

    suspects_by_facility: dict[Any, list[dict[str, Any]]] = defaultdict(list)
    resolved_checked = 0
    for facility_id, desc, raw_code, raw_type, sys_res, code_res, count in rows:
        resolved_checked += 1
        current = apply_cdm_crosswalk(str(raw_code or ""), str(raw_type), str(desc or ""))
        current_code = current[0] if current else None
        if current_code == str(code_res):
            continue  # still resolves the same way — not a false positive
        proc = code_to_proc.get((str(sys_res).upper(), str(code_res)))
        proc_id = proc[0] if proc else None
        suspects_by_facility[facility_id].append(
            {
                "procedure": proc[1] if proc else None,
                "raw_description": desc,
                "raw_code": str(raw_code),
                "raw_code_type": str(raw_type),
                "stale_resolved_code": f"{sys_res}:{code_res}",
                "current_crosswalk_result": (
                    f"{current[1]}:{current[0]}" if current else "NO_MATCH"
                ),
                "records_affected": int(count),
                "contributes_to_public_price": bool(
                    proc_id is not None and (facility_id, proc_id) in publishable
                ),
            }
        )

    per_facility = []
    totals = {"CLEAN": 0, "REVIEW_REQUIRED": 0, "REIMPORT_RECOMMENDED": 0}
    total_suspect_descriptions = 0
    total_public_suspects = 0
    for facility_id, meta in facilities.items():
        suspects = sorted(
            suspects_by_facility.get(facility_id, []),
            key=lambda s: (not s["contributes_to_public_price"], -s["records_affected"]),
        )
        public = [s for s in suspects if s["contributes_to_public_price"]]
        total_suspect_descriptions += len(suspects)
        total_public_suspects += len(public)
        if not suspects:
            classification = "CLEAN"
        elif public:
            classification = "REIMPORT_RECOMMENDED"
        else:
            classification = "REVIEW_REQUIRED"
        totals[classification] += 1
        per_facility.append(
            {
                "ccn": meta["ccn"],
                "hospital": meta["name"],
                "classification": classification,
                "suspect_description_count": len(suspects),
                "public_suspect_count": len(public),
                "records_affected": sum(s["records_affected"] for s in suspects),
                "samples": suspects[:sample],
            }
        )

    per_facility.sort(key=lambda f: (-f["public_suspect_count"], -f["suspect_description_count"]))
    return {
        "state": state.upper(),
        "resolved_codes_checked": resolved_checked,
        "facility_classification_totals": totals,
        "total_suspect_descriptions": total_suspect_descriptions,
        "total_public_suspect_descriptions": total_public_suspects,
        "facilities": per_facility,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Detect CDM crosswalk false-positive mappings")
    parser.add_argument("--state", default="NH")
    parser.add_argument("--sample", type=int, default=8)
    args = parser.parse_args()
    result = detect(state=args.state, sample=args.sample)
    print("CROSSWALK_FALSE_POSITIVES=" + json.dumps(result, default=str, separators=(",", ":")))
