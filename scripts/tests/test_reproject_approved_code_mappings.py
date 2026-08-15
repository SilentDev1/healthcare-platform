"""Test the approved-code reprojection: add for new codes, remove orphaned mappings."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from packages.database import (
    Base,
    Facility,
    FacilityLocation,
    HospitalPriceRecord,
    ImportRun,
    PriceRecordProcedureMapping,
    PriceServiceCode,
    Procedure,
    SourceFile,
)
from packages.database.models import ImportStatus, SourceStatus
from scripts.reproject_approved_code_mappings import apply_plan, build_plan
from scripts.seed_price_mappings import seed_price_mappings
from scripts.seed_procedure_catalog import seed_catalog


def _record(
    session: Session,
    facility_id: uuid.UUID,
    source_file_id: uuid.UUID,
    import_run_id: uuid.UUID,
    *,
    description: str,
    code_system: str | None,
    code: str | None,
    map_to: uuid.UUID | None,
) -> uuid.UUID:
    rec = HospitalPriceRecord(
        facility_id=facility_id,
        source_file_id=source_file_id,
        import_run_id=import_run_id,
        source_record_identifier=description,
        source_payload_hash=uuid.uuid4().hex,
        raw_description=description,
        raw_payload={},
        parser_name="cms_hpt_csv",
        parser_version="1.0.0",
        observed_at=datetime.now(UTC),
    )
    session.add(rec)
    session.flush()
    if code_system and code:
        session.add(
            PriceServiceCode(
                hospital_price_record_id=rec.id,
                code_system=code_system,
                code=code,
                raw_code_type=code_system,
                raw_code=code,
            )
        )
    if map_to is not None:
        session.add(
            PriceRecordProcedureMapping(
                hospital_price_record_id=rec.id,
                procedure_id=map_to,
                mapping_method="exact_approved_code",
                confidence_score=1,
                reviewed=True,
            )
        )
    session.flush()
    return rec.id


def test_reprojection_adds_new_and_removes_orphaned() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        seed_catalog(session)
        seed_price_mappings(session)
        vaginal = session.scalar(select(Procedure).where(Procedure.slug == "vaginal-delivery"))
        cesarean = session.scalar(select(Procedure).where(Procedure.slug == "cesarean-delivery"))
        assert vaginal is not None and cesarean is not None
        vaginal_id = vaginal.id
        cesarean_id = cesarean.id

        facility = Facility(
            cms_certification_number="990040", legal_name="T HOSPITAL", display_name="T"
        )
        facility.locations.append(
            FacilityLocation(
                address_line_1="1 Test St", city="Concord", state="NH", postal_code="03301"
            )
        )
        session.add(facility)
        session.flush()
        source = SourceFile(
            source_name="mrf",
            source_url="https://example.test/f.csv",
            source_type="hospital_price_mrf",
            storage_path="/tmp/f.csv",
            checksum_sha256="b" * 64,
            file_size=1,
            parser_version="1.0.0",
            status=SourceStatus.COMPLETED,
        )
        session.add(source)
        session.flush()
        run = ImportRun(
            importer_name="hospital_prices",
            status=ImportStatus.COMPLETED,
            source_file_id=source.id,
        )
        session.add(run)
        session.flush()

        # A: approved vaginal code (MS-DRG 807), NO mapping yet -> should ADD.
        add_rec = _record(
            session,
            facility.id,
            source.id,
            run.id,
            description="Vaginal Delivery Without Sterilization",
            code_system="MS_DRG",
            code="807",
            map_to=None,
        )
        # B: mapped to cesarean but its code (767) is NOT approved -> orphan, REMOVE.
        orphan_rec = _record(
            session,
            facility.id,
            source.id,
            run.id,
            description="Vaginal Delivery W Sterilization",
            code_system="MS_DRG",
            code="767",
            map_to=cesarean_id,
        )
        # C: approved vaginal code AND already mapped -> unchanged.
        keep_rec = _record(
            session,
            facility.id,
            source.id,
            run.id,
            description="Vaginal Delivery Without Sterilization w CC",
            code_system="MS_DRG",
            code="806",
            map_to=vaginal_id,
        )
        session.commit()

        plan = build_plan(session, "NH", ["vaginal-delivery", "cesarean-delivery"])
        assert plan["mappings_to_add"] == 1
        assert plan["add_manifest"][0]["record_id"] == str(add_rec)
        assert plan["add_manifest"][0]["procedure_slug"] == "vaginal-delivery"
        assert plan["mappings_to_remove"] == 1
        assert plan["remove_manifest"][0]["record_id"] == str(orphan_rec)
        assert plan["remove_manifest"][0]["procedure_slug"] == "cesarean-delivery"

        apply_plan(session, plan)

    with Session(engine) as verify:
        # add_rec now maps to vaginal; orphan_rec no longer maps to cesarean; keep_rec intact.
        add_map = verify.scalar(
            select(func.count(PriceRecordProcedureMapping.id)).where(
                PriceRecordProcedureMapping.hospital_price_record_id == add_rec,
                PriceRecordProcedureMapping.procedure_id == vaginal_id,
            )
        )
        assert add_map == 1
        orphan_map = verify.scalar(
            select(func.count(PriceRecordProcedureMapping.id)).where(
                PriceRecordProcedureMapping.hospital_price_record_id == orphan_rec
            )
        )
        assert orphan_map == 0
        keep_map = verify.scalar(
            select(func.count(PriceRecordProcedureMapping.id)).where(
                PriceRecordProcedureMapping.hospital_price_record_id == keep_rec
            )
        )
        assert keep_map == 1
        # Raw records untouched.
        assert (verify.scalar(select(func.count(HospitalPriceRecord.id))) or 0) == 3
    engine.dispose()
