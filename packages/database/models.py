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
    Numeric,
    String,
    Text,
    UniqueConstraint,
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
    RUNNING = "running"
    COMPLETED = "completed"
    COMPLETED_WITH_ERRORS = "completed_with_errors"
    FAILED = "failed"


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class Facility(TimestampMixin, Base):
    __tablename__ = "facilities"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    cms_certification_number: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    legal_name: Mapped[str] = mapped_column(String(255))
    display_name: Mapped[str] = mapped_column(String(255))
    facility_type: Mapped[str | None] = mapped_column(String(100))
    ownership_type: Mapped[str | None] = mapped_column(String(100))
    phone: Mapped[str | None] = mapped_column(String(30))
    website_url: Mapped[str | None] = mapped_column(String(2048))
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    source_file_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("source_files.id"), index=True)

    locations: Mapped[list["FacilityLocation"]] = relationship(
        back_populates="facility", cascade="all, delete-orphan"
    )


class FacilityLocation(TimestampMixin, Base):
    __tablename__ = "facility_locations"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    facility_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("facilities.id"), unique=True)
    address_line_1: Mapped[str] = mapped_column(String(255))
    address_line_2: Mapped[str | None] = mapped_column(String(255))
    city: Mapped[str] = mapped_column(String(100))
    state: Mapped[str] = mapped_column(String(2), index=True)
    postal_code: Mapped[str] = mapped_column(String(10))
    county: Mapped[str | None] = mapped_column(String(100))
    latitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    longitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))

    facility: Mapped[Facility] = relationship(back_populates="locations")


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
