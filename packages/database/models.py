import enum
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, Boolean, DateTime, Enum, ForeignKey, Numeric, String, Text, func
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
