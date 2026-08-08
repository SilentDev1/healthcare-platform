"""Add Phase 4.1 performance, checkpointing, and large-file reliability."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

import packages.database.pricing_models  # noqa: F401
from packages.database.models import Base

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

NEW_TABLES = ("import_checkpoints",)

# All columns added as nullable first; non-nullable ones get backfilled then altered.
IMPORT_RUN_COLUMNS = (
    ("stage", sa.String(50)),
    ("stage_started_at", sa.DateTime(timezone=True)),
    ("batches_committed", sa.BigInteger()),
    ("bytes_processed", sa.BigInteger()),
    ("throughput_rows_per_sec", sa.Numeric(10, 2)),
    ("parser_version_used", sa.String(50)),
    ("source_checksum_used", sa.String(64)),
    ("last_checkpoint_at", sa.DateTime(timezone=True)),
)

# Columns that should be NOT NULL with a default of 0 after backfill
NON_NULLABLE_DEFAULTS = {
    "batches_committed": "0",
    "bytes_processed": "0",
}


def upgrade() -> None:
    bind = op.get_bind()
    # Create new tables
    for table_name in NEW_TABLES:
        Base.metadata.tables[table_name].create(bind=bind, checkfirst=True)

    # Add all new columns as nullable
    for col_name, col_type in IMPORT_RUN_COLUMNS:
        op.add_column(
            "import_runs",
            sa.Column(col_name, col_type, nullable=True),
        )

    # Backfill non-nullable columns
    for col_name, default_val in NON_NULLABLE_DEFAULTS.items():
        op.execute(f"UPDATE import_runs SET {col_name} = {default_val} WHERE {col_name} IS NULL")

    # Alter to NOT NULL
    for col_name in NON_NULLABLE_DEFAULTS:
        op.alter_column("import_runs", col_name, nullable=False, server_default=sa.text("0"))


def downgrade() -> None:
    bind = op.get_bind()
    for table_name in reversed(NEW_TABLES):
        Base.metadata.tables[table_name].drop(bind=bind, checkfirst=True)
    for col_name, _ in IMPORT_RUN_COLUMNS:
        op.drop_column("import_runs", col_name)
