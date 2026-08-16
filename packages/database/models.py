import enum
import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class SourceStatus(str, enum.Enum):
    DOWNLOADED = "downloaded"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class ImportStatus(str, enum.Enum):
    QUEUED = "queued"
    DOWNLOADING = "downloading"
    PARSING = "parsing"
    NORMALIZING = "normalizing"
    PERSISTING = "persisting"
    POST_PROCESSING = "post_processing"
    COMPLETED = "completed"
    COMPLETED_WITH_ERRORS = "completed_with_errors"
    FAILED = "failed"
    INTERRUPTED = "interrupted"
    RESUMABLE = "resumable"
    CANCELLED = "cancelled"
    RUNNING = "running"  # backwards compat


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class Organization(TimestampMixin, Base):
    """The business / health-system / provider organization that owns service locations.

    Provider-neutral: one organization (e.g. Quest Diagnostics, an independent imaging
    group, or a hospital system) may own MANY service locations. This is additive
    metadata above the existing Facility/location layer — hospitals backfill 1:1 so
    nothing changes for them, while multi-location organizations attach many facilities
    to one organization. Organization type is a stable canonical identifier; display
    labels live in i18n. Organization identity NEVER implies a location's capabilities
    or that a service is offered — those are modeled separately with their own evidence.
    """

    __tablename__ = "organizations"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    canonical_name: Mapped[str] = mapped_column(String(255))
    display_name: Mapped[str] = mapped_column(String(255))
    # Canonical organization type id, e.g. hospital_system, independent_lab,
    # imaging_group, urgent_care_group, physician_group, rehab_group, other. Extensible.
    organization_type: Mapped[str] = mapped_column(
        String(60), default="other", server_default="other", index=True
    )
    npi_organization: Mapped[str | None] = mapped_column(String(20), index=True)
    ein: Mapped[str | None] = mapped_column(String(20))
    website_url: Mapped[str | None] = mapped_column(String(2048))
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    # Provenance for the organization identity itself (verified source, not inferred).
    source_file_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("source_files.id"), index=True
    )

    facilities: Mapped[list["Facility"]] = relationship(back_populates="organization")


class Facility(TimestampMixin, Base):
    __tablename__ = "facilities"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    cms_certification_number: Mapped[str | None] = mapped_column(
        String(20), unique=True, index=True
    )
    legal_name: Mapped[str] = mapped_column(String(255))
    display_name: Mapped[str] = mapped_column(String(255))
    facility_type: Mapped[str | None] = mapped_column(String(100))
    ownership_type: Mapped[str | None] = mapped_column(String(100))
    phone: Mapped[str | None] = mapped_column(String(30))
    website_url: Mapped[str | None] = mapped_column(String(2048))
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    source_file_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("source_files.id"), index=True
    )
    # Owning organization (additive, nullable). Backfilled 1:1 for existing hospitals;
    # multi-location organizations (e.g. Quest) point many facilities at one org.
    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("organizations.id"), index=True
    )

    organization: Mapped["Organization | None"] = relationship(back_populates="facilities")
    locations: Mapped[list["FacilityLocation"]] = relationship(
        back_populates="facility", cascade="all, delete-orphan"
    )


class FacilityLocation(TimestampMixin, Base):
    __tablename__ = "facility_locations"
    __table_args__ = (
        UniqueConstraint(
            "facility_id",
            "address_line_1",
            "city",
            "state",
            "postal_code",
            name="uq_facility_physical_location",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    facility_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("facilities.id"), index=True)
    location_name: Mapped[str | None] = mapped_column(String(255))
    location_type: Mapped[str] = mapped_column(
        String(50), default="hospital_campus", server_default="hospital_campus"
    )
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    address_line_1: Mapped[str] = mapped_column(String(255))
    address_line_2: Mapped[str | None] = mapped_column(String(255))
    city: Mapped[str] = mapped_column(String(100))
    state: Mapped[str] = mapped_column(String(2), index=True)
    postal_code: Mapped[str] = mapped_column(String(10))
    county: Mapped[str | None] = mapped_column(String(100))
    latitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    longitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    # Sub-state geography for filtering as the provider population grows (MA especially).
    # NH ignores these; both nullable and additive.
    region: Mapped[str | None] = mapped_column(String(80), index=True)
    subregion: Mapped[str | None] = mapped_column(String(80))

    facility: Mapped[Facility] = relationship(back_populates="locations")
    capabilities: Mapped[list["LocationCapability"]] = relationship(
        back_populates="location", cascade="all, delete-orphan"
    )


class LocationCapability(TimestampMixin, Base):
    """A capability a physical service location has (one location -> MANY capabilities).

    A hospital campus may legitimately be hospital + emergency_department + laboratory
    + imaging + physical_therapy at the same address; an independent lab is just
    laboratory. Capability is a stable canonical identifier (display labels in i18n),
    NOT a mutually-exclusive location type. Emergency_department and urgent_care are
    DISTINCT capabilities and must never be conflated. Each capability may carry the
    evidence/source that established it — presence here means the location HAS the
    capability, which is separate from whether any specific service is offered or priced.
    """

    __tablename__ = "location_capabilities"
    __table_args__ = (
        UniqueConstraint("facility_location_id", "capability", name="uq_location_capability"),
        Index("ix_location_capability_capability", "capability"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    facility_location_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("facility_locations.id"), index=True
    )
    # Canonical capability id, e.g. hospital, hospital_outpatient, emergency_department,
    # freestanding_emergency_department, urgent_care, laboratory, independent_laboratory,
    # imaging, ambulatory_surgery, physical_therapy, rehabilitation, chiropractic, ...
    capability: Mapped[str] = mapped_column(String(60))
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    # Evidence that this capability is real (verified source), never inferred silently.
    evidence_source_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("source_files.id"), nullable=True
    )

    location: Mapped[FacilityLocation] = relationship(back_populates="capabilities")


class LocationServiceAvailability(TimestampMixin, Base):
    """ "This service is offered at this location" — SEPARATE from whether we have a price.

    The crux of the provider-neutral promise: a verified location that offers a service
    for which Carevero has no price must render "Price not currently available in
    Carevero" rather than being hidden or shown as $0. Availability requires evidence
    (never inferred from organization type alone: "Quest is a lab" does NOT prove every
    Quest location performs every lab procedure). Status is offered / not_offered /
    unknown. Price availability is a third, independent state expressed by the existing
    pricing chain; the two are never collapsed.
    """

    __tablename__ = "location_service_availability"
    __table_args__ = (
        UniqueConstraint(
            "facility_location_id", "procedure_id", name="uq_location_service_availability"
        ),
        Index("ix_location_service_availability_proc", "procedure_id", "availability_status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    facility_location_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("facility_locations.id"), index=True
    )
    procedure_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("procedures.id"), index=True)
    # offered | not_offered | unknown — never assume "offered" without evidence.
    availability_status: Mapped[str] = mapped_column(
        String(20), default="unknown", server_default="unknown"
    )
    evidence_source_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("source_files.id"), nullable=True
    )
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")


class MediaVerificationStatus(str, enum.Enum):
    """Lifecycle of a facility image. Only VERIFIED media may ever become the
    public primary photo; everything else falls back to the neutral placeholder."""

    PENDING = "pending"  # discovered or uploaded, not yet reviewed
    VERIFIED = "verified"  # reviewed, licensing established, eligible to publish
    REJECTED = "rejected"  # reviewed and not usable (wrong building, licensing, quality)
    BROKEN = "broken"  # a previously-usable asset failed retrieval/validation


class FacilityMediaSourceType(str, enum.Enum):
    """Provenance category. Governs whether an asset may be verified for public use;
    see docs/FACILITY_MEDIA_POLICY.md. State-neutral: applies to any US facility."""

    OFFICIAL_HOSPITAL = "official_hospital"
    OFFICIAL_WEBSITE = "official_website"
    GOVERNMENT_PUBLIC_DOMAIN = "government_public_domain"
    WIKIMEDIA = "wikimedia"
    MEDIA_KIT = "media_kit"
    ADMIN_UPLOAD = "admin_upload"


class FacilityMedia(TimestampMixin, Base):
    """State-neutral facility / service-location imagery with full provenance,
    licensing, verification lifecycle, and deterministic primary selection.

    Scale contract (NH -> MA -> nationwide): identity is by facility_id (and an
    optional service_location_id for location-specific photos), never by state.
    A row only becomes a public primary image when verification_status is
    'verified'; the selection layer prefers a verified location-specific photo,
    then a verified facility photo, else the neutral placeholder.
    """

    __tablename__ = "facility_media"
    __table_args__ = (
        Index(
            "ix_facility_media_facility_status_primary",
            "facility_id",
            "verification_status",
            "is_primary",
            "display_order",
        ),
        Index("ix_facility_media_location_status", "service_location_id", "verification_status"),
        Index("ix_facility_media_checksum", "checksum_sha256"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    facility_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("facilities.id"), index=True)
    # Location-specific imagery. NULL means the photo represents the facility as a
    # whole (used only when an exact-location photo is unavailable).
    service_location_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("facility_locations.id"), nullable=True
    )
    media_type: Mapped[str] = mapped_column(String(30), default="photo", server_default="photo")

    # Delivery: a Carevero-controlled object key (preferred when licensing permits
    # copying) and/or an external reference. At least one must be populated.
    storage_key: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    source_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    cdn_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)

    # Provenance + licensing (see FacilityMediaSourceType / media policy).
    source_type: Mapped[str] = mapped_column(String(40))
    source_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    license_type: Mapped[str | None] = mapped_column(String(80), nullable=True)
    license_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    attribution_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    copyright_owner: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Verification lifecycle + display selection.
    verification_status: Mapped[str] = mapped_column(
        String(20), default="pending", server_default="pending", index=True
    )
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    display_order: Mapped[int] = mapped_column(Integer, default=0, server_default="0")

    # Technical metadata (from validation).
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    mime_type: Mapped[str | None] = mapped_column(String(80), nullable=True)
    file_size: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    checksum_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # Optional curator-provided alt text; the consumer UI otherwise localizes a
    # neutral "Photo of {hospital}" string per locale.
    alt_text: Mapped[str | None] = mapped_column(String(500), nullable=True)

    captured_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    verified_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    review_notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class SourceFile(Base):
    __tablename__ = "source_files"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    source_name: Mapped[str] = mapped_column(String(255))
    source_url: Mapped[str] = mapped_column(String(2048))
    source_type: Mapped[str] = mapped_column(String(100))
    storage_path: Mapped[str] = mapped_column(String(2048))
    checksum_sha256: Mapped[str] = mapped_column(String(64), index=True)
    etag: Mapped[str | None] = mapped_column(String(255))
    last_modified: Mapped[str | None] = mapped_column(String(255))
    source_published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    downloaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    file_size: Mapped[int] = mapped_column(BigInteger)
    parser_version: Mapped[str] = mapped_column(String(50))
    status: Mapped[SourceStatus] = mapped_column(Enum(SourceStatus, native_enum=False))


class ImportRun(Base):
    __tablename__ = "import_runs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    importer_name: Mapped[str] = mapped_column(String(255))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[ImportStatus] = mapped_column(Enum(ImportStatus, native_enum=False))
    rows_read: Mapped[int] = mapped_column(BigInteger, default=0)
    rows_inserted: Mapped[int] = mapped_column(BigInteger, default=0)
    rows_updated: Mapped[int] = mapped_column(BigInteger, default=0)
    rows_rejected: Mapped[int] = mapped_column(BigInteger, default=0)
    error_summary: Mapped[str | None] = mapped_column(Text)
    source_file_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("source_files.id"), index=True)
    # Phase 4.1 performance tracking columns
    stage: Mapped[str | None] = mapped_column(String(50), nullable=True)
    stage_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    batches_committed: Mapped[int] = mapped_column(BigInteger, default=0)
    bytes_processed: Mapped[int] = mapped_column(BigInteger, default=0)
    throughput_rows_per_sec: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    parser_version_used: Mapped[str | None] = mapped_column(String(50), nullable=True)
    source_checksum_used: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_checkpoint_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class QualityMeasureDefinition(TimestampMixin, Base):
    __tablename__ = "quality_measure_definitions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    cms_measure_id: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    measure_name: Mapped[str] = mapped_column(String(500))
    consumer_name: Mapped[str | None] = mapped_column(String(500))
    description: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(100), index=True)
    unit: Mapped[str | None] = mapped_column(String(50))
    directionality: Mapped[str] = mapped_column(String(30))
    data_type: Mapped[str] = mapped_column(String(30))
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")


class FacilitySourceObservation(Base):
    __tablename__ = "facility_source_observations"
    __table_args__ = (
        UniqueConstraint(
            "source_file_id",
            "import_run_id",
            "source_record_identifier",
            name="uq_facility_source_observation_record",
        ),
        Index("ix_facility_source_observations_facility_observed", "facility_id", "observed_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    facility_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("facilities.id"), index=True)
    source_file_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("source_files.id"), index=True)
    import_run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("import_runs.id"), index=True)
    source_record_identifier: Mapped[str] = mapped_column(String(500))
    source_payload_hash: Mapped[str] = mapped_column(String(64), index=True)
    raw_payload: Mapped[dict[str, object]] = mapped_column(JSON)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class FacilityQualityMeasureObservation(Base):
    __tablename__ = "facility_quality_measure_observations"
    __table_args__ = (
        UniqueConstraint(
            "source_file_id",
            "import_run_id",
            "quality_measure_definition_id",
            "source_record_identifier",
            name="uq_quality_observation_source_measure_record",
        ),
        Index(
            "ix_quality_observations_facility_measure_period",
            "facility_id",
            "quality_measure_definition_id",
            "reporting_period_end",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    facility_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("facilities.id"), index=True)
    quality_measure_definition_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("quality_measure_definitions.id"), index=True
    )
    source_file_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("source_files.id"), index=True)
    import_run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("import_runs.id"), index=True)
    source_record_identifier: Mapped[str] = mapped_column(String(500))
    raw_value: Mapped[str | None] = mapped_column(Text)
    numeric_value: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    text_value: Mapped[str | None] = mapped_column(Text)
    score: Mapped[str | None] = mapped_column(String(100))
    footnote_code: Mapped[str | None] = mapped_column(String(100))
    reporting_period_start: Mapped[date | None] = mapped_column(Date)
    reporting_period_end: Mapped[date | None] = mapped_column(Date, index=True)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class UnmatchedSourceRecord(Base):
    __tablename__ = "unmatched_source_records"
    __table_args__ = (
        UniqueConstraint(
            "source_file_id",
            "import_run_id",
            "source_record_identifier",
            name="uq_unmatched_source_record_import",
        ),
        Index("ix_unmatched_records_status_created", "review_status", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    source_file_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("source_files.id"), index=True)
    import_run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("import_runs.id"), index=True)
    source_record_identifier: Mapped[str] = mapped_column(String(500))
    supplied_cms_certification_number: Mapped[str | None] = mapped_column(String(20), index=True)
    supplied_facility_name: Mapped[str | None] = mapped_column(String(500))
    reason_unmatched: Mapped[str] = mapped_column(String(500))
    raw_payload: Mapped[dict[str, object]] = mapped_column(JSON)
    review_status: Mapped[str] = mapped_column(String(30), default="pending", index=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reviewed_by: Mapped[str | None] = mapped_column(String(255))
    resolution_notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class FacilityIdentifier(TimestampMixin, Base):
    __tablename__ = "facility_identifiers"
    __table_args__ = (
        UniqueConstraint(
            "identifier_type", "normalized_value", name="uq_facility_identifier_strong"
        ),
        Index("ix_facility_identifier_lookup", "identifier_type", "normalized_value"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    facility_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("facilities.id"), index=True)
    identifier_type: Mapped[str] = mapped_column(String(40))
    identifier_value: Mapped[str] = mapped_column(String(500))
    normalized_value: Mapped[str] = mapped_column(String(500))
    issuing_authority: Mapped[str | None] = mapped_column(String(255))
    source_file_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("source_files.id"))
    source_observation_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("facility_source_observations.id")
    )
    valid_from: Mapped[date | None] = mapped_column(Date)
    valid_to: Mapped[date | None] = mapped_column(Date)
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    confidence_score: Mapped[Decimal] = mapped_column(Numeric(5, 4), default=1)


class FacilityAlias(TimestampMixin, Base):
    __tablename__ = "facility_aliases"
    __table_args__ = (
        UniqueConstraint("facility_id", "normalized_alias", "alias_type", name="uq_facility_alias"),
        Index("ix_facility_alias_normalized", "normalized_alias"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    facility_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("facilities.id"), index=True)
    alias_name: Mapped[str] = mapped_column(String(500))
    normalized_alias: Mapped[str] = mapped_column(String(500))
    alias_type: Mapped[str] = mapped_column(String(40))
    source_file_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("source_files.id"))
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")


class FacilityRelationship(TimestampMixin, Base):
    __tablename__ = "facility_relationships"
    __table_args__ = (
        UniqueConstraint(
            "parent_facility_id",
            "child_facility_id",
            "relationship_type",
            name="uq_facility_relationship",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    parent_facility_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("facilities.id"), index=True)
    child_facility_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("facilities.id"), index=True)
    relationship_type: Mapped[str] = mapped_column(String(40))
    valid_from: Mapped[date | None] = mapped_column(Date)
    valid_to: Mapped[date | None] = mapped_column(Date)
    source_file_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("source_files.id"))
    confidence_score: Mapped[Decimal] = mapped_column(Numeric(5, 4), default=1)
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")


class FacilityIdentityCandidate(TimestampMixin, Base):
    __tablename__ = "facility_identity_candidates"
    __table_args__ = (
        UniqueConstraint(
            "source_file_id", "source_record_identifier", name="uq_identity_candidate_source_record"
        ),
        Index("ix_identity_candidate_status_created", "status", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    source_file_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("source_files.id"), index=True)
    import_run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("import_runs.id"), index=True)
    source_record_identifier: Mapped[str] = mapped_column(String(500))
    candidate_facility_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("facilities.id"), index=True
    )
    supplied_name: Mapped[str | None] = mapped_column(String(500))
    supplied_address: Mapped[str | None] = mapped_column(String(500))
    supplied_city: Mapped[str | None] = mapped_column(String(100))
    supplied_state: Mapped[str | None] = mapped_column(String(2))
    supplied_postal_code: Mapped[str | None] = mapped_column(String(10))
    supplied_phone: Mapped[str | None] = mapped_column(String(30))
    supplied_identifiers: Mapped[dict[str, object]] = mapped_column(JSON)
    deterministic_method: Mapped[str] = mapped_column(String(100))
    score: Mapped[Decimal] = mapped_column(Numeric(5, 4))
    reason: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30), index=True)
    raw_payload: Mapped[dict[str, object]] = mapped_column(JSON)


class FacilityIdentityDecision(Base):
    __tablename__ = "facility_identity_decisions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    candidate_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("facility_identity_candidates.id"), index=True
    )
    selected_facility_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("facilities.id"))
    decision: Mapped[str] = mapped_column(String(50))
    reason: Mapped[str] = mapped_column(Text)
    reviewer: Mapped[str] = mapped_column(String(255))
    reviewed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ProcedureCategory(TimestampMixin, Base):
    __tablename__ = "procedure_categories"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    parent_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("procedure_categories.id"))
    slug: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text)
    sort_order: Mapped[int] = mapped_column(default=0)
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")


class Procedure(TimestampMixin, Base):
    __tablename__ = "procedures"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    slug: Mapped[str] = mapped_column(String(150), unique=True, index=True)
    consumer_name: Mapped[str] = mapped_column(String(255), index=True)
    short_description: Mapped[str] = mapped_column(String(500))
    long_description: Mapped[str] = mapped_column(Text)
    category_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("procedure_categories.id"), index=True
    )
    service_setting: Mapped[str] = mapped_column(String(30))
    complexity: Mapped[str] = mapped_column(String(30))
    shoppable: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")


class ProcedureAlias(TimestampMixin, Base):
    __tablename__ = "procedure_aliases"
    __table_args__ = (
        UniqueConstraint("procedure_id", "normalized_alias", name="uq_procedure_alias"),
    )
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    procedure_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("procedures.id"), index=True)
    alias_name: Mapped[str] = mapped_column(String(255))
    normalized_alias: Mapped[str] = mapped_column(String(255), index=True)
    alias_type: Mapped[str] = mapped_column(String(40))
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")


class ProcedureCodeSystem(TimestampMixin, Base):
    __tablename__ = "procedure_code_systems"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    code_system: Mapped[str] = mapped_column(String(40), unique=True)
    display_name: Mapped[str] = mapped_column(String(255))
    version: Mapped[str | None] = mapped_column(String(100))
    licensing_notes: Mapped[str] = mapped_column(Text)
    public_display_allowed: Mapped[bool] = mapped_column(Boolean, default=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")


class ProcedureCodeMapping(TimestampMixin, Base):
    __tablename__ = "procedure_code_mappings"
    __table_args__ = (
        UniqueConstraint(
            "procedure_id",
            "code_system_id",
            "code",
            "version",
            "modifier",
            name="uq_procedure_code_mapping",
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    procedure_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("procedures.id"), index=True)
    code_system_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("procedure_code_systems.id"), index=True
    )
    code: Mapped[str] = mapped_column(String(50), index=True)
    modifier: Mapped[str | None] = mapped_column(String(255))
    version: Mapped[str | None] = mapped_column(String(100))
    mapping_status: Mapped[str] = mapped_column(String(30), default="draft", index=True)
    source_file_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("source_files.id"))


class ProcedureBundle(TimestampMixin, Base):
    __tablename__ = "procedure_bundles"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    slug: Mapped[str] = mapped_column(String(150), unique=True)
    consumer_name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text)
    bundle_type: Mapped[str] = mapped_column(String(30))
    service_setting: Mapped[str] = mapped_column(String(30))
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")


class ProcedureBundleComponent(TimestampMixin, Base):
    __tablename__ = "procedure_bundle_components"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    procedure_bundle_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("procedure_bundles.id"), index=True
    )
    procedure_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("procedures.id"))
    procedure_code_mapping_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("procedure_code_mappings.id")
    )
    component_name: Mapped[str] = mapped_column(String(255))
    required: Mapped[bool] = mapped_column(Boolean, default=True)
    quantity_min: Mapped[int | None] = mapped_column()
    quantity_max: Mapped[int | None] = mapped_column()
    notes: Mapped[str | None] = mapped_column(Text)


class SearchDocument(TimestampMixin, Base):
    __tablename__ = "search_documents"
    __table_args__ = (
        UniqueConstraint("entity_type", "entity_id", name="uq_search_document_entity"),
        Index("ix_search_document_filters", "entity_type", "state", "city", "postal_code"),
    )
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    entity_type: Mapped[str] = mapped_column(String(40), index=True)
    entity_id: Mapped[uuid.UUID] = mapped_column(Uuid, index=True)
    primary_text: Mapped[str] = mapped_column(String(500))
    secondary_text: Mapped[str] = mapped_column(Text)
    normalized_text: Mapped[str] = mapped_column(Text)
    search_vector: Mapped[str | None] = mapped_column(Text)
    state: Mapped[str | None] = mapped_column(String(2), index=True)
    city: Mapped[str | None] = mapped_column(String(100), index=True)
    postal_code: Mapped[str | None] = mapped_column(String(10), index=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    metadata_json: Mapped[dict[str, object]] = mapped_column("metadata", JSON)


class DataHealthRule(TimestampMixin, Base):
    __tablename__ = "data_health_rules"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    rule_key: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text)
    entity_type: Mapped[str] = mapped_column(String(40), index=True)
    severity: Mapped[str] = mapped_column(String(20), index=True)
    weight: Mapped[Decimal] = mapped_column(Numeric(6, 2))
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    configuration: Mapped[dict[str, object]] = mapped_column(JSON)


class DataHealthEvaluation(Base):
    __tablename__ = "data_health_evaluations"
    __table_args__ = (Index("ix_health_eval_filters", "entity_type", "status", "evaluated_at"),)
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    rule_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("data_health_rules.id"), index=True)
    entity_type: Mapped[str] = mapped_column(String(40))
    entity_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, index=True)
    source_file_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("source_files.id"))
    import_run_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("import_runs.id"))
    status: Mapped[str] = mapped_column(String(20), index=True)
    score: Mapped[Decimal] = mapped_column(Numeric(6, 2))
    message: Mapped[str] = mapped_column(Text)
    details: Mapped[dict[str, object]] = mapped_column(JSON)
    evaluated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class EntityDataHealthScore(Base):
    __tablename__ = "entity_data_health_scores"
    __table_args__ = (UniqueConstraint("entity_type", "entity_id", name="uq_entity_health_score"),)
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    entity_type: Mapped[str] = mapped_column(String(40), index=True)
    entity_id: Mapped[uuid.UUID] = mapped_column(Uuid, index=True)
    completeness_score: Mapped[Decimal] = mapped_column(Numeric(6, 2))
    freshness_score: Mapped[Decimal] = mapped_column(Numeric(6, 2))
    validity_score: Mapped[Decimal] = mapped_column(Numeric(6, 2))
    provenance_score: Mapped[Decimal] = mapped_column(Numeric(6, 2))
    overall_score: Mapped[Decimal] = mapped_column(Numeric(6, 2), index=True)
    details: Mapped[dict[str, object]] = mapped_column(JSON)
    calculated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class PipelineStatusSnapshot(Base):
    __tablename__ = "pipeline_status_snapshots"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    importer_name: Mapped[str] = mapped_column(String(255), index=True)
    source_type: Mapped[str] = mapped_column(String(100))
    latest_import_run_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("import_runs.id"))
    latest_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    latest_failure_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    current_status: Mapped[str] = mapped_column(String(30), index=True)
    freshness_status: Mapped[str] = mapped_column(String(30))
    expected_refresh_interval_hours: Mapped[int | None] = mapped_column()
    records_last_imported: Mapped[int | None] = mapped_column(BigInteger)
    error_summary: Mapped[str | None] = mapped_column(Text)
    calculated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
