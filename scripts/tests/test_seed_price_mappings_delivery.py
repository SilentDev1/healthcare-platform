"""Guards the reviewed maternity registry mappings against false positives.

Delivery mappings are exact code→procedure entries (never description regex), so a
lookalike can only slip in if a wrong CODE is registered. These tests assert the
registry maps exactly the reviewed delivery codes and that unrelated obstetric,
neonatal, surgical, sterilization-bundle and VBAC codes cannot map into
vaginal/cesarean delivery.
"""

from collections import defaultdict

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from packages.database import (
    Base,
    Procedure,
    ProcedureCodeMapping,
    ProcedureCodeSystem,
)
from scripts.seed_price_mappings import seed_price_mappings
from scripts.seed_procedure_catalog import seed_catalog


def _mapping_index(session: Session) -> dict[tuple[str, str], set[str]]:
    rows = session.execute(
        select(ProcedureCodeSystem.code_system, ProcedureCodeMapping.code, Procedure.slug)
        .join(ProcedureCodeSystem, ProcedureCodeSystem.id == ProcedureCodeMapping.code_system_id)
        .join(Procedure, Procedure.id == ProcedureCodeMapping.procedure_id)
        .where(ProcedureCodeMapping.mapping_status.in_(["approved", "reviewed"]))
    ).all()
    idx: dict[tuple[str, str], set[str]] = defaultdict(set)
    for sysname, code, slug in rows:
        idx[(str(sysname), str(code))].add(str(slug))
    return idx


def _seed() -> Session:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session = Session(engine)
    seed_catalog(session)
    seed_price_mappings(session)
    session.commit()
    return session


def test_reviewed_delivery_codes_are_mapped() -> None:
    idx = _mapping_index(_seed())
    for code in ("805", "806", "807", "775", "774"):
        assert "vaginal-delivery" in idx[("MS_DRG", code)]
    for code in ("59400", "59409", "59410"):
        assert "vaginal-delivery" in idx[("CPT", code)]
    for code in ("786", "787", "788", "766", "765"):
        assert "cesarean-delivery" in idx[("MS_DRG", code)]
    for code in ("59510", "59514", "59515"):
        assert "cesarean-delivery" in idx[("CPT", code)]


def test_lookalike_codes_never_map_to_delivery() -> None:
    idx = _mapping_index(_seed())
    excluded = [
        ("MS_DRG", "767"),  # actually "Vaginal delivery w/ sterilization/D&C"
        ("MS_DRG", "768"),  # vaginal delivery w/ O.R. procedure
        ("MS_DRG", "796"),
        ("MS_DRG", "797"),
        ("MS_DRG", "798"),  # vaginal w/ sterilization/D&C
        ("MS_DRG", "783"),
        ("MS_DRG", "784"),
        ("MS_DRG", "785"),  # cesarean w/ sterilization
        ("MS_DRG", "789"),
        ("MS_DRG", "790"),
        ("MS_DRG", "793"),
        ("MS_DRG", "794"),
        ("MS_DRG", "795"),  # neonates
        ("CPT", "59610"),
        ("CPT", "59612"),
        ("CPT", "59618"),
        ("CPT", "59620"),  # VBAC
        ("CPT", "59425"),
        ("CPT", "59426"),
        ("CPT", "59430"),  # antepartum / postpartum only
        ("CPT", "59812"),
        ("CPT", "59820"),  # D&C / missed abortion
        ("CPT", "58150"),  # hysterectomy
    ]
    for key in excluded:
        procs = idx.get(key, set())
        assert "vaginal-delivery" not in procs, key
        assert "cesarean-delivery" not in procs, key


def test_no_cross_contamination_between_vaginal_and_cesarean() -> None:
    idx = _mapping_index(_seed())
    # A vaginal code must not also register as cesarean, and vice versa.
    assert "cesarean-delivery" not in idx[("MS_DRG", "807")]
    assert "cesarean-delivery" not in idx[("CPT", "59409")]
    assert "vaginal-delivery" not in idx[("MS_DRG", "788")]
    assert "vaginal-delivery" not in idx[("CPT", "59514")]


def test_misregistered_767_is_superseded_not_deleted() -> None:
    from packages.database import ProcedureCodeSystem

    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        seed_catalog(session)
        cesarean = session.scalar(select(Procedure).where(Procedure.slug == "cesarean-delivery"))
        ms_drg = session.scalar(
            select(ProcedureCodeSystem).where(ProcedureCodeSystem.code_system == "MS_DRG")
        )
        assert cesarean is not None and ms_drg is not None
        # Simulate the pre-existing mis-registration (approved 767 -> cesarean).
        session.add(
            ProcedureCodeMapping(
                procedure_id=cesarean.id,
                code_system_id=ms_drg.id,
                code="767",
                mapping_status="approved",
                version="stale",
            )
        )
        session.commit()

        seed_price_mappings(session)
        session.commit()

        idx = _mapping_index(session)
        assert "cesarean-delivery" not in idx.get(("MS_DRG", "767"), set())  # de-approved
        row = session.scalar(select(ProcedureCodeMapping).where(ProcedureCodeMapping.code == "767"))
        assert row is not None  # kept for provenance, not deleted
        assert row.mapping_status == "superseded"
    engine.dispose()
