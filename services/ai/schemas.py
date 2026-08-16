from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

Locale = Literal["en", "es", "vi", "zh-TW", "zh-CN"]


class SortOption(StrEnum):
    RELEVANCE = "relevance"
    DISTANCE = "distance"
    CASH_PRICE = "cash_price"


class CareSearchIntent(BaseModel):
    """Validated model/tool boundary; never interpolate these values into SQL."""

    model_config = ConfigDict(extra="forbid")
    query_text: str = Field(min_length=2, max_length=500)
    procedure_candidate_id: UUID | None = None
    procedure_slug: str | None = Field(default=None, pattern=r"^[a-z0-9-]+$")
    procedure_name: str | None = None
    procedure_confidence: float = Field(default=0, ge=0, le=1)
    procedure_clarification_needed: bool = False
    clarification_question: str | None = Field(default=None, max_length=300)
    location_text: str | None = Field(default=None, max_length=120)
    zip: str | None = Field(default=None, pattern=r"^\d{5}(?:-\d{4})?$")
    city: str | None = Field(default=None, max_length=100)
    state: str | None = Field(default=None, pattern=r"^[A-Z]{2}$")
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    radius_miles: float | None = Field(default=None, gt=0, le=500)
    payer_text: str | None = Field(default=None, max_length=150)
    payer_id: UUID | None = None
    payer_slug: str | None = Field(default=None, pattern=r"^[a-z0-9-]+$")
    payer_name: str | None = None
    plan_text: str | None = Field(default=None, max_length=500)
    plan_id: UUID | None = None
    service_setting: str | None = Field(default=None, max_length=40)
    cash_only: bool = False
    insurance_price_only: bool = False
    sort: SortOption = SortOption.RELEVANCE
    locale: Locale = "en"
    follow_up_context: str | None = Field(default=None, max_length=100)


class SourceContext(BaseModel):
    model_config = ConfigDict(extra="forbid")
    fact_type: Literal["hospital_mrf", "cms_care_compare", "carevero_calculation"]
    label: str
    source_url: str | None = None
    last_checked: datetime | None = None


class AIFacilityFact(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: UUID
    name: str
    city: str
    state: str
    distance_miles: float | None = None
    cms_rating: str | None = None
    comparable_cash_price: Decimal | None = None
    selected_insurance_price_min: Decimal | None = None
    selected_insurance_price_max: Decimal | None = None
    selected_payer_name: str | None = None
    selected_plan_name: str | None = None
    published_payer_rate_count: int = 0
    billing_scope: str | None = None
    setting: str | None = None
    comparability: Literal[
        "directly_comparable", "partially_comparable", "not_comparable", "unknown"
    ] = "unknown"
    savings_difference: Decimal | None = None
    savings_basis: str | None = None
    service_availability_state: Literal["published_price_found", "unknown"] = "unknown"
    additional_published_prices: list[dict[str, object]] = Field(default_factory=list)
    sources: list[SourceContext] = Field(default_factory=list)


class CareveroAIContext(BaseModel):
    model_config = ConfigDict(extra="forbid")
    procedure_slug: str
    procedure_name: str
    search_origin: str | None = None
    radius_miles: float | None = None
    payer_name: str | None = None
    plan_name: str | None = None
    facilities: list[AIFacilityFact] = Field(max_length=25)
    limitations: list[str] = Field(default_factory=list, max_length=10)


class AIRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    message: str = Field(min_length=2, max_length=500)
    locale: Locale = "en"
    current_context: CareveroAIContext | None = None
    session_id: str | None = Field(default=None, min_length=8, max_length=100)

    @field_validator("message")
    @classmethod
    def reject_control_characters(cls, value: str) -> str:
        if any(ord(char) < 32 and char not in "\n\t" for char in value):
            raise ValueError("message contains unsupported control characters")
        return value.strip()


class AIResponse(BaseModel):
    intent: CareSearchIntent | None = None
    clarification_needed: bool = False
    clarification_question: str | None = None
    answer: str | None = None
    context: CareveroAIContext | None = None
    fallback_used: bool = False
    ai_generated: bool = True
    prompt_version: str
    trace_id: str


class AIResolveResponse(BaseModel):
    """Result of scope-locked intent resolution. No model names leaked to consumers."""

    domain: str
    intent_type: str
    candidate_slugs: list[str] = Field(default_factory=list)
    clarification_needed: bool = False
    clarification_question: str | None = None
    refusal_message: str | None = None
    source: str
    used_llm: bool = False
    escalated: bool = False
    trace_id: str
