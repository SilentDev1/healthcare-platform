"""CPT->HCPCS Level-I equivalence remediation: numeric-only, additive, reversible."""

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
from scripts.remediate_code_system_equivalence import EQUIV_VERSION, remediate


def _session() -> Session:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    return Session(engine)


def _build(session: Session):
    cat = ProcedureCategory(slug="c", name="C", description="d", sort_order=0)
    session.add(cat)
    session.flush()
    p = Procedure(slug="cbc", consumer_name="CBC", short_description="s", long_description="l",
                  category_id=cat.id, service_setting="outpatient", complexity="low", active=True)
    session.add(p)
    cpt = ProcedureCodeSystem(code_system="CPT", display_name="CPT", licensing_notes="n",
                              public_display_allowed=True, active=True)
    rev = ProcedureCodeSystem(code_system="REV_CODE", display_name="Rev", licensing_notes="n", active=True)
    session.add_all([cpt, rev])
    session.flush()
    # numeric CPT (aliasable), a Level-II alphanumeric HCPCS-style CPT (should NOT alias),
    # and a REV_CODE (should NOT alias)
    session.add(ProcedureCodeMapping(procedure_id=p.id, code_system_id=cpt.id, code="85025",
                                     mapping_status="approved"))
    session.add(ProcedureCodeMapping(procedure_id=p.id, code_system_id=cpt.id, code="G0306",
                                     mapping_status="approved"))
    session.add(ProcedureCodeMapping(procedure_id=p.id, code_system_id=rev.id, code="0300",
                                     mapping_status="approved"))
    session.commit()
    return p


def test_aliases_only_numeric_cpt_codes() -> None:
    session = _session()
    p = _build(session)
    result = remediate(session, apply=True)
    assert result["hcpcs_aliases_added"] == 1  # only 85025
    hcpcs = session.scalar(select(ProcedureCodeSystem).where(ProcedureCodeSystem.code_system == "HCPCS"))
    aliases = list(session.scalars(
        select(ProcedureCodeMapping).where(ProcedureCodeMapping.code_system_id == hcpcs.id)
    ))
    assert len(aliases) == 1
    a = aliases[0]
    assert a.code == "85025" and a.procedure_id == p.id
    assert a.version == EQUIV_VERSION  # reversible marker
    assert a.mapping_status == "approved"


def test_idempotent() -> None:
    session = _session()
    _build(session)
    remediate(session, apply=True)
    second = remediate(session, apply=True)
    assert second["hcpcs_aliases_added"] == 0


def test_dry_run_persists_nothing() -> None:
    session = _session()
    _build(session)
    remediate(session, apply=False)
    hcpcs = session.scalar(select(ProcedureCodeSystem).where(ProcedureCodeSystem.code_system == "HCPCS"))
    # dry-run rolls back; the HCPCS system creation is rolled back too
    assert hcpcs is None
