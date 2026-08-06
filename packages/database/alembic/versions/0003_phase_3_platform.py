"""Add Phase 3 identity, catalog, search, and data-health platform."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from packages.database.models import Base

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLES = (
    "facility_identifiers",
    "facility_aliases",
    "facility_relationships",
    "facility_identity_candidates",
    "facility_identity_decisions",
    "procedure_categories",
    "procedures",
    "procedure_aliases",
    "procedure_code_systems",
    "procedure_code_mappings",
    "procedure_bundles",
    "procedure_bundle_components",
    "search_documents",
    "data_health_rules",
    "data_health_evaluations",
    "entity_data_health_scores",
    "pipeline_status_snapshots",
)


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.alter_column(
        "facilities", "cms_certification_number", existing_type=sa.String(20), nullable=True
    )
    op.alter_column("facilities", "source_file_id", existing_type=sa.Uuid(), nullable=True)
    for table_name in TABLES:
        Base.metadata.tables[table_name].create(bind=bind, checkfirst=True)
    if bind.dialect.name == "postgresql":
        op.execute(
            "CREATE INDEX ix_search_documents_trgm ON search_documents "
            "USING gin (normalized_text gin_trgm_ops)"
        )
        op.execute(
            "CREATE INDEX ix_search_documents_fts ON search_documents "
            "USING gin (to_tsvector('english', normalized_text))"
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("DROP INDEX IF EXISTS ix_search_documents_fts")
        op.execute("DROP INDEX IF EXISTS ix_search_documents_trgm")
    for table_name in reversed(TABLES):
        Base.metadata.tables[table_name].drop(bind=bind, checkfirst=True)
    op.alter_column("facilities", "source_file_id", existing_type=sa.Uuid(), nullable=False)
    op.alter_column(
        "facilities", "cms_certification_number", existing_type=sa.String(20), nullable=False
    )
