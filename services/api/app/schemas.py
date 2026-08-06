import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class FacilityLocationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    address_line_1: str
    address_line_2: str | None
    city: str
    state: str
    postal_code: str
    county: str | None
    latitude: Decimal | None
    longitude: Decimal | None


class FacilityResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    cms_certification_number: str
    legal_name: str
    display_name: str
    facility_type: str | None
    ownership_type: str | None
    phone: str | None
    website_url: str | None
    active: bool
    created_at: datetime
    updated_at: datetime
    locations: list[FacilityLocationResponse]


class FacilityPage(BaseModel):
    items: list[FacilityResponse]
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=100)
    total: int = Field(ge=0)


class StatusResponse(BaseModel):
    status: str


class PageMetadata(BaseModel):
    page: int
    page_size: int
    total: int


class QualityMeasureDefinitionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    cms_measure_id: str
    measure_name: str
    consumer_name: str | None
    description: str | None
    category: str
    unit: str | None
    directionality: str
    data_type: str
    active: bool


class QualityMeasurePage(PageMetadata):
    items: list[QualityMeasureDefinitionResponse]


class FacilityQualityObservationResponse(BaseModel):
    id: uuid.UUID
    cms_measure_id: str
    measure_name: str
    consumer_name: str | None
    category: str
    unit: str | None
    directionality: str
    raw_value: str | None
    numeric_value: Decimal | None
    text_value: str | None
    score: str | None
    footnote_code: str | None
    reporting_period_start: date | None
    reporting_period_end: date | None
    observed_at: datetime
    source_file_id: uuid.UUID


class FacilityQualityPage(PageMetadata):
    items: list[FacilityQualityObservationResponse]


class ImportRunResponse(BaseModel):
    id: uuid.UUID
    importer_name: str
    started_at: datetime
    finished_at: datetime | None
    status: str
    rows_read: int
    rows_inserted: int
    rows_updated: int
    rows_rejected: int
    error_summary: str | None
    source_file_id: uuid.UUID
    source_name: str


class ImportRunPage(PageMetadata):
    items: list[ImportRunResponse]


class SourceFileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    source_name: str
    source_url: str
    source_type: str
    storage_path: str
    checksum_sha256: str
    etag: str | None
    last_modified: str | None
    source_published_at: datetime | None
    downloaded_at: datetime
    file_size: int
    parser_version: str
    status: str


class SourceFilePage(PageMetadata):
    items: list[SourceFileResponse]


class UnmatchedRecordResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    source_file_id: uuid.UUID
    import_run_id: uuid.UUID
    source_record_identifier: str
    supplied_cms_certification_number: str | None
    supplied_facility_name: str | None
    reason_unmatched: str
    review_status: str
    reviewed_at: datetime | None
    reviewed_by: str | None
    resolution_notes: str | None
    created_at: datetime


class UnmatchedRecordPage(PageMetadata):
    items: list[UnmatchedRecordResponse]


class AdminFacilityResponse(BaseModel):
    id: uuid.UUID
    cms_certification_number: str
    display_name: str
    legal_name: str
    facility_type: str | None
    active: bool
    city: str | None
    state: str | None
    latest_source_name: str
    quality_measure_count: int
    updated_at: datetime


class AdminFacilityPage(PageMetadata):
    items: list[AdminFacilityResponse]


class AdminFacilityDetailResponse(BaseModel):
    facility: FacilityResponse
    latest_source: SourceFileResponse
    import_run_count: int
    raw_source_observation_count: int
    quality_measure_count: int


class AdminDashboardResponse(BaseModel):
    total_facilities: int
    nh_facilities: int
    latest_import_status: str | None
    failed_import_count: int
    unmatched_record_count: int
    facilities_with_quality: int
    facilities_without_quality: int
    latest_source_downloaded_at: datetime | None
