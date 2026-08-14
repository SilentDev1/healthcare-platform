"""Tests for the procedure terminology/crosswalk coverage audit (read-only).

The load-bearing invariant: candidate discovery (keyword/description matching)
is reported SEPARATELY from approved-code coverage and never promotes a record to
publishable/approved. The root-cause classification is exercised across branches.
"""

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session

from packages.database import (
    Base,
    Facility,
    FacilityLocation,
    FacilityProcedurePriceObservation,
    FacilityProcedurePriceSummary,
    HospitalPriceRecord,
    ImportRun,
    PriceRecordProcedureMapping,
    PriceServiceCode,
    Procedure,
    ProcedureCategory,
    ProcedureCodeMapping,
    ProcedureCodeSystem,
    SourceFile,
)
from packages.database.models import ImportStatus, SourceStatus
from scripts.audit_procedure_mapping_coverage import audit


def _engine() -> Engine:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    return engine


def _catalog(session: Session) -> tuple[Procedure, ProcedureCodeSystem]:
    category = ProcedureCategory(slug="labs", name="Labs", description="labs")
    session.add(category)
    session.flush()
    cpt = ProcedureCodeSystem(code_system="CPT", display_name="CPT", licensing_notes="n/a")
    session.add(cpt)
    session.flush()
    # slug matches a DISCOVERY_KEYWORDS entry so candidate discovery can fire.
    procedure = Procedure(
        slug="complete-blood-count",
        consumer_name="Complete Blood Count",
        short_description="CBC",
        long_description="cbc",
        category_id=category.id,
        service_setting="outpatient",
        complexity="low",
    )
    session.add(procedure)
    session.flush()
    session.add(
        ProcedureCodeMapping(
            procedure_id=procedure.id,
            code_system_id=cpt.id,
            code="85025",
            mapping_status="approved",
        )
    )
    session.flush()
    return procedure, cpt


def _facility(session: Session, ccn: str, name: str) -> Facility:
    facility = Facility(cms_certification_number=ccn, legal_name=name, display_name=name)
    facility.locations.append(
        FacilityLocation(
            address_line_1="1 Test St", city="Concord", state="NH", postal_code="03301"
        )
    )
    session.add(facility)
    session.flush()
    return facility


def _src(session: Session) -> tuple[SourceFile, ImportRun]:
    source = SourceFile(
        source_name="mrf",
        source_url="https://example.test/mrf.csv",
        source_type="hospital_price_mrf",
        storage_path="/tmp/mrf.csv",
        checksum_sha256="e" * 64,
        file_size=1,
        parser_version="1.0.0",
        status=SourceStatus.COMPLETED,
    )
    session.add(source)
    session.flush()
    run = ImportRun(
        importer_name="hospital_prices", status=ImportStatus.COMPLETED, source_file_id=source.id
    )
    session.add(run)
    session.flush()
    return source, run


def _record(
    session: Session,
    facility: Facility,
    src: SourceFile,
    run: ImportRun,
    code_system: str,
    code: str,
    description: str,
    *,
    setting: str = "outpatient",
    billing_class: str = "facility",
) -> HospitalPriceRecord:
    record = HospitalPriceRecord(
        facility_id=facility.id,
        source_file_id=src.id,
        import_run_id=run.id,
        source_record_identifier=str(uuid.uuid4()),
        source_payload_hash=uuid.uuid4().hex,
        raw_description=description,
        service_description_normalized=description.lower(),
        setting=setting,
        billing_class=billing_class,
        raw_payload={},
        parser_name="cms_hpt_csv",
        parser_version="1.0.0",
        observed_at=datetime.now(UTC),
    )
    session.add(record)
    session.flush()
    session.add(
        PriceServiceCode(
            hospital_price_record_id=record.id,
            code_system=code_system,
            code=code,
            raw_code_type=code_system,
            raw_code=code,
        )
    )
    session.flush()
    return record


def _reviewed_mapping(session: Session, record: HospitalPriceRecord, procedure: Procedure) -> None:
    session.add(
        PriceRecordProcedureMapping(
            hospital_price_record_id=record.id,
            procedure_id=procedure.id,
            mapping_method="exact_approved_code",
            confidence_score=Decimal("1"),
            reviewed=True,
            reviewed_by="test",
            reviewed_at=datetime.now(UTC),
        )
    )
    session.flush()


def _publishable_summary(
    session: Session, facility: Facility, procedure: Procedure, src: SourceFile
) -> None:
    session.add(
        FacilityProcedurePriceSummary(
            facility_id=facility.id,
            facility_location_id=facility.locations[0].id,
            procedure_id=procedure.id,
            service_setting="outpatient",
            included_component_scope="facility",
            cash_price_median=Decimal("50"),
            record_count=1,
            source_file_id=src.id,
            calculated_at=datetime.now(UTC),
            publication_status="publishable",
            completeness_score=Decimal("100"),
        )
    )
    session.flush()


def _publishable_observation(
    session: Session, facility: Facility, procedure: Procedure, record: HospitalPriceRecord
) -> None:
    session.add(
        FacilityProcedurePriceObservation(
            facility_id=facility.id,
            facility_location_id=facility.locations[0].id,
            procedure_id=procedure.id,
            hospital_price_record_id=record.id,
            price_type="discounted_cash",
            amount=Decimal("50"),
            service_setting="outpatient",
            included_component_scope="facility",
            source_confidence=Decimal("1"),
            mapping_confidence=Decimal("1"),
            publication_status="publishable",
        )
    )
    session.flush()


def test_audit_classifies_cells_and_keeps_discovery_separate() -> None:
    engine = _engine()
    with Session(engine) as session:
        procedure, _cpt = _catalog(session)
        src, run = _src(session)

        # A: publishable (approved code + reviewed mapping + summary) -> NONE.
        pub = _facility(session, "990001", "PUBLISHED")
        rec_a = _record(session, pub, src, run, "CPT", "85025", "CBC")
        _reviewed_mapping(session, rec_a, procedure)
        _publishable_summary(session, pub, procedure, src)

        # B: canonical code present, NO reviewed mapping -> KNOWN_CODE_NOT_MAPPED.
        known = _facility(session, "990002", "KNOWN CODE")
        _record(session, known, src, run, "CPT", "85025", "CBC")

        # C: local code + matching description, no approved code -> LOCAL_CODE_NEEDS_REVIEW.
        # This is the discovery-separation case: a keyword hit must NOT publish/approve.
        local = _facility(session, "990003", "LOCAL CANDIDATE")
        _record(session, local, src, run, "CDM", "7527989-LAB", "COMPLETE BLOOD COUNT W/DIFF")

        # D: no records at all -> NO_SOURCE_DATA.
        _facility(session, "990004", "EMPTY")

        # E: records, but nothing resembling CBC -> NO_MATCHING_RAW_RECORD.
        nomatch = _facility(session, "990005", "NO MATCH")
        _record(session, nomatch, src, run, "CPT", "70450", "CT HEAD WITHOUT CONTRAST")

        # F: approved code + reviewed mapping + publishable observation but no summary
        #    -> SUMMARY_BUILD_GAP.
        gap = _facility(session, "990006", "SUMMARY GAP")
        rec_f = _record(session, gap, src, run, "CPT", "85025", "CBC")
        _reviewed_mapping(session, rec_f, procedure)
        _publishable_observation(session, gap, procedure, rec_f)

        session.commit()

        report = audit(session, state="NH")

    engine.dispose()

    proc = report["per_procedure"]["complete-blood-count"]
    assert proc["publishing_hospitals"] == 1  # only A publishes
    assert proc["total_hospitals"] == 6
    assert proc["canonical_codes"] == ["CPT:85025"]

    by_ccn = {c["ccn"]: c for c in report["matrix"] if c["procedure"] == "complete-blood-count"}

    assert by_ccn["990001"]["root_cause"] == "NONE"
    assert by_ccn["990001"]["publishable"] is True

    assert by_ccn["990002"]["root_cause"] == "KNOWN_CODE_NOT_MAPPED"
    assert by_ccn["990002"]["approved_code_present"] is True
    assert by_ccn["990002"]["reviewed_mapped"] is False

    # The discovery-separation invariant: a description/keyword hit stays a candidate.
    local_cell = by_ccn["990003"]
    assert local_cell["root_cause"] == "LOCAL_CODE_NEEDS_REVIEW"
    assert local_cell["publishable"] is False
    assert local_cell["approved_code_present"] is False
    assert local_cell["reviewed_mapped"] is False
    assert local_cell["candidate_count"] >= 1
    assert local_cell["candidates"][0]["code_system"] == "CDM"

    assert by_ccn["990004"]["root_cause"] == "NO_SOURCE_DATA"
    assert by_ccn["990005"]["root_cause"] == "NO_MATCHING_RAW_RECORD"
    assert by_ccn["990005"]["candidate_count"] == 0
    assert by_ccn["990006"]["root_cause"] == "SUMMARY_BUILD_GAP"

    # Histogram totals across all 6 hospitals for this procedure.
    hist = proc["root_cause_histogram"]
    assert hist["NONE"] == 1
    assert hist["KNOWN_CODE_NOT_MAPPED"] == 1
    assert hist["LOCAL_CODE_NEEDS_REVIEW"] == 1
    assert hist["NO_SOURCE_DATA"] == 1
    assert hist["NO_MATCHING_RAW_RECORD"] == 1
    assert hist["SUMMARY_BUILD_GAP"] == 1
    # Recoverable = "Carevero couldn't find/map the terminology" bucket (not NONE, not
    # genuinely-absent). Here: KNOWN_CODE + LOCAL_CODE + SUMMARY_BUILD_GAP = 3.
    assert proc["recoverable_hospitals"] == 3


def _fetch(report: dict[str, Any], ccn: str) -> dict[str, Any]:
    return next(c for c in report["matrix"] if c["ccn"] == ccn)


def test_candidate_discovery_never_marks_publishable() -> None:
    """A strong keyword match with only a local code must never read as covered."""
    engine = _engine()
    with Session(engine) as session:
        procedure, _cpt = _catalog(session)
        src, run = _src(session)
        facility = _facility(session, "990101", "DESC ONLY")
        # Exact consumer wording, but only a proprietary code and no reviewed mapping.
        _record(session, facility, src, run, "CDM", "LOCAL999", "COMPLETE BLOOD COUNT")
        session.commit()
        report = audit(session, state="NH")
    engine.dispose()

    cell = _fetch(report, "990101")
    assert cell["publishable"] is False
    assert cell["reviewed_mapped"] is False
    assert cell["approved_code_present"] is False
    assert cell["candidate_count"] >= 1
    assert cell["root_cause"] == "LOCAL_CODE_NEEDS_REVIEW"
    assert report["per_procedure"]["complete-blood-count"]["publishing_hospitals"] == 0
