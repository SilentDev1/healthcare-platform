"""Safety test for the crosswalk false-positive remediation.

Proves the surgical removal deletes ONLY mappings the corrected crosswalk no longer
supports (a ciprofloxacin-DEXAMETHASONE drug mis-mapped to a DXA bone-density scan)
while preserving a genuine DEXA record that still resolves to the same code.
"""

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
from scripts.remediate_crosswalk_false_positives import apply_remediation, build_manifest
from scripts.seed_price_mappings import seed_price_mappings
from scripts.seed_procedure_catalog import seed_catalog


def _record_with_mapping(
    session: Session,
    facility_id: uuid.UUID,
    source_file_id: uuid.UUID,
    import_run_id: uuid.UUID,
    procedure_id: uuid.UUID,
    *,
    description: str,
    raw_code: str,
) -> uuid.UUID:
    """A record whose CDM code was crosswalk-resolved to CPT 77080 and mapped to DXA."""
    rec = HospitalPriceRecord(
        facility_id=facility_id,
        source_file_id=source_file_id,
        import_run_id=import_run_id,
        source_record_identifier=raw_code,
        source_payload_hash=uuid.uuid4().hex,
        raw_description=description,
        raw_payload={},
        parser_name="cms_hpt_csv",
        parser_version="1.0.0",
        observed_at=datetime.now(UTC),
    )
    session.add(rec)
    session.flush()
    session.add(
        PriceServiceCode(
            hospital_price_record_id=rec.id,
            code_system="CPT",  # resolved by the (old, broad) crosswalk
            code="77080",
            raw_code_type="CDM",  # original local type
            raw_code=raw_code,
        )
    )
    session.add(
        PriceRecordProcedureMapping(
            hospital_price_record_id=rec.id,
            procedure_id=procedure_id,
            mapping_method="exact_approved_code",
            confidence_score=1,
            reviewed=True,
        )
    )
    session.flush()
    return rec.id


def test_remediation_removes_false_positive_keeps_legit() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        seed_catalog(session)  # creates the procedure catalog (bone-density-scan, ...)
        seed_price_mappings(session)  # seeds bone-density-scan -> CPT 77080 (approved)
        dxa = session.scalar(select(Procedure).where(Procedure.slug == "bone-density-scan"))
        assert dxa is not None

        facility = Facility(
            cms_certification_number="990030", legal_name="T HOSPITAL", display_name="T"
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
            checksum_sha256="a" * 64,
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

        # FALSE positive: a drug whose description the fixed crosswalk rejects.
        false_id = _record_with_mapping(
            session, facility.id, source.id, run.id, dxa.id,
            description="Ciprofloxacin-Dexamethasone Ear Drops Suspension",
            raw_code="DEXDROP",
        )
        # LEGIT: a real DEXA scan that still resolves to 77080 under the fixed crosswalk.
        legit_id = _record_with_mapping(
            session, facility.id, source.id, run.id, dxa.id,
            description="DEXA Axial Bone Density",
            raw_code="BDXA",
        )
        session.commit()

        manifest = build_manifest(session, "NH")
        assert manifest["mappings_to_delete"] == 1
        only = manifest["mapping_manifest"][0]
        assert only["record_id"] == str(false_id)
        assert only["procedure_slug"] == "bone-density-scan"
        assert only["contributes_to_public_price"] is False  # no summaries in this fixture
        assert manifest["code_slots_to_revert"] == 1

        apply_remediation(session, manifest)

    with Session(engine) as verify:
        # The false mapping is gone; the legit one survives.
        remaining = verify.scalars(select(PriceRecordProcedureMapping)).all()
        assert len(remaining) == 1
        assert remaining[0].hospital_price_record_id == legit_id
        # The false slot was reverted to its raw local code; the legit slot untouched.
        false_slot = verify.scalar(
            select(PriceServiceCode).where(
                PriceServiceCode.hospital_price_record_id == false_id
            )
        )
        assert false_slot is not None
        assert false_slot.code_system == "CDM"
        assert false_slot.code == "DEXDROP"
        legit_slot = verify.scalar(
            select(PriceServiceCode).where(
                PriceServiceCode.hospital_price_record_id == legit_id
            )
        )
        assert legit_slot is not None
        assert legit_slot.code_system == "CPT" and legit_slot.code == "77080"
        # Raw price records are never deleted.
        assert (verify.scalar(select(func.count(HospitalPriceRecord.id))) or 0) == 2
    engine.dispose()
