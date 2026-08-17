"""Backfill included_component_scope on already-published non-hospital summaries.

Provider-published cash summaries were first ingested without a billing scope, so
they surface on the comparison as price-only rows with comparability "unknown" — the
price shows but never participates in cheapest/savings ranking. This one-time backfill
sets included_component_scope from the SAME cited source data (evidence-driven, via
normalize_component_scope), so a complete published GLOBAL self-pay charge becomes
legitimately comparable with hospital cash for the same canonical procedure.

Safety:
- Touches ONLY publishable summaries whose SourceFile.source_type is
  'provider_published_price' (never hospital MRF, never candidate rows).
- Only fills rows where included_component_scope IS NULL (never overwrites an
  existing scope), and only with a scope in the known vocabulary (ambiguous /
  unrecognized component_scope stays NULL — never fabricated).
- Additive & reversible: apply writes a rollback artifact (summary ids set).

Run (Cloud Run job):
  python -m scripts.backfill_nonhospital_component_scope [--dry-run] \
    [--rollback-out=/mnt/sources/verification/nonhospital_scope_backfill_rollback.json]
"""

from __future__ import annotations

# ruff: noqa: E501
import argparse
import json
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from packages.database import (
    Facility,
    FacilityLocation,
    Organization,
    Procedure,
    SourceFile,
    get_session,
)
from packages.database.pricing_models import FacilityProcedurePriceSummary as Summary
from scripts.ingest_nonhospital_published_prices import DATA_PATH, normalize_component_scope


def run(session: Session, *, dry_run: bool) -> dict[str, Any]:
    data = json.loads(DATA_PATH.read_text())
    result: dict[str, Any] = {
        "updated": 0,
        "skipped_no_scope_token": 0,
        "already_scoped": 0,
        "by_org": {},
        "updated_summary_ids": [],
    }

    for org_block in data["organizations"]:
        org = session.scalar(
            select(Organization).where(Organization.canonical_name == org_block["organization"])
        )
        if org is None:
            continue
        loc_ids = list(
            session.scalars(
                select(FacilityLocation.id)
                .join(Facility, Facility.id == FacilityLocation.facility_id)
                .where(Facility.organization_id == org.id)
            )
        )
        if not loc_ids:
            continue
        for item in org_block["prices"]:
            scope = normalize_component_scope(item.get("component_scope"))
            if scope is None:
                result["skipped_no_scope_token"] += 1
                continue
            procedure = session.scalar(
                select(Procedure).where(Procedure.slug == item["canonical_slug"])
            )
            if procedure is None:
                continue
            # Publishable, provider-published summaries for this (org, procedure).
            rows = session.execute(
                select(Summary)
                .join(SourceFile, SourceFile.id == Summary.source_file_id)
                .where(
                    Summary.facility_location_id.in_(loc_ids),
                    Summary.procedure_id == procedure.id,
                    Summary.publication_status == "publishable",
                    SourceFile.source_type == "provider_published_price",
                )
            ).scalars()
            for summ in rows:
                current = (summ.included_component_scope or "").strip().lower()
                # Fill only the sentinel/blank scope; never overwrite a genuine
                # recognized billing scope that is already set.
                if current and current != "unknown":
                    result["already_scoped"] += 1
                    continue
                summ.included_component_scope = scope
                result["updated"] += 1
                result["updated_summary_ids"].append(str(summ.id))
                by = result["by_org"].setdefault(org_block["organization"], {})
                by[item["canonical_slug"]] = by.get(item["canonical_slug"], 0) + 1

    if dry_run:
        session.rollback()
    else:
        session.commit()
    return result


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--rollback-out", default=None)
    args = ap.parse_args()
    session = next(get_session())
    result = run(session, dry_run=args.dry_run)
    prefix = "DRY-RUN " if args.dry_run else ""
    slim = {k: v for k, v in result.items() if k != "updated_summary_ids"}
    print(f"{prefix}SCOPE_BACKFILL {json.dumps(slim)}")
    if not args.dry_run and args.rollback_out:
        Path(args.rollback_out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.rollback_out).write_text(
            json.dumps(
                {
                    "updated_summary_ids": result["updated_summary_ids"],
                    "revert": "UPDATE facility_procedure_price_summaries SET included_component_scope=NULL WHERE id IN (updated_summary_ids);",
                },
                indent=2,
            )
        )
        print(f"  wrote rollback artifact {args.rollback_out}")


if __name__ == "__main__":
    main()
