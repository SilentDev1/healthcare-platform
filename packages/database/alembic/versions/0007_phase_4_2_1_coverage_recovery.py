"""Phase 4.2.1 coverage recovery: FacilityPriceSourceHistory table and metadata columns."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    op.create_table(
        "facility_price_source_history",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "facility_price_source_id",
            sa.Uuid(),
            sa.ForeignKey("facility_price_sources.id"),
            nullable=False,
        ),
        sa.Column("previous_url", sa.String(2048), nullable=False),
        sa.Column("new_url", sa.String(2048), nullable=False),
        sa.Column("change_reason", sa.String(255), nullable=False),
        sa.Column("changed_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index(
        "ix_facility_price_source_history_facility_price_source_id",
        "facility_price_source_history",
        ["facility_price_source_id"],
    )
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
    op.drop_column("facility_price_sources", "vendor_name")
    op.drop_column("facility_price_sources", "health_system_name")
    op.drop_column("facility_price_sources", "file_role")
    op.drop_table("facility_price_source_history")
