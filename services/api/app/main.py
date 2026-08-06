import time
import uuid
from collections.abc import Awaitable, Callable
from typing import Annotated

import structlog
from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response, status
from sqlalchemy import desc, func, select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, selectinload
from sqlalchemy.sql.elements import ColumnElement

from packages.database import (
    Facility,
    FacilityLocation,
    FacilityQualityMeasureObservation,
    FacilitySourceObservation,
    ImportRun,
    QualityMeasureDefinition,
    SourceFile,
    UnmatchedSourceRecord,
    get_session,
)
from services.api.app.logging import configure_logging
from services.api.app.schemas import (
    AdminDashboardResponse,
    AdminFacilityDetailResponse,
    AdminFacilityPage,
    FacilityPage,
    FacilityQualityPage,
    FacilityResponse,
    ImportRunPage,
    QualityMeasurePage,
    SourceFilePage,
    StatusResponse,
    UnmatchedRecordPage,
)
from services.api.app.settings import api_settings

configure_logging(api_settings.log_level)
logger = structlog.get_logger()
app = FastAPI(title=api_settings.api_title, version=api_settings.api_version)


@app.middleware("http")
async def request_logging(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    started = time.perf_counter()
    request_id = request.headers.get("x-request-id", str(uuid.uuid4()))
    try:
        response = await call_next(request)
    except Exception:
        logger.exception(
            "request_failed", method=request.method, path=request.url.path, request_id=request_id
        )
        raise
    response.headers["x-request-id"] = request_id
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
    query = select(Facility).options(selectinload(Facility.locations))
    count_query = select(func.count(Facility.id))
    if state_code:
        normalized_state = state_code.upper()
        query = query.join(FacilityLocation)
        count_query = count_query.join(FacilityLocation)
        filters.append(FacilityLocation.state == normalized_state)
    items = session.scalars(
        query.where(*filters)
        .order_by(Facility.display_name, Facility.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    total = session.scalar(count_query.where(*filters)) or 0
    return FacilityPage(items=list(items), page=page, page_size=page_size, total=total)


@app.get("/api/v1/facilities/{facility_id}", response_model=FacilityResponse, tags=["facilities"])
def get_facility(
    facility_id: uuid.UUID, session: Annotated[Session, Depends(get_session)]
) -> Facility:
    facility = session.scalar(
        select(Facility)
        .options(selectinload(Facility.locations))
        .where(Facility.id == facility_id, Facility.active.is_(True))
    )
    if facility is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="facility not found")
    return facility


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
            select(func.count(Facility.id))
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
    filters = [FacilityLocation.state == state_code.upper()] if state_code else []
    sort_column = {
        "display_name": Facility.display_name,
        "updated_at": Facility.updated_at,
        "cms_certification_number": Facility.cms_certification_number,
    }[sort]
    rows = session.execute(
        select(Facility, FacilityLocation, SourceFile, quality_count)
        .outerjoin(FacilityLocation, FacilityLocation.facility_id == Facility.id)
        .join(SourceFile, SourceFile.id == Facility.source_file_id)
        .where(*filters)
        .order_by(sort_column, Facility.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    count_query = select(func.count(Facility.id)).outerjoin(FacilityLocation)
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
