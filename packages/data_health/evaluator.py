from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import delete, desc, func, select
from sqlalchemy.orm import Session

from packages.database import (
    DataHealthEvaluation,
    DataHealthRule,
    EntityDataHealthScore,
    Facility,
    FacilityIdentifier,
    FacilityIdentityCandidate,
    FacilityLocation,
    FacilityQualityMeasureObservation,
    FacilitySourceObservation,
    ImportRun,
    PipelineStatusSnapshot,
    SourceFile,
)
from packages.database.models import ImportStatus

RULES = (
    ("missing_source_provenance", "Missing source provenance", "facility", "error", 25),
    ("stale_source_file", "Stale source file", "source", "warning", 10),
    ("failed_latest_import", "Failed latest import", "pipeline", "error", 20),
    ("missing_facility_location", "Missing facility location", "facility", "error", 20),
    ("missing_cms_ccn", "Missing CMS CCN for CMS hospital", "facility", "warning", 10),
    ("duplicate_strong_identifiers", "Duplicate strong identifiers", "facility", "critical", 30),
    ("invalid_postal_code", "Invalid postal code", "facility", "warning", 10),
    ("missing_display_name", "Missing facility display name", "facility", "error", 20),
    ("quality_data_absent", "Quality data absent", "facility", "warning", 10),
    ("quality_period_stale", "Quality reporting period stale", "facility", "warning", 10),
    (
        "unmatched_identity_candidate",
        "Unmatched identity candidate",
        "identity_candidate",
        "warning",
        10,
    ),
    ("source_file_shrank", "Source file unexpectedly shrank", "source", "warning", 10),
    ("source_checksum_unchanged", "Source file checksum unchanged", "source", "info", 0),
    ("import_rejection_rate", "Importer rejection rate above threshold", "pipeline", "warning", 10),
)


def evaluate_data_health(session: Session) -> dict[str, int | float]:
    rules: dict[str, DataHealthRule] = {}
    for key, name, entity_type, severity, weight in RULES:
        rule = session.scalar(select(DataHealthRule).where(DataHealthRule.rule_key == key))
        if rule is None:
            rule = DataHealthRule(
                rule_key=key,
                name=name,
                description=name,
                entity_type=entity_type,
                severity=severity,
                weight=weight,
                configuration={},
            )
            session.add(rule)
            session.flush()
        rules[key] = rule
    session.execute(delete(DataHealthEvaluation))
    session.execute(delete(EntityDataHealthScore))
    session.execute(delete(PipelineStatusSnapshot))
    evaluations = 0
    scores: list[float] = []
    now = datetime.now(UTC)
    for facility in session.scalars(select(Facility)):
        location = session.scalar(
            select(FacilityLocation).where(FacilityLocation.facility_id == facility.id)
        )
        provenance = (
            session.scalar(
                select(func.count(FacilitySourceObservation.id)).where(
                    FacilitySourceObservation.facility_id == facility.id
                )
            )
            or 0
        )
        quality = (
            session.scalar(
                select(func.count(FacilityQualityMeasureObservation.id)).where(
                    FacilityQualityMeasureObservation.facility_id == facility.id
                )
            )
            or 0
        )
        ccn = session.scalar(
            select(FacilityIdentifier.id).where(
                FacilityIdentifier.facility_id == facility.id,
                FacilityIdentifier.identifier_type == "CMS_CCN",
            )
        )
        checks = (
            (
                "missing_source_provenance",
                bool(provenance),
                "Facility has immutable source observations",
            ),
            ("missing_facility_location", location is not None, "Facility has a location"),
            ("missing_cms_ccn", ccn is not None, "Facility has a CMS CCN identifier"),
            (
                "invalid_postal_code",
                bool(location and len(location.postal_code) in {5, 10}),
                "Facility postal code is valid",
            ),
            (
                "missing_display_name",
                bool(facility.display_name.strip()),
                "Facility has a display name",
            ),
            ("quality_data_absent", bool(quality), "Facility has quality observations"),
        )
        passed = 0
        for key, ok, message in checks:
            session.add(
                DataHealthEvaluation(
                    rule_id=rules[key].id,
                    entity_type="facility",
                    entity_id=facility.id,
                    status="pass" if ok else "warning",
                    score=100 if ok else 0,
                    message=message if ok else message.replace("has", "is missing"),
                    details={},
                )
            )
            evaluations += 1
            passed += int(ok)
        completeness = Decimal(str(round(passed / len(checks) * 100, 2)))
        comparison_now = now if facility.updated_at.tzinfo else now.replace(tzinfo=None)
        freshness = (
            Decimal("100")
            if facility.updated_at >= comparison_now - timedelta(days=365)
            else Decimal("50")
        )
        overall = (
            completeness
            + freshness
            + Decimal("100")
            + (Decimal("100") if provenance else Decimal("0"))
        ) / 4
        scores.append(float(overall))
        session.add(
            EntityDataHealthScore(
                entity_type="facility",
                entity_id=facility.id,
                completeness_score=completeness,
                freshness_score=freshness,
                validity_score=100,
                provenance_score=100 if provenance else 0,
                overall_score=overall,
                details={"checks_passed": passed, "checks_total": len(checks)},
            )
        )
    for candidate in session.scalars(
        select(FacilityIdentityCandidate).where(
            FacilityIdentityCandidate.status.in_(["pending", "probable_match"])
        )
    ):
        session.add(
            DataHealthEvaluation(
                rule_id=rules["unmatched_identity_candidate"].id,
                entity_type="identity_candidate",
                entity_id=candidate.id,
                source_file_id=candidate.source_file_id,
                import_run_id=candidate.import_run_id,
                status="warning",
                score=0,
                message="Identity candidate requires human review",
                details={"method": candidate.deterministic_method},
            )
        )
        evaluations += 1
    importer_names = session.scalars(select(ImportRun.importer_name).distinct()).all()
    for importer_name in importer_names:
        latest = session.scalar(
            select(ImportRun)
            .where(ImportRun.importer_name == importer_name)
            .order_by(desc(ImportRun.started_at))
            .limit(1)
        )
        source = session.get(SourceFile, latest.source_file_id) if latest else None
        success = session.scalar(
            select(ImportRun)
            .where(
                ImportRun.importer_name == importer_name,
                ImportRun.status.in_([ImportStatus.COMPLETED, ImportStatus.COMPLETED_WITH_ERRORS]),
            )
            .order_by(desc(ImportRun.finished_at))
            .limit(1)
        )
        failure = session.scalar(
            select(ImportRun)
            .where(
                ImportRun.importer_name == importer_name, ImportRun.status == ImportStatus.FAILED
            )
            .order_by(desc(ImportRun.finished_at))
            .limit(1)
        )
        session.add(
            PipelineStatusSnapshot(
                importer_name=importer_name,
                source_type=source.source_type if source else "unknown",
                latest_import_run_id=latest.id if latest else None,
                latest_success_at=success.finished_at if success else None,
                latest_failure_at=failure.finished_at if failure else None,
                current_status=latest.status.value.lower() if latest else "unknown",
                freshness_status=(
                    "fresh"
                    if source
                    and source.downloaded_at
                    >= (now if source.downloaded_at.tzinfo else now.replace(tzinfo=None))
                    - timedelta(days=90)
                    else "stale"
                ),
                expected_refresh_interval_hours=2160,
                records_last_imported=int(latest.rows_inserted) if latest else None,
                error_summary=latest.error_summary if latest else None,
            )
        )
    session.flush()
    return {
        "rules": len(RULES),
        "evaluations": evaluations,
        "facility_scores": len(scores),
        "average_facility_score": round(sum(scores) / len(scores), 2) if scores else 0,
    }
