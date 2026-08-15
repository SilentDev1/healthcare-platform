"""Regression: the everyday consumer queries we found broken must resolve.

Specifically proves "lab tests"/"blood work" resolve to the Laboratory category
(never 0 results), "childbirth" presents both deliveries, ambiguous scans clarify
rather than assuming MRI, and common natural wording reaches the deterministic
resolver. All deterministic — no LLM.
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from packages.database import Base
from packages.search.resolution import resolve_search
from packages.search.service import rebuild_index
from scripts.seed_procedure_catalog import seed_catalog


@pytest.fixture(scope="module")
def session() -> Session:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    s = Session(engine)
    seed_catalog(s)
    s.commit()
    rebuild_index(s)
    s.commit()
    return s


CATEGORY_CASES = [
    ("lab tests", "laboratory"),
    ("laboratory", "laboratory"),
    ("blood work", "laboratory"),
    ("I need a blood test", "laboratory"),
    ("labs", "laboratory"),
    ("ER", "emergency"),
    ("emergency room", "emergency"),
    ("rehab", "rehabilitation"),
    ("imaging", "imaging"),
    ("childbirth", "maternity"),
]

PROCEDURE_CASES = [
    "cbc",
    "complete blood count",
    "knee MRI",
    "MRI knee",
    "MRI of my knee",
    "I need an MRI for my knee",
    "vaginal delivery",
    "C section",
    "cesarean",
    "urgent care",
    "physical therapy",
    "I need physical therapy",
]

AMBIGUOUS_CASES = [
    "knee scan",  # must NOT assume MRI
    "give birth",
    "how much does it cost to have a baby",
]


@pytest.mark.parametrize("query,category", CATEGORY_CASES)
def test_category_queries_resolve(session: Session, query: str, category: str) -> None:
    r = resolve_search(session, query)
    assert r.intent_type.value == "category", f"{query!r} -> {r.intent_type.value}"
    assert r.canonical_category_slug == category
    assert r.results, f"{query!r} returned 0 results"


@pytest.mark.parametrize("query", PROCEDURE_CASES)
def test_procedure_queries_resolve(session: Session, query: str) -> None:
    r = resolve_search(session, query)
    assert r.intent_type.value == "procedure", f"{query!r} -> {r.intent_type.value}"


@pytest.mark.parametrize("query", AMBIGUOUS_CASES)
def test_ambiguous_queries_clarify(session: Session, query: str) -> None:
    r = resolve_search(session, query)
    assert r.intent_type.value in {"ambiguous", "category"}
    assert r.clarification_needed or r.intent_type.value == "category"


def test_childbirth_presents_both_deliveries(session: Session) -> None:
    r = resolve_search(session, "childbirth")
    titles = {x.title for x in r.results if x.entity_type == "procedure"}
    assert "Vaginal delivery" in titles
    assert "Cesarean delivery" in titles


def test_knee_scan_does_not_assume_mri(session: Session) -> None:
    r = resolve_search(session, "knee scan")
    assert r.clarification_needed is True
    assert r.intent_type.value == "ambiguous"
