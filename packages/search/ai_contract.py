from __future__ import annotations

import json
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from packages.database import Procedure, ProcedureCategory
from packages.search.categories import consumer_categories


class ProposedDomain(StrEnum):
    """Layer-3 scope declared by the model itself, re-checked in application logic."""

    CAREVERO = "carevero"
    MEDICAL_ADVICE = "medical_advice"
    OUT_OF_SCOPE = "out_of_scope"


class ProposedIntentType(StrEnum):
    PROCEDURE = "procedure"
    CATEGORY = "category"
    HOSPITAL = "hospital"
    LOCATION = "location"
    PRICE_COMPARISON = "price_comparison"
    EXPLANATION = "explanation"
    CLARIFICATION = "clarification"
    AMBIGUOUS = "ambiguous"
    UNKNOWN = "unknown"


class AIIntentProposal(BaseModel):
    """Untrusted structured output accepted from the AI provider layer.

    Every field is validated and every candidate is canonical-checked before it can
    influence a response; the model never becomes the source of truth.
    """

    model_config = ConfigDict(extra="forbid")
    domain: ProposedDomain = ProposedDomain.CAREVERO
    intent_type: ProposedIntentType
    canonical_candidates: list[str] = Field(default_factory=list, max_length=10)
    confidence: float = Field(ge=0, le=1)
    clarification_needed: bool = False
    clarification_question: str | None = Field(default=None, max_length=300)


def intent_json_schema() -> dict[str, object]:
    """Strict JSON schema handed to the provider for structured intent output."""
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "domain": {"type": "string", "enum": [d.value for d in ProposedDomain]},
            "intent_type": {"type": "string", "enum": [t.value for t in ProposedIntentType]},
            "canonical_candidates": {
                "type": "array",
                "items": {"type": "string"},
                "maxItems": 10,
            },
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            "clarification_needed": {"type": "boolean"},
            "clarification_question": {"type": ["string", "null"], "maxLength": 300},
        },
        "required": [
            "domain",
            "intent_type",
            "canonical_candidates",
            "confidence",
            "clarification_needed",
            "clarification_question",
        ],
    }


def parse_intent_proposal(raw_text: str) -> AIIntentProposal | None:
    """Parse untrusted provider JSON into a validated proposal, or None if malformed."""
    try:
        data = json.loads(raw_text)
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(data, dict):
        return None
    try:
        return AIIntentProposal.model_validate(data)
    except ValidationError:
        return None


class ValidatedIntent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    intent_type: ProposedIntentType
    canonical_candidates: list[str]
    rejected_candidates: list[str]
    clarification_needed: bool
    clarification_question: str | None


def category_registry_for_ai(session: Session, locale: str = "en") -> list[dict[str, object]]:
    """Bounded read-only taxonomy for Carevero AI tools; membership is canonical DB data."""
    registry = consumer_categories()
    # Count in application code so this bounded catalog query stays portable
    # across SQLite and PostgreSQL.
    totals: dict[str, int] = {}
    for slug, _procedure_id in session.execute(
        select(ProcedureCategory.slug, Procedure.id)
        .join(Procedure, Procedure.category_id == ProcedureCategory.id)
        .where(ProcedureCategory.active.is_(True), Procedure.active.is_(True))
    ):
        totals[slug] = totals.get(slug, 0) + 1
    return [
        {
            "canonical_id": item.slug,
            "slug": item.slug,
            "consumer_display_name": item.label(locale),
            "localized_display_names": item.labels,
            "reviewed_aliases": list(item.aliases),
            "procedure_count": totals.get(item.slug, 0),
        }
        for item in registry.values()
    ]


def _is_active_category(session: Session, slug: str) -> bool:
    return (
        slug in consumer_categories()
        and session.scalar(
            select(ProcedureCategory.id).where(
                ProcedureCategory.slug == slug,
                ProcedureCategory.active.is_(True),
            )
        )
        is not None
    )


def _is_active_procedure(session: Session, slug: str) -> bool:
    return (
        session.scalar(
            select(Procedure.id).where(Procedure.slug == slug, Procedure.active.is_(True))
        )
        is not None
    )


def validate_ai_intent(session: Session, proposal: AIIntentProposal) -> ValidatedIntent:
    """Reject every AI candidate that is not an active canonical Carevero entity.

    A candidate is accepted only if it is an active procedure slug (or, for a category
    intent, an active category slug). Any slug the model invents — including a plausible
    but non-existent one — is rejected, so a model can never introduce an entity that is
    not already in Carevero's reviewed catalog.
    """
    valid: list[str] = []
    rejected: list[str] = []
    for candidate in proposal.canonical_candidates:
        if proposal.intent_type == ProposedIntentType.CATEGORY:
            exists = _is_active_category(session, candidate)
        else:
            # For every non-category intent, only a real active procedure slug is valid.
            exists = _is_active_procedure(session, candidate)
        if exists:
            valid.append(candidate)
        else:
            rejected.append(candidate)
    clarification_needed = proposal.clarification_needed or not valid
    return ValidatedIntent(
        intent_type=proposal.intent_type if valid else ProposedIntentType.UNKNOWN,
        canonical_candidates=valid,
        rejected_candidates=rejected,
        clarification_needed=clarification_needed,
        clarification_question=proposal.clarification_question,
    )
