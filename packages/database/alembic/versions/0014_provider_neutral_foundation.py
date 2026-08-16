"""Provider-neutral foundation: organizations, capabilities, service availability.

Additive and reversible. Introduces the layers needed to model non-hospital providers
without disturbing the audited NH hospital pipeline:

- organizations                     (business/health-system owning many service locations)
- facilities.organization_id        (nullable FK; backfilled 1:1 for existing hospitals)
- location_capabilities             (one location -> MANY capabilities; ER != urgent care)
- location_service_availability     ("offered here" -> SEPARATE from price availability)
- facility_locations.region/subregion   (sub-state filtering; NH ignores, MA needs it)
- facility_price_sources.source_class    (non-hospital price feeds not forced into MRF)

Backfill maps everything to hospital semantics (1 org per facility reusing its UUID,
capability 'hospital' per existing location reusing the location UUID, source_class
'HOSPITAL_MRF'), so no existing hospital behavior, coverage, provenance, comparability,
or raw pricing changes. No existing column is dropped or renamed; the raw
hospital_price_* tables are untouched. Idempotent (inspector-guarded) so re-running is safe.

Revision ID: 0014
Revises: 0013
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0014"
down_revision: str | None = "0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    def has_column(table: str, column: str) -> bool:
        if table not in tables:
            return False
        return column in {item["name"] for item in inspector.get_columns(table)}

    # --- organizations ---------------------------------------------------------------
    if "organizations" not in tables:
        op.create_table(
            "organizations",
            sa.Column("id", sa.Uuid(), primary_key=True),
            sa.Column("canonical_name", sa.String(length=255), nullable=False),
            sa.Column("display_name", sa.String(length=255), nullable=False),
            sa.Column(
                "organization_type",
                sa.String(length=60),
                nullable=False,
                server_default="other",
            ),
            sa.Column("npi_organization", sa.String(length=20), nullable=True),
            sa.Column("ein", sa.String(length=20), nullable=True),
            sa.Column("website_url", sa.String(length=2048), nullable=True),
            sa.Column("active", sa.Boolean(), nullable=False, server_default="true"),
            sa.Column("source_file_id", sa.Uuid(), sa.ForeignKey("source_files.id"), nullable=True),
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
            "ix_organizations_organization_type", "organizations", ["organization_type"]
        )
        op.create_index("ix_organizations_npi_organization", "organizations", ["npi_organization"])
        op.create_index("ix_organizations_source_file_id", "organizations", ["source_file_id"])

    # --- facilities.organization_id ---------------------------------------------------
    if not has_column("facilities", "organization_id"):
        op.add_column(
            "facilities",
            sa.Column(
                "organization_id", sa.Uuid(), sa.ForeignKey("organizations.id"), nullable=True
            ),
        )
        op.create_index("ix_facilities_organization_id", "facilities", ["organization_id"])

    # --- location_capabilities --------------------------------------------------------
    if "location_capabilities" not in tables:
        op.create_table(
            "location_capabilities",
            sa.Column("id", sa.Uuid(), primary_key=True),
            sa.Column(
                "facility_location_id",
                sa.Uuid(),
                sa.ForeignKey("facility_locations.id"),
                nullable=False,
            ),
            sa.Column("capability", sa.String(length=60), nullable=False),
            sa.Column("active", sa.Boolean(), nullable=False, server_default="true"),
            sa.Column(
                "evidence_source_id", sa.Uuid(), sa.ForeignKey("source_files.id"), nullable=True
            ),
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
            sa.UniqueConstraint(
                "facility_location_id", "capability", name="uq_location_capability"
            ),
        )
        op.create_index(
            "ix_location_capabilities_facility_location_id",
            "location_capabilities",
            ["facility_location_id"],
        )
        op.create_index(
            "ix_location_capability_capability", "location_capabilities", ["capability"]
        )

    # --- location_service_availability ------------------------------------------------
    if "location_service_availability" not in tables:
        op.create_table(
            "location_service_availability",
            sa.Column("id", sa.Uuid(), primary_key=True),
            sa.Column(
                "facility_location_id",
                sa.Uuid(),
                sa.ForeignKey("facility_locations.id"),
                nullable=False,
            ),
            sa.Column("procedure_id", sa.Uuid(), sa.ForeignKey("procedures.id"), nullable=False),
            sa.Column(
                "availability_status",
                sa.String(length=20),
                nullable=False,
                server_default="unknown",
            ),
            sa.Column(
                "evidence_source_id", sa.Uuid(), sa.ForeignKey("source_files.id"), nullable=True
            ),
            sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("active", sa.Boolean(), nullable=False, server_default="true"),
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
            sa.UniqueConstraint(
                "facility_location_id", "procedure_id", name="uq_location_service_availability"
            ),
        )
        op.create_index(
            "ix_location_service_availability_facility_location_id",
            "location_service_availability",
            ["facility_location_id"],
        )
        op.create_index(
            "ix_location_service_availability_proc",
            "location_service_availability",
            ["procedure_id", "availability_status"],
        )

    # --- facility_locations.region / subregion ---------------------------------------
    if not has_column("facility_locations", "region"):
        op.add_column(
            "facility_locations", sa.Column("region", sa.String(length=80), nullable=True)
        )
        op.create_index("ix_facility_locations_region", "facility_locations", ["region"])
    if not has_column("facility_locations", "subregion"):
        op.add_column(
            "facility_locations", sa.Column("subregion", sa.String(length=80), nullable=True)
        )

    # --- facility_price_sources.source_class -----------------------------------------
    if not has_column("facility_price_sources", "source_class"):
        op.add_column(
            "facility_price_sources", sa.Column("source_class", sa.String(length=40), nullable=True)
        )
        op.create_index(
            "ix_facility_price_sources_source_class", "facility_price_sources", ["source_class"]
        )

    # --- Backfill to hospital semantics (idempotent; pure in-DB, portable) ------------
    # 1 organization per existing facility, REUSING the facility UUID as the org id so
    # the link is deterministic and needs no UUID generation.
    op.execute(
        sa.text(
            "INSERT INTO organizations "
            "(id, canonical_name, display_name, organization_type, active, source_file_id) "
            "SELECT f.id, f.legal_name, f.display_name, 'hospital_system', f.active, "
            "f.source_file_id "
            "FROM facilities f "
            "WHERE NOT EXISTS (SELECT 1 FROM organizations o WHERE o.id = f.id)"
        )
    )
    op.execute(sa.text("UPDATE facilities SET organization_id = id WHERE organization_id IS NULL"))

    # capability 'hospital' for every existing location (all hospital campuses today),
    # reusing the location UUID as the capability-row id.
    op.execute(
        sa.text(
            "INSERT INTO location_capabilities (id, facility_location_id, capability) "
            "SELECT fl.id, fl.id, 'hospital' FROM facility_locations fl "
            "WHERE NOT EXISTS (SELECT 1 FROM location_capabilities lc "
            "WHERE lc.facility_location_id = fl.id AND lc.capability = 'hospital')"
        )
    )

    op.execute(
        sa.text(
            "UPDATE facility_price_sources SET source_class = 'HOSPITAL_MRF' "
            "WHERE source_class IS NULL"
        )
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    def has_column(table: str, column: str) -> bool:
        if table not in tables:
            return False
        return column in {item["name"] for item in inspector.get_columns(table)}

    if "location_service_availability" in tables:
        op.drop_table("location_service_availability")
    if "location_capabilities" in tables:
        op.drop_table("location_capabilities")

    # Drop FK column before the organizations table it references.
    if has_column("facilities", "organization_id"):
        with op.batch_alter_table("facilities") as batch:
            batch.drop_column("organization_id")
    if "organizations" in tables:
        op.drop_table("organizations")

    for column in ("region", "subregion"):
        if has_column("facility_locations", column):
            with op.batch_alter_table("facility_locations") as batch:
                batch.drop_column(column)

    if has_column("facility_price_sources", "source_class"):
        with op.batch_alter_table("facility_price_sources") as batch:
            batch.drop_column("source_class")
