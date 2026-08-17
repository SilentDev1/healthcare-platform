"""Ingest REAL provider-published non-hospital cash prices as NON-PUBLIC candidate rows.

Reads data/nh_nonhospital_published_prices.json (prices transcribed verbatim from official
provider price pages) and writes, per priced line item:
  * a SourceFile capturing provenance (source URL, retrieval date, format), and
  * a FacilityProcedurePriceSummary with publication_status="candidate_review" — a NON-PUBLIC
    status. Consumer endpoints only ever return publication_status=="publishable", so these
    NEVER reach consumers automatically. Promotion to public is a deliberate human-review step,
    exactly like hospital mapping approvals.

Safety guarantees (per directive):
- Never inferred: every price is transcribed from the cited official source; the loader fails
  loudly if a price is missing or <= 0 (missing price stays "not available", never $0).
- Candidate discovery stays SEPARATE from approved public mappings: canonical_slug is a
  PROPOSED exact-name match, written only at the non-public candidate_review status.
- Additive & reversible: only inserts candidate_review rows; touches no hospital data, no
  publishable summaries, no baseline metric.

Prices are organization-wide list prices; they are attached to EVERY active service location
of the organization (a Derry Imaging list price applies at all Derry Imaging sites).

Run: python -m scripts.ingest_nonhospital_published_prices [--dry-run]
"""

from __future__ import annotations

import argparse
import hashlib
import json
from decimal import Decimal
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
from packages.database.models import SourceStatus
from packages.database.pricing_models import FacilityProcedurePriceSummary

DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "nh_nonhospital_published_prices.json"
CANDIDATE_STATUS = "candidate_review"  # NON-PUBLIC: consumer endpoints require "publishable"

# Billing scopes the comparability engine treats as a complete facility charge a
# self-pay consumer can compare across providers. We only ever persist a scope when
# the provider's published component_scope maps to one of these (or an explicit
# partial component); an unrecognized/absent scope stays NULL (never fabricated).
_KNOWN_SCOPES = {
    "global",
    "combined",
    "facility",
    "bundled",
    "professional",
    "technical",
    "component",
}


def normalize_component_scope(component_scope: str | None) -> str | None:
    """Map a provider-published component_scope to a canonical billing scope token.

    The published value may carry a procedure-identity qualifier after a ';'
    (e.g. "global; WITH contrast") — that qualifier is about the mapped procedure,
    not the billing component, so the billing scope is the leading token. Returns
    None for anything not in the known scope vocabulary so we never invent a
    comparable scope for an ambiguous component.
    """
    if not component_scope:
        return None
    token = component_scope.split(";", 1)[0].strip().lower()
    return token if token in _KNOWN_SCOPES else None


def _source_file(session: Session, url: str, name: str, retrieval_date: str) -> SourceFile:
    existing = session.scalar(select(SourceFile).where(SourceFile.source_url == url))
    if existing is not None:
        return existing
    source = SourceFile(
        source_name=f"{name} (published cash prices, retrieved {retrieval_date})",
        source_url=url,
        source_type="provider_published_price",
        storage_path=f"provenance/{hashlib.sha256(url.encode()).hexdigest()[:16]}",
        checksum_sha256=hashlib.sha256(url.encode()).hexdigest(),
        file_size=0,
        parser_version="nonhospital-published-prices-manual",
        status=SourceStatus.COMPLETED,
    )
    session.add(source)
    session.flush()
    return source


def _load_data_ok(path: Path | None = None) -> bool:
    """Validate the shipped data file: every price present and > 0 (never $0/inferred)."""
    data = json.loads((path or DATA_PATH).read_text())
    for org_block in data["organizations"]:
        for key in ("organization", "source_url", "retrieval_date", "service_setting", "prices"):
            if key not in org_block:
                return False
        for item in org_block["prices"]:
            if item.get("cash_price") is None or float(item["cash_price"]) <= 0:
                return False
            if not item.get("canonical_slug") or not item.get("published_description"):
                return False
    return True


def ingest(
    session: Session | None = None,
    *,
    dry_run: bool = False,
    data: dict[str, Any] | None = None,
) -> dict[str, int]:
    if session is None:
        session = next(get_session())
    if data is None:
        data = json.loads(DATA_PATH.read_text())

    result = {"candidate_summaries": 0, "locations_priced": 0, "unmatched_procedures": 0}

    for org_block in data["organizations"]:
        org = session.scalar(
            select(Organization).where(Organization.canonical_name == org_block["organization"])
        )
        if org is None:
            continue
        locations = list(
            session.scalars(
                select(FacilityLocation)
                .join(Facility, Facility.id == FacilityLocation.facility_id)
                .where(Facility.organization_id == org.id, FacilityLocation.active.is_(True))
            )
        )
        source = _source_file(
            session, org_block["source_url"], org_block["organization"], org_block["retrieval_date"]
        )
        setting = org_block["service_setting"]

        for item in org_block["prices"]:
            price = item["cash_price"]
            if price is None or float(price) <= 0:  # never $0, never inferred
                raise ValueError(f"invalid published price for {item['published_description']!r}")
            procedure = session.scalar(
                select(Procedure).where(Procedure.slug == item["canonical_slug"])
            )
            if procedure is None:
                result["unmatched_procedures"] += 1
                continue
            for loc in locations:
                # Idempotent across ANY status: never re-create a candidate for a
                # (location, procedure, setting) that already has a summary — including
                # one already promoted to publishable (else we'd duplicate / violate the
                # unique constraint after promotion).
                exists = session.scalar(
                    select(FacilityProcedurePriceSummary).where(
                        FacilityProcedurePriceSummary.facility_location_id == loc.id,
                        FacilityProcedurePriceSummary.procedure_id == procedure.id,
                        FacilityProcedurePriceSummary.service_setting == setting,
                    )
                )
                if exists is not None:
                    continue
                session.add(
                    FacilityProcedurePriceSummary(
                        facility_id=loc.facility_id,
                        facility_location_id=loc.id,
                        procedure_id=procedure.id,
                        service_setting=setting,
                        # Non-nullable column (sentinel default "unknown"); persist a
                        # recognized billing scope when the source has one, else the
                        # sentinel — never NULL, never a fabricated comparable scope.
                        included_component_scope=(
                            normalize_component_scope(item.get("component_scope")) or "unknown"
                        ),
                        cash_price_min=Decimal(str(price)),
                        cash_price_max=Decimal(str(price)),
                        cash_price_median=Decimal(str(price)),
                        record_count=1,
                        source_file_id=source.id,
                        publication_status=CANDIDATE_STATUS,
                        completeness_score=Decimal("1.0"),
                        notes=(
                            f"Provider-published cash price. Source: "
                            f"{item.get('product_url') or org_block['source_url']} "
                            f"(retrieved {item.get('retrieval_date') or org_block['retrieval_date']}). "
                            f"Published as {item['published_description']!r}; component_scope="
                            f"{item['component_scope']}; mapping={item['mapping_confidence']}."
                            + (
                                f" Components: test={item.get('test_price')} + "
                                f"physician_service_fee={item.get('physician_service_fee')} "
                                f"= total={item.get('total_price')}; sku={item.get('sku')};"
                                f" national_dtc={item.get('national_dtc')}."
                                if item.get("total_price") is not None
                                else ""
                            )
                            + (f" NOTE: {item['mapping_note']}." if item.get("mapping_note") else "")
                            + " NON-PUBLIC candidate — requires human review before publish."
                        ),
                    )
                )
                result["candidate_summaries"] += 1
        result["locations_priced"] += len(locations)

    if dry_run:
        session.rollback()
    else:
        session.commit()
    return result


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Ingest non-hospital published cash prices (candidate)"
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    result = ingest(dry_run=args.dry_run)
    prefix = "DRY-RUN " if args.dry_run else ""
    print(f"{prefix}NONHOSPITAL_PUBLISHED_PRICES={result}")


if __name__ == "__main__":
    main()
