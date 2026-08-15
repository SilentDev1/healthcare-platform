"""Index the observation -> rate_detail inbound FK.

Revision ID: 0013
Revises: 0012

`facility_procedure_price_observations.hospital_price_rate_detail_id` is a foreign
key to `hospital_price_rate_details.id` that was never indexed (the model declared
the FK without an index, and migration 0004 created the table via
`metadata.create(checkfirst=True)`, so no index was ever built in prod).

Because of that, every DELETE of a `hospital_price_rate_details` row fires a
referential-integrity trigger that runs `SELECT 1 FROM
facility_procedure_price_observations WHERE hospital_price_rate_detail_id = ?` —
with no usable index (the composite unique constraint leads with a different
column), each check is a full seq scan of the whole all-hospitals observations
table. Deleting a large source's rate details is then O(rows^2) and never
completes (it wedged the price-refresh restart job for 6+ hours making zero
progress). This additive index makes each RI check an index lookup.

Idempotent: `CREATE INDEX IF NOT EXISTS`, matching 0011's style.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0013"
down_revision: str | None = "0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_price_observation_rate_detail_id "
        "ON facility_procedure_price_observations "
        "(hospital_price_rate_detail_id)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_price_observation_rate_detail_id")
