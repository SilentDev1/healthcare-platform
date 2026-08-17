"""Remediate the CPT vs HCPCS-Level-I code-system labeling gap (evidence-based, reversible).

The exhaustive false-negative audit (scripts.audit_false_negative_mapping) proved that four NH
hospitals (Elliot, Exeter, Monadnock, Southern NH Medical Center) publish standard procedure
codes LABELED as `HCPCS` in their machine-readable files — e.g. `HCPCS:85025` "Complete cbc
automated", `HCPCS:71250` "CT CHEST W/O CONTRAST", `HCPCS:72148` "Mri lumbar spine w/o dye".
Our approved crosswalk stores those same codes under `CPT`, so the exact `(code_system, code)`
match drops them and their real prices never reach consumers.

This is a DETERMINISTIC, AUTHORITATIVE equivalence, not a fuzzy match: the AMA CPT code set
(5-digit numeric, 00100-99999) IS HCPCS Level I. `HCPCS:85025` and `CPT:85025` are the same
procedure by definition.

Remediation (additive, reviewable, reversible): for every APPROVED `CPT:NNNNN` mapping whose
code is exactly 5 numeric digits, register the equivalent `HCPCS:NNNNN` approved mapping to the
SAME procedure, tagged `version="cpt_hcpcs_l1_equiv"`. It does NOT touch price records, rate
details, existing mappings, or any non-numeric / Level-II (alphanumeric, e.g. G0438, J1100) or
REV_CODE / MS_DRG code. The existing reproject + summary-rebuild pipeline then matches the
HCPCS-labeled raw records exactly as it already does for CPT.

Reverse: delete ProcedureCodeMapping rows with version="cpt_hcpcs_l1_equiv".

Run: python -m scripts.remediate_code_system_equivalence [--apply]   (default: dry-run)
"""

from __future__ import annotations

# ruff: noqa: E501
import argparse
import json
import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from packages.database import (
    Procedure,
    ProcedureCodeMapping,
    ProcedureCodeSystem,
    get_session,
    session_factory,
)

EQUIV_VERSION = "cpt_hcpcs_l1_equiv"
_NUMERIC_CPT = re.compile(r"^\d{5}$")


def _get_or_create_hcpcs(session: Session) -> ProcedureCodeSystem:
    hcpcs = session.scalar(
        select(ProcedureCodeSystem).where(ProcedureCodeSystem.code_system == "HCPCS")
    )
    if hcpcs is not None:
        return hcpcs
    cpt = session.scalar(select(ProcedureCodeSystem).where(ProcedureCodeSystem.code_system == "CPT"))
    hcpcs = ProcedureCodeSystem(
        code_system="HCPCS",
        display_name="HCPCS (incl. Level I = CPT)",
        licensing_notes="HCPCS Level I is the AMA CPT code set; numeric 5-digit codes are CPT.",
        public_display_allowed=bool(cpt.public_display_allowed) if cpt else False,
        active=True,
    )
    session.add(hcpcs)
    session.flush()
    return hcpcs


def remediate(session: Session | None = None, *, apply: bool = False) -> dict[str, object]:
    if session is None:
        session = next(get_session())
    hcpcs = _get_or_create_hcpcs(session)
    proc_slug = {p.id: p.slug for p in session.scalars(select(Procedure))}

    cpt_sys = session.scalar(select(ProcedureCodeSystem).where(ProcedureCodeSystem.code_system == "CPT"))
    if cpt_sys is None:
        return {"status": "no_cpt_system"}

    approved_cpt = session.execute(
        select(ProcedureCodeMapping.procedure_id, ProcedureCodeMapping.code).where(
            ProcedureCodeMapping.code_system_id == cpt_sys.id,
            ProcedureCodeMapping.mapping_status.in_(["approved", "reviewed"]),
        )
    ).all()

    added: list[str] = []
    skipped_existing = 0
    skipped_non_numeric = 0
    for proc_id, code in approved_cpt:
        if not _NUMERIC_CPT.match(code):
            skipped_non_numeric += 1
            continue
        exists = session.scalar(
            select(ProcedureCodeMapping).where(
                ProcedureCodeMapping.procedure_id == proc_id,
                ProcedureCodeMapping.code_system_id == hcpcs.id,
                ProcedureCodeMapping.code == code,
            )
        )
        if exists is not None:
            skipped_existing += 1
            continue
        session.add(
            ProcedureCodeMapping(
                procedure_id=proc_id,
                code_system_id=hcpcs.id,
                code=code,
                mapping_status="approved",
                version=EQUIV_VERSION,
            )
        )
        added.append(f"{proc_slug.get(proc_id, proc_id)}:HCPCS:{code}")

    result: dict[str, object] = {
        "status": "applied" if apply else "dry_run",
        "hcpcs_aliases_added": len(added),
        "skipped_existing": skipped_existing,
        "skipped_non_numeric_cpt": skipped_non_numeric,
        "sample_added": sorted(added)[:20],
    }
    if apply:
        session.commit()
    else:
        session.rollback()
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Add CPT->HCPCS Level-I equivalence aliases")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    with session_factory() as session:
        result = remediate(session, apply=args.apply)
    print("CODE_SYSTEM_EQUIV=" + json.dumps(result, default=str, separators=(",", ":")))


if __name__ == "__main__":
    main()
