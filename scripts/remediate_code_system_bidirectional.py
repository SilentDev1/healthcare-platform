"""Bidirectional CPT<->HCPCS approved-code equivalence (evidence-based, reversible).

Extends the numeric CPT->HCPCS remediation (scripts.remediate_code_system_equivalence) to be
BIDIRECTIONAL and cover ALL approved CPT/HCPCS codes, not just 5-digit numerics. The exhaustive
false-negative audit surfaced a remaining class: hospitals publish a HCPCS Level-II code (e.g.
`G0438` = Medicare Annual Wellness Visit, initial) but LABEL it `CPT` in their MRF, while our
crosswalk stores it under `HCPCS` — so the exact (code_system, code) match drops it (Mary
Hitchcock, Cheshire AWV confirmed missing).

Why this is deterministic & safe (not fuzzy): CPT (Category I numeric = HCPCS Level I; Category
II `NNNNF`; Category III `NNNNT`) and HCPCS Level II (`[A-V]NNNN`) share ONE code namespace with
NO colliding values — a code value means the same service whichever system label a hospital
uses. So registering every approved CPT/HCPCS code under BOTH labels cannot create a wrong
mapping. It NEVER touches REV_CODE / MS_DRG / APC / ICD10PCS (distinct namespaces).

Reversible: rows are tagged version in {cpt_hcpcs_l1_equiv (prior), cpt_hcpcs_bidir_equiv}.

Run: python -m scripts.remediate_code_system_bidirectional [--apply]   (default: dry-run)
"""

from __future__ import annotations

# ruff: noqa: E501
import argparse
import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from packages.database import (
    Procedure,
    ProcedureCodeMapping,
    ProcedureCodeSystem,
    get_session,
    session_factory,
)

BIDIR_VERSION = "cpt_hcpcs_bidir_equiv"


def _get_or_create(session: Session, code_system: str, display: str) -> ProcedureCodeSystem:
    existing = session.scalar(
        select(ProcedureCodeSystem).where(ProcedureCodeSystem.code_system == code_system)
    )
    if existing is not None:
        return existing
    ref = session.scalar(select(ProcedureCodeSystem).where(ProcedureCodeSystem.code_system == "CPT"))
    row = ProcedureCodeSystem(
        code_system=code_system,
        display_name=display,
        licensing_notes="CPT (HCPCS Level I) and HCPCS Level II share one code namespace.",
        public_display_allowed=bool(ref.public_display_allowed) if ref else False,
        active=True,
    )
    session.add(row)
    session.flush()
    return row


def remediate(session: Session | None = None, *, apply: bool = False) -> dict[str, Any]:
    if session is None:
        session = next(get_session())
    cpt = _get_or_create(session, "CPT", "CPT (HCPCS Level I)")
    hcpcs = _get_or_create(session, "HCPCS", "HCPCS (incl. Level I = CPT)")
    proc_slug = {p.id: p.slug for p in session.scalars(select(Procedure))}
    sys_by_id = {cpt.id: cpt, hcpcs.id: hcpcs}
    other = {cpt.id: hcpcs, hcpcs.id: cpt}

    approved = session.execute(
        select(
            ProcedureCodeMapping.procedure_id,
            ProcedureCodeMapping.code_system_id,
            ProcedureCodeMapping.code,
        ).where(
            ProcedureCodeMapping.code_system_id.in_([cpt.id, hcpcs.id]),
            ProcedureCodeMapping.mapping_status.in_(["approved", "reviewed"]),
        )
    ).all()

    added: list[str] = []
    skipped_existing = 0
    for proc_id, sys_id, code in approved:
        if sys_id not in sys_by_id:
            continue
        target = other[sys_id]
        exists = session.scalar(
            select(ProcedureCodeMapping).where(
                ProcedureCodeMapping.procedure_id == proc_id,
                ProcedureCodeMapping.code_system_id == target.id,
                ProcedureCodeMapping.code == code,
            )
        )
        if exists is not None:
            skipped_existing += 1
            continue
        session.add(
            ProcedureCodeMapping(
                procedure_id=proc_id,
                code_system_id=target.id,
                code=code,
                mapping_status="approved",
                version=BIDIR_VERSION,
            )
        )
        added.append(f"{proc_slug.get(proc_id, proc_id)}:{target.code_system}:{code}")

    result: dict[str, Any] = {
        "status": "applied" if apply else "dry_run",
        "aliases_added": len(added),
        "skipped_existing": skipped_existing,
        "sample_added": sorted(added)[:25],
    }
    if apply:
        session.commit()
    else:
        session.rollback()
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Bidirectional CPT<->HCPCS approved-code aliases")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    with session_factory() as session:
        result = remediate(session, apply=args.apply)
    print("CODE_SYSTEM_BIDIR=" + json.dumps(result, default=str, separators=(",", ":")))


if __name__ == "__main__":
    main()
