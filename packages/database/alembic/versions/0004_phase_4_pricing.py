"""Add Phase 4 hospital pricing platform."""

from collections.abc import Sequence

from alembic import op

import packages.database.pricing_models  # noqa: F401
from packages.database.models import Base

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLES = (
    "facility_price_sources",
    "price_source_discovery_runs",
    "price_source_discovery_observations",
    "parser_reviews",
    "parser_mapping_proposals",
    "parser_mapping_decisions",
    "payer_entities",
    "payer_aliases",
    "insurance_plan_entities",
    "insurance_plan_aliases",
    "hospital_price_records",
    "hospital_price_rate_details",
    "price_service_codes",
    "pricing_unmatched_records",
    "price_record_procedure_candidates",
    "price_record_procedure_mappings",
    "pricing_anomalies",
    "facility_procedure_price_observations",
    "facility_procedure_price_summaries",
    "pricing_health_scores",
    "pricing_review_audits",
)


def upgrade() -> None:
    bind = op.get_bind()
    for table_name in TABLES:
        Base.metadata.tables[table_name].create(bind=bind, checkfirst=True)


def downgrade() -> None:
    bind = op.get_bind()
    for table_name in reversed(TABLES):
        Base.metadata.tables[table_name].drop(bind=bind, checkfirst=True)
