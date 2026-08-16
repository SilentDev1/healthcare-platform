"""Canonical entity validation and provider/model configuration.

Guarantees the model can never introduce an entity that is not already an active Carevero
catalog record, and that provider/model IDs are environment-configurable with the secret
never exposed.
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from packages.database import Base
from packages.search.ai_contract import (
    AIIntentProposal,
    ProposedDomain,
    ProposedIntentType,
    intent_json_schema,
    parse_intent_proposal,
    validate_ai_intent,
)
from packages.search.service import rebuild_index
from scripts.seed_procedure_catalog import seed_catalog
from services.api.app.settings import ApiSettings


@pytest.fixture(scope="module")
def session() -> Session:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    s = Session(engine)
    seed_catalog(s)
    s.commit()
    rebuild_index(s)
    s.commit()
    return s


def test_valid_procedure_slug_accepted(session: Session) -> None:
    proposal = AIIntentProposal(
        intent_type=ProposedIntentType.PROCEDURE,
        canonical_candidates=["complete-blood-count"],
        confidence=0.9,
    )
    validated = validate_ai_intent(session, proposal)
    assert validated.canonical_candidates == ["complete-blood-count"]
    assert validated.rejected_candidates == []


def test_fabricated_candidates_are_all_rejected(session: Session) -> None:
    proposal = AIIntentProposal(
        intent_type=ProposedIntentType.PROCEDURE,
        canonical_candidates=["totally-fake", "another-made-up-slug", "complete-blood-count"],
        confidence=0.9,
    )
    validated = validate_ai_intent(session, proposal)
    assert validated.canonical_candidates == ["complete-blood-count"]
    assert set(validated.rejected_candidates) == {"totally-fake", "another-made-up-slug"}


def test_category_slug_validated_against_catalog(session: Session) -> None:
    proposal = AIIntentProposal(
        intent_type=ProposedIntentType.CATEGORY,
        canonical_candidates=["laboratory", "not-a-real-category"],
        confidence=0.8,
    )
    validated = validate_ai_intent(session, proposal)
    assert validated.canonical_candidates == ["laboratory"]
    assert validated.rejected_candidates == ["not-a-real-category"]


def test_no_valid_candidate_forces_clarification(session: Session) -> None:
    proposal = AIIntentProposal(
        intent_type=ProposedIntentType.PROCEDURE,
        canonical_candidates=["nope"],
        confidence=0.9,
    )
    validated = validate_ai_intent(session, proposal)
    assert validated.canonical_candidates == []
    assert validated.clarification_needed is True


def test_parse_rejects_malformed_and_non_object() -> None:
    assert parse_intent_proposal("not json") is None
    assert parse_intent_proposal("[1,2,3]") is None
    assert parse_intent_proposal('{"intent_type":"procedure"}') is None  # missing required fields


def test_parse_accepts_well_formed() -> None:
    proposal = parse_intent_proposal(
        '{"domain":"carevero","intent_type":"category",'
        '"canonical_candidates":["laboratory"],"confidence":0.9,'
        '"clarification_needed":false,"clarification_question":null}'
    )
    assert proposal is not None
    assert proposal.domain == ProposedDomain.CAREVERO
    assert proposal.intent_type == ProposedIntentType.CATEGORY


def test_intent_schema_is_strict() -> None:
    schema = intent_json_schema()
    assert schema["additionalProperties"] is False
    assert "domain" in schema["properties"]  # type: ignore[operator]


def test_settings_model_ids_are_configurable_and_key_hidden() -> None:
    settings = ApiSettings(
        ai_provider="openai",
        ai_primary_model="gpt-5.6-luna",
        ai_escalation_model="gpt-5.6-terra",
        openai_api_key="sk-secret-value",
    )
    assert settings.ai_primary_model == "gpt-5.6-luna"
    assert settings.ai_escalation_model == "gpt-5.6-terra"
    assert settings.resolved_ai_endpoint == "https://api.openai.com/v1/responses"
    assert settings.resolved_ai_api_key == "sk-secret-value"
    assert settings.ai_provider_configured is True
    # The key must never appear in a serialized settings dump surfaced anywhere.
    assert "sk-secret-value" not in settings.model_dump_json(
        exclude={"openai_api_key", "ai_provider_api_key", "admin_shared_secret", "database_url"}
    )


def test_provider_not_configured_without_key() -> None:
    settings = ApiSettings(ai_provider="openai", openai_api_key=None)
    assert settings.ai_provider_configured is False


def test_default_settings_keep_ai_off() -> None:
    settings = ApiSettings()
    assert settings.ai_assistant_enabled is False
    assert settings.ai_intent_search_enabled is False
    assert settings.ai_explanations_enabled is False
    assert settings.ai_provider == "none"
    assert settings.ai_daily_budget_usd == 0.0
    assert settings.ai_provider_configured is False
