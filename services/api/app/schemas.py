import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class FacilityLocationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    location_name: str | None
    location_type: str
    active: bool
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


class PricingSourceResponse(BaseModel):
    id: uuid.UUID
    facility_id: uuid.UUID
    facility_name: str
    source_type: str
    source_page_url: str | None
    machine_readable_file_url: str
    cms_hpt_txt_url: str | None
    detected_format: str | None
    detected_schema_version: str | None
    discovery_method: str
    last_seen_at: datetime
    last_successful_download_at: datetime | None
    source_file_id: uuid.UUID | None
    checksum_sha256: str | None
    file_size: int | None


class PricingSourcePage(PageMetadata):
    items: list[PricingSourceResponse]


class PriceRecordResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    facility_id: uuid.UUID
    source_file_id: uuid.UUID
    import_run_id: uuid.UUID
    source_record_identifier: str
    raw_description: str
    setting: str | None
    billing_class: str | None
    gross_charge: Decimal | None
    discounted_cash_price: Decimal | None
    deidentified_minimum_negotiated_rate: Decimal | None
    deidentified_maximum_negotiated_rate: Decimal | None
    currency: str
    parser_name: str
    parser_version: str
    observed_at: datetime


class PriceRecordPage(PageMetadata):
    items: list[PriceRecordResponse]


class PricingAdminItem(BaseModel):
    id: uuid.UUID
    data: dict[str, object]


class PricingAdminPage(PageMetadata):
    items: list[PricingAdminItem]


class PublicPriceSummaryResponse(BaseModel):
    id: uuid.UUID
    facility_id: uuid.UUID
    facility_name: str
    facility_location_id: uuid.UUID | None
    location_name: str | None
    location_type: str | None
    address_line_1: str | None
    city: str | None
    procedure_slug: str
    procedure_name: str
    payer_slug: str | None
    payer_name: str | None
    plan_name: str | None
    service_setting: str
    cash_price_min: Decimal | None
    cash_price_max: Decimal | None
    negotiated_price_min: Decimal | None
    negotiated_price_max: Decimal | None
    record_count: int
    source_url: str
    source_checksum_sha256: str
    last_updated: datetime
    included_component_scope: str
    disclaimer: str = (
        "Public hospital transparency prices may not equal a patient's final bill or "
        "out-of-pocket responsibility. Verify network status and benefits separately."
    )


class PublicPriceSummaryPage(PageMetadata):
    items: list[PublicPriceSummaryResponse]


class ProcedureComparisonItem(BaseModel):
    facility_id: uuid.UUID
    facility_name: str
    facility_location_id: uuid.UUID
    location_name: str | None
    location_type: str
    address_line_1: str
    city: str
    state: str
    postal_code: str
    facility_type: str | None
    cms_overall_rating: str | None
    price_available: bool
    cash_price_min: Decimal | None
    cash_price_max: Decimal | None
    negotiated_price_min: Decimal | None
    negotiated_price_max: Decimal | None
    service_settings: list[str]
    summary_count: int
    source_count: int
    latest_updated: datetime | None
    source_url: str | None


class ProcedureComparisonResponse(BaseModel):
    procedure_slug: str
    procedure_name: str
    state: str
    active_facilities: int
    facilities_with_prices: int
    service_locations: int
    items: list[ProcedureComparisonItem]


class PricingCoverageResponse(BaseModel):
    nh_facilities: int
    facilities_with_sources: int
    facilities_with_downloads: int
    facilities_with_parsed_records: int
    facilities_with_publishable_prices: int
    publishable_procedures: int
    last_updated: datetime | None


class FreshnessEntry(BaseModel):
    facility_id: uuid.UUID
    facility_name: str
    last_download_at: datetime | None
    freshness_score: float
    days_since_download: int | None


class FreshnessResponse(BaseModel):
    items: list[FreshnessEntry]
    average_freshness: float


class StatewideScorecard(BaseModel):
    state: str
    total_facilities: int
    component_scores: dict[str, float]
    overall_readiness: float
    target: float
    meets_target: bool
    details: dict[str, object]


class FacilityScoreResponse(BaseModel):
    facility_id: uuid.UUID
    facility_name: str
    city: str | None
    overall_score: float
    source_discovery_score: float
    download_score: float
    parse_score: float
    mapping_score: float
    payer_normalization_score: float
    anomaly_score: float
    freshness_score: float
    price_coverage_score: float
    calculated_at: datetime


class FacilityScorePage(PageMetadata):
    items: list[FacilityScoreResponse]


class PricingHealthResponse(BaseModel):
    facility_id: uuid.UUID
    overall_score: float
    source_discovery_score: float
    download_score: float
    parse_score: float
    mapping_score: float
    payer_normalization_score: float
    anomaly_score: float
    freshness_score: float
    price_coverage_score: float
    details: dict[str, object]
    calculated_at: datetime


class MapFacility(BaseModel):
    type: str = "Feature"
    geometry: dict[str, object]
    properties: dict[str, object]


class MapDataResponse(BaseModel):
    type: str = "FeatureCollection"
    features: list[MapFacility]
