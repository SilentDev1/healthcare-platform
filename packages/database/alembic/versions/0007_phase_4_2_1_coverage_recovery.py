"""Phase 4.2.1 coverage recovery: FacilityPriceSourceHistory table and metadata columns."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

import packages.database.pricing_models  # noqa: F401
from packages.database.models import Base

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

NEW_TABLES = ("facility_price_source_history",)


def upgrade() -> None:
    bind = op.get_bind()
    # Create new tables
    for table_name in NEW_TABLES:
        Base.metadata.tables[table_name].create(bind=bind, checkfirst=True)
    # Add new columns (idempotent via checkfirst pattern)
    from sqlalchemy import inspect as sa_inspect

    inspector = sa_inspect(bind)
    existing_cols = {c["name"] for c in inspector.get_columns("facility_price_sources")}
    if "file_role" not in existing_cols:
        op.add_column(
            "facility_price_sources", sa.Column("file_role", sa.String(50), nullable=True)
        )
    if "health_system_name" not in existing_cols:
        op.add_column(
            "facility_price_sources", sa.Column("health_system_name", sa.String(255), nullable=True)
        )
    if "vendor_name" not in existing_cols:
        op.add_column(
            "facility_price_sources", sa.Column("vendor_name", sa.String(100), nullable=True)
        )


def downgrade() -> None:
    bind = op.get_bind()
    op.drop_column("facility_price_sources", "vendor_name")
    op.drop_column("facility_price_sources", "health_system_name")
    op.drop_column("facility_price_sources", "file_role")
    for table_name in reversed(NEW_TABLES):
        Base.metadata.tables[table_name].drop(bind=bind, checkfirst=True)
