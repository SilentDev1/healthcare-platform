"""Bidirectional CPT<->HCPCS equivalence: G-codes and numerics aliased both ways, not DRG."""

from __future__ import annotations

# ruff: noqa: E501
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from packages.database import (
    Base,
    Procedure,
    ProcedureCategory,
    ProcedureCodeMapping,
    ProcedureCodeSystem,
)
from scripts.remediate_code_system_bidirectional import BIDIR_VERSION, remediate


def _session() -> Session:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    return Session(engine)


def _build(session: Session):
    cat = ProcedureCategory(slug="c", name="C", description="d", sort_order=0)
    session.add(cat)
    session.flush()
    awv = Procedure(slug="annual-wellness-visit", consumer_name="AWV", short_description="s",
                    long_description="l", category_id=cat.id, service_setting="outpatient",
                    complexity="low", active=True)
    cbc = Procedure(slug="cbc", consumer_name="CBC", short_description="s", long_description="l",
                    category_id=cat.id, service_setting="outpatient", complexity="low", active=True)
    drg = Procedure(slug="knee", consumer_name="Knee", short_description="s", long_description="l",
                    category_id=cat.id, service_setting="inpatient", complexity="high", active=True)
    session.add_all([awv, cbc, drg])
    hcpcs = ProcedureCodeSystem(code_system="HCPCS", display_name="H", licensing_notes="n", active=True)
    cpt = ProcedureCodeSystem(code_system="CPT", display_name="C", licensing_notes="n", active=True)
    msdrg = ProcedureCodeSystem(code_system="MS_DRG", display_name="D", licensing_notes="n", active=True)
    session.add_all([hcpcs, cpt, msdrg])
    session.flush()
    # AWV approved only under HCPCS (G0438) -> must gain CPT:G0438
    session.add(ProcedureCodeMapping(procedure_id=awv.id, code_system_id=hcpcs.id, code="G0438", mapping_status="approved"))
    # CBC approved only under CPT (85025) -> must gain HCPCS:85025
    session.add(ProcedureCodeMapping(procedure_id=cbc.id, code_system_id=cpt.id, code="85025", mapping_status="approved"))
    # knee approved under MS_DRG (470) -> must NOT be aliased to CPT/HCPCS
    session.add(ProcedureCodeMapping(procedure_id=drg.id, code_system_id=msdrg.id, code="470", mapping_status="approved"))
    session.commit()
    return awv, cbc, drg, cpt, hcpcs


def _codes(session, proc_id, sys_code):
    sys = session.scalar(select(ProcedureCodeSystem).where(ProcedureCodeSystem.code_system == sys_code))
    return sorted(session.scalars(select(ProcedureCodeMapping.code).where(
        ProcedureCodeMapping.procedure_id == proc_id, ProcedureCodeMapping.code_system_id == sys.id)))


def test_bidirectional_aliases_gcode_and_numeric_not_drg() -> None:
    session = _session()
    awv, cbc, drg, cpt, hcpcs = _build(session)
    result = remediate(session, apply=True)
    assert result["aliases_added"] == 2  # G0438->CPT, 85025->HCPCS
    assert _codes(session, awv.id, "CPT") == ["G0438"]
    assert _codes(session, cbc.id, "HCPCS") == ["85025"]
    # MS_DRG never aliased into CPT/HCPCS
    assert _codes(session, drg.id, "CPT") == []
    assert _codes(session, drg.id, "HCPCS") == []
    # tagged reversible
    alias = session.scalar(select(ProcedureCodeMapping).where(
        ProcedureCodeMapping.procedure_id == awv.id,
        ProcedureCodeMapping.code_system_id == cpt.id))
    assert alias.version == BIDIR_VERSION


def test_idempotent() -> None:
    session = _session()
    _build(session)
    remediate(session, apply=True)
    second = remediate(session, apply=True)
    assert second["aliases_added"] == 0
