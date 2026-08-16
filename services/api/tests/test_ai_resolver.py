"""Carevero AI intent resolver: deterministic-first, canonical-validated, budgeted.

Uses a fake provider (no network, no API key) to prove the safety-critical control flow:
scope refusals and obvious requests never call the model; the model can never introduce a
non-canonical entity; escalation to Terra happens only for genuine ambiguity; and provider
failure / budget exhaustion always falls back deterministically.
"""

from __future__ import annotations

import asyncio
import json
from typing import cast

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from packages.database import Base
from packages.search.service import rebuild_index
from scripts.seed_procedure_catalog import seed_catalog
from services.ai.budget import AIBudgetTracker
from services.ai.domain import DomainClass
from services.ai.provider import AIProvider, ProviderResult
from services.ai.resolver import CareveroIntentResolver, ResolvedIntent, ResolverConfig


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


class FakeProvider:
    def __init__(self, responses: dict[str, object]) -> None:
        self.responses = responses
        self.calls: list[str] = []

    async def generate_result(self, request: object) -> ProviderResult:
        model = request.model  # type: ignore[attr-defined]
        self.calls.append(model)
        value = self.responses[model]
        if isinstance(value, Exception):
            raise value
        assert isinstance(value, ProviderResult)
        return value

    async def generate(self, request: object) -> str:
        return (await self.generate_result(request)).text


def _proposal(**kw: object) -> ProviderResult:
    payload = {
        "domain": "carevero",
        "intent_type": "procedure",
        "canonical_candidates": [],
        "confidence": 0.9,
        "clarification_needed": False,
        "clarification_question": None,
    }
    payload.update(kw)
    return ProviderResult(text=json.dumps(payload), input_tokens=200, output_tokens=40)


def _config(**kw: object) -> ResolverConfig:
    base: dict[str, object] = {
        "enabled": True,
        "daily_budget_usd": 100.0,
        "cost_input_per_million": 1.0,
        "cost_output_per_million": 2.0,
    }
    base.update(kw)
    return ResolverConfig(**base)  # type: ignore[arg-type]


def _resolve(
    session: Session,
    provider: object,
    message: str,
    config: ResolverConfig,
    budget: AIBudgetTracker | None = None,
) -> ResolvedIntent:
    resolver = CareveroIntentResolver(
        provider=cast(AIProvider, provider), config=config, budget=budget or AIBudgetTracker()
    )
    return asyncio.run(resolver.resolve(session, message, "en"))


# A message that is in-domain (Carevero) but does NOT resolve deterministically, so the
# LLM path is exercised.
UNRESOLVED = "find me an obscure service option nearby"


def test_out_of_scope_never_calls_the_model(session: Session) -> None:
    provider = FakeProvider({})
    result = _resolve(session, provider, "Who won the Super Bowl?", _config())
    assert result.domain == DomainClass.OUT_OF_SCOPE
    assert result.refusal_message
    assert result.used_llm is False
    assert provider.calls == []


def test_medical_advice_never_calls_the_model(session: Session) -> None:
    provider = FakeProvider({})
    result = _resolve(session, provider, "What scan should I get for chest pain?", _config())
    assert result.domain == DomainClass.MEDICAL_ADVICE
    assert result.refusal_message
    assert provider.calls == []


def test_obvious_request_resolves_deterministically_without_llm(session: Session) -> None:
    provider = FakeProvider({})
    result = _resolve(session, provider, "lab tests", _config())
    assert result.source == "deterministic"
    assert result.intent_type == "category"
    assert result.candidate_slugs == ["laboratory"]
    assert provider.calls == []


def test_fabricated_slug_from_model_is_rejected(session: Session) -> None:
    provider = FakeProvider(
        {"gpt-5.6-luna": _proposal(canonical_candidates=["totally-made-up-procedure"])}
    )
    result = _resolve(session, provider, UNRESOLVED, _config())
    assert "gpt-5.6-luna" in provider.calls
    assert result.candidate_slugs == []  # invented slug rejected -> no fabricated entity
    assert result.clarification_needed is True


def test_valid_slug_from_model_is_accepted(session: Session) -> None:
    provider = FakeProvider(
        {"gpt-5.6-luna": _proposal(canonical_candidates=["complete-blood-count"])}
    )
    result = _resolve(session, provider, UNRESOLVED, _config())
    assert result.candidate_slugs == ["complete-blood-count"]
    assert result.used_llm is True
    assert result.escalated is False


def test_model_declaring_out_of_scope_is_refused(session: Session) -> None:
    provider = FakeProvider(
        {"gpt-5.6-luna": _proposal(domain="out_of_scope", intent_type="unknown")}
    )
    result = _resolve(session, provider, UNRESOLVED, _config())
    assert result.domain == DomainClass.OUT_OF_SCOPE
    assert result.refusal_message


def test_escalates_to_terra_only_on_ambiguity(session: Session) -> None:
    provider = FakeProvider(
        {
            "gpt-5.6-luna": _proposal(
                canonical_candidates=["complete-blood-count", "basic-metabolic-panel"]
            ),
            "gpt-5.6-terra": _proposal(canonical_candidates=["complete-blood-count"]),
        }
    )
    result = _resolve(session, provider, UNRESOLVED, _config())
    assert provider.calls == ["gpt-5.6-luna", "gpt-5.6-terra"]
    assert result.escalated is True
    assert result.candidate_slugs == ["complete-blood-count"]


def test_single_confident_candidate_does_not_escalate(session: Session) -> None:
    provider = FakeProvider(
        {"gpt-5.6-luna": _proposal(canonical_candidates=["complete-blood-count"])}
    )
    result = _resolve(session, provider, UNRESOLVED, _config())
    assert provider.calls == ["gpt-5.6-luna"]
    assert result.escalated is False


def test_provider_failure_falls_back_deterministically(session: Session) -> None:
    provider = FakeProvider({"gpt-5.6-luna": RuntimeError("429 rate limited")})
    result = _resolve(session, provider, UNRESOLVED, _config())
    assert result.clarification_needed is True
    assert result.candidate_slugs == []


def test_budget_exhausted_skips_model(session: Session) -> None:
    provider = FakeProvider(
        {"gpt-5.6-luna": _proposal(canonical_candidates=["complete-blood-count"])}
    )
    budget = AIBudgetTracker()
    budget.record(model="x", input_tokens=0, output_tokens=0, cost_usd=100.0, escalated=False)
    result = _resolve(session, provider, UNRESOLVED, _config(daily_budget_usd=50.0), budget)
    assert provider.calls == []
    assert result.source == "fallback"


def test_disabled_flag_skips_model(session: Session) -> None:
    provider = FakeProvider(
        {"gpt-5.6-luna": _proposal(canonical_candidates=["complete-blood-count"])}
    )
    result = _resolve(session, provider, UNRESOLVED, _config(enabled=False))
    assert provider.calls == []
    assert result.source == "fallback"
