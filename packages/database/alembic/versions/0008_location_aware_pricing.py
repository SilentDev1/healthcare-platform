"""Add physical-location pricing provenance and consumer summary identity."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())

    def has_column(table: str, column: str) -> bool:
        return column in {item["name"] for item in inspector.get_columns(table)}

    op.drop_constraint("facility_locations_facility_id_key", "facility_locations", type_="unique")
    op.add_column("facility_locations", sa.Column("location_name", sa.String(255)))
    op.add_column(
        "facility_locations",
        sa.Column("location_type", sa.String(50), server_default="hospital_campus", nullable=False),
    )
    op.add_column(
        "facility_locations",
        sa.Column("active", sa.Boolean(), server_default=sa.true(), nullable=False),
    )
    op.create_index("ix_facility_locations_facility_id", "facility_locations", ["facility_id"])
    op.create_unique_constraint(
        "uq_facility_physical_location",
        "facility_locations",
        ["facility_id", "address_line_1", "city", "state", "postal_code"],
    )

    if not has_column("facility_price_sources", "facility_location_id"):
        op.add_column(
            "facility_price_sources", sa.Column("facility_location_id", sa.Uuid(), nullable=True)
        )
        op.add_column(
            "facility_price_sources",
            sa.Column(
                "location_association_status",
                sa.String(40),
                server_default="unresolved",
                nullable=False,
            ),
        )
        op.add_column(
            "facility_price_sources", sa.Column("location_association_evidence", sa.JSON())
        )
        op.create_foreign_key(
            "fk_price_source_location",
            "facility_price_sources",
            "facility_locations",
            ["facility_location_id"],
            ["id"],
        )
        op.create_index(
            "ix_facility_price_sources_location",
            "facility_price_sources",
            ["facility_location_id"],
        )
        op.create_index(
            "ix_facility_price_sources_location_status",
            "facility_price_sources",
            ["location_association_status"],
        )

    for table in ("hospital_price_records", "facility_procedure_price_observations"):
        if not has_column(table, "facility_location_id"):
            op.add_column(table, sa.Column("facility_location_id", sa.Uuid(), nullable=True))
            op.create_foreign_key(
                f"fk_{table}_location",
                table,
                "facility_locations",
                ["facility_location_id"],
                ["id"],
            )
            op.create_index(f"ix_{table}_location", table, ["facility_location_id"])

    if not has_column("facility_procedure_price_summaries", "facility_location_id"):
        op.drop_constraint(
            "uq_facility_procedure_price_summary",
            "facility_procedure_price_summaries",
            type_="unique",
        )
        op.add_column(
            "facility_procedure_price_summaries",
            sa.Column("facility_location_id", sa.Uuid(), nullable=True),
        )
        op.add_column(
            "facility_procedure_price_summaries",
            sa.Column(
                "included_component_scope",
                sa.String(100),
                server_default="unknown",
                nullable=False,
            ),
        )
        op.create_foreign_key(
            "fk_price_summary_location",
            "facility_procedure_price_summaries",
            "facility_locations",
            ["facility_location_id"],
            ["id"],
        )
        op.create_index(
            "ix_price_summary_location",
            "facility_procedure_price_summaries",
            ["facility_location_id"],
        )
        op.create_unique_constraint(
            "uq_facility_procedure_price_summary",
            "facility_procedure_price_summaries",
            [
                "facility_id",
                "facility_location_id",
                "procedure_id",
                "payer_entity_id",
                "insurance_plan_entity_id",
                "service_setting",
                "included_component_scope",
            ],
        )

    op.create_table(
        "facility_procedure_price_summary_sources",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "summary_id",
            sa.Uuid(),
            sa.ForeignKey("facility_procedure_price_summaries.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("source_file_id", sa.Uuid(), sa.ForeignKey("source_files.id"), nullable=False),
        sa.Column("observation_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("summary_id", "source_file_id", name="uq_summary_source_file"),
    )
    op.create_index(
        "ix_summary_sources_summary", "facility_procedure_price_summary_sources", ["summary_id"]
    )
    op.create_index(
        "ix_summary_sources_file", "facility_procedure_price_summary_sources", ["source_file_id"]
    )
    op.create_table(
        "price_source_overlap_analyses",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("facility_id", sa.Uuid(), sa.ForeignKey("facilities.id"), nullable=False),
        sa.Column(
            "left_source_file_id", sa.Uuid(), sa.ForeignKey("source_files.id"), nullable=False
        ),
        sa.Column(
            "right_source_file_id", sa.Uuid(), sa.ForeignKey("source_files.id"), nullable=False
        ),
        sa.Column("left_location_id", sa.Uuid(), sa.ForeignKey("facility_locations.id")),
        sa.Column("right_location_id", sa.Uuid(), sa.ForeignKey("facility_locations.id")),
        sa.Column("classification", sa.String(60), nullable=False),
        sa.Column("metrics", sa.JSON(), nullable=False),
        sa.Column("evidence", sa.JSON(), nullable=False),
        sa.Column("analyzed_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint(
            "left_source_file_id", "right_source_file_id", name="uq_price_source_overlap_pair"
        ),
    )
    op.create_index(
        "ix_price_source_overlap_facility", "price_source_overlap_analyses", ["facility_id"]
    )
    op.create_index(
        "ix_price_source_overlap_classification",
        "price_source_overlap_analyses",
        ["classification"],
    )
    if not has_column("price_change_snapshots", "facility_location_id"):
        op.add_column("price_change_snapshots", sa.Column("facility_location_id", sa.Uuid()))
        op.add_column(
            "price_change_snapshots",
            sa.Column(
                "included_component_scope",
                sa.String(100),
                server_default="unknown",
                nullable=False,
            ),
        )
        op.create_foreign_key(
            "fk_price_change_location",
            "price_change_snapshots",
            "facility_locations",
            ["facility_location_id"],
            ["id"],
        )
        op.create_index(
            "ix_price_change_location", "price_change_snapshots", ["facility_location_id"]
        )


def downgrade() -> None:
    op.drop_index("ix_price_change_location", table_name="price_change_snapshots")
    op.drop_constraint("fk_price_change_location", "price_change_snapshots", type_="foreignkey")
    op.drop_column("price_change_snapshots", "included_component_scope")
    op.drop_column("price_change_snapshots", "facility_location_id")
    op.drop_table("price_source_overlap_analyses")
    op.drop_table("facility_procedure_price_summary_sources")
    op.drop_constraint(
        "uq_facility_procedure_price_summary",
        "facility_procedure_price_summaries",
        type_="unique",
    )
    op.drop_index("ix_price_summary_location", table_name="facility_procedure_price_summaries")
    op.drop_constraint(
        "fk_price_summary_location", "facility_procedure_price_summaries", type_="foreignkey"
    )
    op.drop_column("facility_procedure_price_summaries", "included_component_scope")
    op.drop_column("facility_procedure_price_summaries", "facility_location_id")
    op.create_unique_constraint(
        "uq_facility_procedure_price_summary",
        "facility_procedure_price_summaries",
        [
            "facility_id",
            "procedure_id",
            "payer_entity_id",
            "insurance_plan_entity_id",
            "service_setting",
        ],
    )
    for table in ("facility_procedure_price_observations", "hospital_price_records"):
        op.drop_index(f"ix_{table}_location", table_name=table)
        op.drop_constraint(f"fk_{table}_location", table, type_="foreignkey")
        op.drop_column(table, "facility_location_id")
    op.drop_index("ix_facility_price_sources_location_status", table_name="facility_price_sources")
    op.drop_index("ix_facility_price_sources_location", table_name="facility_price_sources")
    op.drop_constraint("fk_price_source_location", "facility_price_sources", type_="foreignkey")
    op.drop_column("facility_price_sources", "location_association_evidence")
    op.drop_column("facility_price_sources", "location_association_status")
    op.drop_column("facility_price_sources", "facility_location_id")
    op.drop_constraint("uq_facility_physical_location", "facility_locations", type_="unique")
    op.drop_index("ix_facility_locations_facility_id", table_name="facility_locations")
    op.drop_column("facility_locations", "active")
    op.drop_column("facility_locations", "location_type")
    op.drop_column("facility_locations", "location_name")
    op.create_unique_constraint(
        "facility_locations_facility_id_key", "facility_locations", ["facility_id"]
    )
