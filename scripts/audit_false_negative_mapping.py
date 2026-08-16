"""Exhaustive false-negative mapping audit — 50 procedures x 26 NH hospitals = 1,300 cells.

Answers the release question the other gates do NOT: are we MISSING legitimate prices because a
hospital's terminology/code failed to map? Read-only. Never creates mappings.

Efficient + resumable by construction (the previous implementation timed out because it ran a
correlated NOT-EXISTS and LIKE scans across all 5.8M records at once):

  * Per-HOSPITAL sharding — each hospital's ~220k records are touched once.
  * Cell coverage (publishable / reviewed-mapped / approved-code-present) is computed with a
    handful of SET-BASED, index-friendly grouped queries per hospital (facility_id is indexed;
    the approved (system,code) IN-list is bounded).
  * Candidate discovery runs a description LIKE scoped to ONE facility_id AND only for the
    procedures still UNCOVERED at that hospital (a small set) — no scan of all 5.8M, no
    correlated subquery.
  * Each hospital's result is printed as `PHAUDIT=<ccn>|<json>` the moment it finishes and
    flushed, so a timeout never loses completed work. Re-run with `--skip-ccns` (or read the
    completed CCNs from Cloud Logging) to resume; only missing hospitals recompute.

Per (procedure, hospital) cell classification (the six required states):
  PUBLISHING_VERIFIED_PRICE            — publishable summary exists
  MATCHING_APPROVED_RAW_RECORD_NO_SUMMARY — reviewed mapping exists but no publishable summary
  KNOWN_CODE_NOT_MAPPED                — an APPROVED code for the procedure is in the raw data,
                                         but no reviewed mapping was made
  REVIEW_REQUIRED                      — a description candidate carries a STANDARD billing code
                                         (CPT/HCPCS/*DRG/APC/ICD10PCS) not in our approved set
  DESCRIPTION_CANDIDATE_NOT_MAPPED     — description matches the procedure's terminology, only a
                                         local/CDM/unknown code
  NO_MATCHING_RAW_RECORD               — hospital has data but nothing matches this procedure

Run (single execution, all NH hospitals):
    gcloud run jobs execute carevero-beta-price-audit --region=us-east4 \
        --args="-m,scripts.audit_false_negative_mapping,--state,NH"
Resume (skip already-emitted hospitals):
    ...,--state,NH,--skip-ccns,300001,300003,...
"""

from __future__ import annotations

# ruff: noqa: E501
import argparse
import json
import sys
from collections import Counter, defaultdict
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, or_, select, tuple_
from sqlalchemy.orm import Session

from collectors.hospital_prices.scope import active_consumer_facility_ids
from packages.database import (
    Facility,
    FacilityProcedurePriceSummary,
    HospitalPriceRecord,
    PriceServiceCode,
    Procedure,
    ProcedureCodeMapping,
    ProcedureCodeSystem,
    session_factory,
)
from packages.database.pricing_models import PriceRecordProcedureMapping
from scripts.audit_procedure_mapping_coverage import _STANDARD_SYSTEMS, DISCOVERY_KEYWORDS

CATEGORIES = (
    "PUBLISHING_VERIFIED_PRICE",
    "MATCHING_APPROVED_RAW_RECORD_NO_SUMMARY",
    "KNOWN_CODE_NOT_MAPPED",
    "REVIEW_REQUIRED",
    "DESCRIPTION_CANDIDATE_NOT_MAPPED",
    "NO_MATCHING_RAW_RECORD",
)


def _procedures(session: Session) -> dict[Any, dict[str, Any]]:
    return {
        p.id: {"slug": p.slug, "consumer_name": p.consumer_name, "service_setting": p.service_setting}
        for p in session.scalars(select(Procedure).where(Procedure.active.is_(True)))
    }


def _approved_codes(session: Session) -> dict[Any, list[tuple[str, str]]]:
    codes: dict[Any, list[tuple[str, str]]] = defaultdict(list)
    for mapping, system in session.execute(
        select(ProcedureCodeMapping, ProcedureCodeSystem)
        .join(ProcedureCodeSystem, ProcedureCodeMapping.code_system_id == ProcedureCodeSystem.id)
        .where(ProcedureCodeMapping.mapping_status.in_(["approved", "reviewed"]))
    ).all():
        codes[mapping.procedure_id].append((system.code_system, mapping.code))
    return codes


def _desc_expr() -> Any:
    return func.lower(
        func.coalesce(
            HospitalPriceRecord.service_description_normalized, HospitalPriceRecord.raw_description
        )
    )


def audit_hospital(
    session: Session,
    facility_id: Any,
    procedures: dict[Any, dict[str, Any]],
    approved: dict[Any, list[tuple[str, str]]],
    code_to_procs: dict[tuple[str, str], set[Any]],
    approved_pairs: list[tuple[str, str]],
    candidate_sample: int,
) -> dict[Any, dict[str, Any]]:
    """Classify all 50 procedures for ONE hospital. Returns {proc_id: cell}."""
    slug_to_proc = {m["slug"]: pid for pid, m in procedures.items()}

    has_records = (
        session.scalar(
            select(func.count(HospitalPriceRecord.id)).where(
                HospitalPriceRecord.facility_id == facility_id
            )
        )
        or 0
    )

    # (1) publishable procedures
    pub = set(
        session.scalars(
            select(FacilityProcedurePriceSummary.procedure_id)
            .where(
                FacilityProcedurePriceSummary.facility_id == facility_id,
                FacilityProcedurePriceSummary.publication_status == "publishable",
            )
            .distinct()
        )
    )

    # (2) reviewed-mapped procedures
    reviewed: dict[Any, int] = {}
    for pid, cnt in session.execute(
        select(PriceRecordProcedureMapping.procedure_id, func.count())
        .join(
            HospitalPriceRecord,
            HospitalPriceRecord.id == PriceRecordProcedureMapping.hospital_price_record_id,
        )
        .where(
            HospitalPriceRecord.facility_id == facility_id,
            PriceRecordProcedureMapping.reviewed.is_(True),
        )
        .group_by(PriceRecordProcedureMapping.procedure_id)
    ).all():
        reviewed[pid] = cnt

    # (3) approved-code presence per procedure (bounded IN-list, one grouped query)
    approved_present: dict[Any, dict[str, Any]] = {}
    if approved_pairs:
        for system, code, sample_desc, cnt in session.execute(
            select(
                PriceServiceCode.code_system,
                PriceServiceCode.code,
                func.min(HospitalPriceRecord.raw_description),
                func.count(),
            )
            .join(
                HospitalPriceRecord,
                HospitalPriceRecord.id == PriceServiceCode.hospital_price_record_id,
            )
            .where(
                HospitalPriceRecord.facility_id == facility_id,
                tuple_(PriceServiceCode.code_system, PriceServiceCode.code).in_(approved_pairs),
            )
            .group_by(PriceServiceCode.code_system, PriceServiceCode.code)
        ).all():
            for pid in code_to_procs.get((system, code), ()):
                cell = approved_present.setdefault(
                    pid, {"count": 0, "codes": set(), "sample": sample_desc}
                )
                cell["count"] += cnt
                cell["codes"].add(f"{system}:{code}")

    covered = pub | set(reviewed) | set(approved_present)

    # (4) candidate discovery — ONLY for uncovered procedures, scoped to this facility.
    candidates: dict[Any, list[dict[str, Any]]] = {}
    for slug, keywords in DISCOVERY_KEYWORDS.items():
        pid = slug_to_proc.get(slug)
        if pid is None or pid in covered:
            continue
        like = [_desc_expr().like(f"%{kw}%") for kw in keywords]
        rows = session.execute(
            select(
                PriceServiceCode.code_system,
                PriceServiceCode.code,
                func.min(HospitalPriceRecord.raw_description),
                func.count(),
            )
            .select_from(HospitalPriceRecord)
            .outerjoin(
                PriceServiceCode,
                PriceServiceCode.hospital_price_record_id == HospitalPriceRecord.id,
            )
            .where(HospitalPriceRecord.facility_id == facility_id, or_(*like))
            .group_by(PriceServiceCode.code_system, PriceServiceCode.code)
            .order_by(func.count().desc())
            .limit(candidate_sample)
        ).all()
        if rows:
            candidates[pid] = [
                {
                    "code_system": str(cs) if cs else "UNKNOWN",
                    "code": str(c) if c else None,
                    "raw_description": desc,
                    "count": cnt,
                }
                for cs, c, desc, cnt in rows
            ]

    # (5) classify every procedure
    cells: dict[Any, dict[str, Any]] = {}
    for pid, meta in procedures.items():
        out_cell: dict[str, Any] = {"procedure": meta["slug"]}
        if pid in pub:
            out_cell["category"] = "PUBLISHING_VERIFIED_PRICE"
        elif pid in reviewed:
            out_cell["category"] = "MATCHING_APPROVED_RAW_RECORD_NO_SUMMARY"
            out_cell["reviewed_records"] = reviewed[pid]
        elif pid in approved_present:
            out_cell["category"] = "KNOWN_CODE_NOT_MAPPED"
            out_cell["approved_codes_in_data"] = sorted(approved_present[pid]["codes"])
            out_cell["raw_description"] = approved_present[pid]["sample"]
        elif pid in candidates:
            clist = candidates[pid]
            systems = {c["code_system"] for c in clist}
            out_cell["candidates"] = clist
            if systems & _STANDARD_SYSTEMS:
                out_cell["category"] = "REVIEW_REQUIRED"
            else:
                out_cell["category"] = "DESCRIPTION_CANDIDATE_NOT_MAPPED"
        elif has_records:
            out_cell["category"] = "NO_MATCHING_RAW_RECORD"
        else:
            out_cell["category"] = "NO_MATCHING_RAW_RECORD"
        cells[pid] = out_cell
    return cells


def run(
    session: Session, state: str, candidate_sample: int, skip_ccns: set[str]
) -> dict[str, Any]:
    procedures = _procedures(session)
    approved = _approved_codes(session)
    code_to_procs: dict[tuple[str, str], set[Any]] = defaultdict(set)
    for pid, pairs in approved.items():
        for pair in pairs:
            code_to_procs[pair].add(pid)
    approved_pairs = list(code_to_procs)

    facility_ids = active_consumer_facility_ids(session, state.upper())
    facilities = {
        f.id: {"name": f.display_name, "ccn": f.cms_certification_number}
        for f in session.scalars(select(Facility).where(Facility.id.in_(facility_ids)))
    }

    all_cells: list[dict[str, Any]] = []
    per_hospital_done = 0
    for fid, fmeta in facilities.items():
        ccn = fmeta["ccn"]
        if ccn in skip_ccns:
            continue
        cells = audit_hospital(
            session, fid, procedures, approved, code_to_procs, approved_pairs, candidate_sample
        )
        hist: Counter[str] = Counter()
        rows = []
        for cell in cells.values():
            cell["hospital"] = fmeta["name"]
            cell["ccn"] = ccn
            hist[cell["category"]] += 1
            rows.append(cell)
            all_cells.append(cell)
        # Emit per-hospital result immediately (resumable checkpoint via logs).
        print(
            "PHAUDIT="
            + json.dumps(
                {"ccn": ccn, "hospital": fmeta["name"], "histogram": dict(hist), "cells": rows},
                default=str,
                separators=(",", ":"),
            ),
            flush=True,
        )
        per_hospital_done += 1

    overall: Counter[str] = Counter()
    for c in all_cells:
        overall[c["category"]] += 1
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "state": state.upper(),
        "hospitals_audited": per_hospital_done,
        "procedures": len(procedures),
        "cells": len(all_cells),
        "overall_histogram": dict(overall),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state", default="NH")
    parser.add_argument("--candidate-sample", type=int, default=5)
    parser.add_argument("--skip-ccns", default="", help="comma-separated CCNs already completed")
    args = parser.parse_args()
    skip = {c.strip() for c in args.skip_ccns.split(",") if c.strip()}
    with session_factory() as session:
        summary = run(session, args.state, args.candidate_sample, skip)
    print("FN_AUDIT_SUMMARY=" + json.dumps(summary, default=str, separators=(",", ":")), flush=True)
    # Non-zero exit if nothing was audited (so a silent no-op is visible).
    if summary["hospitals_audited"] == 0 and not skip:
        sys.exit(2)


if __name__ == "__main__":
    main()
