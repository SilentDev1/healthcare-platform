"""Regression: the everyday consumer queries we found broken must resolve.

Specifically proves "lab tests"/"blood work" resolve to the Laboratory category
(never 0 results), "childbirth" presents both deliveries, ambiguous scans clarify
rather than assuming MRI, and common natural wording reaches the deterministic
resolver. All deterministic — no LLM.
"""

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from packages.database import Base, Procedure, ProcedureCategory
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


def _canonical_category_members(session: Session, slug: str) -> set[str]:
    """The exact membership /api/v1/procedures?category=<slug> lists."""
    return set(
        session.scalars(
            select(Procedure.slug)
            .join(ProcedureCategory)
            .where(ProcedureCategory.slug == slug, Procedure.active.is_(True))
        ).all()
    )


# Queries that resolve to a category VIA A LABEL/ALIAS not present in the member
# procedures' indexed text. These are exactly the cases that rendered a count with
# zero procedure cards in production (Postgres) before the canonical-membership fix.
# NOTE: on SQLite the Postgres-only text filter is skipped, so this asserts the
# invariant rather than reproducing the dialect-specific drop; the true regression
# guard is test_category_membership_postgres.py.
CATEGORY_MEMBERSHIP_CASES = [
    ("lab tests", "laboratory"),
    ("blood work", "laboratory"),
    ("labs", "laboratory"),
    ("laboratory", "laboratory"),
    ("imaging", "imaging"),
    ("scans", "imaging"),
]


@pytest.mark.parametrize("query,slug", CATEGORY_MEMBERSHIP_CASES)
def test_category_render_membership_matches_catalog(
    session: Session, query: str, slug: str
) -> None:
    """The rendered procedure set must equal the canonical catalog and the count.

    Guards against the search view showing "N procedures" with zero cards: the
    category_member results, the category's procedure_count, and the procedures
    directory membership must all agree.
    """
    r = resolve_search(session, query)
    assert r.canonical_category_slug == slug
    category = next(x for x in r.results if x.entity_type == "procedure_category")
    members = [
        x for x in r.results if x.entity_type == "procedure" and x.match_reason == "category_member"
    ]
    member_slugs = {str(x.metadata.get("slug")) for x in members}
    canonical = _canonical_category_members(session, slug)

    assert canonical, f"{slug!r} has no catalog procedures — fixture problem"
    assert member_slugs == canonical, (
        f"{query!r}: rendered members {member_slugs} != catalog {canonical}"
    )
    assert len(members) == category.metadata["procedure_count"], (
        f"{query!r}: rendered {len(members)} != procedure_count "
        f"{category.metadata['procedure_count']}"
    )
    # Every rendered card carries what the UI needs to navigate and match.
    for item in members:
        assert item.metadata.get("category") == slug
        assert item.metadata.get("slug")


def test_lab_member_absent_from_query_text_is_still_rendered(session: Session) -> None:
    """A member whose name shares no token with the query alias must still appear.

    "Surgical pathology examination" contains neither "blood" nor "work", so the
    old query-text-bounded expansion dropped it on Postgres.
    """
    r = resolve_search(session, "blood work")
    titles = {x.title for x in r.results if x.match_reason == "category_member"}
    assert "Surgical pathology examination" in titles
    assert "Complete blood count" in titles


def test_cbc_navigates_to_complete_blood_count(session: Session) -> None:
    r = resolve_search(session, "cbc")
    slugs = {str(x.metadata.get("slug")) for x in r.results if x.entity_type == "procedure"}
    assert "complete-blood-count" in slugs


# Consumer terms that phrase/prefix-match MULTIPLE procedures without matching any
# single procedure name exactly. resolve_search used to drop these prefix_or_phrase
# matches and return UNKNOWN with 0 results ("how can CT Scan be 0"). They must now
# resolve to procedure results the consumer can pick from — deterministically, no LLM.
PROCEDURE_PHRASE_CASES = [
    ("CT scan", {"CT scan of abdomen and pelvis", "CT scan of the chest"}),
    ("ct scan", {"CT scan of abdomen and pelvis", "CT scan of the chest"}),
    ("mammogram", {"Screening mammogram", "Diagnostic mammogram"}),
]


@pytest.mark.parametrize("query,expected", PROCEDURE_PHRASE_CASES)
def test_phrase_procedure_matches_resolve(session: Session, query: str, expected: set[str]) -> None:
    r = resolve_search(session, query)
    assert r.intent_type.value == "procedure", f"{query!r} -> {r.intent_type.value}"
    titles = {x.title for x in r.results if x.entity_type == "procedure"}
    assert expected <= titles, f"{query!r}: {titles} missing {expected - titles}"


def test_phrase_fallback_does_not_override_clarification(session: Session) -> None:
    """The new procedure fallback must not swallow ambiguous-scan clarification."""
    r = resolve_search(session, "knee scan")
    assert r.intent_type.value == "ambiguous"
    assert r.clarification_needed is True


def test_true_nonsense_still_returns_no_results(session: Session) -> None:
    r = resolve_search(session, "xqzptnw")
    assert r.intent_type.value == "unknown"
    assert r.results == []
