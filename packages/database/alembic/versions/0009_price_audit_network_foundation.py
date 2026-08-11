"""Add append-only price audits and provider-directory network evidence."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "price_audit_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("state", sa.String(2), nullable=False),
        sa.Column("seed", sa.Integer(), nullable=False),
        sa.Column("requested_sample_size", sa.Integer(), nullable=False),
        sa.Column("full_audit", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("filters", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("audit_version", sa.String(30), nullable=False),
        sa.Column("result_counts", sa.JSON()),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_price_audit_runs_state", "price_audit_runs", ["state"])
    op.create_index("ix_price_audit_runs_status", "price_audit_runs", ["status"])
    op.create_table(
        "price_audit_results",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("observation_id", sa.Uuid(), nullable=False),
        sa.Column("summary_id", sa.Uuid()),
        sa.Column("record_id", sa.Uuid(), nullable=False),
        sa.Column("source_file_id", sa.Uuid(), nullable=False),
        sa.Column("audit_status", sa.String(40), nullable=False),
        sa.Column("source_amount", sa.Numeric(18, 6)),
        sa.Column("normalized_amount", sa.Numeric(18, 6), nullable=False),
        sa.Column("difference", sa.Numeric(18, 6)),
        sa.Column("semantic_checks", sa.JSON(), nullable=False),
        sa.Column("provenance_checks", sa.JSON(), nullable=False),
        sa.Column("evidence", sa.JSON(), nullable=False),
        sa.Column("audit_version", sa.String(30), nullable=False),
        sa.Column("audited_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["run_id"], ["price_audit_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["observation_id"], ["facility_procedure_price_observations.id"]),
        sa.ForeignKeyConstraint(["summary_id"], ["facility_procedure_price_summaries.id"]),
        sa.ForeignKeyConstraint(["record_id"], ["hospital_price_records.id"]),
        sa.ForeignKeyConstraint(["source_file_id"], ["source_files.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", "observation_id", name="uq_price_audit_observation"),
    )
    for column in ("run_id", "observation_id", "summary_id", "record_id", "source_file_id"):
        op.create_index(f"ix_price_audit_results_{column}", "price_audit_results", [column])
    op.create_index(
        "ix_price_audit_result_status", "price_audit_results", ["audit_status", "audited_at"]
    )

    op.create_table(
        "insurance_network_entities",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("payer_entity_id", sa.Uuid(), nullable=False),
        sa.Column("canonical_name", sa.String(500), nullable=False),
        sa.Column("normalized_name", sa.String(500), nullable=False),
        sa.Column("active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["payer_entity_id"], ["payer_entities.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("payer_entity_id", "normalized_name", name="uq_network_payer_name"),
    )
    op.create_index(
        "ix_insurance_network_entities_payer_entity_id",
        "insurance_network_entities",
        ["payer_entity_id"],
    )
    op.create_index(
        "ix_insurance_network_entities_normalized_name",
        "insurance_network_entities",
        ["normalized_name"],
    )
    op.create_table(
        "provider_directory_sources",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("payer_entity_id", sa.Uuid()),
        sa.Column("insurance_plan_entity_id", sa.Uuid()),
        sa.Column("insurance_network_entity_id", sa.Uuid()),
        sa.Column("state", sa.String(2)),
        sa.Column("source_name", sa.String(255), nullable=False),
        sa.Column("source_url", sa.String(2048), nullable=False),
        sa.Column("source_type", sa.String(60), nullable=False),
        sa.Column("machine_readable", sa.Boolean(), nullable=False),
        sa.Column("api_available", sa.Boolean(), nullable=False),
        sa.Column("authentication_required", sa.Boolean(), nullable=False),
        sa.Column("checksum_sha256", sa.String(64)),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_effective_at", sa.DateTime(timezone=True)),
        sa.Column("freshness_days", sa.Integer(), nullable=False),
        sa.Column("active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.ForeignKeyConstraint(["payer_entity_id"], ["payer_entities.id"]),
        sa.ForeignKeyConstraint(["insurance_plan_entity_id"], ["insurance_plan_entities.id"]),
        sa.ForeignKeyConstraint(["insurance_network_entity_id"], ["insurance_network_entities.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in (
        "payer_entity_id",
        "insurance_plan_entity_id",
        "insurance_network_entity_id",
        "state",
    ):
        op.create_index(
            f"ix_provider_directory_sources_{column}", "provider_directory_sources", [column]
        )
    op.create_table(
        "network_participation_observations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.Column("payer_entity_id", sa.Uuid(), nullable=False),
        sa.Column("insurance_plan_entity_id", sa.Uuid()),
        sa.Column("insurance_network_entity_id", sa.Uuid()),
        sa.Column("facility_id", sa.Uuid()),
        sa.Column("facility_location_id", sa.Uuid()),
        sa.Column("state", sa.String(2), nullable=False),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("source_provider_identifier", sa.String(255)),
        sa.Column("identifier_match_evidence", sa.JSON(), nullable=False),
        sa.Column("source_evidence", sa.JSON(), nullable=False),
        sa.Column("normalized_evidence", sa.JSON(), nullable=False),
        sa.Column("confidence", sa.Numeric(5, 4), nullable=False),
        sa.Column("review_status", sa.String(30), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_effective_at", sa.DateTime(timezone=True)),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["source_id"], ["provider_directory_sources.id"]),
        sa.ForeignKeyConstraint(["payer_entity_id"], ["payer_entities.id"]),
        sa.ForeignKeyConstraint(["insurance_plan_entity_id"], ["insurance_plan_entities.id"]),
        sa.ForeignKeyConstraint(["insurance_network_entity_id"], ["insurance_network_entities.id"]),
        sa.ForeignKeyConstraint(["facility_id"], ["facilities.id"]),
        sa.ForeignKeyConstraint(["facility_location_id"], ["facility_locations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    observation_indexes = {
        "source_id": "ix_network_obs_source",
        "payer_entity_id": "ix_network_obs_payer",
        "insurance_plan_entity_id": "ix_network_obs_plan",
        "insurance_network_entity_id": "ix_network_obs_network",
        "facility_id": "ix_network_obs_facility",
        "facility_location_id": "ix_network_obs_location",
        "state": "ix_network_obs_state",
        "status": "ix_network_obs_status",
        "review_status": "ix_network_obs_review",
        "observed_at": "ix_network_obs_observed",
    }
    for column, index_name in observation_indexes.items():
        op.create_index(index_name, "network_participation_observations", [column])
    op.create_index(
        "ix_network_observation_lookup",
        "network_participation_observations",
        ["facility_id", "status", "observed_at"],
    )


def downgrade() -> None:
    op.drop_table("network_participation_observations")
    op.drop_table("provider_directory_sources")
    op.drop_table("insurance_network_entities")
    op.drop_table("price_audit_results")
    op.drop_table("price_audit_runs")
