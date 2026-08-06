"""Create Phase 1 provenance and facility tables."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "source_files",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("source_name", sa.String(255), nullable=False),
        sa.Column("source_url", sa.String(2048), nullable=False),
        sa.Column("source_type", sa.String(100), nullable=False),
        sa.Column("storage_path", sa.String(2048), nullable=False),
        sa.Column("checksum_sha256", sa.String(64), nullable=False),
        sa.Column("etag", sa.String(255)),
        sa.Column("last_modified", sa.String(255)),
        sa.Column("source_published_at", sa.DateTime(timezone=True)),
        sa.Column(
            "downloaded_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("file_size", sa.BigInteger(), nullable=False),
        sa.Column("parser_version", sa.String(50), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
    )
    op.create_index("ix_source_files_checksum_sha256", "source_files", ["checksum_sha256"])
    op.create_table(
        "facilities",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("cms_certification_number", sa.String(20), nullable=False, unique=True),
        sa.Column("legal_name", sa.String(255), nullable=False),
        sa.Column("display_name", sa.String(255), nullable=False),
        sa.Column("facility_type", sa.String(100)),
        sa.Column("ownership_type", sa.String(100)),
        sa.Column("phone", sa.String(30)),
        sa.Column("website_url", sa.String(2048)),
        sa.Column("active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("source_file_id", sa.Uuid(), sa.ForeignKey("source_files.id"), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index(
        "ix_facilities_cms_certification_number", "facilities", ["cms_certification_number"]
    )
    op.create_index("ix_facilities_source_file_id", "facilities", ["source_file_id"])
    op.create_table(
        "facility_locations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "facility_id", sa.Uuid(), sa.ForeignKey("facilities.id"), nullable=False, unique=True
        ),
        sa.Column("address_line_1", sa.String(255), nullable=False),
        sa.Column("address_line_2", sa.String(255)),
        sa.Column("city", sa.String(100), nullable=False),
        sa.Column("state", sa.String(2), nullable=False),
        sa.Column("postal_code", sa.String(10), nullable=False),
        sa.Column("county", sa.String(100)),
        sa.Column("latitude", sa.Numeric(9, 6)),
        sa.Column("longitude", sa.Numeric(9, 6)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_facility_locations_state", "facility_locations", ["state"])
    op.create_table(
        "import_runs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("importer_name", sa.String(255), nullable=False),
        sa.Column(
            "started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("rows_read", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("rows_inserted", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("rows_updated", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("rows_rejected", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("error_summary", sa.Text()),
        sa.Column("source_file_id", sa.Uuid(), sa.ForeignKey("source_files.id"), nullable=False),
    )
    op.create_index("ix_import_runs_source_file_id", "import_runs", ["source_file_id"])


def downgrade() -> None:
    op.drop_table("import_runs")
    op.drop_table("facility_locations")
    op.drop_table("facilities")
    op.drop_table("source_files")
