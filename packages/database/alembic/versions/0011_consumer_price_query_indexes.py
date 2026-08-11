"""Add bounded consumer price comparison and detail indexes.

Revision ID: 0011
Revises: 0010
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0011"
down_revision: str | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_price_observation_consumer_detail "
        "ON facility_procedure_price_observations "
        "(procedure_id, facility_location_id, publication_status, price_type)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_price_summary_consumer_insurance "
        "ON facility_procedure_price_summaries "
        "(procedure_id, facility_location_id, publication_status, "
        "payer_entity_id, insurance_plan_entity_id)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_price_summary_consumer_insurance")
    op.execute("DROP INDEX IF EXISTS ix_price_observation_consumer_detail")
