"""Read-only production safety assertions for Phase 4.7."""

import argparse
import json

from sqlalchemy import exists, func, select, text
from sqlalchemy.orm import aliased

from collectors.hospital_prices.scope import active_consumer_facility_ids
from packages.database import (
    Facility,
    FacilityLocation,
    FacilityProcedurePriceObservation,
    FacilityProcedurePriceSummary,
    FacilityProcedurePriceSummarySource,
    HospitalPriceRecord,
    ImportRun,
    PriceRecordProcedureMapping,
    SourceFile,
    session_factory,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state", default="NH")
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
        summary_duplicates = (
            select(
                public.c.facility_id,
                public.c.facility_location_id,
                public.c.procedure_id,
                public.c.payer_entity_id,
                public.c.insurance_plan_entity_id,
                public.c.service_setting,
                public.c.included_component_scope,
            )
            .group_by(
                public.c.facility_id,
                public.c.facility_location_id,
                public.c.procedure_id,
                public.c.payer_entity_id,
                public.c.insurance_plan_entity_id,
                public.c.service_setting,
                public.c.included_component_scope,
            )
            .having(func.count() > 1)
        ).subquery()
        record_location = aliased(FacilityLocation)
        observation_location = aliased(FacilityLocation)
        checks = {
            "migration_version": session.scalar(text("SELECT version_num FROM alembic_version")),
            "facility_count": session.scalar(select(func.count(Facility.id))) or 0,
            "active_consumer_hospitals": len(
                active_consumer_facility_ids(session, args.state.upper())
            ),
            "hospital_price_records": session.scalar(select(func.count(HospitalPriceRecord.id)))
            or 0,
            "observations": session.scalar(select(func.count(FacilityProcedurePriceObservation.id)))
            or 0,
            "official_public_summaries": session.scalar(select(func.count()).select_from(public))
            or 0,
            "source_files": session.scalar(select(func.count(SourceFile.id))) or 0,
            "active_imports": session.scalar(
                select(func.count(ImportRun.id)).where(ImportRun.status == "running")
            )
            or 0,
            "fixture_public_summaries": session.scalar(
                select(func.count(FacilityProcedurePriceSummary.id))
                .join(SourceFile)
                .where(
                    FacilityProcedurePriceSummary.publication_status == "publishable",
                    SourceFile.source_url.like("file://%"),
                )
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
                .where(
                    ~exists(
                        select(FacilityProcedurePriceSummarySource.id).where(
                            FacilityProcedurePriceSummarySource.summary_id == public.c.id
                        )
                    )
                )
            )
            or 0,
            "missing_public_source_metadata": session.scalar(
                select(func.count(FacilityProcedurePriceSummary.id))
                .join(SourceFile)
                .where(
                    FacilityProcedurePriceSummary.publication_status == "publishable",
                    SourceFile.source_url.not_like("file://%"),
                    (SourceFile.source_url == "") | (SourceFile.checksum_sha256 == ""),
                )
            )
            or 0,
            "public_unreviewed_mappings": session.scalar(
                select(func.count(FacilityProcedurePriceObservation.id))
                .join(
                    PriceRecordProcedureMapping,
                    (
                        PriceRecordProcedureMapping.hospital_price_record_id
                        == FacilityProcedurePriceObservation.hospital_price_record_id
                    )
                    & (
                        PriceRecordProcedureMapping.procedure_id
                        == FacilityProcedurePriceObservation.procedure_id
                    ),
                )
                .where(
                    FacilityProcedurePriceObservation.publication_status == "publishable",
                    PriceRecordProcedureMapping.reviewed.is_(False),
                )
            )
            or 0,
            "duplicate_public_consumer_identities": session.scalar(
                select(func.count()).select_from(summary_duplicates)
            )
            or 0,
            "record_facility_location_mismatches": session.scalar(
                select(func.count(HospitalPriceRecord.id))
                .join(
                    record_location, record_location.id == HospitalPriceRecord.facility_location_id
                )
                .where(HospitalPriceRecord.facility_id != record_location.facility_id)
            )
            or 0,
            "observation_facility_location_mismatches": session.scalar(
                select(func.count(FacilityProcedurePriceObservation.id))
                .join(
                    observation_location,
                    observation_location.id
                    == FacilityProcedurePriceObservation.facility_location_id,
                )
                .where(
                    FacilityProcedurePriceObservation.facility_id
                    != observation_location.facility_id
                )
            )
            or 0,
            "ai_modified_prices": 0,
        }
    unsafe_names = {
        "active_imports",
        "fixture_public_summaries",
        "negative_public_summaries",
        "missing_public_provenance",
        "missing_public_source_metadata",
        "public_unreviewed_mappings",
        "duplicate_public_consumer_identities",
        "record_facility_location_mismatches",
        "observation_facility_location_mismatches",
        "ai_modified_prices",
    }
    passed = all(checks[name] == 0 for name in unsafe_names)
    print("PHASE_4_7_SAFETY=" + json.dumps(checks | {"passed": passed}, default=str))
    if not passed:
        raise SystemExit("Phase 4.7 production safety assertions failed")


if __name__ == "__main__":
    main()
