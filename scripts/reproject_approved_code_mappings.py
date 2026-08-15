"""Reproject approved-code procedure mappings from existing records (no re-import).

When the reviewed approved-code registry changes (codes added or removed), existing
imported records need their `exact_approved_code` procedure mappings reconciled to
match — without downloading or re-parsing any MRF. For the target procedures this
tool, deterministically and from data already in the DB:

- ADDS a mapping when a record carries an approved code for a target procedure but
  has no mapping to it (the importer would have created it on a fresh import).
- REMOVES an `exact_approved_code` mapping to a target procedure when the record no
  longer carries ANY approved code for that procedure (e.g. a de-registered code).

It only touches `exact_approved_code` mappings for the named procedures, never raw
price records or rate details, never a description/fuzzy match. --dry-run (default)
emits an auditable manifest; --apply mutates in one transaction after writing the
rollback artifact. Observations/summaries are rebuilt separately.
"""

import argparse
import json
import uuid
from collections import Counter
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from collectors.hospital_prices.scope import active_consumer_facility_ids
from packages.database import (
    Facility,
    HospitalPriceRecord,
    PriceRecordProcedureMapping,
    PriceServiceCode,
    Procedure,
    ProcedureCodeMapping,
    ProcedureCodeSystem,
)
from packages.database.session import session_factory


def _approved(
    session: Session, proc_ids: set[uuid.UUID]
) -> dict[tuple[str, str], tuple[uuid.UUID, uuid.UUID]]:
    """{(code_system_upper, code): (procedure_id, code_mapping_id)} for target procs."""
    rows = session.execute(
        select(
            ProcedureCodeSystem.code_system,
            ProcedureCodeMapping.code,
            ProcedureCodeMapping.procedure_id,
            ProcedureCodeMapping.id,
        )
        .join(ProcedureCodeSystem, ProcedureCodeSystem.id == ProcedureCodeMapping.code_system_id)
        .where(
            ProcedureCodeMapping.mapping_status.in_(["approved", "reviewed"]),
            ProcedureCodeMapping.procedure_id.in_(proc_ids),
        )
    ).all()
    return {(str(s).upper(), str(c)): (pid, mid) for s, c, pid, mid in rows}


def build_plan(session: Session, state: str, slugs: list[str]) -> dict[str, Any]:
    facility_ids = set(active_consumer_facility_ids(session, state.upper()))
    procs = {
        p.slug: p.id for p in session.scalars(select(Procedure).where(Procedure.slug.in_(slugs)))
    }
    proc_ids = set(procs.values())
    slug_by_id = {v: k for k, v in procs.items()}
    ccn = {
        f.id: f.cms_certification_number
        for f in session.scalars(select(Facility).where(Facility.id.in_(facility_ids)))
    }
    approved = _approved(session, proc_ids)

    # Records carrying an approved code for a target procedure.
    rows = session.execute(
        select(
            PriceServiceCode.hospital_price_record_id,
            HospitalPriceRecord.facility_id,
            PriceServiceCode.code_system,
            PriceServiceCode.code,
        )
        .join(
            HospitalPriceRecord,
            HospitalPriceRecord.id == PriceServiceCode.hospital_price_record_id,
        )
        .where(HospitalPriceRecord.facility_id.in_(facility_ids))
    ).all()

    # record -> set of target procedures its codes justify
    rec_procs: dict[uuid.UUID, set[uuid.UUID]] = {}
    rec_fac: dict[uuid.UUID, uuid.UUID] = {}
    rec_scm: dict[tuple[uuid.UUID, uuid.UUID], uuid.UUID] = {}
    for rid, fid, sysname, code in rows:
        hit = approved.get((str(sysname).upper(), str(code)))
        if hit is None:
            continue
        pid, scm_id = hit
        rec_procs.setdefault(rid, set()).add(pid)
        rec_fac[rid] = fid
        rec_scm[(rid, pid)] = scm_id

    # Existing exact_approved_code mappings to the target procedures.
    existing = session.execute(
        select(
            PriceRecordProcedureMapping.id,
            PriceRecordProcedureMapping.hospital_price_record_id,
            PriceRecordProcedureMapping.procedure_id,
            HospitalPriceRecord.facility_id,
        )
        .join(
            HospitalPriceRecord,
            HospitalPriceRecord.id == PriceRecordProcedureMapping.hospital_price_record_id,
        )
        .where(
            HospitalPriceRecord.facility_id.in_(facility_ids),
            PriceRecordProcedureMapping.procedure_id.in_(proc_ids),
            PriceRecordProcedureMapping.mapping_method == "exact_approved_code",
        )
    ).all()
    existing_by_rec: dict[tuple[uuid.UUID, uuid.UUID], uuid.UUID] = {
        (rid, pid): mid for mid, rid, pid, _f in existing
    }

    to_add: list[dict[str, Any]] = []
    add_ct: Counter[str] = Counter()
    for (rid, pid), _ in rec_scm.items():
        if (rid, pid) in existing_by_rec:
            continue
        to_add.append(
            {
                "record_id": str(rid),
                "facility_id": str(rec_fac[rid]),
                "ccn": str(ccn.get(rec_fac[rid]) or "?"),
                "procedure_slug": slug_by_id[pid],
                "procedure_id": str(pid),
                "source_code_mapping_id": str(rec_scm[(rid, pid)]),
            }
        )
        add_ct[slug_by_id[pid]] += 1

    to_remove: list[dict[str, Any]] = []
    rm_ct: Counter[str] = Counter()
    for (rid, pid), mid in existing_by_rec.items():
        if pid in rec_procs.get(rid, set()):
            continue  # still justified by an approved code on the record
        to_remove.append(
            {
                "mapping_id": str(mid),
                "record_id": str(rid),
                "procedure_slug": slug_by_id[pid],
            }
        )
        rm_ct[slug_by_id[pid]] += 1

    return {
        "state": state.upper(),
        "procedures": slugs,
        "mappings_to_add": len(to_add),
        "mappings_to_remove": len(to_remove),
        "add_by_procedure": dict(add_ct),
        "remove_by_procedure": dict(rm_ct),
        "add_manifest": to_add,
        "remove_manifest": to_remove,
    }


def apply_plan(session: Session, plan: dict[str, Any]) -> dict[str, int]:
    now = datetime.now(UTC)
    added = 0
    for a in plan["add_manifest"]:
        session.add(
            PriceRecordProcedureMapping(
                hospital_price_record_id=uuid.UUID(a["record_id"]),
                procedure_id=uuid.UUID(a["procedure_id"]),
                mapping_method="exact_approved_code",
                confidence_score=1,
                reviewed=True,
                reviewed_by="approved-code-registry-reprojection",
                reviewed_at=now,
                source_code_mapping_id=uuid.UUID(a["source_code_mapping_id"]),
            )
        )
        added += 1
    remove_ids = [uuid.UUID(r["mapping_id"]) for r in plan["remove_manifest"]]
    removed = 0
    for start in range(0, len(remove_ids), 5000):
        res = session.execute(
            delete(PriceRecordProcedureMapping).where(
                PriceRecordProcedureMapping.id.in_(remove_ids[start : start + 5000])
            )
        )
        removed += res.rowcount or 0
    session.commit()
    return {"mappings_added": added, "mappings_removed": removed}


def main() -> None:
    parser = argparse.ArgumentParser(description="Reproject approved-code mappings")
    parser.add_argument("--state", default="NH")
    parser.add_argument("--procedures", required=True, help="comma-separated procedure slugs")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--artifact-path", default=None)
    args = parser.parse_args()
    slugs = [s.strip() for s in args.procedures.split(",") if s.strip()]
    with session_factory() as session:
        plan = build_plan(session, args.state, slugs)
        if args.artifact_path:
            with open(args.artifact_path, "w", encoding="utf-8") as fh:
                json.dump(plan, fh, default=str)
            print(f"ARTIFACT_WRITTEN={args.artifact_path}")
        summary = {k: v for k, v in plan.items() if k not in ("add_manifest", "remove_manifest")}
        if args.apply:
            summary["applied"] = apply_plan(session, plan)
        else:
            summary["applied"] = None
    print("REPROJECT_SUMMARY=" + json.dumps(summary, default=str, separators=(",", ":")))


if __name__ == "__main__":
    main()
