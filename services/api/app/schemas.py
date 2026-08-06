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
    cms_certification_number: str | None
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
    cms_certification_number: str | None
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


class SearchResultResponse(BaseModel):
    entity_type: str
    entity_id: uuid.UUID
    title: str
    subtitle: str
    location: str | None
    score: float
    match_reason: str
    matched_term: str
    metadata: dict[str, object]


class SearchPage(PageMetadata):
    items: list[SearchResultResponse]
    elapsed_ms: float


class ProcedureCategoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    parent_id: uuid.UUID | None
    slug: str
    name: str
    description: str
    sort_order: int


class ProcedureResponse(BaseModel):
    id: uuid.UUID
    slug: str
    consumer_name: str
    short_description: str
    long_description: str
    category: ProcedureCategoryResponse
    service_setting: str
    complexity: str
    shoppable: bool
    aliases: list[str]
    billing_notice: str = "Final treatment and billing may involve multiple services."


class ProcedurePage(PageMetadata):
    items: list[ProcedureResponse]


class IdentityCandidateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    source_file_id: uuid.UUID
    import_run_id: uuid.UUID
    source_record_identifier: str
    candidate_facility_id: uuid.UUID | None
    supplied_name: str | None
    supplied_address: str | None
    supplied_city: str | None
    supplied_state: str | None
    supplied_postal_code: str | None
    supplied_phone: str | None
    supplied_identifiers: dict[str, object]
    deterministic_method: str
    score: Decimal
    reason: str
    status: str
    raw_payload: dict[str, object]
    created_at: datetime


class IdentityCandidatePage(PageMetadata):
    items: list[IdentityCandidateResponse]


class DataHealthEvaluationResponse(BaseModel):
    id: uuid.UUID
    rule_key: str
    rule_name: str
    severity: str
    entity_type: str
    entity_id: uuid.UUID | None
    status: str
    score: Decimal
    message: str
    details: dict[str, object]
    evaluated_at: datetime


class DataHealthPage(PageMetadata):
    items: list[DataHealthEvaluationResponse]


class FacilityHealthResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    entity_id: uuid.UUID
    completeness_score: Decimal
    freshness_score: Decimal
    validity_score: Decimal
    provenance_score: Decimal
    overall_score: Decimal
    details: dict[str, object]
    calculated_at: datetime


class FacilityHealthPage(PageMetadata):
    items: list[FacilityHealthResponse]


class PipelineStatusResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    importer_name: str
    source_type: str
    latest_import_run_id: uuid.UUID | None
    latest_success_at: datetime | None
    latest_failure_at: datetime | None
    current_status: str
    freshness_status: str
    expected_refresh_interval_hours: int | None
    records_last_imported: int | None
    error_summary: str | None
    calculated_at: datetime


class PipelineStatusPage(PageMetadata):
    items: list[PipelineStatusResponse]
