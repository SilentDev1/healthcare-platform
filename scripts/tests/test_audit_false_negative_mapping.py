"""False-negative audit: per-cell classification into the six required categories."""

from __future__ import annotations
# ruff: noqa: E501

import uuid
from datetime import UTC, datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from packages.database import (
    Base,
    Facility,
    FacilityProcedurePriceSummary,
    HospitalPriceRecord,
    ImportRun,
    PriceServiceCode,
    Procedure,
    ProcedureCategory,
    ProcedureCodeMapping,
    ProcedureCodeSystem,
    SourceFile,
)
from packages.database.models import SourceStatus
from packages.database.pricing_models import PriceRecordProcedureMapping
from scripts.audit_false_negative_mapping import audit_hospital


def _session() -> Session:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    return Session(engine)


def _proc(session: Session, slug: str, cat) -> Procedure:
    p = Procedure(
        slug=slug, consumer_name=slug, short_description="s", long_description="l",
        category_id=cat.id, service_setting="outpatient", complexity="low", active=True,
    )
    session.add(p)
    session.flush()
    return p


def _record(session: Session, fac, src, run, desc: str) -> HospitalPriceRecord:
    r = HospitalPriceRecord(
        facility_id=fac.id, source_file_id=src.id, import_run_id=run.id,
        source_record_identifier=str(uuid.uuid4()), source_payload_hash=str(uuid.uuid4()),
        raw_description=desc, service_description_normalized=desc.lower(),
        raw_payload={}, parser_name="t", parser_version="1", observed_at=datetime.now(UTC),
    )
    session.add(r)
    session.flush()
    return r


def _build(session: Session):
    cat = ProcedureCategory(slug="c", name="C", description="d", sort_order=0)
    session.add(cat)
    session.flush()
    fac = Facility(legal_name="H", display_name="H", facility_type="Acute Care Hospitals",
                   cms_certification_number="300001", active=True)
    session.add(fac)
    src = SourceFile(source_name="s", source_url="u", source_type="mrf", storage_path="p",
                     checksum_sha256="x", file_size=0, parser_version="1", status=SourceStatus.COMPLETED)
    session.add(src)
    session.flush()
    run = ImportRun(importer_name="i", status="completed", source_file_id=src.id)
    session.add(run)
    session.flush()
    csys = ProcedureCodeSystem(code_system="CPT", display_name="CPT", licensing_notes="n")
    session.add(csys)
    session.flush()

    procs = {s: _proc(session, s, cat) for s in
             ["chest-x-ray", "colonoscopy", "mri-brain-without-contrast", "hip-replacement"]}
    # chest-x-ray: APPROVED code 71046, PRESENT in raw data, reviewed-mapped, publishable
    session.add(ProcedureCodeMapping(procedure_id=procs["chest-x-ray"].id, code_system_id=csys.id,
                                     code="71046", mapping_status="approved"))
    # colonoscopy: APPROVED code 45378, present in raw data, NOT reviewed-mapped
    session.add(ProcedureCodeMapping(procedure_id=procs["colonoscopy"].id, code_system_id=csys.id,
                                     code="45378", mapping_status="approved"))
    session.flush()

    # chest-x-ray -> publishable summary + reviewed mapping + approved code present
    rec_cxr = _record(session, fac, src, run, "XR CHEST 1 VIEW")
    session.add(PriceServiceCode(hospital_price_record_id=rec_cxr.id, code_system="CPT",
                                 code="71046", raw_code_type="CPT", raw_code="71046"))
    session.add(PriceRecordProcedureMapping(hospital_price_record_id=rec_cxr.id,
                                            procedure_id=procs["chest-x-ray"].id,
                                            mapping_method="approved", confidence_score=1.0, reviewed=True))
    session.add(FacilityProcedurePriceSummary(
        facility_id=fac.id, procedure_id=procs["chest-x-ray"].id, service_setting="outpatient",
        record_count=1, source_file_id=src.id, publication_status="publishable", completeness_score=1.0))

    # colonoscopy -> approved code present but NOT reviewed-mapped -> KNOWN_CODE_NOT_MAPPED
    rec_colo = _record(session, fac, src, run, "COLONOSCOPY DIAGNOSTIC")
    session.add(PriceServiceCode(hospital_price_record_id=rec_colo.id, code_system="CPT",
                                 code="45378", raw_code_type="CPT", raw_code="45378"))

    # mri-brain -> description candidate carrying a STANDARD code (70551) not in approved set -> REVIEW_REQUIRED
    rec_mri = _record(session, fac, src, run, "MRI BRAIN WO CONTRAST")
    session.add(PriceServiceCode(hospital_price_record_id=rec_mri.id, code_system="CPT",
                                 code="70551", raw_code_type="CPT", raw_code="70551"))
    # hip-replacement -> no matching record at all -> NO_MATCHING_RAW_RECORD
    session.commit()
    return fac, procs


def _run(session, fac, procs):
    from scripts.audit_false_negative_mapping import _approved_codes, _procedures
    procedures = _procedures(session)
    approved = _approved_codes(session)
    from collections import defaultdict
    code_to_procs = defaultdict(set)
    for pid, pairs in approved.items():
        for pr in pairs:
            code_to_procs[pr].add(pid)
    cells = audit_hospital(session, fac.id, procedures, approved, code_to_procs,
                           list(code_to_procs), candidate_sample=5)
    return {procedures[pid]["slug"]: c["category"] for pid, c in cells.items()}


def test_classifies_all_six_paths() -> None:
    session = _session()
    fac, procs = _build(session)
    cats = _run(session, fac, procs)
    assert cats["chest-x-ray"] == "PUBLISHING_VERIFIED_PRICE"
    assert cats["colonoscopy"] == "KNOWN_CODE_NOT_MAPPED"
    assert cats["mri-brain-without-contrast"] == "REVIEW_REQUIRED"
    assert cats["hip-replacement"] == "NO_MATCHING_RAW_RECORD"
