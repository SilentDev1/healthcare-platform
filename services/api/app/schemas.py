import uuid
from datetime import datetime
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
