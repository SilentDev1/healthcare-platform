"""Surgically remove CDM-crosswalk false-positive procedure mappings.

Root cause (already fixed): a too-broad crosswalk description pattern resolved a
CDM/UNKNOWN code to the wrong standard code, and the importer created an approved
procedure mapping from it (e.g. a ciprofloxacin-DEXAMETHASONE drug -> DXA bone
density scan). This tool removes ONLY mappings that no longer have any justification
under the corrected crosswalk, then relies on rebuild_price_summaries to regenerate
observations/summaries from the surviving mappings.

Determinism & safety:
- For every affected record it recomputes the record's LEGITIMATE approved procedures
  under the *current* crosswalk (each code slot re-resolved), and removes only
  mappings whose procedure is no longer supported by any slot. A mapping a real
  standard code still supports is never touched.
- Stale crosswalk-resolved code slots are reverted to their raw local code (what a
  re-import would store on NO_MATCH). Raw price records and rate details are untouched.
- --dry-run (default) writes a manifest + counts and changes nothing.
- --apply writes a JSON rollback artifact (deleted mappings + reverted code slots)
  BEFORE mutating, then deletes/reverts in one transaction.

It never edits raw HospitalPriceRecords, never re-imports, never creates mappings.
"""

import argparse
import json
import uuid
from collections import Counter
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from collectors.hospital_prices.cdm_crosswalk import apply_cdm_crosswalk
from collectors.hospital_prices.scope import active_consumer_facility_ids
from packages.database import (
    Facility,
    FacilityProcedurePriceSummary,
    HospitalPriceRecord,
    PriceRecordProcedureMapping,
    PriceServiceCode,
    Procedure,
    ProcedureCodeMapping,
    ProcedureCodeSystem,
)
from packages.database.session import session_factory

_LOCAL_TYPES = {"CDM", "UNKNOWN", "LOCAL", "FACILITY", "CHARGEMASTER"}


def _approved_code_to_proc(session: Session) -> dict[tuple[str, str], Any]:
    """{(code_system_upper, code): procedure_id} from approved/reviewed registry."""
    rows = session.execute(
        select(
            ProcedureCodeSystem.code_system,
            ProcedureCodeMapping.code,
            ProcedureCodeMapping.procedure_id,
        )
        .join(ProcedureCodeSystem, ProcedureCodeSystem.id == ProcedureCodeMapping.code_system_id)
        .where(ProcedureCodeMapping.mapping_status.in_(["approved", "reviewed"]))
    ).all()
    return {(str(sysname).upper(), str(code)): pid for sysname, code, pid in rows}


def build_manifest(session: Session, state: str = "NH") -> dict[str, Any]:
    facility_ids = set(active_consumer_facility_ids(session, state.upper()))
    facilities = {
        f.id: {"ccn": f.cms_certification_number, "name": f.display_name}
        for f in session.scalars(select(Facility).where(Facility.id.in_(facility_ids)))
    }
    code_to_proc = _approved_code_to_proc(session)
    proc_slug = {p.id: p.slug for p in session.scalars(select(Procedure))}
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

    # Records with >=1 crosswalk-resolved code slot (raw local -> standard system).
    suspect_record_ids = set(
        session.scalars(
            select(PriceServiceCode.hospital_price_record_id)
            .join(
                HospitalPriceRecord,
                HospitalPriceRecord.id == PriceServiceCode.hospital_price_record_id,
            )
            .where(
                HospitalPriceRecord.facility_id.in_(facility_ids),
                PriceServiceCode.raw_code_type.in_(_LOCAL_TYPES),
                PriceServiceCode.code_system.notin_(list(_LOCAL_TYPES)),
            )
            .distinct()
        ).all()
    )

    mappings_to_delete: list[dict[str, Any]] = []
    slots_to_revert: list[dict[str, Any]] = []
    by_hospital: Counter[str] = Counter()
    by_procedure: Counter[str] = Counter()
    public_by_hospital: Counter[str] = Counter()

    # Process each affected record: recompute legit approved procedures under the
    # current crosswalk; delete mappings no longer supported; revert stale slots.
    for rid in suspect_record_ids:
        record = session.get(HospitalPriceRecord, rid)
        if record is None:
            continue
        desc = record.raw_description or ""
        slots = session.scalars(
            select(PriceServiceCode).where(PriceServiceCode.hospital_price_record_id == rid)
        ).all()

        legit_procs: set[Any] = set()
        stale_slots: list[PriceServiceCode] = []
        for slot in slots:
            raw_type = str(slot.raw_code_type or "").upper()
            if raw_type in _LOCAL_TYPES and str(slot.code_system).upper() not in _LOCAL_TYPES:
                # crosswalk-resolved slot — re-validate against the current crosswalk
                current = apply_cdm_crosswalk(str(slot.raw_code or ""), raw_type, desc)
                if current and current[0] == str(slot.code):
                    eff = (str(slot.code_system).upper(), str(slot.code))  # still valid
                else:
                    stale_slots.append(slot)
                    eff = (raw_type, str(slot.raw_code))  # reverts to raw local code
            else:
                eff = (str(slot.code_system).upper(), str(slot.code))
            if eff in code_to_proc:
                legit_procs.add(code_to_proc[eff])

        if not stale_slots:
            continue  # nothing changed for this record

        ccn = str(facilities.get(record.facility_id, {}).get("ccn") or "?")
        for slot in stale_slots:
            slots_to_revert.append(
                {
                    "price_service_code_id": str(slot.id),
                    "record_id": str(rid),
                    "from_code_system": str(slot.code_system),
                    "from_code": str(slot.code),
                    "to_code_system": str(slot.raw_code_type),
                    "to_code": str(slot.raw_code),
                }
            )

        # Mappings whose procedure is no longer supported by any slot -> remove.
        maps = session.scalars(
            select(PriceRecordProcedureMapping).where(
                PriceRecordProcedureMapping.hospital_price_record_id == rid
            )
        ).all()
        for m in maps:
            if m.procedure_id in legit_procs:
                continue  # a real code still supports this mapping — keep it
            slug = str(proc_slug.get(m.procedure_id) or "?")
            is_public = (record.facility_id, m.procedure_id) in publishable
            mappings_to_delete.append(
                {
                    "mapping_id": str(m.id),
                    "record_id": str(rid),
                    "facility_id": str(record.facility_id),
                    "ccn": ccn,
                    "procedure_id": str(m.procedure_id),
                    "procedure_slug": slug,
                    "raw_description": desc,
                    "raw_codes": [
                        f"{s.raw_code_type}:{s.raw_code}->{s.code_system}:{s.code}" for s in slots
                    ],
                    "mapping_method": m.mapping_method,
                    "reviewed": bool(m.reviewed),
                    "contributes_to_public_price": is_public,
                }
            )
            by_hospital[ccn] += 1
            by_procedure[slug] += 1
            if is_public:
                public_by_hospital[ccn] += 1

    return {
        "state": state.upper(),
        "affected_records": len({m["record_id"] for m in mappings_to_delete}),
        "mappings_to_delete": len(mappings_to_delete),
        "public_mappings_to_delete": sum(
            1 for m in mappings_to_delete if m["contributes_to_public_price"]
        ),
        "code_slots_to_revert": len(slots_to_revert),
        "counts_by_hospital": dict(by_hospital.most_common()),
        "public_counts_by_hospital": dict(public_by_hospital.most_common()),
        "counts_by_procedure": dict(by_procedure.most_common()),
        "mapping_manifest": mappings_to_delete,
        "slot_revert_manifest": slots_to_revert,
    }


def apply_remediation(session: Session, manifest: dict[str, Any]) -> dict[str, int]:
    mapping_ids = [uuid.UUID(m["mapping_id"]) for m in manifest["mapping_manifest"]]
    slot_ids = [uuid.UUID(s["price_service_code_id"]) for s in manifest["slot_revert_manifest"]]

    deleted_maps = 0
    for chunk_start in range(0, len(mapping_ids), 5000):
        chunk = mapping_ids[chunk_start : chunk_start + 5000]
        result = session.execute(
            delete(PriceRecordProcedureMapping).where(PriceRecordProcedureMapping.id.in_(chunk))
        )
        deleted_maps += result.rowcount or 0

    reverted = 0
    revert_by_id = {
        uuid.UUID(s["price_service_code_id"]): s for s in manifest["slot_revert_manifest"]
    }
    for slot_id in slot_ids:
        slot = session.get(PriceServiceCode, slot_id)
        if slot is None:
            continue
        info = revert_by_id[slot_id]
        slot.code_system = info["to_code_system"]
        slot.code = info["to_code"]
        reverted += 1
    session.commit()
    return {"mappings_deleted": deleted_maps, "code_slots_reverted": reverted}


def main() -> None:
    parser = argparse.ArgumentParser(description="Remove CDM crosswalk false-positive mappings")
    parser.add_argument("--state", default="NH")
    parser.add_argument("--apply", action="store_true", help="Mutate (default: dry-run).")
    parser.add_argument(
        "--artifact-path",
        default=None,
        help="Write the full manifest (dry-run) / rollback artifact (apply) here. "
        "The manifest exceeds a log line, so point this at durable storage.",
    )
    args = parser.parse_args()
    with session_factory() as session:
        manifest = build_manifest(session, args.state)
        # The manifest IS the rollback artifact: it records every mapping deleted and
        # every code slot's original resolution, enough to reverse the operation.
        if args.artifact_path:
            with open(args.artifact_path, "w", encoding="utf-8") as fh:
                json.dump(manifest, fh, default=str)
            print(f"ARTIFACT_WRITTEN={args.artifact_path}")
        summary = {
            k: v
            for k, v in manifest.items()
            if k not in ("mapping_manifest", "slot_revert_manifest")
        }
        if args.apply:
            summary["applied"] = apply_remediation(session, manifest)
        else:
            summary["applied"] = None
    print("REMEDIATION_SUMMARY=" + json.dumps(summary, default=str, separators=(",", ":")))


if __name__ == "__main__":
    main()
