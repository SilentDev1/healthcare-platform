"""Fail deployment when public data invariants are unsafe."""

import argparse

from sqlalchemy import func, select

from collectors.hospital_prices.scope import active_consumer_facility_ids
from packages.database import (
    FacilityProcedurePriceSummary,
    SourceFile,
    session_factory,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--require-no-fixtures", action="store_true")
    args = parser.parse_args()
    with session_factory() as session:
        public = (
            select(FacilityProcedurePriceSummary)
            .join(SourceFile, SourceFile.id == FacilityProcedurePriceSummary.source_file_id)
            .where(
                FacilityProcedurePriceSummary.publication_status == "publishable",
                SourceFile.source_url.not_like("file://%"),
            )
        ).subquery()
        checks = {
            "active_consumer_facilities": len(active_consumer_facility_ids(session, "NH")),
            "official_public_summaries": session.scalar(select(func.count()).select_from(public))
            or 0,
            "fixture_public_summaries": session.scalar(
                select(func.count()).select_from(public).where(public.c.source_file_id.is_(None))
            )
            or 0,
            "stored_fixture_sources": session.scalar(
                select(func.count(SourceFile.id)).where(SourceFile.source_url.like("file://%"))
            )
            or 0,
            "negative_public_summaries": session.scalar(
                select(func.count())
                .select_from(public)
                .where(
                    (public.c.cash_price_min < 0)
                    | (public.c.cash_price_max < 0)
                    | (public.c.negotiated_price_min < 0)
                    | (public.c.negotiated_price_max < 0)
                )
            )
            or 0,
            "missing_public_provenance": session.scalar(
                select(func.count())
                .select_from(public)
                .where((public.c.source_file_id.is_(None)) | (public.c.facility_id.is_(None)))
            )
            or 0,
            "public_unreviewed_mappings": session.scalar(
                select(func.count()).select_from(public).where(public.c.procedure_id.is_(None))
            )
            or 0,
        }
    unsafe = (
        checks["active_consumer_facilities"] < 1
        or checks["official_public_summaries"] < 1
        or any(
            checks[key]
            for key in (
                "fixture_public_summaries",
                "negative_public_summaries",
                "missing_public_provenance",
                "public_unreviewed_mappings",
            )
        )
        or (args.require_no_fixtures and checks["stored_fixture_sources"] > 0)
    )
    for key, value in checks.items():
        print(f"{key}={value}")
    if unsafe:
        raise SystemExit("beta data smoke: FAIL")
    print("beta data smoke: PASS")


if __name__ == "__main__":
    main()
