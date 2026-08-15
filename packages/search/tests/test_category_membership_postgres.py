"""True regression guard for the category-search render bug — on real Postgres.

The bug only manifests on Postgres: `search()` applies a trigram/tsvector/ILIKE
text filter (guarded by `dialect.name == "postgresql"`) so that only procedures
whose indexed text matches the query are fetched. When a category was matched via
a label/alias absent from its members' text ("lab tests"/"blood work"/"labs" ->
Laboratory, "scans" -> Imaging), the old category-member expansion — which looped
over that text-filtered set — emitted zero (or partial) members while the UI still
showed the category's procedure_count. Result: "11 procedures" with no cards.

SQLite skips that filter entirely (every document is always in scope), so no
SQLite test can reproduce the drop. This module runs against a disposable Postgres
database and asserts rendered members == procedure_count == catalog membership for
the alias queries. It is skipped unless CAREVERO_PG_TEST_URL points at a Postgres
server the test may create/drop a throwaway database on (never the real app DB).

Run locally against docker compose Postgres:
    CAREVERO_PG_TEST_URL=postgresql+psycopg://carecompare:<pw>@localhost:5432/postgres \\
        uv run pytest packages/search/tests/test_category_membership_postgres.py
"""

from __future__ import annotations

import os
import re
import uuid
from collections.abc import Iterator

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session

from packages.database import Base, Procedure, ProcedureCategory
from packages.search.resolution import resolve_search
from packages.search.service import rebuild_index
from scripts.seed_procedure_catalog import seed_catalog

_BASE_URL = os.environ.get("CAREVERO_PG_TEST_URL")

pytestmark = pytest.mark.skipif(
    not _BASE_URL,
    reason="set CAREVERO_PG_TEST_URL to a disposable Postgres server to run",
)


@pytest.fixture(scope="module")
def pg_session() -> Iterator[Session]:
    assert _BASE_URL
    tmp_db = f"carevero_catsearch_test_{uuid.uuid4().hex[:12]}"
    server_url = re.sub(r"/[^/]+$", "/postgres", _BASE_URL)
    tmp_url = re.sub(r"/[^/]+$", f"/{tmp_db}", _BASE_URL)

    admin = create_engine(server_url, isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text(f'CREATE DATABASE "{tmp_db}"'))
    try:
        engine = create_engine(tmp_url)
        with engine.connect() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
            conn.commit()
        Base.metadata.create_all(engine)
        session = Session(engine)
        seed_catalog(session)
        session.commit()
        rebuild_index(session)
        session.commit()
        assert session.bind is not None
        assert session.bind.dialect.name == "postgresql"
        yield session
        session.close()
        engine.dispose()
    finally:
        with admin.connect() as conn:
            conn.execute(
                text(
                    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                    "WHERE datname = :name AND pid <> pg_backend_pid()"
                ),
                {"name": tmp_db},
            )
            conn.execute(text(f'DROP DATABASE IF EXISTS "{tmp_db}"'))
        admin.dispose()


ALIAS_CASES = [
    ("lab tests", "laboratory"),
    ("blood work", "laboratory"),
    ("labs", "laboratory"),
    ("scans", "imaging"),
]


def _catalog_members(session: Session, slug: str) -> set[str]:
    return set(
        session.scalars(
            select(Procedure.slug)
            .join(ProcedureCategory)
            .where(ProcedureCategory.slug == slug, Procedure.active.is_(True))
        ).all()
    )


@pytest.mark.parametrize("query,slug", ALIAS_CASES)
def test_alias_category_renders_full_membership_on_postgres(
    pg_session: Session, query: str, slug: str
) -> None:
    r = resolve_search(pg_session, query)
    assert r.canonical_category_slug == slug
    category = next(x for x in r.results if x.entity_type == "procedure_category")
    members = [
        x for x in r.results if x.entity_type == "procedure" and x.match_reason == "category_member"
    ]
    member_slugs = {str(x.metadata.get("slug")) for x in members}
    catalog = _catalog_members(pg_session, slug)

    assert catalog
    # The exact failure the production screenshot showed: count > 0, cards == 0.
    assert len(members) == category.metadata["procedure_count"]
    assert member_slugs == catalog
