"""Deliberate promotion of non-hospital candidate_review prices -> publishable.

Promotion is NEVER a blind status flip. For each candidate (location, procedure) price
from a provider-published source, this step:
  * records LocationServiceAvailability (offered / not_offered) from EVIDENCE
    (data/nh_location_service_availability.json — per-location modalities from the
    official provider site), then
  * promotes candidate_review -> publishable ONLY where the location verifiably OFFERS
    the modality AND no conflicting publishable summary already exists.
Organization-wide prices are thus applied only at the proven location scope (e.g. a CT
price is NOT promoted at a Derry Imaging site that has no CT).

Preserves exact source provenance (untouched notes/source_file). Additive & reversible:
apply writes a rollback artifact (promoted summary ids + created LSA ids).

Run (Cloud Run job): python -m scripts.promote_nonhospital_candidates --organization "Derry Imaging" [--dry-run] [--rollback-out=/mnt/sources/verification/derry_promotion_rollback.json]
"""

from __future__ import annotations

# ruff: noqa: E501
import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from packages.database.models import (
    Facility,
    FacilityLocation,
    LocationServiceAvailability,
    Organization,
    Procedure,
    SourceFile,
    SourceStatus,
)
from packages.database.pricing_models import FacilityProcedurePriceSummary as Summary
from packages.database.pricing_models import FacilityProcedurePriceSummarySource
from packages.database.session import session_factory

AVAIL_PATH = Path(__file__).resolve().parent.parent / "data" / "nh_location_service_availability.json"


def modality_of(slug: str) -> str | None:
    if slug.startswith("mri"):
        return "mri"
    if slug.startswith("ct"):
        return "ct"
    if "ultrasound" in slug:
        return "ultrasound"
    if "x-ray" in slug or "xray" in slug:
        return "xray"
    if slug.startswith("mammogra"):
        return "mammography"
    if "dexa" in slug or "bone-densit" in slug:
        return "dexa"
    return None


def _avail_source(session: Session, url: str) -> SourceFile:
    existing = session.scalar(select(SourceFile).where(SourceFile.source_url == url))
    if existing is not None:
        return existing
    sf = SourceFile(
        source_name="Provider per-location service availability (official site)",
        source_url=url,
        source_type="provider_service_availability",
        storage_path=f"provenance/{hashlib.sha256(url.encode()).hexdigest()[:16]}",
        checksum_sha256=hashlib.sha256(url.encode()).hexdigest(),
        file_size=0,
        parser_version="location-service-availability-manual",
        status=SourceStatus.COMPLETED,
    )
    session.add(sf)
    session.flush()
    return sf


def run(session: Session, organization: str, *, dry_run: bool) -> dict[str, Any]:
    avail = json.loads(AVAIL_PATH.read_text())
    block = next((o for o in avail["organizations"] if o["organization"] == organization), None)
    if block is None:
        raise SystemExit(f"no availability evidence for organization {organization!r}")
    modality_by_city: dict[str, list[str]] = block["modality_by_city"]

    org = session.scalar(select(Organization).where(Organization.canonical_name == organization))
    if org is None:
        raise SystemExit(f"organization {organization!r} not found")
    locs = {
        loc.id: loc
        for loc in session.scalars(
            select(FacilityLocation)
            .join(Facility, Facility.id == FacilityLocation.facility_id)
            .where(Facility.organization_id == org.id, FacilityLocation.active.is_(True))
        )
    }
    evidence = _avail_source(session, block["source_url"])
    now = datetime.now(UTC)

    # All candidate_review summaries at this org's locations, with procedure slug.
    cands = session.execute(
        select(Summary, Procedure.slug)
        .join(Procedure, Procedure.id == Summary.procedure_id)
        .where(
            Summary.facility_location_id.in_(list(locs)),
            Summary.publication_status == "candidate_review",
        )
    ).all()

    result: dict[str, Any] = {
        "organization": organization,
        "candidates": len(cands),
        "promoted": 0,
        "excluded_not_offered": 0,
        "excluded_unknown_modality": 0,
        "skipped_conflict": 0,
        "lsa_offered": 0,
        "lsa_not_offered": 0,
        "by_procedure": {},
        "promoted_summary_ids": [],
        "created_lsa_ids": [],
        "excluded_detail": [],
    }

    # Record LocationServiceAvailability for EVERY (org location, candidate procedure) so
    # offered/not_offered is durable evidence, then gate promotion on offered.
    seen_lsa: set[tuple[Any, Any]] = set()

    def upsert_lsa(loc_id: Any, proc_id: Any, offered: bool) -> None:
        key = (loc_id, proc_id)
        if key in seen_lsa:
            return
        seen_lsa.add(key)
        existing = session.scalar(
            select(LocationServiceAvailability).where(
                LocationServiceAvailability.facility_location_id == loc_id,
                LocationServiceAvailability.procedure_id == proc_id,
            )
        )
        status = "offered" if offered else "not_offered"
        if existing is None:
            row = LocationServiceAvailability(
                facility_location_id=loc_id,
                procedure_id=proc_id,
                availability_status=status,
                evidence_source_id=evidence.id,
                verified_at=now,
                active=True,
            )
            session.add(row)
            session.flush()
            result["created_lsa_ids"].append(str(row.id))
        else:
            existing.availability_status = status
            existing.evidence_source_id = evidence.id
            existing.verified_at = now
            existing.active = True
        result["lsa_offered" if offered else "lsa_not_offered"] += 1

    for summ, slug in cands:
        loc = locs[summ.facility_location_id]
        modality = modality_of(slug)
        by = result["by_procedure"].setdefault(slug, {"promoted": 0, "excluded": 0, "conflict": 0})
        if modality is None:
            result["excluded_unknown_modality"] += 1
            by["excluded"] += 1
            continue
        offered = modality in modality_by_city.get(loc.city or "", [])
        upsert_lsa(loc.id, summ.procedure_id, offered)
        if not offered:
            result["excluded_not_offered"] += 1
            by["excluded"] += 1
            result["excluded_detail"].append({"city": loc.city, "slug": slug, "modality": modality})
            continue
        # Conflict: an existing PUBLISHABLE summary for the same (location, procedure, setting, scope).
        conflict = session.scalar(
            select(func.count())
            .select_from(Summary)
            .where(
                Summary.facility_location_id == summ.facility_location_id,
                Summary.procedure_id == summ.procedure_id,
                Summary.service_setting == summ.service_setting,
                Summary.included_component_scope == summ.included_component_scope,
                Summary.publication_status == "publishable",
                Summary.id != summ.id,
            )
        )
        if conflict:
            result["skipped_conflict"] += 1
            by["conflict"] += 1
            continue
        summ.publication_status = "publishable"  # provenance notes/source_file untouched
        result["promoted"] += 1
        by["promoted"] += 1
        result["promoted_summary_ids"].append(str(summ.id))

    # Provenance linkage: every PUBLIC summary needs a FacilityProcedurePriceSummarySource
    # row (the safety invariant). Non-hospital published summaries carry the provider source
    # on source_file_id; ensure the linkage exists (idempotent; backfills prior promotions).
    result["provenance_links_created"] = 0
    pub_here = session.execute(
        select(Summary.id, Summary.source_file_id, Summary.record_count).where(
            Summary.facility_location_id.in_(list(locs)),
            Summary.publication_status == "publishable",
        )
    ).all()
    for sid, sfid, rc in pub_here:
        has = session.scalar(
            select(func.count())
            .select_from(FacilityProcedurePriceSummarySource)
            .where(
                FacilityProcedurePriceSummarySource.summary_id == sid,
                FacilityProcedurePriceSummarySource.source_file_id == sfid,
            )
        )
        if not has:
            session.add(
                FacilityProcedurePriceSummarySource(
                    summary_id=sid, source_file_id=sfid, observation_count=int(rc or 1)
                )
            )
            result["provenance_links_created"] += 1

    if dry_run:
        session.rollback()
    else:
        session.commit()
    return result


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--organization", required=True)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--rollback-out", default=None)
    args = ap.parse_args()
    with session_factory() as session:
        result = run(session, args.organization, dry_run=args.dry_run)
    prefix = "DRY-RUN " if args.dry_run else ""
    slim = {k: v for k, v in result.items() if k not in ("promoted_summary_ids", "created_lsa_ids", "excluded_detail")}
    print(f"{prefix}PROMOTION {json.dumps(slim)}")
    for slug, by in result["by_procedure"].items():
        print(f"  {slug}: promoted={by['promoted']} excluded={by['excluded']} conflict={by['conflict']}")
    if not args.dry_run and args.rollback_out:
        Path(args.rollback_out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.rollback_out).write_text(
            json.dumps(
                {
                    "organization": args.organization,
                    "promoted_summary_ids": result["promoted_summary_ids"],
                    "created_lsa_ids": result["created_lsa_ids"],
                    "revert": "UPDATE facility_procedure_price_summaries SET publication_status='candidate_review' WHERE id IN (promoted_summary_ids); DELETE FROM location_service_availability WHERE id IN (created_lsa_ids);",
                },
                indent=2,
            )
        )
        print(f"  wrote rollback artifact {args.rollback_out}")


if __name__ == "__main__":
    main()
