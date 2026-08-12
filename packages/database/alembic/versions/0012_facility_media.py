"""Add state-neutral facility_media table (facility / service-location imagery).

Additive and reversible. Does not touch any pricing, facility, location, quality,
or source table. Only creates the new facility_media table and its indexes.

Revision ID: 0012
Revises: 0011
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0012"
down_revision: str | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "facility_media",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "facility_id",
            sa.Uuid(),
            sa.ForeignKey("facilities.id"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "service_location_id",
            sa.Uuid(),
            sa.ForeignKey("facility_locations.id"),
            nullable=True,
        ),
        sa.Column(
            "media_type", sa.String(length=30), nullable=False, server_default="photo"
        ),
        sa.Column("storage_key", sa.String(length=1024), nullable=True),
        sa.Column("source_url", sa.String(length=2048), nullable=True),
        sa.Column("cdn_url", sa.String(length=2048), nullable=True),
        sa.Column("source_type", sa.String(length=40), nullable=False),
        sa.Column("source_name", sa.String(length=255), nullable=True),
        sa.Column("license_type", sa.String(length=80), nullable=True),
        sa.Column("license_url", sa.String(length=2048), nullable=True),
        sa.Column("attribution_text", sa.Text(), nullable=True),
        sa.Column("copyright_owner", sa.String(length=255), nullable=True),
        sa.Column(
            "verification_status",
            sa.String(length=20),
            nullable=False,
            server_default="pending",
        ),
        sa.Column(
            "is_primary", sa.Boolean(), nullable=False, server_default="false"
        ),
        sa.Column("display_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("mime_type", sa.String(length=80), nullable=True),
        sa.Column("file_size", sa.BigInteger(), nullable=True),
        sa.Column("checksum_sha256", sa.String(length=64), nullable=True),
        sa.Column("alt_text", sa.String(length=500), nullable=True),
        sa.Column("captured_at", sa.Date(), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("verified_by", sa.String(length=255), nullable=True),
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("review_notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_facility_media_facility_id", "facility_media", ["facility_id"]
    )
    op.create_index(
        "ix_facility_media_verification_status",
        "facility_media",
        ["verification_status"],
    )
    op.create_index(
        "ix_facility_media_facility_status_primary",
        "facility_media",
        ["facility_id", "verification_status", "is_primary", "display_order"],
    )
    op.create_index(
        "ix_facility_media_location_status",
        "facility_media",
        ["service_location_id", "verification_status"],
    )
    op.create_index(
        "ix_facility_media_checksum", "facility_media", ["checksum_sha256"]
    )


def downgrade() -> None:
    op.drop_index("ix_facility_media_checksum", table_name="facility_media")
    op.drop_index("ix_facility_media_location_status", table_name="facility_media")
    op.drop_index(
        "ix_facility_media_facility_status_primary", table_name="facility_media"
    )
    op.drop_index(
        "ix_facility_media_verification_status", table_name="facility_media"
    )
    op.drop_index("ix_facility_media_facility_id", table_name="facility_media")
    op.drop_table("facility_media")
