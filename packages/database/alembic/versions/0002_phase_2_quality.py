"""Add immutable quality, source observation, and unmatched review tables."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "quality_measure_definitions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("cms_measure_id", sa.String(100), nullable=False),
        sa.Column("measure_name", sa.String(500), nullable=False),
        sa.Column("consumer_name", sa.String(500)),
        sa.Column("description", sa.Text()),
        sa.Column("category", sa.String(100), nullable=False),
        sa.Column("unit", sa.String(50)),
        sa.Column("directionality", sa.String(30), nullable=False),
        sa.Column("data_type", sa.String(30), nullable=False),
        sa.Column("active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("cms_measure_id"),
    )
    op.create_index(
        "ix_quality_measure_definitions_cms_measure_id",
        "quality_measure_definitions",
        ["cms_measure_id"],
    )
    op.create_index(
        "ix_quality_measure_definitions_category", "quality_measure_definitions", ["category"]
    )
    op.create_table(
        "facility_source_observations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("facility_id", sa.Uuid(), sa.ForeignKey("facilities.id"), nullable=False),
        sa.Column("source_file_id", sa.Uuid(), sa.ForeignKey("source_files.id"), nullable=False),
        sa.Column("import_run_id", sa.Uuid(), sa.ForeignKey("import_runs.id"), nullable=False),
        sa.Column("source_record_identifier", sa.String(500), nullable=False),
        sa.Column("source_payload_hash", sa.String(64), nullable=False),
        sa.Column("raw_payload", sa.JSON(), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint(
            "source_file_id",
            "import_run_id",
            "source_record_identifier",
            name="uq_facility_source_observation_record",
        ),
    )
    for column in ("facility_id", "source_file_id", "import_run_id", "source_payload_hash"):
        op.create_index(
            f"ix_facility_source_observations_{column}", "facility_source_observations", [column]
        )
    op.create_index(
        "ix_facility_source_observations_facility_observed",
        "facility_source_observations",
        ["facility_id", "observed_at"],
    )
    op.create_table(
        "facility_quality_measure_observations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("facility_id", sa.Uuid(), sa.ForeignKey("facilities.id"), nullable=False),
        sa.Column(
            "quality_measure_definition_id",
            sa.Uuid(),
            sa.ForeignKey("quality_measure_definitions.id"),
            nullable=False,
        ),
        sa.Column("source_file_id", sa.Uuid(), sa.ForeignKey("source_files.id"), nullable=False),
        sa.Column("import_run_id", sa.Uuid(), sa.ForeignKey("import_runs.id"), nullable=False),
        sa.Column("source_record_identifier", sa.String(500), nullable=False),
        sa.Column("raw_value", sa.Text()),
        sa.Column("numeric_value", sa.Numeric(18, 6)),
        sa.Column("text_value", sa.Text()),
        sa.Column("score", sa.String(100)),
        sa.Column("footnote_code", sa.String(100)),
        sa.Column("reporting_period_start", sa.Date()),
        sa.Column("reporting_period_end", sa.Date()),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint(
            "source_file_id",
            "import_run_id",
            "quality_measure_definition_id",
            "source_record_identifier",
            name="uq_quality_observation_source_measure_record",
        ),
    )
    for name, column in (
        ("ix_fqmo_facility", "facility_id"),
        ("ix_fqmo_measure", "quality_measure_definition_id"),
        ("ix_fqmo_source", "source_file_id"),
        ("ix_fqmo_import", "import_run_id"),
        ("ix_fqmo_period_end", "reporting_period_end"),
    ):
        op.create_index(name, "facility_quality_measure_observations", [column])
    op.create_index(
        "ix_quality_observations_facility_measure_period",
        "facility_quality_measure_observations",
        ["facility_id", "quality_measure_definition_id", "reporting_period_end"],
    )
    op.create_table(
        "unmatched_source_records",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("source_file_id", sa.Uuid(), sa.ForeignKey("source_files.id"), nullable=False),
        sa.Column("import_run_id", sa.Uuid(), sa.ForeignKey("import_runs.id"), nullable=False),
        sa.Column("source_record_identifier", sa.String(500), nullable=False),
        sa.Column("supplied_cms_certification_number", sa.String(20)),
        sa.Column("supplied_facility_name", sa.String(500)),
        sa.Column("reason_unmatched", sa.String(500), nullable=False),
        sa.Column("raw_payload", sa.JSON(), nullable=False),
        sa.Column("review_status", sa.String(30), server_default="pending", nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
        sa.Column("reviewed_by", sa.String(255)),
        sa.Column("resolution_notes", sa.Text()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint(
            "source_file_id",
            "import_run_id",
            "source_record_identifier",
            name="uq_unmatched_source_record_import",
        ),
    )
    for name, column in (
        ("ix_unmatched_source", "source_file_id"),
        ("ix_unmatched_import", "import_run_id"),
        ("ix_unmatched_ccn", "supplied_cms_certification_number"),
        ("ix_unmatched_status", "review_status"),
    ):
        op.create_index(name, "unmatched_source_records", [column])
    op.create_index(
        "ix_unmatched_records_status_created",
        "unmatched_source_records",
        ["review_status", "created_at"],
    )


def downgrade() -> None:
    op.drop_table("unmatched_source_records")
    op.drop_table("facility_quality_measure_observations")
    op.drop_table("facility_source_observations")
    op.drop_table("quality_measure_definitions")
