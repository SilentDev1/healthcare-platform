"""Tests for the parsed-but-unmapped facility diagnostic (read-only)."""

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, cast

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session

from packages.database import (
    Base,
    Facility,
    FacilityLocation,
    FacilityProcedurePriceSummary,
    HospitalPriceRecord,
    ImportRun,
    PriceRecordProcedureMapping,
    PriceServiceCode,
    Procedure,
    ProcedureCategory,
    SourceFile,
)
from packages.database.models import ImportStatus, SourceStatus
from scripts.diagnose_unmapped_facilities import diagnose


def _engine() -> Engine:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    return engine


def _facility(session: Session, ccn: str, name: str, state: str = "NH") -> Facility:
    facility = Facility(cms_certification_number=ccn, legal_name=name, display_name=name)
    facility.locations.append(
        FacilityLocation(
            address_line_1="1 Test St", city="Concord", state=state, postal_code="03301"
        )
    )
    session.add(facility)
    session.flush()
    return facility


def _source_and_run(session: Session) -> tuple[SourceFile, ImportRun]:
    source = SourceFile(
        source_name="mrf",
        source_url="https://example.test/mrf.csv",
        source_type="hospital_price_mrf",
        storage_path="/tmp/mrf.csv",
        checksum_sha256="c" * 64,
        file_size=10,
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


def _procedure(session: Session) -> Procedure:
    category = ProcedureCategory(slug="labs", name="Labs", description="Lab tests")
    session.add(category)
    session.flush()
    procedure = Procedure(
        slug="complete-blood-count",
        consumer_name="Complete Blood Count",
        short_description="CBC",
        long_description="Complete blood count",
        category_id=category.id,
        service_setting="outpatient",
        complexity="low",
    )
    session.add(procedure)
    session.flush()
    return procedure


def _record(
    session: Session,
    facility: Facility,
    source: SourceFile,
    run: ImportRun,
    code_system: str,
    code: str,
    description: str,
    raw_code_type: str | None = None,
    raw_payload: dict[str, object] | None = None,
) -> HospitalPriceRecord:
    record = HospitalPriceRecord(
        facility_id=facility.id,
        source_file_id=source.id,
        import_run_id=run.id,
        source_record_identifier=str(uuid.uuid4()),
        source_payload_hash=uuid.uuid4().hex,
        raw_description=description,
        service_description_normalized=description.lower(),
        setting="outpatient",
        billing_class="facility",
        raw_payload=raw_payload if raw_payload is not None else {},
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
            raw_code_type=raw_code_type if raw_code_type is not None else code_system,
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
    session: Session, facility: Facility, procedure: Procedure, source: SourceFile
) -> None:
    session.add(
        FacilityProcedurePriceSummary(
            facility_id=facility.id,
            facility_location_id=facility.locations[0].id,
            procedure_id=procedure.id,
            service_setting="outpatient",
            included_component_scope="facility",
            cash_price_median=Decimal("100"),
            record_count=1,
            source_file_id=source.id,
            calculated_at=datetime.now(UTC),
            publication_status="publishable",
            completeness_score=Decimal("100"),
        )
    )
    session.flush()


def test_diagnose_identifies_parsed_but_unmapped_and_ranks_codes() -> None:
    engine = _engine()
    with Session(engine) as session:
        source, run = _source_and_run(session)
        procedure = _procedure(session)

        # A: records + a publishable summary → excluded.
        published = _facility(session, "990201", "PUBLISHED HOSPITAL")
        rec_a = _record(session, published, source, run, "CPT", "85025", "CBC")
        _reviewed_mapping(session, rec_a, procedure)
        _publishable_summary(session, published, procedure, source)

        # B: records, no reviewed mapping, no summary → parsed-but-unmapped.
        # Model a proprietary chargemaster: local code, non-standard type label,
        # and a raw_payload carrying a standard code column the parser didn't prefer.
        unmapped = _facility(session, "990202", "UNMAPPED HOSPITAL")
        for _ in range(2):
            _record(
                session,
                unmapped,
                source,
                run,
                "CDM",
                "ABC123",
                "LOCAL LAB PANEL",
                raw_code_type="LOCAL",
                raw_payload={
                    "code": "ABC123",
                    "cpt_hcpcs": "80053",
                    "description": "LOCAL LAB PANEL",
                },
            )
        _record(
            session,
            unmapped,
            source,
            run,
            "CDM",
            "XYZ999",
            "LOCAL IMAGING",
            raw_code_type="LOCAL",
            raw_payload={"code": "XYZ999", "cpt_hcpcs": "70450", "description": "LOCAL IMAGING"},
        )

        # C: records + reviewed mapping but no publishable summary → investigate.
        stuck = _facility(session, "990203", "STUCK HOSPITAL")
        rec_c = _record(session, stuck, source, run, "CPT", "80053", "CMP")
        _reviewed_mapping(session, rec_c, procedure)

        # D: no records → excluded.
        _facility(session, "990204", "EMPTY HOSPITAL")

        # Out-of-state facility with the same problem → excluded by state filter.
        ma = _facility(session, "220001", "MASS HOSPITAL", state="MA")
        _record(session, ma, source, run, "CDM", "MA111", "OUT OF STATE")

        session.commit()

        report = diagnose(session, state="NH", top_codes=25)

    engine.dispose()

    assert report["state"] == "NH"
    entries = cast("list[dict[str, Any]]", report["parsed_but_unmapped"])
    by_ccn = {item["ccn"]: item for item in entries}
    assert set(by_ccn) == {"990202", "990203"}

    unmapped_entry = by_ccn["990202"]
    assert unmapped_entry["likely_cause"] == "no_approved_code_mappings"
    assert unmapped_entry["records"] == 3
    assert unmapped_entry["reviewed_mappings"] == 0
    # Codes ranked by frequency; the doubled CDM code leads.
    top = unmapped_entry["top_unmapped_codes"]
    assert top[0]["code"] == "ABC123"
    assert top[0]["count"] == 2
    assert top[0]["sample_description"] == "LOCAL LAB PANEL"
    assert top[0]["raw_code_type"] == "LOCAL"
    assert {c["code"] for c in top} == {"ABC123", "XYZ999"}
    assert unmapped_entry["code_system_distribution"] == {"CDM": 3}
    # Raw source type label surfaced — the signal for parser-fix vs. crosswalk.
    assert unmapped_entry["raw_code_type_distribution"] == {"LOCAL": 3}
    # Sample raw rows expose the standard code column the parser didn't prefer.
    samples = unmapped_entry["raw_payload_samples"]
    assert samples and len(samples) == 3
    assert all(s["raw_code_type"] == "LOCAL" for s in samples)
    assert any(s["raw_payload"].get("cpt_hcpcs") == "80053" for s in samples)

    stuck_entry = by_ccn["990203"]
    assert stuck_entry["likely_cause"] == "mapped_but_not_publishable_investigate"
    assert stuck_entry["reviewed_mappings"] == 1
    # A record with a reviewed mapping is not surfaced as an unmapped code.
    assert stuck_entry["top_unmapped_codes"] == []


def test_diagnose_reports_empty_when_all_publishable() -> None:
    engine = _engine()
    with Session(engine) as session:
        source, run = _source_and_run(session)
        procedure = _procedure(session)
        facility = _facility(session, "990301", "GOOD HOSPITAL")
        rec = _record(session, facility, source, run, "CPT", "85025", "CBC")
        _reviewed_mapping(session, rec, procedure)
        _publishable_summary(session, facility, procedure, source)
        session.commit()

        report = diagnose(session, state="NH")
    engine.dispose()

    assert report["parsed_but_unmapped_count"] == 0
    assert report["parsed_but_unmapped"] == []
