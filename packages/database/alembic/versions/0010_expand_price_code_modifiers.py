"""Preserve long hospital price-code modifiers from official MRFs."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "price_service_codes",
        "modifier",
        existing_type=sa.String(20),
        type_=sa.String(255),
        existing_nullable=True,
    )
    op.alter_column(
        "procedure_code_mappings",
        "modifier",
        existing_type=sa.String(20),
        type_=sa.String(255),
        existing_nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "procedure_code_mappings",
        "modifier",
        existing_type=sa.String(255),
        type_=sa.String(20),
        existing_nullable=True,
    )
    op.alter_column(
        "price_service_codes",
        "modifier",
        existing_type=sa.String(255),
        type_=sa.String(20),
        existing_nullable=True,
    )
