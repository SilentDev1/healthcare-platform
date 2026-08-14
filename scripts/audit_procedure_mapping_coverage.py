"""Systematic procedure terminology / crosswalk coverage audit (read-only).

For every canonical Carevero procedure x hospital, this inspects the ACTUAL
normalized/raw pricing records — not merely whether a publishable summary exists —
and classifies why the service is or is not covered. It answers the acceptance
question: can we distinguish "Carevero couldn't find the hospital's terminology"
from "the hospital data genuinely has no safely comparable published price"?

Two signals are computed SEPARATELY and never conflated:

  1. APPROVED-CODE coverage — deterministic: does the hospital publish a reviewed,
     approved-code price for the procedure (the only path to consumer visibility)?
  2. CANDIDATE discovery — keyword/description matching over records that are NOT
     approved-mapped. These are *candidates for human review only*. A description
     match (e.g. "delivery services") is NEVER treated as a mapping; discovery and
     approved mapping are kept strictly apart, per policy.

Per (procedure, hospital) cell it emits a matrix row and a root cause:
  NO_SOURCE_DATA, NO_MATCHING_RAW_RECORD, KNOWN_CODE_NOT_MAPPED,
  DESCRIPTION_VARIANT_NOT_MAPPED, LOCAL_CODE_NEEDS_REVIEW, COMPONENT_ONLY,
  SETTING_MISMATCH, PUBLISHABILITY_FILTER, SUMMARY_BUILD_GAP, OTHER, or NONE
  (already covered).

Strictly read-only: no writes, no automatic mapping. Run in prod via the
read-only price-audit job:

    gcloud run jobs execute carevero-beta-price-audit --region=us-east4 \
        --args="-m,scripts.audit_procedure_mapping_coverage,--state,NH"
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import and_, exists, func, select
from sqlalchemy.orm import Session

from collectors.hospital_prices.scope import active_consumer_facility_ids
from packages.database import (
    Facility,
    FacilityProcedurePriceObservation,
    FacilityProcedurePriceSummary,
    HospitalPriceRecord,
    PriceRecordProcedureMapping,
    PriceServiceCode,
    Procedure,
    ProcedureCodeMapping,
    ProcedureCodeSystem,
    session_factory,
)

# --------------------------------------------------------------------------- #
# Candidate-discovery keywords (FOR REVIEW ONLY — never an approved mapping).
# Lowercased substrings that plausibly indicate a hospital is publishing the
# service under alternate terminology. Deterministic and transparent; used only
# to surface records for a human to review, not to promote anything to consumer
# pricing. Kept deliberately specific to limit obvious false positives, but every
# hit is a CANDIDATE, never a decision.
# --------------------------------------------------------------------------- #
DISCOVERY_KEYWORDS: dict[str, tuple[str, ...]] = {
    "mri-brain-without-contrast": ("mri brain", "brain mri", "mri head", "mr brain"),
    "mri-knee-without-contrast": ("mri knee", "knee mri", "mr knee"),
    "mri-lumbar-spine-without-contrast": ("mri lumbar", "lumbar mri", "mri l-spine", "mri l spine"),
    "ct-abdomen-pelvis": ("ct abdomen", "ct abd", "abdomen and pelvis", "ct abdomen/pelvis"),
    "ct-chest": ("ct chest", "chest ct", "ct thorax"),
    "chest-x-ray": ("chest x-ray", "chest xray", "xr chest", "chest radiograph", "cxr"),
    "screening-mammogram": ("screening mammogram", "mammogram screening", "screening mammo"),
    "diagnostic-mammogram": ("diagnostic mammogram", "mammogram diagnostic", "diagnostic mammo"),
    "abdominal-ultrasound": ("ultrasound abdomen", "abdominal ultrasound", "us abdomen", "abd us"),
    "pelvic-ultrasound": ("pelvic ultrasound", "ultrasound pelvic", "us pelvis", "pelvis us"),
    "colonoscopy": ("colonoscopy",),
    "upper-endoscopy": ("upper endoscopy", "egd", "esophagogastroduodenoscopy"),
    "cataract-surgery": ("cataract",),
    "hernia-repair": ("hernia repair", "herniorrhaphy", "hernia"),
    "gallbladder-removal": ("cholecystectomy", "gallbladder removal", "lap chole"),
    "knee-replacement": ("knee replacement", "knee arthroplasty", "total knee", "tka"),
    "hip-replacement": ("hip replacement", "hip arthroplasty", "total hip", "tha"),
    "carpal-tunnel-release": ("carpal tunnel",),
    "rotator-cuff-repair": ("rotator cuff",),
    "vaginal-delivery": ("vaginal delivery", "vaginal deliv", "spontaneous vaginal", "svd"),
    "cesarean-delivery": ("cesarean", "c-section", "c section", "cesarian", "csection"),
    "ed-visit-level-1": ("emergency dept", "emergency department", "ed visit", "er visit"),
    "ed-visit-level-2": ("emergency dept", "emergency department", "ed visit", "er visit"),
    "ed-visit-level-3": ("emergency dept", "emergency department", "ed visit", "er visit"),
    "ed-visit-level-4": ("emergency dept", "emergency department", "ed visit", "er visit"),
    "ed-visit-level-5": ("emergency dept", "emergency department", "ed visit", "er visit"),
    "electrocardiogram": ("electrocardiogram", "ekg", "ecg", "12 lead"),
    "echocardiogram": ("echocardiogram", "echocardiography", "echo "),
    "cardiac-stress-test": ("stress test", "cardiac stress", "exercise stress"),
    "cardiac-catheterization": ("cardiac cath", "heart catheterization", "coronary angiogra"),
    "complete-blood-count": ("complete blood count", "cbc", "hemogram", "blood count"),
    "basic-metabolic-panel": ("basic metabolic", "bmp ", "metabolic panel basic"),
    "comprehensive-metabolic-panel": ("comprehensive metabolic", "cmp ", "metabolic panel comp"),
    "lipid-panel": ("lipid panel", "lipid profile", "cholesterol panel", "lipids"),
    "a1c-test": ("a1c", "hemoglobin a1c", "hgb a1c", "glycohemoglobin"),
    "thyroid-test": ("tsh", "thyroid stimulating", "thyrotropin"),
    "urinalysis": ("urinalysis", "urine analysis", "ua "),
    "pregnancy-test": ("pregnancy test", "hcg", "beta hcg"),
    "strep-test": ("strep", "streptococcus"),
    "covid-test": ("covid", "sars-cov-2", "sars cov 2"),
    "surgical-pathology": ("surgical pathology", "pathology tissue", "path exam tissue"),
    "pap-test": ("pap smear", "pap test", "cervical cytology", "papanicolaou"),
    "bone-density-scan": ("bone density", "dexa", "dxa "),
    "physical-therapy-evaluation": (
        "physical therapy eval",
        "pt evaluation",
        "physical therapy evaluation",
    ),
    "sleep-study": ("sleep study", "polysomnography", "polysomnogram"),
    "allergy-testing": ("allergy test", "allergen", "percutaneous allergy"),
    "flu-vaccine": ("flu vaccine", "influenza vaccine", "influenza virus vaccine"),
    "annual-wellness-visit": ("wellness visit", "annual wellness", "awv"),
    "dialysis-session": ("dialysis", "hemodialysis"),
}

ROOT_CAUSES = (
    "NONE",
    "NO_SOURCE_DATA",
    "NO_MATCHING_RAW_RECORD",
    "KNOWN_CODE_NOT_MAPPED",
    "DESCRIPTION_VARIANT_NOT_MAPPED",
    "LOCAL_CODE_NEEDS_REVIEW",
    "COMPONENT_ONLY",
    "SETTING_MISMATCH",
    "PUBLISHABILITY_FILTER",
    "SUMMARY_BUILD_GAP",
    "OTHER",
)

# Code systems that carry an authoritative billing identifier (a candidate with one
# of these is a KNOWN_CODE variant to review; otherwise it is a local/proprietary
# code needing review, or a pure description variant).
_STANDARD_SYSTEMS = frozenset({"CPT", "HCPCS", "MS_DRG", "APR_DRG", "APC", "ICD10PCS"})


def _procedures(session: Session) -> dict[Any, dict[str, Any]]:
    return {
        proc.id: {
            "slug": proc.slug,
            "consumer_name": proc.consumer_name,
            "service_setting": proc.service_setting,
        }
        for proc in session.scalars(select(Procedure).where(Procedure.active.is_(True)))
    }


def _approved_codes(session: Session) -> dict[Any, list[tuple[str, str]]]:
    """{procedure_id: [(code_system, code), ...]} from the reviewed/approved registry."""
    codes: dict[Any, list[tuple[str, str]]] = defaultdict(list)
    for mapping, system in session.execute(
        select(ProcedureCodeMapping, ProcedureCodeSystem)
        .join(ProcedureCodeSystem, ProcedureCodeMapping.code_system_id == ProcedureCodeSystem.id)
        .where(ProcedureCodeMapping.mapping_status.in_(["approved", "reviewed"]))
    ).all():
        codes[mapping.procedure_id].append((system.code_system, mapping.code))
    return codes


def _publishable_cells(
    session: Session, facility_ids: set[Any]
) -> dict[tuple[Any, Any], dict[str, Any]]:
    """{(facility_id, procedure_id): {settings, scopes}} for publishable summaries."""
    cells: dict[tuple[Any, Any], dict[str, Any]] = {}
    for row in session.execute(
        select(
            FacilityProcedurePriceSummary.facility_id,
            FacilityProcedurePriceSummary.procedure_id,
            func.count(FacilityProcedurePriceSummary.id),
        )
        .where(
            FacilityProcedurePriceSummary.facility_id.in_(facility_ids),
            FacilityProcedurePriceSummary.publication_status == "publishable",
        )
        .group_by(
            FacilityProcedurePriceSummary.facility_id,
            FacilityProcedurePriceSummary.procedure_id,
        )
    ).all():
        cells[(row[0], row[1])] = {"summaries": row[2]}
    return cells


def _facility_record_counts(session: Session, facility_ids: set[Any]) -> dict[Any, int]:
    return {
        row[0]: row[1]
        for row in session.execute(
            select(HospitalPriceRecord.facility_id, func.count(HospitalPriceRecord.id))
            .where(HospitalPriceRecord.facility_id.in_(facility_ids))
            .group_by(HospitalPriceRecord.facility_id)
        ).all()
    }


def _approved_code_hits(
    session: Session, facility_ids: set[Any], approved: dict[Any, list[tuple[str, str]]]
) -> dict[tuple[Any, Any], dict[str, Any]]:
    """For each (facility, procedure), records whose PriceServiceCode is a canonical
    code — separated into whether a reviewed mapping to that procedure exists.

    This is the DETERMINISTIC coverage signal: an approved code present in the raw
    data, with or without a reviewed mapping.
    """
    # Reverse map (system, code) -> {procedure_ids}
    code_to_procs: dict[tuple[str, str], set[Any]] = defaultdict(set)
    for proc_id, pairs in approved.items():
        for system, code in pairs:
            code_to_procs[(system, code)].add(proc_id)
    all_pairs = list(code_to_procs)
    if not all_pairs:
        return {}

    reviewed_for_proc = exists().where(
        and_(
            PriceRecordProcedureMapping.hospital_price_record_id == HospitalPriceRecord.id,
            PriceRecordProcedureMapping.reviewed.is_(True),
        )
    )
    hits: dict[tuple[Any, Any], dict[str, Any]] = {}
    # One query per code keeps the IN-list small and index-friendly.
    for system, code in all_pairs:
        rows = session.execute(
            select(
                HospitalPriceRecord.facility_id,
                func.count(PriceServiceCode.id),
                func.min(HospitalPriceRecord.raw_description),
                func.min(HospitalPriceRecord.setting),
                func.min(HospitalPriceRecord.billing_class),
                reviewed_for_proc.label("has_reviewed"),
            )
            .join(
                HospitalPriceRecord,
                PriceServiceCode.hospital_price_record_id == HospitalPriceRecord.id,
            )
            .where(
                HospitalPriceRecord.facility_id.in_(facility_ids),
                PriceServiceCode.code_system == system,
                PriceServiceCode.code == code,
            )
            .group_by(HospitalPriceRecord.facility_id, reviewed_for_proc.label("has_reviewed"))
        ).all()
        for facility_id, count, sample_desc, setting, billing_class, has_reviewed in rows:
            for proc_id in code_to_procs[(system, code)]:
                cell = hits.setdefault(
                    (facility_id, proc_id),
                    {
                        "count": 0,
                        "reviewed_count": 0,
                        "codes": set(),
                        "sample_description": sample_desc,
                        "settings": set(),
                        "billing_classes": set(),
                    },
                )
                cell["count"] += count
                if has_reviewed:
                    cell["reviewed_count"] += count
                cell["codes"].add(f"{system}:{code}")
                if setting:
                    cell["settings"].add(setting)
                if billing_class:
                    cell["billing_classes"].add(billing_class)
    return hits


def _candidate_hits(
    session: Session, facility_ids: set[Any], procedures: dict[Any, dict[str, Any]], sample: int
) -> dict[tuple[Any, Any], list[dict[str, Any]]]:
    """Keyword-discovered candidate records lacking a reviewed mapping to the
    procedure. FOR REVIEW ONLY — never an approved mapping.
    """
    slug_to_proc = {meta["slug"]: proc_id for proc_id, meta in procedures.items()}
    reviewed_any = exists().where(
        and_(
            PriceRecordProcedureMapping.hospital_price_record_id == HospitalPriceRecord.id,
            PriceRecordProcedureMapping.reviewed.is_(True),
        )
    )
    candidates: dict[tuple[Any, Any], list[dict[str, Any]]] = defaultdict(list)
    for slug, keywords in DISCOVERY_KEYWORDS.items():
        proc_id = slug_to_proc.get(slug)
        if proc_id is None:
            continue
        like_clauses = [
            func.lower(HospitalPriceRecord.raw_description).like(f"%{kw}%") for kw in keywords
        ]
        rows = session.execute(
            select(
                HospitalPriceRecord.facility_id,
                PriceServiceCode.code_system,
                PriceServiceCode.code,
                func.min(HospitalPriceRecord.raw_description),
                func.count(PriceServiceCode.id),
            )
            .join(
                PriceServiceCode,
                PriceServiceCode.hospital_price_record_id == HospitalPriceRecord.id,
            )
            .where(
                HospitalPriceRecord.facility_id.in_(facility_ids),
                ~reviewed_any,
                _or_clauses(like_clauses),
            )
            .group_by(
                HospitalPriceRecord.facility_id,
                PriceServiceCode.code_system,
                PriceServiceCode.code,
            )
            .order_by(func.count(PriceServiceCode.id).desc())
            .limit(len(facility_ids) * sample)
        ).all()
        seen_per_facility: Counter[Any] = Counter()
        for facility_id, code_system, code, sample_desc, count in rows:
            if seen_per_facility[facility_id] >= sample:
                continue
            seen_per_facility[facility_id] += 1
            candidates[(facility_id, proc_id)].append(
                {
                    "code_system": str(code_system),
                    "code": str(code),
                    "sample_description": sample_desc,
                    "count": count,
                }
            )
    return candidates


def _or_clauses(clauses: list[Any]) -> Any:  # noqa: ANN401
    """OR-combine a non-empty list of SQL boolean clauses."""
    combined = clauses[0]
    for clause in clauses[1:]:
        combined = combined | clause
    return combined


def _publish_status_for_cell(
    session: Session, facility_id: Any, procedure_id: Any
) -> dict[str, Any]:
    """Observation-level detail for a (facility, procedure) with a reviewed mapping
    but no publishable summary — to tell COMPONENT_ONLY / SETTING_MISMATCH /
    PUBLISHABILITY_FILTER / SUMMARY_BUILD_GAP apart.
    """
    rows = session.execute(
        select(
            FacilityProcedurePriceObservation.publication_status,
            FacilityProcedurePriceObservation.included_component_scope,
            FacilityProcedurePriceObservation.service_setting,
            func.count(FacilityProcedurePriceObservation.id),
        )
        .where(
            FacilityProcedurePriceObservation.facility_id == facility_id,
            FacilityProcedurePriceObservation.procedure_id == procedure_id,
        )
        .group_by(
            FacilityProcedurePriceObservation.publication_status,
            FacilityProcedurePriceObservation.included_component_scope,
            FacilityProcedurePriceObservation.service_setting,
        )
    ).all()
    statuses: Counter[str] = Counter()
    scopes: set[str] = set()
    settings: set[str] = set()
    for status, scope, setting, count in rows:
        statuses[str(status)] += count
        if scope:
            scopes.add(str(scope))
        if setting:
            settings.add(str(setting))
    return {"statuses": dict(statuses), "scopes": sorted(scopes), "settings": sorted(settings)}


def _classify(
    session: Session,
    facility_id: Any,
    procedure_id: Any,
    proc_meta: dict[str, Any],
    record_count: int,
    publishable: bool,
    approved_hit: dict[str, Any] | None,
    candidate_list: list[dict[str, Any]],
) -> dict[str, Any]:
    """Return the matrix row + root cause for one (procedure, hospital) cell."""
    row: dict[str, Any] = {
        "procedure": proc_meta["slug"],
        "canonical_setting": proc_meta["service_setting"],
        "publishable": publishable,
        "approved_code_present": bool(approved_hit and approved_hit["count"]),
        "reviewed_mapped": bool(approved_hit and approved_hit["reviewed_count"]),
        "approved_codes_in_data": sorted(approved_hit["codes"]) if approved_hit else [],
        "raw_description_sample": approved_hit["sample_description"] if approved_hit else None,
        "settings_in_data": sorted(approved_hit["settings"]) if approved_hit else [],
        "billing_classes_in_data": sorted(approved_hit["billing_classes"]) if approved_hit else [],
        "candidate_count": len(candidate_list),
        "candidates": candidate_list[:5],
    }

    if publishable:
        row["root_cause"] = "NONE"
        return row
    if record_count == 0:
        row["root_cause"] = "NO_SOURCE_DATA"
        return row

    if approved_hit and approved_hit["reviewed_count"]:
        # Reviewed-mapped yet not published — inspect the projection.
        detail = _publish_status_for_cell(session, facility_id, procedure_id)
        row["observation_detail"] = detail
        statuses = detail["statuses"]
        if not statuses:
            row["root_cause"] = "SUMMARY_BUILD_GAP"
        elif "publishable" in statuses:
            # Publishable observations exist but no summary was built.
            row["root_cause"] = "SUMMARY_BUILD_GAP"
        elif proc_meta["service_setting"] not in ("mixed", "unknown") and not any(
            proc_meta["service_setting"].startswith(s[:4]) for s in detail["settings"]
        ):
            row["root_cause"] = "SETTING_MISMATCH"
        elif detail["scopes"] and all(
            scope in ("professional", "technical", "component") for scope in detail["scopes"]
        ):
            row["root_cause"] = "COMPONENT_ONLY"
        else:
            row["root_cause"] = "PUBLISHABILITY_FILTER"
        return row

    if approved_hit and approved_hit["count"]:
        # Canonical code sits in the raw data but no reviewed mapping was made.
        row["root_cause"] = "KNOWN_CODE_NOT_MAPPED"
        return row

    if candidate_list:
        systems = {c["code_system"] for c in candidate_list}
        if systems & _STANDARD_SYSTEMS:
            # A standard billing code we don't have in the registry (a code variant).
            row["root_cause"] = "KNOWN_CODE_NOT_MAPPED"
        elif systems <= {"CDM", "UNKNOWN"}:
            row["root_cause"] = "LOCAL_CODE_NEEDS_REVIEW"
        else:
            row["root_cause"] = "DESCRIPTION_VARIANT_NOT_MAPPED"
        return row

    row["root_cause"] = "NO_MATCHING_RAW_RECORD"
    return row


def audit(session: Session, state: str = "NH", candidate_sample: int = 3) -> dict[str, Any]:
    procedures = _procedures(session)
    approved = _approved_codes(session)
    facility_ids = set(active_consumer_facility_ids(session, state.upper()))
    facilities = {
        f.id: {"name": f.display_name, "ccn": f.cms_certification_number}
        for f in session.scalars(select(Facility).where(Facility.id.in_(facility_ids)))
    }
    publishable = _publishable_cells(session, facility_ids)
    record_counts = _facility_record_counts(session, facility_ids)
    approved_hits = _approved_code_hits(session, facility_ids, approved)
    candidates = _candidate_hits(session, facility_ids, procedures, candidate_sample)

    matrix: list[dict[str, Any]] = []
    per_procedure: dict[str, dict[str, Any]] = {}
    for proc_id, meta in procedures.items():
        slug = meta["slug"]
        publishing_facilities = 0
        causes: Counter[str] = Counter()
        cells: list[dict[str, Any]] = []
        for facility_id, facility_meta in facilities.items():
            is_pub = (facility_id, proc_id) in publishable
            cell = _classify(
                session,
                facility_id,
                proc_id,
                meta,
                record_counts.get(facility_id, 0),
                is_pub,
                approved_hits.get((facility_id, proc_id)),
                candidates.get((facility_id, proc_id), []),
            )
            cell["hospital"] = facility_meta["name"]
            cell["ccn"] = facility_meta["ccn"]
            causes[cell["root_cause"]] += 1
            if is_pub:
                publishing_facilities += 1
            cells.append(cell)
            matrix.append(cell)
        per_procedure[slug] = {
            "consumer_name": meta["consumer_name"],
            "canonical_codes": [f"{s}:{c}" for s, c in approved.get(proc_id, [])],
            "publishing_hospitals": publishing_facilities,
            "total_hospitals": len(facilities),
            "root_cause_histogram": dict(causes),
            # Actionable: hospitals that likely offer it but Carevero didn't map it.
            "recoverable_hospitals": sum(
                causes[c]
                for c in (
                    "KNOWN_CODE_NOT_MAPPED",
                    "DESCRIPTION_VARIANT_NOT_MAPPED",
                    "LOCAL_CODE_NEEDS_REVIEW",
                    "COMPONENT_ONLY",
                    "SETTING_MISMATCH",
                    "PUBLISHABILITY_FILTER",
                    "SUMMARY_BUILD_GAP",
                )
            ),
        }

    overall_causes: Counter[str] = Counter()
    for cell in matrix:
        overall_causes[cell["root_cause"]] += 1

    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "state": state.upper(),
        "procedures": len(procedures),
        "hospitals": len(facilities),
        "overall_root_cause_histogram": dict(overall_causes),
        "per_procedure": per_procedure,
        "matrix": matrix,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state", default="NH")
    parser.add_argument("--candidate-sample", type=int, default=3)
    parser.add_argument(
        "--summary-only",
        action="store_true",
        help="Emit only per-procedure aggregates (omit the full cell matrix).",
    )
    args = parser.parse_args()
    with session_factory() as session:
        report = audit(session, args.state, args.candidate_sample)
    if args.summary_only:
        report.pop("matrix", None)
    print("PROCEDURE_MAPPING_AUDIT=" + json.dumps(report, default=str, separators=(",", ":")))


if __name__ == "__main__":
    main()
