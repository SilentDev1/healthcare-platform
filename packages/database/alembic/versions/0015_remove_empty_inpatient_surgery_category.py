"""Remove the empty setting-based 'inpatient-surgery' consumer category.

Taxonomy audit (2026-08-16): consumer categories are clinical service groupings, not care
SETTINGS. 'inpatient-surgery' was a setting label with ZERO canonical procedures — major
surgeries (knee/hip replacement) correctly live under their clinical category (Orthopedics)
with the inpatient/mixed setting tracked on the price record, so nothing legitimately
belonged in it. It only surfaced as a confusing "0 procedures" category. This removes it
(guarded: only if no procedure references it) and its stale search document.

Data-only, idempotent, guarded. No procedure, price, or hospital record is touched; the
50/50 procedure catalog is unchanged (the category had no members).

Revision ID: 0015
Revises: 0014
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0015"
down_revision: str | None = "0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SLUG = "inpatient-surgery"


def upgrade() -> None:
    bind = op.get_bind()
    # Remove the stale search document for the category first (entity_id is the cat id).
    bind.execute(
        sa.text(
            "DELETE FROM search_documents WHERE entity_type = 'procedure_category' "
            "AND entity_id IN (SELECT id FROM procedure_categories WHERE slug = :slug)"
        ),
        {"slug": _SLUG},
    )
    # Delete the category ONLY if it is genuinely empty (no procedure references it).
    bind.execute(
        sa.text(
            "DELETE FROM procedure_categories pc WHERE pc.slug = :slug "
            "AND NOT EXISTS (SELECT 1 FROM procedures p WHERE p.category_id = pc.id)"
        ),
        {"slug": _SLUG},
    )


def downgrade() -> None:
    # Reversibility: re-create the (empty) category if it is absent. gen_random_uuid()
    # is built in on the deployed PostgreSQL; migrations run only against Postgres.
    bind = op.get_bind()
    exists = bind.execute(
        sa.text("SELECT 1 FROM procedure_categories WHERE slug = :slug"), {"slug": _SLUG}
    ).first()
    if exists is None:
        bind.execute(
            sa.text(
                "INSERT INTO procedure_categories "
                "(id, slug, name, description, sort_order, active) "
                "VALUES (gen_random_uuid(), 'inpatient-surgery', 'Inpatient surgery', "
                "'Consumer services related to inpatient surgery.', 6, true)"
            )
        )
