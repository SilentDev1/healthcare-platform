"""Consumer-category taxonomy integrity.

Consumer categories are clinical service groupings, not care settings. No active
consumer-facing category may be empty (0 procedures) — an empty category renders a
confusing "0 procedures" and usually signals a setting/category confusion (e.g. the
removed 'inpatient-surgery'). The search registry and the DB catalog must agree.
"""

from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from packages.database import Base, Procedure, ProcedureCategory
from scripts.seed_procedure_catalog import seed_catalog


def _session() -> Session:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    s = Session(engine)
    seed_catalog(s)
    s.commit()
    return s


def test_no_active_consumer_category_is_empty() -> None:
    session = _session()
    empty = [
        (slug, name)
        for slug, name, count in session.execute(
            select(ProcedureCategory.slug, ProcedureCategory.name, func.count(Procedure.id))
            .select_from(ProcedureCategory)
            .outerjoin(Procedure, Procedure.category_id == ProcedureCategory.id)
            .where(ProcedureCategory.active.is_(True))
            .group_by(ProcedureCategory.id)
        )
        if count == 0
    ]
    assert empty == [], f"active categories with 0 procedures: {empty}"


def test_setting_based_inpatient_surgery_category_is_gone() -> None:
    session = _session()
    assert (
        session.scalar(
            select(ProcedureCategory).where(ProcedureCategory.slug == "inpatient-surgery")
        )
        is None
    ), "inpatient-surgery is a care setting, not a consumer category — must not be seeded"


def test_search_registry_matches_seeded_categories() -> None:
    """The consumer_procedure_categories.json registry must not name a category absent
    from the seeded catalog (which would index a phantom category into search)."""
    session = _session()
    seeded = {c.slug for c in session.scalars(select(ProcedureCategory))}
    registry = json.loads(
        (
            Path(__file__).resolve().parents[3] / "data" / "consumer_procedure_categories.json"
        ).read_text(encoding="utf-8")
    )
    registry_slugs = {item["slug"] for item in registry}
    assert registry_slugs <= seeded, (
        f"registry has categories not in catalog: {registry_slugs - seeded}"
    )
