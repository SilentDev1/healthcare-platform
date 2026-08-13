from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from packages.database import Procedure, ProcedureCategory
from packages.search.categories import consumer_categories


class ProposedIntentType(StrEnum):
    PROCEDURE = "procedure"
    CATEGORY = "category"
    HOSPITAL = "hospital"
    LOCATION = "location"
    AMBIGUOUS = "ambiguous"
    UNKNOWN = "unknown"


class AIIntentProposal(BaseModel):
    """Untrusted structured output accepted from the existing AI provider layer."""

    model_config = ConfigDict(extra="forbid")
    intent_type: ProposedIntentType
    canonical_candidates: list[str] = Field(default_factory=list, max_length=10)
    confidence: float = Field(ge=0, le=1)
    clarification_needed: bool = False
    clarification_question: str | None = Field(default=None, max_length=300)


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


def validate_ai_intent(session: Session, proposal: AIIntentProposal) -> ValidatedIntent:
    """Reject every AI candidate that is not an active canonical Carevero entity."""
    valid: list[str] = []
    rejected: list[str] = []
    for candidate in proposal.canonical_candidates:
        exists = False
        if proposal.intent_type == ProposedIntentType.CATEGORY:
            exists = (
                candidate in consumer_categories()
                and session.scalar(
                    select(ProcedureCategory.id).where(
                        ProcedureCategory.slug == candidate,
                        ProcedureCategory.active.is_(True),
                    )
                )
                is not None
            )
        elif proposal.intent_type == ProposedIntentType.PROCEDURE:
            exists = (
                session.scalar(
                    select(Procedure.id).where(
                        Procedure.slug == candidate,
                        Procedure.active.is_(True),
                    )
                )
                is not None
            )
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
