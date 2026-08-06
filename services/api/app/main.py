import time
import uuid
from collections.abc import Awaitable, Callable
from typing import Annotated

import structlog
from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response, status
from sqlalchemy import func, select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, selectinload
from sqlalchemy.sql.elements import ColumnElement

from packages.database import Facility, FacilityLocation, get_session
from services.api.app.logging import configure_logging
from services.api.app.schemas import FacilityPage, FacilityResponse, StatusResponse
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
