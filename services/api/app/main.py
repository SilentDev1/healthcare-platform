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
    DataHealthEvaluation,
    DataHealthRule,
    EntityDataHealthScore,
    Facility,
    FacilityIdentityCandidate,
    FacilityLocation,
    FacilityQualityMeasureObservation,
    FacilitySourceObservation,
    ImportRun,
    PipelineStatusSnapshot,
    Procedure,
    ProcedureAlias,
    ProcedureCategory,
    QualityMeasureDefinition,
    SourceFile,
    UnmatchedSourceRecord,
    get_session,
)
from packages.search import search
from services.api.app.logging import configure_logging
from services.api.app.schemas import (
    AdminDashboardResponse,
    AdminFacilityDetailResponse,
    AdminFacilityPage,
    DataHealthPage,
    FacilityHealthPage,
    FacilityPage,
    FacilityQualityPage,
    FacilityResponse,
    IdentityCandidatePage,
    ImportRunPage,
    PipelineStatusPage,
    ProcedureCategoryResponse,
    ProcedurePage,
    ProcedureResponse,
    QualityMeasurePage,
    SearchPage,
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
