"""Register verified MA hospital MRF sources into FacilityPriceSource (Phase 2).

Reads data/ma_hospital_price_sources.json — a verified acquisition matrix built from official
hospital/health-system price-transparency pages (each URL HEAD-verified during discovery) — and
creates get-or-create ``FacilityPriceSource`` rows for the matching MA hospitals (joined by CCN).

This registers WHERE to fetch each hospital's machine-readable standard-charges file. It does NOT
download, parse, or publish anything — the state-scoped pipeline (``download_all_sources`` /
``import_all_sources`` / ``rebuild_price_summaries`` for ``--state MA``) does that as a separate,
gated step. Seeding a source is NOT price availability.

Safety:
  * Idempotent: dedups on the DB unique key (facility_id, machine_readable_file_url). Re-run creates nothing.
  * MA only — matches facilities by CCN against the seeded MA hospitals; never touches NH sources.
  * Only registers rows with status == "MRF_FOUND" and a non-empty verified URL (honest coverage:
    MRF_NOT_FOUND / SOURCE_BLOCKED / MRF_INDEX_ONLY are recorded in the fixture but NOT registered).
  * ``--only-ccns`` restricts to a pilot subset so ingestion can be bounded.

Run: python -m scripts.seed_ma_price_sources [--dry-run] [--only-ccns 220071,220086,...]
"""

from __future__ import annotations

# ruff: noqa: E501
import argparse
import json
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from packages.database import Facility, FacilityLocation, get_session
from packages.database.pricing_models import FacilityPriceSource

DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "ma_hospital_price_sources.json"


def seed(
    session: Session | None = None,
    *,
    dry_run: bool = False,
    data: dict[str, Any] | None = None,
    only_ccns: set[str] | None = None,
    refresh_urls: bool = False,
) -> dict[str, int]:
    if session is None:
        session = next(get_session())
    if data is None:
        data = json.loads(DATA_PATH.read_text())

    counts = {"registered": 0, "already_present": 0, "skipped_not_found": 0, "unmatched_ccn": 0, "url_refreshed": 0}

    for rec in data["sources"]:
        ccn = rec["ccn"]
        if only_ccns is not None and ccn not in only_ccns:
            continue
        if rec.get("status") != "MRF_FOUND" or not rec.get("mrf_url"):
            counts["skipped_not_found"] += 1
            continue

        # Match the MA hospital facility by CCN (must be an MA-seeded hospital location).
        facility = session.scalar(
            select(Facility)
            .join(FacilityLocation, FacilityLocation.facility_id == Facility.id)
            .where(Facility.cms_certification_number == ccn, FacilityLocation.state == "MA")
        )
        if facility is None:
            counts["unmatched_ccn"] += 1
            continue
        location = session.scalar(
            select(FacilityLocation).where(
                FacilityLocation.facility_id == facility.id, FacilityLocation.state == "MA"
            )
        )

        existing = session.scalar(
            select(FacilityPriceSource).where(
                FacilityPriceSource.facility_id == facility.id,
                FacilityPriceSource.machine_readable_file_url == rec["mrf_url"],
            )
        )
        if existing is not None:
            counts["already_present"] += 1
            continue

        # URL refresh: a stale-URL source for this facility that never downloaded (source_file_id NULL)
        # gets re-pointed to the fixture's new URL in place. Already-downloaded sources are left alone,
        # so a hospital already imported under a working URL is never disturbed.
        if refresh_urls:
            stale = session.scalar(
                select(FacilityPriceSource).where(
                    FacilityPriceSource.facility_id == facility.id,
                    FacilityPriceSource.source_file_id.is_(None),
                    FacilityPriceSource.machine_readable_file_url != rec["mrf_url"],
                )
            )
            if stale is not None:
                stale.machine_readable_file_url = rec["mrf_url"]
                stale.declared_format = rec.get("format") or stale.declared_format
                stale.source_page_url = rec.get("transparency_page_url") or stale.source_page_url
                stale.last_failed_download_at = None
                stale.active = True
                counts["url_refreshed"] += 1
                continue

        session.add(
            FacilityPriceSource(
                facility_id=facility.id,
                facility_location_id=location.id if location else None,
                location_association_status="resolved" if location else "unresolved",
                source_type="hospital_mrf",
                source_class="HOSPITAL_MRF",
                source_page_url=rec.get("transparency_page_url") or rec.get("official_site"),
                machine_readable_file_url=rec["mrf_url"],
                declared_format=(rec.get("format") or None),
                discovery_method="verified_manual",
                health_system_name=rec.get("system") or None,
                vendor_name=rec.get("vendor_name") or None,
                active=True,
            )
        )
        counts["registered"] += 1

    if dry_run:
        session.rollback()
    else:
        session.commit()
    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description="Register verified MA hospital MRF sources (no download, no pricing)")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--only-ccns", default="", help="comma-separated CCNs to restrict (pilot subset)")
    parser.add_argument("--refresh-urls", action="store_true", help="re-point stale-URL, not-yet-downloaded sources to the fixture URL")
    args = parser.parse_args()
    only = {c.strip() for c in args.only_ccns.split(",") if c.strip()} or None
    result = seed(dry_run=args.dry_run, only_ccns=only, refresh_urls=args.refresh_urls)
    prefix = "DRY-RUN " if args.dry_run else ""
    print(f"{prefix}MA_PRICE_SOURCES={result}")


if __name__ == "__main__":
    main()
