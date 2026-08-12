import time
import uuid
from collections import defaultdict, deque
from collections.abc import Awaitable, Callable
from typing import Annotated, Any, cast

import structlog
from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import case, desc, exists, func, select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, selectinload
from sqlalchemy.sql.elements import ColumnElement
from starlette.middleware.trustedhost import TrustedHostMiddleware

from collectors.hospital_prices.scope import active_consumer_facility_ids
from packages.database import (
    DataHealthEvaluation,
    DataHealthRule,
    EntityDataHealthScore,
    Facility,
    FacilityIdentityCandidate,
    FacilityLocation,
    FacilityMedia,
    FacilityPriceSource,
    FacilityProcedurePriceObservation,
    FacilityProcedurePriceSummary,
    FacilityQualityMeasureObservation,
    FacilitySourceObservation,
    HospitalPriceRateDetail,
    HospitalPriceRecord,
    ImportRun,
    InsurancePlanEntity,
    PayerEntity,
    PipelineStatusSnapshot,
    PriceRecordProcedureCandidate,
    PriceServiceCode,
    PriceSourceDiscoveryObservation,
    PriceSourceDiscoveryRun,
    PricingAnomaly,
    PricingHealthScore,
    PricingUnmatchedRecord,
    Procedure,
    ProcedureAlias,
    ProcedureCategory,
    QualityMeasureDefinition,
    SourceFile,
    UnmatchedSourceRecord,
    get_session,
)
from packages.geo import resolve_origin
from packages.search import search
from services.api.app.comparison_insights import annotate as annotate_comparison
from services.api.app.comparison_insights import summarize_cash_components
from services.api.app.coverage import consumer_pricing_status, pricing_status_matches
from services.api.app.facility_media import (
    media_fields,
    pick_media,
    resolve_facility_media,
)
from services.api.app.logging import configure_logging
from services.api.app.schemas import (
    AdminDashboardResponse,
    AdminFacilityDetailResponse,
    AdminFacilityMediaItem,
    AdminFacilityMediaPage,
    AdminFacilityPage,
    ConsumerPriceDetailResponse,
    DataHealthPage,
    FacilityHealthPage,
    FacilityPage,
    FacilityProcedureOverviewResponse,
    FacilityQualityPage,
    FacilityResponse,
    FacilityScorePage,
    FreshnessResponse,
    IdentityCandidatePage,
    ImportRunPage,
    MapDataResponse,
    PipelineStatusPage,
    PriceRecordPage,
    PricingAdminPage,
    PricingCoverageResponse,
    PricingHealthResponse,
    PricingSourcePage,
    ProcedureCategoryResponse,
    ProcedureComparisonResponse,
    ProcedurePage,
    ProcedureResponse,
    PublicPriceSummaryPage,
    QualityMeasurePage,
    SearchPage,
    SourceFilePage,
    StatewideScorecard,
    StatusResponse,
    UnmatchedRecordPage,
)
from services.api.app.settings import api_settings

configure_logging(api_settings.log_level)
logger = structlog.get_logger(service="api", environment=api_settings.app_env.value)
app = FastAPI(title=api_settings.api_title, version=api_settings.api_version)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=api_settings.hosts)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin for origin in api_settings.origins],
    allow_credentials=False,
    allow_methods=["GET", "OPTIONS"],
    allow_headers=["*"],
)

_rate_windows: dict[str, deque[float]] = defaultdict(deque)
_RATE_LIMITED_PREFIXES = (
    "/api/v1/search",
    "/api/v1/procedures/",
    "/api/v1/facilities/map-data",
    "/api/v1/pricing/",
)


def _client_key(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "").split(",", 1)[0].strip()
    return forwarded or (request.client.host if request.client else "unknown")


def _security_headers(response: Response) -> None:
    response.headers["x-content-type-options"] = "nosniff"
    response.headers["x-frame-options"] = "DENY"
    response.headers["referrer-policy"] = "strict-origin-when-cross-origin"
    response.headers["permissions-policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["content-security-policy"] = "default-src 'none'; frame-ancestors 'none'"
    if api_settings.is_deployed:
        response.headers["strict-transport-security"] = "max-age=31536000; includeSubDomains"


@app.middleware("http")
async def request_logging(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    started = time.perf_counter()
    request_id = request.headers.get("x-request-id", str(uuid.uuid4()))
    if len(request.scope.get("query_string", b"")) > api_settings.max_query_string_bytes:
        return JSONResponse(
            status_code=414,
            content={"detail": "query string too large", "request_id": request_id},
            headers={"x-request-id": request_id},
        )
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > api_settings.max_request_body_bytes:
        return JSONResponse(
            status_code=413,
            content={"detail": "request body too large", "request_id": request_id},
            headers={"x-request-id": request_id},
        )
    if request.url.path.startswith("/api/v1/admin"):
        supplied = request.headers.get("x-carevero-admin-key")
        if not api_settings.admin_api_enabled:
            return JSONResponse(status_code=404, content={"detail": "not found"})
        if api_settings.admin_shared_secret and supplied != api_settings.admin_shared_secret:
            return JSONResponse(status_code=404, content={"detail": "not found"})
    if not api_settings.public_pricing_enabled and (
        "/prices" in request.url.path
        or "/comparison" in request.url.path
        or "/procedure-overview" in request.url.path
        or request.url.path.startswith("/api/v1/pricing")
    ):
        return JSONResponse(
            status_code=503,
            content={"detail": "pricing is temporarily unavailable", "request_id": request_id},
            headers={"x-request-id": request_id, "retry-after": "300"},
        )
    if request.method == "GET" and request.url.path.startswith(_RATE_LIMITED_PREFIXES):
        now = time.monotonic()
        key = f"{_client_key(request)}:{request.url.path}"
        window = _rate_windows[key]
        cutoff = now - api_settings.rate_limit_window_seconds
        while window and window[0] < cutoff:
            window.popleft()
        if len(window) >= api_settings.rate_limit_requests:
            return JSONResponse(
                status_code=429,
                content={"detail": "request rate limit exceeded", "request_id": request_id},
                headers={"x-request-id": request_id, "retry-after": "60"},
            )
        window.append(now)
    try:
        response = await call_next(request)
    except Exception as exc:
        logger.exception(
            "request_failed",
            method=request.method,
            path=request.url.path,
            request_id=request_id,
            error_category=type(exc).__name__,
        )
        response = JSONResponse(
            status_code=500,
            content={"detail": "internal server error", "request_id": request_id},
        )
    response.headers["x-request-id"] = request_id
    _security_headers(response)
    logger.info(
        "request_completed",
        method=request.method,
        path=request.url.path,
        status_code=response.status_code,
        duration_ms=round((time.perf_counter() - started) * 1000, 2),
        request_id=request_id,
    )
    return response


@app.get("/health", response_model=StatusResponse, tags=["system"])
def health() -> StatusResponse:
    return StatusResponse(status="ok")


@app.get("/version", tags=["system"])
def version() -> dict[str, str]:
    return {
        "service": "api",
        "version": api_settings.api_version,
        "build": api_settings.app_version,
        "environment": api_settings.app_env.value,
    }


@app.get("/ready", response_model=StatusResponse, tags=["system"])
def ready(session: Annotated[Session, Depends(get_session)]) -> StatusResponse:
    try:
        session.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        logger.warning("database_not_ready", error_type=type(exc).__name__)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="database unavailable"
        ) from exc
    return StatusResponse(status="ready")


@app.get("/api/v1/facilities", response_model=FacilityPage, tags=["facilities"])
def list_facilities(
    session: Annotated[Session, Depends(get_session)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
    state_code: Annotated[str | None, Query(alias="state", min_length=2, max_length=2)] = None,
) -> FacilityPage:
    filters: list[ColumnElement[bool]] = [Facility.active.is_(True)]
    query = (
        select(Facility)
        .distinct()
        .options(selectinload(Facility.locations.and_(FacilityLocation.active.is_(True))))
    )
    count_query = select(func.count(func.distinct(Facility.id)))
    if state_code:
        normalized_state = state_code.upper()
        consumer_facility_ids = active_consumer_facility_ids(session, normalized_state)
        query = query.join(FacilityLocation)
        count_query = count_query.join(FacilityLocation)
        filters.extend(
            [
                Facility.id.in_(consumer_facility_ids),
                FacilityLocation.state == normalized_state,
                FacilityLocation.active.is_(True),
            ]
        )
    items = session.scalars(
        query.where(*filters)
        .order_by(Facility.display_name, Facility.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    total = session.scalar(count_query.where(*filters)) or 0
    media = resolve_facility_media(session, [f.id for f in items], api_settings)
    responses = [
        FacilityResponse.model_validate(facility).model_copy(
            update=media_fields(pick_media(media, facility.id, None))
        )
        for facility in items
    ]
    return FacilityPage(items=responses, page=page, page_size=page_size, total=total)


@app.get("/api/v1/facilities/map-data", response_model=MapDataResponse, tags=["facilities"])
def facilities_map_data(
    session: Annotated[Session, Depends(get_session)],
    pricing_status: Annotated[str | None, Query(max_length=30)] = None,
    state_code: Annotated[str, Query(alias="state", min_length=2, max_length=2)] = "NH",
) -> MapDataResponse:
    facility_ids = active_consumer_facility_ids(session, state_code)
    rows = session.execute(
        select(Facility, FacilityLocation)
        .join(FacilityLocation)
        .where(
            Facility.active.is_(True),
            Facility.id.in_(facility_ids),
            FacilityLocation.state == state_code.upper(),
            FacilityLocation.active.is_(True),
            FacilityLocation.latitude.is_not(None),
            FacilityLocation.longitude.is_not(None),
        )
        .order_by(Facility.display_name)
    ).all()

    features = []
    for facility, location in rows:
        procedure_count = (
            session.scalar(
                select(func.count(func.distinct(FacilityProcedurePriceSummary.procedure_id))).where(
                    FacilityProcedurePriceSummary.facility_id == facility.id,
                    FacilityProcedurePriceSummary.facility_location_id == location.id,
                    FacilityProcedurePriceSummary.publication_status == "publishable",
                    FacilityProcedurePriceSummary.source_file_id.in_(
                        select(SourceFile.id).where(SourceFile.source_url.not_like("file://%"))
                    ),
                )
            )
            or 0
        )
        fac_status = consumer_pricing_status(procedure_count)
        if not pricing_status_matches(fac_status, pricing_status):
            continue

        features.append(
            {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [float(location.longitude), float(location.latitude)],
                },
                "properties": {
                    "id": str(location.id),
                    "facility_id": str(facility.id),
                    "name": facility.display_name,
                    "location_name": location.location_name,
                    "city": location.city,
                    "pricing_status": fac_status,
                    "procedure_count": procedure_count,
                },
            }
        )
    return MapDataResponse(features=features)


@app.get("/api/v1/facilities/{facility_id}", response_model=FacilityResponse, tags=["facilities"])
def get_facility(
    facility_id: uuid.UUID, session: Annotated[Session, Depends(get_session)]
) -> FacilityResponse:
    facility = session.scalar(
        select(Facility)
        .options(selectinload(Facility.locations.and_(FacilityLocation.active.is_(True))))
        .where(Facility.id == facility_id, Facility.active.is_(True))
    )
    if facility is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="facility not found")
    media = resolve_facility_media(session, [facility.id], api_settings)
    return FacilityResponse.model_validate(facility).model_copy(
        update=media_fields(pick_media(media, facility.id, None))
    )


@app.get("/api/v1/quality-measures", response_model=QualityMeasurePage, tags=["quality"])
def list_quality_measures(
    session: Annotated[Session, Depends(get_session)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
    category: Annotated[str | None, Query(max_length=100)] = None,
    sort: Annotated[
        str, Query(pattern="^(cms_measure_id|measure_name|category)$")
    ] = "measure_name",
) -> QualityMeasurePage:
    filters: list[ColumnElement[bool]] = [QualityMeasureDefinition.active.is_(True)]
    if category:
        filters.append(QualityMeasureDefinition.category == category)
    sort_column = {
        "cms_measure_id": QualityMeasureDefinition.cms_measure_id,
        "measure_name": QualityMeasureDefinition.measure_name,
        "category": QualityMeasureDefinition.category,
    }[sort]
    items = session.scalars(
        select(QualityMeasureDefinition)
        .where(*filters)
        .order_by(sort_column, QualityMeasureDefinition.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    total = session.scalar(select(func.count(QualityMeasureDefinition.id)).where(*filters)) or 0
    return QualityMeasurePage(items=list(items), page=page, page_size=page_size, total=total)


@app.get(
    "/api/v1/facilities/{facility_id}/quality",
    response_model=FacilityQualityPage,
    tags=["quality"],
)
def facility_quality(
    facility_id: uuid.UUID,
    session: Annotated[Session, Depends(get_session)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
    category: Annotated[str | None, Query(max_length=100)] = None,
) -> FacilityQualityPage:
    if session.scalar(select(Facility.id).where(Facility.id == facility_id)) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="facility not found")
    filters: list[ColumnElement[bool]] = [
        FacilityQualityMeasureObservation.facility_id == facility_id
    ]
    if category:
        filters.append(QualityMeasureDefinition.category == category)
    query = (
        select(FacilityQualityMeasureObservation, QualityMeasureDefinition)
        .join(
            QualityMeasureDefinition,
            QualityMeasureDefinition.id
            == FacilityQualityMeasureObservation.quality_measure_definition_id,
        )
        .where(*filters)
    )
    rows = session.execute(
        query.order_by(
            desc(FacilityQualityMeasureObservation.reporting_period_end),
            QualityMeasureDefinition.measure_name,
        )
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    total = (
        session.scalar(
            select(func.count(FacilityQualityMeasureObservation.id))
            .join(QualityMeasureDefinition)
            .where(*filters)
        )
        or 0
    )
    items = [
        {
            "id": observation.id,
            "cms_measure_id": definition.cms_measure_id,
            "measure_name": definition.measure_name,
            "consumer_name": definition.consumer_name,
            "category": definition.category,
            "unit": definition.unit,
            "directionality": definition.directionality,
            "raw_value": observation.raw_value,
            "numeric_value": observation.numeric_value,
            "text_value": observation.text_value,
            "score": observation.score,
            "footnote_code": observation.footnote_code,
            "reporting_period_start": observation.reporting_period_start,
            "reporting_period_end": observation.reporting_period_end,
            "observed_at": observation.observed_at,
            "source_file_id": observation.source_file_id,
        }
        for observation, definition in rows
    ]
    return FacilityQualityPage(items=items, page=page, page_size=page_size, total=total)


@app.get("/api/v1/admin/dashboard", response_model=AdminDashboardResponse, tags=["admin"])
def admin_dashboard(
    session: Annotated[Session, Depends(get_session)],
) -> AdminDashboardResponse:
    total = session.scalar(select(func.count(Facility.id))) or 0
    nh = (
        session.scalar(
            select(func.count(func.distinct(Facility.id)))
            .join(FacilityLocation)
            .where(FacilityLocation.state == "NH")
        )
        or 0
    )
    latest_run = session.scalar(select(ImportRun).order_by(desc(ImportRun.started_at)).limit(1))
    failed = (
        session.scalar(select(func.count(ImportRun.id)).where(ImportRun.status == "FAILED")) or 0
    )
    unmatched = (
        session.scalar(
            select(func.count(UnmatchedSourceRecord.id)).where(
                UnmatchedSourceRecord.review_status == "pending"
            )
        )
        or 0
    )
    with_quality = (
        session.scalar(
            select(func.count(func.distinct(FacilityQualityMeasureObservation.facility_id)))
        )
        or 0
    )
    latest_source = session.scalar(
        select(SourceFile).order_by(desc(SourceFile.downloaded_at)).limit(1)
    )
    return AdminDashboardResponse(
        total_facilities=total,
        nh_facilities=nh,
        latest_import_status=latest_run.status.value if latest_run else None,
        failed_import_count=failed,
        unmatched_record_count=unmatched,
        facilities_with_quality=with_quality,
        facilities_without_quality=max(total - with_quality, 0),
        latest_source_downloaded_at=latest_source.downloaded_at if latest_source else None,
    )


@app.get("/api/v1/admin/import-runs", response_model=ImportRunPage, tags=["admin"])
def admin_import_runs(
    session: Annotated[Session, Depends(get_session)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
    import_status: Annotated[str | None, Query(alias="status", max_length=50)] = None,
    sort: Annotated[
        str, Query(pattern="^(started_at|finished_at|importer_name|status)$")
    ] = "started_at",
) -> ImportRunPage:
    filters = [ImportRun.status == import_status] if import_status else []
    sort_column = {
        "started_at": ImportRun.started_at,
        "finished_at": ImportRun.finished_at,
        "importer_name": ImportRun.importer_name,
        "status": ImportRun.status,
    }[sort]
    rows = session.execute(
        select(ImportRun, SourceFile)
        .join(SourceFile, SourceFile.id == ImportRun.source_file_id)
        .where(*filters)
        .order_by(desc(sort_column), ImportRun.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    total = session.scalar(select(func.count(ImportRun.id)).where(*filters)) or 0
    items = [
        {
            "id": run.id,
            "importer_name": run.importer_name,
            "started_at": run.started_at,
            "finished_at": run.finished_at,
            "status": run.status.value,
            "rows_read": run.rows_read,
            "rows_inserted": run.rows_inserted,
            "rows_updated": run.rows_updated,
            "rows_rejected": run.rows_rejected,
            "error_summary": run.error_summary,
            "source_file_id": run.source_file_id,
            "source_name": source.source_name,
            "stage": run.stage,
            "stage_started_at": run.stage_started_at,
            "batches_committed": run.batches_committed,
            "bytes_processed": run.bytes_processed,
            "throughput_rows_per_sec": float(run.throughput_rows_per_sec)
            if run.throughput_rows_per_sec is not None
            else None,
            "last_checkpoint_at": run.last_checkpoint_at,
            "parser_version_used": run.parser_version_used,
            "source_checksum_used": run.source_checksum_used,
            "resumable": run.status.value in ("interrupted", "failed"),
            "elapsed_seconds": round((run.finished_at - run.started_at).total_seconds(), 2)
            if run.finished_at and run.started_at
            else None,
        }
        for run, source in rows
    ]
    return ImportRunPage(items=items, page=page, page_size=page_size, total=total)


@app.get("/api/v1/admin/source-files", response_model=SourceFilePage, tags=["admin"])
def admin_source_files(
    session: Annotated[Session, Depends(get_session)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
    source_type: Annotated[str | None, Query(max_length=100)] = None,
    sort: Annotated[str, Query(pattern="^(downloaded_at|source_name|status)$")] = "downloaded_at",
) -> SourceFilePage:
    filters = [SourceFile.source_type == source_type] if source_type else []
    sort_column = {
        "downloaded_at": SourceFile.downloaded_at,
        "source_name": SourceFile.source_name,
        "status": SourceFile.status,
    }[sort]
    items = session.scalars(
        select(SourceFile)
        .where(*filters)
        .order_by(desc(sort_column), SourceFile.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    total = session.scalar(select(func.count(SourceFile.id)).where(*filters)) or 0
    return SourceFilePage(items=list(items), page=page, page_size=page_size, total=total)


@app.get(
    "/api/v1/admin/facility-media",
    response_model=AdminFacilityMediaPage,
    tags=["admin"],
)
def admin_facility_media(
    session: Annotated[Session, Depends(get_session)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 50,
    verification_status: Annotated[
        str | None, Query(alias="status", max_length=20)
    ] = None,
) -> AdminFacilityMediaPage:
    """Review queue for facility imagery. Read-only: verify/reject/set-primary
    are auditable actions run via `scripts.facility_media` (verified_by /
    review_notes are recorded), matching the existing admin mutation pattern."""
    filters = (
        [FacilityMedia.verification_status == verification_status]
        if verification_status
        else []
    )
    rows = session.execute(
        select(FacilityMedia, Facility.display_name)
        .join(Facility, Facility.id == FacilityMedia.facility_id)
        .where(*filters)
        .order_by(desc(FacilityMedia.created_at), FacilityMedia.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    total = session.scalar(select(func.count(FacilityMedia.id)).where(*filters)) or 0
    counts_rows = session.execute(
        select(FacilityMedia.verification_status, func.count(FacilityMedia.id)).group_by(
            FacilityMedia.verification_status
        )
    ).all()
    base = api_settings.facility_media_public_base_url
    items = [
        AdminFacilityMediaItem(
            id=media.id,
            facility_id=media.facility_id,
            facility_name=display_name,
            service_location_id=media.service_location_id,
            verification_status=media.verification_status,
            is_primary=media.is_primary,
            media_type=media.media_type,
            image_url=(
                media.cdn_url
                or (
                    f"{base.rstrip('/')}/{media.storage_key.lstrip('/')}"
                    if media.storage_key and base
                    else media.source_url
                )
            ),
            source_type=media.source_type,
            source_name=media.source_name,
            source_url=media.source_url,
            license_type=media.license_type,
            attribution_text=media.attribution_text,
            width=media.width,
            height=media.height,
            review_notes=media.review_notes,
            created_at=media.created_at,
        )
        for media, display_name in rows
    ]
    return AdminFacilityMediaPage(
        items=items,
        page=page,
        page_size=page_size,
        total=total,
        status_counts={status: count for status, count in counts_rows},
    )


@app.get("/api/v1/admin/unmatched-records", response_model=UnmatchedRecordPage, tags=["admin"])
def admin_unmatched_records(
    session: Annotated[Session, Depends(get_session)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
    review_status: Annotated[str | None, Query(alias="status", max_length=30)] = None,
) -> UnmatchedRecordPage:
    filters = [UnmatchedSourceRecord.review_status == review_status] if review_status else []
    items = session.scalars(
        select(UnmatchedSourceRecord)
        .where(*filters)
        .order_by(desc(UnmatchedSourceRecord.created_at), UnmatchedSourceRecord.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    total = session.scalar(select(func.count(UnmatchedSourceRecord.id)).where(*filters)) or 0
    return UnmatchedRecordPage(items=list(items), page=page, page_size=page_size, total=total)


@app.get("/api/v1/admin/facilities", response_model=AdminFacilityPage, tags=["admin"])
def admin_facilities(
    session: Annotated[Session, Depends(get_session)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
    state_code: Annotated[str | None, Query(alias="state", min_length=2, max_length=2)] = None,
    sort: Annotated[
        str, Query(pattern="^(display_name|updated_at|cms_certification_number)$")
    ] = "display_name",
) -> AdminFacilityPage:
    quality_count = (
        select(
            func.count(
                func.distinct(FacilityQualityMeasureObservation.quality_measure_definition_id)
            )
        )
        .where(FacilityQualityMeasureObservation.facility_id == Facility.id)
        .correlate(Facility)
        .scalar_subquery()
    )
    primary_location_id = (
        select(FacilityLocation.id)
        .where(FacilityLocation.facility_id == Facility.id)
        .order_by(
            case((FacilityLocation.location_type == "hospital_campus", 0), else_=1),
            FacilityLocation.id,
        )
        .limit(1)
        .correlate(Facility)
        .scalar_subquery()
    )
    filters = [FacilityLocation.state == state_code.upper()] if state_code else []
    sort_column = {
        "display_name": Facility.display_name,
        "updated_at": Facility.updated_at,
        "cms_certification_number": Facility.cms_certification_number,
    }[sort]
    rows = session.execute(
        select(Facility, FacilityLocation, SourceFile, quality_count)
        .outerjoin(FacilityLocation, FacilityLocation.id == primary_location_id)
        .join(SourceFile, SourceFile.id == Facility.source_file_id)
        .where(*filters)
        .order_by(sort_column, Facility.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    count_query = select(func.count(Facility.id)).outerjoin(
        FacilityLocation, FacilityLocation.id == primary_location_id
    )
    total = session.scalar(count_query.where(*filters)) or 0
    items = [
        {
            "id": facility.id,
            "cms_certification_number": facility.cms_certification_number,
            "display_name": facility.display_name,
            "legal_name": facility.legal_name,
            "facility_type": facility.facility_type,
            "active": facility.active,
            "city": location.city if location else None,
            "state": location.state if location else None,
            "latest_source_name": source.source_name,
            "quality_measure_count": count,
            "updated_at": facility.updated_at,
        }
        for facility, location, source, count in rows
    ]
    return AdminFacilityPage(items=items, page=page, page_size=page_size, total=total)


@app.get(
    "/api/v1/admin/facilities/{facility_id}",
    response_model=AdminFacilityDetailResponse,
    tags=["admin"],
)
def admin_facility_detail(
    facility_id: uuid.UUID, session: Annotated[Session, Depends(get_session)]
) -> AdminFacilityDetailResponse:
    facility = session.scalar(
        select(Facility).options(selectinload(Facility.locations)).where(Facility.id == facility_id)
    )
    if facility is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="facility not found")
    source = session.get(SourceFile, facility.source_file_id)
    if source is None:  # pragma: no cover - protected by foreign key
        raise HTTPException(status_code=500, detail="facility provenance missing")
    source_observations = (
        session.scalar(
            select(func.count(FacilitySourceObservation.id)).where(
                FacilitySourceObservation.facility_id == facility_id
            )
        )
        or 0
    )
    import_runs = (
        session.scalar(
            select(func.count(func.distinct(FacilitySourceObservation.import_run_id))).where(
                FacilitySourceObservation.facility_id == facility_id
            )
        )
        or 0
    )
    measures = (
        session.scalar(
            select(
                func.count(
                    func.distinct(FacilityQualityMeasureObservation.quality_measure_definition_id)
                )
            ).where(FacilityQualityMeasureObservation.facility_id == facility_id)
        )
        or 0
    )
    return AdminFacilityDetailResponse(
        facility=facility,
        latest_source=source,
        import_run_count=import_runs,
        raw_source_observation_count=source_observations,
        quality_measure_count=measures,
    )


@app.get(
    "/api/v1/admin/facilities/{facility_id}/quality",
    response_model=FacilityQualityPage,
    tags=["admin"],
)
def admin_facility_quality(
    facility_id: uuid.UUID,
    session: Annotated[Session, Depends(get_session)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 100,
    category: Annotated[str | None, Query(max_length=100)] = None,
) -> FacilityQualityPage:
    return facility_quality(facility_id, session, page, page_size, category)


@app.get("/api/v1/search", response_model=SearchPage, tags=["search"])
def unified_search(
    session: Annotated[Session, Depends(get_session)],
    q: Annotated[str, Query(min_length=2, max_length=100)],
    entity_type: Annotated[
        str | None, Query(pattern="^(facility|procedure|procedure_category)$")
    ] = None,
    state_code: Annotated[str | None, Query(alias="state", min_length=2, max_length=2)] = None,
    city: Annotated[str | None, Query(max_length=100)] = None,
    postal_code: Annotated[str | None, Query(min_length=5, max_length=10)] = None,
    category: Annotated[str | None, Query(max_length=100)] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=50)] = 20,
) -> SearchPage:
    started = time.perf_counter()
    all_items = search(session, q, entity_type, state_code, city, postal_code, category)
    items = all_items[(page - 1) * page_size : page * page_size]
    return SearchPage(
        items=[item.__dict__ for item in items],
        page=page,
        page_size=page_size,
        total=len(all_items),
        elapsed_ms=round((time.perf_counter() - started) * 1000, 2),
    )


@app.get("/api/v1/search/suggestions", response_model=list[dict[str, object]], tags=["search"])
def search_suggestions(
    session: Annotated[Session, Depends(get_session)],
    q: Annotated[str, Query(min_length=2, max_length=100)],
    entity_type: Annotated[
        str | None, Query(pattern="^(facility|procedure|procedure_category)$")
    ] = None,
    state_code: Annotated[str | None, Query(alias="state", min_length=2, max_length=2)] = None,
    limit: Annotated[int, Query(ge=1, le=20)] = 8,
) -> list[dict[str, object]]:
    return [
        {
            "entity_type": item.entity_type,
            "entity_id": item.entity_id,
            "title": item.title,
            "match_reason": item.match_reason,
        }
        for item in search(session, q, entity_type, state_code)[:limit]
    ]


def _procedure_response(session: Session, procedure: Procedure) -> ProcedureResponse:
    category = session.get(ProcedureCategory, procedure.category_id)
    if category is None:
        raise RuntimeError("procedure category missing")
    aliases = session.scalars(
        select(ProcedureAlias.alias_name)
        .where(ProcedureAlias.procedure_id == procedure.id, ProcedureAlias.active.is_(True))
        .order_by(ProcedureAlias.alias_name)
    ).all()
    return ProcedureResponse(
        id=procedure.id,
        slug=procedure.slug,
        consumer_name=procedure.consumer_name,
        short_description=procedure.short_description,
        long_description=procedure.long_description,
        category=ProcedureCategoryResponse.model_validate(category),
        service_setting=procedure.service_setting,
        complexity=procedure.complexity,
        shoppable=procedure.shoppable,
        aliases=list(aliases),
    )


@app.get("/api/v1/procedures", response_model=ProcedurePage, tags=["procedures"])
def list_procedures(
    session: Annotated[Session, Depends(get_session)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
    category: Annotated[str | None, Query(max_length=100)] = None,
) -> ProcedurePage:
    statement = select(Procedure).join(ProcedureCategory).where(Procedure.active.is_(True))
    count = (
        select(func.count(Procedure.id)).join(ProcedureCategory).where(Procedure.active.is_(True))
    )
    if category:
        statement, count = (
            statement.where(ProcedureCategory.slug == category),
            count.where(ProcedureCategory.slug == category),
        )
    rows = session.scalars(
        statement.order_by(Procedure.consumer_name, Procedure.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return ProcedurePage(
        items=[_procedure_response(session, item) for item in rows],
        page=page,
        page_size=page_size,
        total=session.scalar(count) or 0,
    )


@app.get("/api/v1/procedures/{slug}", response_model=ProcedureResponse, tags=["procedures"])
def get_procedure(
    slug: str, session: Annotated[Session, Depends(get_session)]
) -> ProcedureResponse:
    item = session.scalar(
        select(Procedure).where(Procedure.slug == slug, Procedure.active.is_(True))
    )
    if item is None:
        raise HTTPException(status_code=404, detail="procedure not found")
    return _procedure_response(session, item)


@app.get(
    "/api/v1/procedure-categories",
    response_model=list[ProcedureCategoryResponse],
    tags=["procedures"],
)
def list_procedure_categories(
    session: Annotated[Session, Depends(get_session)],
) -> list[ProcedureCategory]:
    return list(
        session.scalars(
            select(ProcedureCategory)
            .where(ProcedureCategory.active.is_(True))
            .order_by(ProcedureCategory.sort_order, ProcedureCategory.name)
        )
    )


@app.get("/api/v1/admin/identity-candidates", response_model=IdentityCandidatePage, tags=["admin"])
def identity_candidates(
    session: Annotated[Session, Depends(get_session)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
    candidate_status: Annotated[str | None, Query(alias="status", max_length=30)] = None,
) -> IdentityCandidatePage:
    filters = [FacilityIdentityCandidate.status == candidate_status] if candidate_status else []
    items = session.scalars(
        select(FacilityIdentityCandidate)
        .where(*filters)
        .order_by(desc(FacilityIdentityCandidate.created_at), FacilityIdentityCandidate.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return IdentityCandidatePage(
        items=list(items),
        page=page,
        page_size=page_size,
        total=session.scalar(select(func.count(FacilityIdentityCandidate.id)).where(*filters)) or 0,
    )


@app.get(
    "/api/v1/admin/identity-candidates/{candidate_id}",
    response_model=dict[str, object],
    tags=["admin"],
)
def identity_candidate_detail(
    candidate_id: uuid.UUID, session: Annotated[Session, Depends(get_session)]
) -> dict[str, object]:
    item = session.get(FacilityIdentityCandidate, candidate_id)
    if item is None:
        raise HTTPException(status_code=404, detail="identity candidate not found")
    return {
        "id": item.id,
        "status": item.status,
        "reason": item.reason,
        "raw_payload": item.raw_payload,
        "review_workflow": "read_only_in_phase_3",
    }


@app.get("/api/v1/admin/data-health", response_model=DataHealthPage, tags=["admin"])
def data_health(
    session: Annotated[Session, Depends(get_session)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
    severity: Annotated[str | None, Query(pattern="^(info|warning|error|critical)$")] = None,
    evaluation_status: Annotated[
        str | None, Query(alias="status", pattern="^(pass|warning|fail|skipped)$")
    ] = None,
    entity_type: Annotated[str | None, Query(max_length=40)] = None,
) -> DataHealthPage:
    filters = []
    if severity:
        filters.append(DataHealthRule.severity == severity)
    if evaluation_status:
        filters.append(DataHealthEvaluation.status == evaluation_status)
    if entity_type:
        filters.append(DataHealthEvaluation.entity_type == entity_type)
    rows = session.execute(
        select(DataHealthEvaluation, DataHealthRule)
        .join(DataHealthRule)
        .where(*filters)
        .order_by(desc(DataHealthEvaluation.evaluated_at), DataHealthEvaluation.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    items = [
        {
            "id": evaluation.id,
            "rule_key": rule.rule_key,
            "rule_name": rule.name,
            "severity": rule.severity,
            "entity_type": evaluation.entity_type,
            "entity_id": evaluation.entity_id,
            "status": evaluation.status,
            "score": evaluation.score,
            "message": evaluation.message,
            "details": evaluation.details,
            "evaluated_at": evaluation.evaluated_at,
        }
        for evaluation, rule in rows
    ]
    total = (
        session.scalar(
            select(func.count(DataHealthEvaluation.id)).join(DataHealthRule).where(*filters)
        )
        or 0
    )
    return DataHealthPage(items=items, page=page, page_size=page_size, total=total)


@app.get("/api/v1/admin/data-health/facilities", response_model=FacilityHealthPage, tags=["admin"])
def facility_health(
    session: Annotated[Session, Depends(get_session)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
    minimum_score: Annotated[float | None, Query(ge=0, le=100)] = None,
    maximum_score: Annotated[float | None, Query(ge=0, le=100)] = None,
) -> FacilityHealthPage:
    filters = [EntityDataHealthScore.entity_type == "facility"]
    if minimum_score is not None:
        filters.append(EntityDataHealthScore.overall_score >= minimum_score)
    if maximum_score is not None:
        filters.append(EntityDataHealthScore.overall_score <= maximum_score)
    items = session.scalars(
        select(EntityDataHealthScore)
        .where(*filters)
        .order_by(EntityDataHealthScore.overall_score, EntityDataHealthScore.entity_id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return FacilityHealthPage(
        items=list(items),
        page=page,
        page_size=page_size,
        total=session.scalar(select(func.count(EntityDataHealthScore.id)).where(*filters)) or 0,
    )


@app.get("/api/v1/admin/data-health/sources", response_model=DataHealthPage, tags=["admin"])
def source_health(
    session: Annotated[Session, Depends(get_session)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
) -> DataHealthPage:
    return data_health(session, page, page_size, None, None, "source")


@app.get("/api/v1/admin/pipeline-status", response_model=PipelineStatusPage, tags=["admin"])
def pipeline_status(
    session: Annotated[Session, Depends(get_session)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
    current_status: Annotated[str | None, Query(alias="status", max_length=30)] = None,
) -> PipelineStatusPage:
    filters = [PipelineStatusSnapshot.current_status == current_status] if current_status else []
    items = session.scalars(
        select(PipelineStatusSnapshot)
        .where(*filters)
        .order_by(PipelineStatusSnapshot.importer_name, desc(PipelineStatusSnapshot.calculated_at))
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return PipelineStatusPage(
        items=list(items),
        page=page,
        page_size=page_size,
        total=session.scalar(select(func.count(PipelineStatusSnapshot.id)).where(*filters)) or 0,
    )


@app.get("/api/v1/admin/pricing/sources", response_model=PricingSourcePage, tags=["admin-pricing"])
def admin_pricing_sources(
    session: Annotated[Session, Depends(get_session)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
    facility_id: uuid.UUID | None = None,
    detected_format: Annotated[str | None, Query(max_length=30)] = None,
) -> PricingSourcePage:
    filters = []
    if facility_id:
        filters.append(FacilityPriceSource.facility_id == facility_id)
    if detected_format:
        filters.append(FacilityPriceSource.detected_format == detected_format)
    rows = session.execute(
        select(FacilityPriceSource, Facility, SourceFile)
        .select_from(FacilityPriceSource)
        .join(Facility, Facility.id == FacilityPriceSource.facility_id)
        .outerjoin(SourceFile, SourceFile.id == FacilityPriceSource.source_file_id)
        .where(*filters)
        .order_by(Facility.display_name, FacilityPriceSource.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    items = [
        {
            "id": source.id,
            "facility_id": facility.id,
            "facility_name": facility.display_name,
            "source_type": source.source_type,
            "source_page_url": source.source_page_url,
            "machine_readable_file_url": source.machine_readable_file_url,
            "cms_hpt_txt_url": source.cms_hpt_txt_url,
            "detected_format": source.detected_format,
            "detected_schema_version": source.detected_schema_version,
            "discovery_method": source.discovery_method,
            "last_seen_at": source.last_seen_at,
            "last_successful_download_at": source.last_successful_download_at,
            "source_file_id": source.source_file_id,
            "checksum_sha256": source_file.checksum_sha256 if source_file else None,
            "file_size": source_file.file_size if source_file else None,
        }
        for source, facility, source_file in rows
    ]
    total = session.scalar(select(func.count(FacilityPriceSource.id)).where(*filters)) or 0
    return PricingSourcePage(items=items, page=page, page_size=page_size, total=total)


def _admin_page(
    session: Session,
    model: Any,
    page: int,
    page_size: int,
    filters: list[ColumnElement[bool]] | None = None,
) -> PricingAdminPage:
    where = filters or []
    model_id = model.id
    rows = session.scalars(
        select(model)
        .where(*where)
        .order_by(desc(model_id))
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    items = []
    for row in rows:
        data = {
            column.name: getattr(row, column.key)
            for column in row.__table__.columns
            if column.name not in {"raw_payload", "source_payload", "bounded_sample"}
        }
        items.append({"id": row.id, "data": data})
    return PricingAdminPage(
        items=items,
        page=page,
        page_size=page_size,
        total=session.scalar(select(func.count(model_id)).where(*where)) or 0,
    )


@app.get(
    "/api/v1/admin/pricing/source-discovery-runs",
    response_model=PricingAdminPage,
    tags=["admin-pricing"],
)
def admin_discovery_runs(
    session: Annotated[Session, Depends(get_session)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
) -> PricingAdminPage:
    return _admin_page(session, PriceSourceDiscoveryRun, page, page_size)


@app.get(
    "/api/v1/admin/pricing/source-discovery-observations",
    response_model=PricingAdminPage,
    tags=["admin-pricing"],
)
def admin_discovery_observations(
    session: Annotated[Session, Depends(get_session)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
    facility_id: uuid.UUID | None = None,
) -> PricingAdminPage:
    filters = [PriceSourceDiscoveryObservation.facility_id == facility_id] if facility_id else []
    return _admin_page(session, PriceSourceDiscoveryObservation, page, page_size, filters)


@app.get("/api/v1/admin/pricing/import-runs", response_model=ImportRunPage, tags=["admin-pricing"])
def admin_pricing_import_runs(
    session: Annotated[Session, Depends(get_session)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
) -> ImportRunPage:
    return admin_import_runs(session, page, page_size, None, "started_at")


@app.get("/api/v1/admin/pricing/records", response_model=PriceRecordPage, tags=["admin-pricing"])
def admin_pricing_records(
    session: Annotated[Session, Depends(get_session)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
    facility_id: uuid.UUID | None = None,
    parser: Annotated[str | None, Query(max_length=100)] = None,
    setting: Annotated[str | None, Query(max_length=40)] = None,
) -> PriceRecordPage:
    filters = []
    if facility_id:
        filters.append(HospitalPriceRecord.facility_id == facility_id)
    if parser:
        filters.append(HospitalPriceRecord.parser_name == parser)
    if setting:
        filters.append(HospitalPriceRecord.setting == setting)
    items = session.scalars(
        select(HospitalPriceRecord)
        .where(*filters)
        .order_by(desc(HospitalPriceRecord.observed_at), HospitalPriceRecord.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return PriceRecordPage(
        items=list(items),
        page=page,
        page_size=page_size,
        total=session.scalar(select(func.count(HospitalPriceRecord.id)).where(*filters)) or 0,
    )


@app.get("/api/v1/admin/pricing/rates", response_model=PricingAdminPage, tags=["admin-pricing"])
def admin_pricing_rates(
    session: Annotated[Session, Depends(get_session)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
    payer_id: uuid.UUID | None = None,
) -> PricingAdminPage:
    return _admin_page(
        session,
        HospitalPriceRateDetail,
        page,
        page_size,
        [HospitalPriceRateDetail.payer_entity_id == payer_id] if payer_id else [],
    )


@app.get("/api/v1/admin/pricing/unmatched", response_model=PricingAdminPage, tags=["admin-pricing"])
def admin_pricing_unmatched(
    session: Annotated[Session, Depends(get_session)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
    review_status: Annotated[str | None, Query(alias="status", max_length=30)] = None,
) -> PricingAdminPage:
    return _admin_page(
        session,
        PricingUnmatchedRecord,
        page,
        page_size,
        [PricingUnmatchedRecord.review_status == review_status] if review_status else [],
    )


@app.get("/api/v1/admin/pricing/anomalies", response_model=PricingAdminPage, tags=["admin-pricing"])
def admin_pricing_anomalies(
    session: Annotated[Session, Depends(get_session)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
    severity: Annotated[str | None, Query(pattern="^(info|warning|error|critical)$")] = None,
    anomaly_status: Annotated[str | None, Query(alias="status", max_length=30)] = None,
) -> PricingAdminPage:
    filters = []
    if severity:
        filters.append(PricingAnomaly.severity == severity)
    if anomaly_status:
        filters.append(PricingAnomaly.status == anomaly_status)
    return _admin_page(session, PricingAnomaly, page, page_size, filters)


@app.get(
    "/api/v1/admin/pricing/procedure-candidates",
    response_model=PricingAdminPage,
    tags=["admin-pricing"],
)
def admin_pricing_candidates(
    session: Annotated[Session, Depends(get_session)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
    candidate_status: Annotated[str | None, Query(alias="status", max_length=30)] = None,
) -> PricingAdminPage:
    return _admin_page(
        session,
        PriceRecordProcedureCandidate,
        page,
        page_size,
        [PriceRecordProcedureCandidate.status == candidate_status] if candidate_status else [],
    )


@app.get("/api/v1/admin/pricing/payers", response_model=PricingAdminPage, tags=["admin-pricing"])
def admin_pricing_payers(
    session: Annotated[Session, Depends(get_session)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
) -> PricingAdminPage:
    return _admin_page(session, PayerEntity, page, page_size)


@app.get("/api/v1/admin/pricing/plans", response_model=PricingAdminPage, tags=["admin-pricing"])
def admin_pricing_plans(
    session: Annotated[Session, Depends(get_session)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
    payer_id: uuid.UUID | None = None,
) -> PricingAdminPage:
    return _admin_page(
        session,
        InsurancePlanEntity,
        page,
        page_size,
        [InsurancePlanEntity.payer_entity_id == payer_id] if payer_id else [],
    )


@app.get(
    "/api/v1/admin/pricing/facility-procedure-summaries",
    response_model=PricingAdminPage,
    tags=["admin-pricing"],
)
def admin_pricing_summaries(
    session: Annotated[Session, Depends(get_session)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
    publication_status: Annotated[str | None, Query(max_length=30)] = None,
) -> PricingAdminPage:
    return _admin_page(
        session,
        FacilityProcedurePriceSummary,
        page,
        page_size,
        [FacilityProcedurePriceSummary.publication_status == publication_status]
        if publication_status
        else [],
    )


def _public_price_page(
    session: Session, filters: list[ColumnElement[bool]], page: int, page_size: int
) -> PublicPriceSummaryPage:
    base = (
        select(
            FacilityProcedurePriceSummary,
            Facility,
            FacilityLocation,
            Procedure,
            PayerEntity,
            InsurancePlanEntity,
            SourceFile,
        )
        .join(Facility, Facility.id == FacilityProcedurePriceSummary.facility_id)
        .outerjoin(
            FacilityLocation,
            FacilityLocation.id == FacilityProcedurePriceSummary.facility_location_id,
        )
        .join(Procedure, Procedure.id == FacilityProcedurePriceSummary.procedure_id)
        .outerjoin(PayerEntity, PayerEntity.id == FacilityProcedurePriceSummary.payer_entity_id)
        .outerjoin(
            InsurancePlanEntity,
            InsurancePlanEntity.id == FacilityProcedurePriceSummary.insurance_plan_entity_id,
        )
        .join(SourceFile, SourceFile.id == FacilityProcedurePriceSummary.source_file_id)
        .where(
            FacilityProcedurePriceSummary.publication_status == "publishable",
            SourceFile.source_url.not_like("file://%"),
            *filters,
        )
    )
    rows = session.execute(
        base.order_by(
            Facility.display_name,
            FacilityProcedurePriceSummary.service_setting,
            FacilityProcedurePriceSummary.id,
        )
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    items = [
        {
            "id": item.id,
            "facility_id": facility.id,
            "facility_name": facility.display_name,
            "facility_location_id": item.facility_location_id,
            "location_name": location.location_name if location else None,
            "location_type": location.location_type if location else None,
            "address_line_1": location.address_line_1 if location else None,
            "city": location.city if location else None,
            "procedure_slug": procedure.slug,
            "procedure_name": procedure.consumer_name,
            "payer_slug": payer.slug if payer else None,
            "payer_name": payer.canonical_name if payer else None,
            "plan_name": plan.canonical_name if plan else None,
            "service_setting": item.service_setting,
            "cash_price_min": item.cash_price_min,
            "cash_price_max": item.cash_price_max,
            "negotiated_price_min": item.negotiated_price_min,
            "negotiated_price_max": item.negotiated_price_max,
            "record_count": item.record_count,
            "included_component_scope": item.included_component_scope,
            "source_url": source.source_url,
            "source_checksum_sha256": source.checksum_sha256,
            "last_updated": item.calculated_at,
        }
        for item, facility, location, procedure, payer, plan, source in rows
    ]
    total = session.scalar(select(func.count()).select_from(base.subquery())) or 0
    return PublicPriceSummaryPage(items=items, page=page, page_size=page_size, total=total)


@app.get(
    "/api/v1/procedures/{slug}/prices", response_model=PublicPriceSummaryPage, tags=["pricing"]
)
def procedure_prices(
    slug: str,
    session: Annotated[Session, Depends(get_session)],
    state_code: Annotated[str, Query(alias="state", min_length=2, max_length=2)] = "NH",
    city: Annotated[str | None, Query(max_length=100)] = None,
    payer: Annotated[str | None, Query(max_length=150)] = None,
    plan: Annotated[str | None, Query(max_length=500)] = None,
    setting: Annotated[str | None, Query(max_length=40)] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=50)] = 25,
) -> PublicPriceSummaryPage:
    procedure = session.scalar(
        select(Procedure).where(Procedure.slug == slug, Procedure.active.is_(True))
    )
    if procedure is None:
        raise HTTPException(status_code=404, detail="procedure not found")
    filters: list[ColumnElement[bool]] = [
        FacilityProcedurePriceSummary.procedure_id == procedure.id,
        FacilityLocation.state == state_code.upper(),
    ]
    if city:
        filters.append(FacilityLocation.city.ilike(city))
    if payer:
        filters.append(PayerEntity.slug == payer)
    if plan:
        filters.append(InsurancePlanEntity.normalized_name == plan.lower())
    if setting:
        filters.append(FacilityProcedurePriceSummary.service_setting == setting)
    return _public_price_page(session, filters, page, page_size)


@app.get(
    "/api/v1/procedures/{slug}/comparison",
    response_model=ProcedureComparisonResponse,
    tags=["pricing"],
)
def procedure_comparison(
    slug: str,
    session: Annotated[Session, Depends(get_session)],
    state_code: Annotated[str, Query(alias="state", min_length=2, max_length=2)] = "NH",
    city: Annotated[str | None, Query(max_length=100)] = None,
    postal_code: Annotated[str | None, Query(min_length=5, max_length=10)] = None,
    payer: Annotated[str | None, Query(max_length=150)] = None,
    plan: Annotated[uuid.UUID | None, Query()] = None,
    setting: Annotated[str | None, Query(max_length=40)] = None,
    origin_zip: Annotated[str | None, Query(min_length=5, max_length=10)] = None,
    origin_city: Annotated[str | None, Query(max_length=100)] = None,
    radius_miles: Annotated[float | None, Query(gt=0, le=500)] = None,
) -> ProcedureComparisonResponse:
    """Return one honest consumer comparison row per physical service location."""
    procedure = session.scalar(
        select(Procedure).where(Procedure.slug == slug, Procedure.active.is_(True))
    )
    if procedure is None:
        raise HTTPException(status_code=404, detail="procedure not found")

    facility_ids = active_consumer_facility_ids(session, state_code)
    location_filters: list[ColumnElement[bool]] = [
        FacilityLocation.facility_id.in_(facility_ids),
        FacilityLocation.state == state_code.upper(),
        FacilityLocation.active.is_(True),
    ]
    if city:
        location_filters.append(FacilityLocation.city.ilike(city))
    if postal_code:
        location_filters.append(FacilityLocation.postal_code == postal_code)
    locations = session.execute(
        select(Facility, FacilityLocation)
        .join(FacilityLocation, FacilityLocation.facility_id == Facility.id)
        .where(*location_filters)
        .order_by(Facility.display_name, FacilityLocation.city, FacilityLocation.id)
    ).all()

    price_filters: list[ColumnElement[bool]] = [
        FacilityProcedurePriceSummary.procedure_id == procedure.id,
        FacilityProcedurePriceSummary.publication_status == "publishable",
        FacilityProcedurePriceSummary.facility_id.in_(facility_ids),
        SourceFile.source_url.not_like("file://%"),
    ]
    if setting:
        price_filters.append(FacilityProcedurePriceSummary.service_setting == setting)
    price_rows = session.execute(
        select(FacilityProcedurePriceSummary, SourceFile, PayerEntity, InsurancePlanEntity)
        .join(SourceFile, SourceFile.id == FacilityProcedurePriceSummary.source_file_id)
        .outerjoin(PayerEntity, PayerEntity.id == FacilityProcedurePriceSummary.payer_entity_id)
        .outerjoin(
            InsurancePlanEntity,
            InsurancePlanEntity.id == FacilityProcedurePriceSummary.insurance_plan_entity_id,
        )
        .where(*price_filters)
    ).all()
    price_source_ids = {source.id for _summary, source, _payer, _plan in price_rows}
    import_dates = {
        source_file_id: imported_at
        for source_file_id, imported_at in session.execute(
            select(
                ImportRun.source_file_id,
                func.max(func.coalesce(ImportRun.finished_at, ImportRun.started_at)),
            )
            .where(ImportRun.source_file_id.in_(price_source_ids))
            .group_by(ImportRun.source_file_id)
        )
    }

    grouped: dict[
        tuple[uuid.UUID, uuid.UUID],
        list[
            tuple[
                FacilityProcedurePriceSummary,
                SourceFile,
                PayerEntity | None,
                InsurancePlanEntity | None,
            ]
        ],
    ] = {}
    for summary, source, payer_entity, plan_entity in price_rows:
        if summary.facility_location_id is not None:
            grouped.setdefault((summary.facility_id, summary.facility_location_id), []).append(
                (summary, source, payer_entity, plan_entity)
            )

    cash_observation_filters: list[ColumnElement[bool]] = [
        FacilityProcedurePriceObservation.procedure_id == procedure.id,
        FacilityProcedurePriceObservation.facility_id.in_(facility_ids),
        FacilityProcedurePriceObservation.price_type == "discounted_cash",
        FacilityProcedurePriceObservation.publication_status == "publishable",
        SourceFile.source_url.not_like("file://%"),
    ]
    if setting:
        cash_observation_filters.append(
            FacilityProcedurePriceObservation.service_setting == setting
        )
    cash_rows = session.execute(
        select(FacilityProcedurePriceObservation, HospitalPriceRecord)
        .join(
            HospitalPriceRecord,
            HospitalPriceRecord.id == FacilityProcedurePriceObservation.hospital_price_record_id,
        )
        .join(SourceFile, SourceFile.id == HospitalPriceRecord.source_file_id)
        .where(*cash_observation_filters)
    ).all()
    cash_by_location: dict[
        tuple[uuid.UUID, uuid.UUID],
        list[tuple[FacilityProcedurePriceObservation, HospitalPriceRecord]],
    ] = defaultdict(list)
    for observation, record in cash_rows:
        if observation.facility_location_id is not None:
            cash_by_location[(observation.facility_id, observation.facility_location_id)].append(
                (observation, record)
            )

    negotiated_count_filters: list[ColumnElement[bool]] = [
        FacilityProcedurePriceObservation.procedure_id == procedure.id,
        FacilityProcedurePriceObservation.facility_id.in_(facility_ids),
        FacilityProcedurePriceObservation.price_type == "payer_negotiated",
        FacilityProcedurePriceObservation.publication_status == "publishable",
        SourceFile.source_url.not_like("file://%"),
    ]
    if setting:
        negotiated_count_filters.append(
            FacilityProcedurePriceObservation.service_setting == setting
        )
    negotiated_counts = {
        (facility_id, location_id, payer_id, plan_id): int(count)
        for facility_id, location_id, payer_id, plan_id, count in session.execute(
            select(
                FacilityProcedurePriceObservation.facility_id,
                FacilityProcedurePriceObservation.facility_location_id,
                FacilityProcedurePriceObservation.payer_entity_id,
                FacilityProcedurePriceObservation.insurance_plan_entity_id,
                func.count(FacilityProcedurePriceObservation.id),
            )
            .join(
                HospitalPriceRecord,
                HospitalPriceRecord.id
                == FacilityProcedurePriceObservation.hospital_price_record_id,
            )
            .join(SourceFile, SourceFile.id == HospitalPriceRecord.source_file_id)
            .where(*negotiated_count_filters)
            .group_by(
                FacilityProcedurePriceObservation.facility_id,
                FacilityProcedurePriceObservation.facility_location_id,
                FacilityProcedurePriceObservation.payer_entity_id,
                FacilityProcedurePriceObservation.insurance_plan_entity_id,
            )
        )
    }

    rating_rows = session.execute(
        select(FacilityQualityMeasureObservation)
        .join(QualityMeasureDefinition)
        .where(
            FacilityQualityMeasureObservation.facility_id.in_(facility_ids),
            QualityMeasureDefinition.cms_measure_id == "OVERALL_RATING",
        )
        .order_by(desc(FacilityQualityMeasureObservation.reporting_period_end))
    ).scalars()
    ratings: dict[uuid.UUID, str | None] = {}
    for observation in rating_rows:
        ratings.setdefault(observation.facility_id, observation.score)

    items: list[dict[str, object]] = []
    priced_facilities: set[uuid.UUID] = set()
    location_coords: dict[uuid.UUID, tuple[float, float]] = {}
    for facility, location in locations:
        if location.latitude is not None and location.longitude is not None:
            location_coords[location.id] = (
                float(location.latitude),
                float(location.longitude),
            )
        all_summaries = grouped.get((facility.id, location.id), [])
        selected_summaries = [
            row
            for row in all_summaries
            if (not payer or (row[2] is not None and row[2].slug == payer))
            and (plan is None or (row[3] is not None and row[3].id == plan))
        ]
        summaries = selected_summaries if payer or plan else all_summaries
        if summaries:
            priced_facilities.add(facility.id)
        cash_details = cash_by_location.get((facility.id, location.id), [])
        cash_amounts = sorted({observation.amount for observation, _record in cash_details})
        cash_descriptions = {record.raw_description for _observation, record in cash_details}
        cash_settings = {observation.service_setting for observation, _record in cash_details}
        cash_components = {observation.included_component_scope for observation, _ in cash_details}
        # Group published cash by (setting, billing scope) so a facility fee is
        # never min/maxed with a professional component into a misleading range.
        cash_summary = summarize_cash_components(
            [
                (
                    observation.amount,
                    observation.service_setting,
                    observation.included_component_scope,
                )
                for observation, _record in cash_details
            ]
        )
        cash_values = [
            value
            for summary, _source, _payer, _plan in all_summaries
            for value in (summary.cash_price_min, summary.cash_price_max)
            if value is not None
        ]
        negotiated_values = [
            value
            for summary, _source, _payer, _plan in summaries
            for value in (summary.negotiated_price_min, summary.negotiated_price_max)
            if value is not None
        ]
        all_negotiated_values = [
            value
            for summary, _source, _payer, _plan in all_summaries
            for value in (summary.negotiated_price_min, summary.negotiated_price_max)
            if value is not None
        ]
        latest = max(
            (summary.calculated_at for summary, _source, _payer, _plan in summaries),
            default=None,
        )
        latest_source = max(
            summaries,
            key=lambda pair: pair[0].calculated_at,
            default=None,
        )
        payer_groups: dict[str, dict[str, Any]] = {}
        for summary, _source, payer_entity, plan_entity in all_summaries:
            if payer_entity is None or summary.negotiated_price_min is None:
                continue
            entry = payer_groups.setdefault(
                payer_entity.slug,
                {
                    "slug": payer_entity.slug,
                    "name": payer_entity.canonical_name,
                    "id": payer_entity.id,
                    "plan_ids": set(),
                },
            )
            if plan_entity is not None:
                plan_ids = entry["plan_ids"]
                assert isinstance(plan_ids, set)
                plan_ids.add(plan_entity.id)
        published_payers = [
            {
                "slug": entry["slug"],
                "name": entry["name"],
                "rate_count": sum(
                    count
                    for (row_facility, row_location, row_payer, _row_plan), count in (
                        negotiated_counts.items()
                    )
                    if row_facility == facility.id
                    and row_location == location.id
                    and row_payer == entry["id"]
                ),
                "plan_count": len(entry["plan_ids"]),
            }
            for entry in sorted(payer_groups.values(), key=lambda value: str(value["name"]))
        ]
        plan_ids = {
            plan_entity.id
            for summary, _source, _payer_entity, plan_entity in all_summaries
            if plan_entity is not None and summary.negotiated_price_min is not None
        }
        selected_payer = next(
            (payer_entity for _s, _f, payer_entity, _p in summaries if payer_entity), None
        )
        selected_plan = next(
            (plan_entity for _s, _f, _p, plan_entity in summaries if plan_entity), None
        )
        requested_payer_id = next(
            (
                payer_entity.id
                for _summary, _source, payer_entity, _plan_entity in all_summaries
                if payer_entity is not None and payer_entity.slug == payer
            ),
            None,
        )
        matching_rate_count = sum(
            count
            for (row_facility, row_location, row_payer, row_plan), count in (
                negotiated_counts.items()
            )
            if row_facility == facility.id
            and row_location == location.id
            and (not payer or row_payer == requested_payer_id)
            and (plan is None or row_plan == plan)
        )
        cash_explanation = None
        cash_reason_codes: list[str] = []
        if len(cash_amounts) > 1:
            qualifiers: list[str] = []
            if any(
                _consumer_service_variant(description) == "bilateral"
                for description in cash_descriptions
            ):
                qualifiers.append("unilateral and bilateral source descriptions")
                cash_reason_codes.append("unilateral_bilateral")
            if len(cash_settings) > 1:
                qualifiers.append("different service settings")
                cash_reason_codes.append("service_settings")
            if len(cash_components) > 1:
                qualifiers.append("different billing components")
                cash_reason_codes.append("billing_components")
            if not cash_reason_codes:
                cash_reason_codes.append("source_records")
            reason = ", ".join(qualifiers) if qualifiers else "different source records"
            cash_explanation = (
                f"{len(cash_amounts)} hospital-published cash prices were found for {reason}."
            )
        negotiated_min = min(negotiated_values) if negotiated_values else None
        negotiated_max = max(negotiated_values) if negotiated_values else None
        extreme_spread = bool(
            negotiated_min is not None
            and negotiated_max is not None
            and negotiated_min > 0
            and negotiated_max / negotiated_min >= 10
        )
        completeness_notes = ["Source and physical location verified", "Procedure mapping reviewed"]
        if cash_values:
            completeness_notes.append("Cash price semantic type known")
        if all_summaries and all(
            summary.service_setting != "unknown" for summary, *_rest in all_summaries
        ):
            completeness_notes.append("Service setting known")
        if payer and negotiated_values:
            completeness_notes.append("Selected payer identity known")
        if plan and negotiated_values:
            completeness_notes.append("Selected plan identity known")
        if not cash_values:
            completeness_notes.append("Cash price not published")
        if payer and not negotiated_values:
            completeness_notes.append("No matching published rate for selected insurance")
        completeness = (
            "high_data_completeness"
            if cash_values and (not payer or negotiated_values)
            else "some_details_unavailable"
            if cash_values or negotiated_values
            else "limited_pricing_detail"
        )
        items.append(
            {
                "facility_id": facility.id,
                "facility_name": facility.display_name,
                "facility_location_id": location.id,
                "location_name": location.location_name,
                "location_type": location.location_type,
                "address_line_1": location.address_line_1,
                "city": location.city,
                "state": location.state,
                "postal_code": location.postal_code,
                "facility_type": facility.facility_type,
                "cms_overall_rating": ratings.get(facility.id),
                "price_available": bool(all_summaries),
                "cash_price_min": cash_summary["cash_price_min"],
                "cash_price_max": cash_summary["cash_price_max"],
                "primary_service_setting": cash_summary["primary_service_setting"],
                "primary_billing_scope": cash_summary["primary_billing_scope"],
                "comparability_status": cash_summary["comparability_status"],
                "comparability_reason": cash_summary["comparability_reason"],
                "additional_published_prices": cash_summary["additional_published_prices"],
                "negotiated_price_min": negotiated_min,
                "negotiated_price_max": negotiated_max,
                "cash_price_value_count": len(cash_amounts),
                "cash_price_record_count": len(cash_details),
                "cash_price_explanation": cash_explanation,
                "cash_price_reason_codes": cash_reason_codes,
                "matching_negotiated_rate_count": matching_rate_count,
                "distinct_payer_count": len(payer_groups),
                "distinct_plan_count": len(plan_ids),
                "published_payers": published_payers,
                "selected_payer_name": selected_payer.canonical_name if selected_payer else None,
                "selected_plan_name": selected_plan.canonical_name if selected_plan else None,
                "all_published_negotiated_min": (
                    min(all_negotiated_values) if all_negotiated_values else None
                ),
                "all_published_negotiated_max": (
                    max(all_negotiated_values) if all_negotiated_values else None
                ),
                "extreme_rate_spread": extreme_spread,
                "data_completeness": completeness,
                "completeness_notes": completeness_notes,
                "service_settings": sorted(
                    {summary.service_setting for summary, _source, _payer, _plan in all_summaries}
                ),
                "summary_count": len(summaries),
                "source_count": len({source.id for _summary, source, _payer, _plan in summaries}),
                "latest_updated": latest,
                "source_file_date": latest_source[1].source_published_at if latest_source else None,
                "source_file_last_modified": (
                    latest_source[1].last_modified if latest_source else None
                ),
                "downloaded_at": latest_source[1].downloaded_at if latest_source else None,
                "imported_at": (import_dates.get(latest_source[1].id) if latest_source else None),
                "carevero_refresh_date": latest,
                "source_url": latest_source[1].source_url if latest_source else None,
            }
        )
    origin = resolve_origin(postal_code=origin_zip, city=origin_city, state=state_code.upper())
    items = annotate_comparison(
        items, coords=location_coords, origin=origin, radius_miles=radius_miles
    )
    # Attach verified imagery per (facility, service location) in one batched
    # lookup (no per-card query), with exact-location-then-facility precedence.
    media = resolve_facility_media(
        session,
        [cast("uuid.UUID", item["facility_id"]) for item in items],
        api_settings,
    )
    for item in items:
        item.update(
            media_fields(
                pick_media(
                    media,
                    cast("uuid.UUID", item["facility_id"]),
                    cast("uuid.UUID | None", item["facility_location_id"]),
                )
            )
        )
    return ProcedureComparisonResponse(
        procedure_slug=procedure.slug,
        procedure_name=procedure.consumer_name,
        state=state_code.upper(),
        active_facilities=len(facility_ids),
        facilities_with_prices=len(priced_facilities),
        service_locations=len(items),
        origin_resolved=origin is not None,
        items=items,
    )


def _consumer_service_variant(description: str) -> str:
    normalized = f" {description.upper()} "
    if any(marker in normalized for marker in (" BILATERAL ", " BI ", " BOTH ")):
        return "bilateral"
    if any(marker in normalized for marker in (" LEFT ", " LT ")):
        return "left"
    if any(marker in normalized for marker in (" RIGHT ", " RT ")):
        return "right"
    return "not_specified_by_source"


@app.get(
    "/api/v1/procedures/{slug}/locations/{location_id}/price-details",
    response_model=ConsumerPriceDetailResponse,
    tags=["pricing"],
)
def consumer_price_details(
    slug: str,
    location_id: uuid.UUID,
    session: Annotated[Session, Depends(get_session)],
    payer: Annotated[str | None, Query(max_length=150)] = None,
    plan: Annotated[uuid.UUID | None, Query()] = None,
) -> ConsumerPriceDetailResponse:
    """Return bounded, consumer-readable source rates for one procedure and location."""
    procedure = session.scalar(
        select(Procedure).where(Procedure.slug == slug, Procedure.active.is_(True))
    )
    if procedure is None:
        raise HTTPException(status_code=404, detail="procedure not found")
    facility_location = session.execute(
        select(FacilityLocation, Facility)
        .join(Facility, Facility.id == FacilityLocation.facility_id)
        .where(FacilityLocation.id == location_id, FacilityLocation.active.is_(True))
    ).one_or_none()
    if facility_location is None:
        raise HTTPException(status_code=404, detail="service location not found")
    location, facility = facility_location

    detail_filters: list[ColumnElement[bool]] = [
        FacilityProcedurePriceObservation.procedure_id == procedure.id,
        FacilityProcedurePriceObservation.facility_location_id == location_id,
        FacilityProcedurePriceObservation.publication_status == "publishable",
        SourceFile.source_url.not_like("file://%"),
    ]
    if payer:
        detail_filters.append(
            (FacilityProcedurePriceObservation.price_type != "payer_negotiated")
            | (PayerEntity.slug == payer)
        )
    if plan:
        detail_filters.append(
            (FacilityProcedurePriceObservation.price_type != "payer_negotiated")
            | (InsurancePlanEntity.id == plan)
        )
    rows = session.execute(
        select(
            FacilityProcedurePriceObservation,
            HospitalPriceRecord,
            SourceFile,
            PayerEntity,
            InsurancePlanEntity,
            HospitalPriceRateDetail,
            ImportRun,
        )
        .join(
            HospitalPriceRecord,
            HospitalPriceRecord.id == FacilityProcedurePriceObservation.hospital_price_record_id,
        )
        .join(SourceFile, SourceFile.id == HospitalPriceRecord.source_file_id)
        .join(ImportRun, ImportRun.id == HospitalPriceRecord.import_run_id)
        .outerjoin(
            PayerEntity,
            PayerEntity.id == FacilityProcedurePriceObservation.payer_entity_id,
        )
        .outerjoin(
            InsurancePlanEntity,
            InsurancePlanEntity.id == FacilityProcedurePriceObservation.insurance_plan_entity_id,
        )
        .outerjoin(
            HospitalPriceRateDetail,
            HospitalPriceRateDetail.id
            == FacilityProcedurePriceObservation.hospital_price_rate_detail_id,
        )
        .where(*detail_filters)
        .order_by(
            FacilityProcedurePriceObservation.price_type,
            PayerEntity.canonical_name,
            InsurancePlanEntity.canonical_name,
            FacilityProcedurePriceObservation.amount,
        )
        .limit(2001)
    ).all()
    records_truncated = len(rows) > 2000
    rows = rows[:2000]
    record_ids = {record.id for _observation, record, *_rest in rows}
    code_rows: list[PriceServiceCode] = (
        list(
            session.execute(
                select(PriceServiceCode).where(
                    PriceServiceCode.hospital_price_record_id.in_(record_ids)
                )
            ).scalars()
        )
        if record_ids
        else []
    )
    codes_by_record: dict[uuid.UUID, list[dict[str, str | None]]] = defaultdict(list)
    for code in code_rows:
        codes_by_record[code.hospital_price_record_id].append(
            {
                "system": code.code_system,
                "code": code.code,
                "modifier": code.modifier,
            }
        )
    semantic_types = {
        "discounted_cash": "cash_self_pay",
        "payer_negotiated": "negotiated_payer_plan",
        "gross": "gross_charge",
        "deidentified_min": "minimum_negotiated_rate",
        "deidentified_max": "maximum_negotiated_rate",
    }
    details = []
    for observation, record, source, payer_entity, plan_entity, rate, import_run in rows:
        semantic_type = semantic_types.get(observation.price_type, "unknown_unsafe_to_classify")
        if observation.price_type == "payer_negotiated" and plan_entity is None:
            semantic_type = "negotiated_payer_only"
        details.append(
            {
                "semantic_type": semantic_type,
                "amount": observation.amount,
                "payer_slug": payer_entity.slug if payer_entity else None,
                "payer_name": payer_entity.canonical_name if payer_entity else None,
                "plan_id": plan_entity.id if plan_entity else None,
                "plan_name": plan_entity.canonical_name if plan_entity else None,
                "negotiated_rate_type": rate.negotiated_rate_type if rate else None,
                "original_description": record.raw_description,
                "billing_codes": codes_by_record.get(record.id, []),
                "service_variant": _consumer_service_variant(record.raw_description),
                "service_setting": observation.service_setting,
                "component_scope": observation.included_component_scope,
                "source_row_identity": record.source_record_identifier,
                "source_url": source.source_url,
                "source_checksum_sha256": source.checksum_sha256,
                "source_file_date": source.source_published_at,
                "source_file_last_modified": source.last_modified,
                "downloaded_at": source.downloaded_at,
                "imported_at": import_run.finished_at or import_run.started_at,
                "carevero_refresh_date": observation.created_at,
            }
        )
    return ConsumerPriceDetailResponse(
        procedure_slug=procedure.slug,
        procedure_name=procedure.consumer_name,
        facility_id=facility.id,
        facility_name=facility.display_name,
        facility_location_id=location.id,
        location_name=location.location_name,
        records=details,
        records_truncated=records_truncated,
    )


@app.get(
    "/api/v1/facilities/{facility_id}/procedure-overview",
    response_model=FacilityProcedureOverviewResponse,
    tags=["pricing"],
)
def facility_procedure_overview(
    facility_id: uuid.UUID,
    session: Annotated[Session, Depends(get_session)],
) -> FacilityProcedureOverviewResponse:
    facility = session.scalar(
        select(Facility).where(Facility.id == facility_id, Facility.active.is_(True))
    )
    if facility is None:
        raise HTTPException(status_code=404, detail="facility not found")
    rows = session.execute(
        select(FacilityProcedurePriceSummary, Procedure, SourceFile, FacilityLocation)
        .join(Procedure, Procedure.id == FacilityProcedurePriceSummary.procedure_id)
        .join(SourceFile, SourceFile.id == FacilityProcedurePriceSummary.source_file_id)
        .join(
            FacilityLocation,
            FacilityLocation.id == FacilityProcedurePriceSummary.facility_location_id,
        )
        .where(
            FacilityProcedurePriceSummary.facility_id == facility_id,
            FacilityProcedurePriceSummary.publication_status == "publishable",
            SourceFile.source_url.not_like("file://%"),
            FacilityLocation.active.is_(True),
        )
    ).all()
    grouped: dict[
        tuple[uuid.UUID, uuid.UUID],
        list[tuple[FacilityProcedurePriceSummary, Procedure, SourceFile, FacilityLocation]],
    ] = {}
    for summary, procedure, source, location in rows:
        grouped.setdefault((procedure.id, location.id), []).append(
            (summary, procedure, source, location)
        )
    items: list[dict[str, object]] = []
    for summaries in grouped.values():
        procedure = summaries[0][1]
        location = summaries[0][3]
        cash = [
            value
            for summary, *_ in summaries
            for value in (summary.cash_price_min, summary.cash_price_max)
            if value is not None
        ]
        negotiated = [
            value
            for summary, *_ in summaries
            for value in (summary.negotiated_price_min, summary.negotiated_price_max)
            if value is not None
        ]
        latest = max(summaries, key=lambda row: row[0].calculated_at)
        items.append(
            {
                "procedure_slug": procedure.slug,
                "procedure_name": procedure.consumer_name,
                "facility_location_id": location.id,
                "location_name": location.location_name,
                "city": location.city,
                "service_settings": sorted({row[0].service_setting for row in summaries}),
                "cash_price_min": min(cash) if cash else None,
                "cash_price_max": max(cash) if cash else None,
                "negotiated_price_min": min(negotiated) if negotiated else None,
                "negotiated_price_max": max(negotiated) if negotiated else None,
                "summary_count": len(summaries),
                "latest_updated": latest[0].calculated_at,
                "source_url": latest[2].source_url,
            }
        )
    items.sort(key=lambda item: (str(item["procedure_name"]), str(item["city"])))
    return FacilityProcedureOverviewResponse(
        facility_id=facility_id,
        procedure_count=len({item["procedure_slug"] for item in items}),
        items=items,
    )


@app.get(
    "/api/v1/facilities/{facility_id}/prices",
    response_model=PublicPriceSummaryPage,
    tags=["pricing"],
)
def facility_prices(
    facility_id: uuid.UUID,
    session: Annotated[Session, Depends(get_session)],
    procedure: Annotated[str | None, Query(max_length=150)] = None,
    payer: Annotated[str | None, Query(max_length=150)] = None,
    setting: Annotated[str | None, Query(max_length=40)] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=50)] = 25,
) -> PublicPriceSummaryPage:
    filters: list[ColumnElement[bool]] = [FacilityProcedurePriceSummary.facility_id == facility_id]
    if procedure:
        filters.append(Procedure.slug == procedure)
    if payer:
        filters.append(PayerEntity.slug == payer)
    if setting:
        filters.append(FacilityProcedurePriceSummary.service_setting == setting)
    return _public_price_page(session, filters, page, page_size)


@app.get("/api/v1/pricing/payers", response_model=list[dict[str, object]], tags=["pricing"])
def public_pricing_payers(
    session: Annotated[Session, Depends(get_session)],
) -> list[dict[str, object]]:
    rows = session.execute(
        select(PayerEntity, func.count(FacilityProcedurePriceSummary.id))
        .join(
            FacilityProcedurePriceSummary,
            FacilityProcedurePriceSummary.payer_entity_id == PayerEntity.id,
        )
        .where(FacilityProcedurePriceSummary.publication_status == "publishable")
        .group_by(PayerEntity.id)
        .order_by(PayerEntity.canonical_name)
    ).all()
    return [
        {"slug": payer.slug, "name": payer.canonical_name, "summary_count": count}
        for payer, count in rows
    ]


@app.get("/api/v1/pricing/plans", response_model=list[dict[str, object]], tags=["pricing"])
def public_pricing_plans(
    session: Annotated[Session, Depends(get_session)],
    payer: Annotated[str | None, Query(max_length=150)] = None,
) -> list[dict[str, object]]:
    query = (
        select(InsurancePlanEntity, PayerEntity)
        .join(PayerEntity)
        .join(
            FacilityProcedurePriceSummary,
            FacilityProcedurePriceSummary.insurance_plan_entity_id == InsurancePlanEntity.id,
        )
        .where(FacilityProcedurePriceSummary.publication_status == "publishable")
    )
    if payer:
        query = query.where(PayerEntity.slug == payer)
    return [
        {"id": plan.id, "name": plan.canonical_name, "payer_slug": payer_entity.slug}
        for plan, payer_entity in session.execute(
            query.distinct().order_by(InsurancePlanEntity.canonical_name)
        ).all()
    ]


@app.get("/api/v1/pricing/freshness", response_model=FreshnessResponse, tags=["pricing"])
def pricing_freshness(
    session: Annotated[Session, Depends(get_session)],
) -> FreshnessResponse:
    from datetime import UTC
    from datetime import datetime as dt

    from collectors.hospital_prices.projections import freshness_score as calc_freshness

    rows = session.execute(
        select(Facility, FacilityPriceSource)
        .join(FacilityPriceSource, FacilityPriceSource.facility_id == Facility.id)
        .where(FacilityPriceSource.active.is_(True))
        .order_by(Facility.display_name)
    ).all()

    items = []
    for facility, source in rows:
        last_dl = source.last_successful_download_at
        if last_dl and last_dl.tzinfo is None:
            last_dl = last_dl.replace(tzinfo=UTC)
        days = (dt.now(UTC) - last_dl).days if last_dl else None
        score = calc_freshness(last_dl)
        items.append(
            {
                "facility_id": facility.id,
                "facility_name": facility.display_name,
                "last_download_at": last_dl,
                "freshness_score": score,
                "days_since_download": days,
            }
        )
    avg = round(sum(i["freshness_score"] for i in items) / len(items), 1) if items else 0
    return FreshnessResponse(items=items, average_freshness=avg)


@app.get("/api/v1/pricing/scorecard", response_model=StatewideScorecard, tags=["pricing"])
def pricing_scorecard(
    session: Annotated[Session, Depends(get_session)],
) -> StatewideScorecard:
    from scripts.statewide_scorecard import calculate_scorecard

    return StatewideScorecard(**calculate_scorecard(session))


@app.get("/api/v1/pricing/facility-scores", response_model=FacilityScorePage, tags=["pricing"])
def facility_scores(
    session: Annotated[Session, Depends(get_session)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
    sort: Annotated[str, Query(pattern="^(overall_score|facility_name)$")] = "overall_score",
    min_score: Annotated[float | None, Query(ge=0, le=100)] = None,
) -> FacilityScorePage:
    rows = session.execute(
        select(PricingHealthScore, Facility, FacilityLocation)
        .join(Facility, Facility.id == PricingHealthScore.facility_id)
        .outerjoin(FacilityLocation, FacilityLocation.facility_id == Facility.id)
        .where(*([PricingHealthScore.overall_score >= min_score] if min_score is not None else []))
        .order_by(
            PricingHealthScore.overall_score if sort == "overall_score" else Facility.display_name,
            PricingHealthScore.facility_id,
        )
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    items = [
        {
            "facility_id": score.facility_id,
            "facility_name": facility.display_name,
            "city": location.city if location else None,
            "overall_score": float(score.overall_score),
            "source_discovery_score": float(score.source_discovery_score),
            "download_score": float(score.download_score),
            "parse_score": float(score.parse_score),
            "mapping_score": float(score.mapping_score),
            "payer_normalization_score": float(score.payer_normalization_score),
            "anomaly_score": float(score.anomaly_score),
            "freshness_score": float(score.freshness_score),
            "price_coverage_score": float(score.price_coverage_score),
            "calculated_at": score.calculated_at,
        }
        for score, facility, location in rows
    ]
    total = (
        session.scalar(
            select(func.count(PricingHealthScore.id)).where(
                *([PricingHealthScore.overall_score >= min_score] if min_score is not None else [])
            )
        )
        or 0
    )
    return FacilityScorePage(items=items, page=page, page_size=page_size, total=total)


@app.get(
    "/api/v1/facilities/{facility_id}/pricing-health",
    response_model=PricingHealthResponse,
    tags=["pricing"],
)
def facility_pricing_health(
    facility_id: uuid.UUID,
    session: Annotated[Session, Depends(get_session)],
) -> PricingHealthResponse:
    score = session.scalar(
        select(PricingHealthScore).where(PricingHealthScore.facility_id == facility_id)
    )
    if score is None:
        raise HTTPException(status_code=404, detail="pricing health not available")
    return PricingHealthResponse(
        facility_id=score.facility_id,
        overall_score=float(score.overall_score),
        source_discovery_score=float(score.source_discovery_score),
        download_score=float(score.download_score),
        parse_score=float(score.parse_score),
        mapping_score=float(score.mapping_score),
        payer_normalization_score=float(score.payer_normalization_score),
        anomaly_score=float(score.anomaly_score),
        freshness_score=float(score.freshness_score),
        price_coverage_score=float(score.price_coverage_score),
        details=score.details,
        calculated_at=score.calculated_at,
    )


@app.get("/api/v1/pricing/coverage", response_model=PricingCoverageResponse, tags=["pricing"])
def pricing_coverage(session: Annotated[Session, Depends(get_session)]) -> PricingCoverageResponse:
    public_summary_source = SourceFile.source_url.not_like("file://%")
    return PricingCoverageResponse(
        nh_facilities=len(active_consumer_facility_ids(session, "NH")),
        facilities_with_sources=session.scalar(
            select(func.count(func.distinct(FacilityPriceSource.facility_id)))
        )
        or 0,
        facilities_with_downloads=session.scalar(
            select(func.count(func.distinct(FacilityPriceSource.facility_id))).where(
                FacilityPriceSource.source_file_id.is_not(None)
            )
        )
        or 0,
        # Count facilities that have at least one parsed record with an
        # EXISTS probe per facility (indexed on facility_id) instead of a
        # DISTINCT scan over the multi-million-row records table, which grew
        # too slow after statewide recovery and stalled the homepage.
        facilities_with_parsed_records=session.scalar(
            select(func.count(Facility.id)).where(
                exists(
                    select(HospitalPriceRecord.id).where(
                        HospitalPriceRecord.facility_id == Facility.id
                    )
                )
            )
        )
        or 0,
        facilities_with_publishable_prices=session.scalar(
            select(func.count(func.distinct(FacilityProcedurePriceSummary.facility_id)))
            .join(SourceFile, SourceFile.id == FacilityProcedurePriceSummary.source_file_id)
            .where(
                FacilityProcedurePriceSummary.publication_status == "publishable",
                public_summary_source,
            )
        )
        or 0,
        publishable_procedures=session.scalar(
            select(func.count(func.distinct(FacilityProcedurePriceSummary.procedure_id)))
            .join(SourceFile, SourceFile.id == FacilityProcedurePriceSummary.source_file_id)
            .where(
                FacilityProcedurePriceSummary.publication_status == "publishable",
                public_summary_source,
            )
        )
        or 0,
        last_updated=session.scalar(
            select(func.max(FacilityProcedurePriceSummary.calculated_at))
            .join(SourceFile, SourceFile.id == FacilityProcedurePriceSummary.source_file_id)
            .where(public_summary_source)
        ),
    )
