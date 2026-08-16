from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from packages.database import get_session
from services.ai.context import build_context
from services.ai.domain import DomainClass, classify_domain, response_for
from services.ai.orchestrator import CareveroAIOrchestrator
from services.ai.prompts import INTENT_PROMPT_VERSION
from services.ai.provider import build_provider
from services.ai.schemas import AIRequest, AIResponse
from services.api.app.settings import api_settings

router = APIRouter(prefix="/api/v1/ai", tags=["ai"])


def _orchestrator() -> CareveroAIOrchestrator:
    provider = build_provider(
        endpoint=api_settings.resolved_ai_endpoint,
        api_key=api_settings.resolved_ai_api_key,
    )
    return CareveroAIOrchestrator(
        provider=provider,
        model=api_settings.ai_primary_model,
        max_output_tokens=api_settings.ai_max_output_tokens,
        timeout_seconds=api_settings.ai_timeout_seconds,
    )


def _require_flag(flag: bool) -> None:
    if not api_settings.ai_assistant_enabled or not flag:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="not found")


def _domain_refusal(request: AIRequest) -> AIResponse | None:
    """Layer-1 scope lock enforced at the API boundary, before any model/tool call.

    Out-of-scope and medical-advice messages get a fixed localized response and never
    reach the deterministic resolver or the LLM.
    """
    domain = classify_domain(request.message)
    if domain == DomainClass.CAREVERO:
        return None
    return AIResponse(
        answer=response_for(domain, request.locale),
        clarification_needed=False,
        fallback_used=True,
        ai_generated=False,
        prompt_version=INTENT_PROMPT_VERSION,
        trace_id="domain-refused",
    )


@router.post("/intent", response_model=AIResponse)
async def ai_intent(
    request: AIRequest, session: Annotated[Session, Depends(get_session)]
) -> AIResponse:
    _require_flag(api_settings.ai_intent_search_enabled)
    refusal = _domain_refusal(request)
    if refusal is not None:
        return refusal
    return await _orchestrator().interpret(session, request)


@router.post("/query", response_model=AIResponse)
async def ai_query(
    request: AIRequest, session: Annotated[Session, Depends(get_session)]
) -> AIResponse:
    """Interpret, retrieve deterministic results, then explain; never accepts SQL or URLs."""
    _require_flag(api_settings.ai_intent_search_enabled)
    refusal = _domain_refusal(request)
    if refusal is not None:
        return refusal
    orchestrator = _orchestrator()
    interpreted = await orchestrator.interpret(session, request)
    intent = interpreted.intent
    if intent is None or intent.procedure_clarification_needed or not intent.procedure_slug:
        return interpreted

    # Local import avoids a route-module cycle. This calls the same deterministic
    # comparison function used by the existing public UI.
    from services.api.app.main import procedure_comparison

    comparison = procedure_comparison(
        slug=intent.procedure_slug,
        session=session,
        state_code=intent.state or "NH",
        city=intent.city,
        postal_code=intent.zip,
        payer=intent.payer_slug,
        plan=intent.plan_id,
        setting=intent.service_setting,
        origin_zip=intent.zip,
        origin_city=intent.city,
        radius_miles=intent.radius_miles,
    )
    context = build_context(intent, comparison)
    if not api_settings.ai_explanations_enabled:
        return AIResponse(
            intent=intent,
            context=context,
            fallback_used=True,
            prompt_version=interpreted.prompt_version,
            trace_id=interpreted.trace_id,
        )
    explained = await orchestrator.explain(request, context)
    explained.intent = intent
    return explained


@router.post("/explain", response_model=AIResponse)
async def ai_explain(request: AIRequest) -> AIResponse:
    _require_flag(api_settings.ai_explanations_enabled)
    refusal = _domain_refusal(request)
    if refusal is not None:
        return refusal
    if request.current_context is None:
        raise HTTPException(status_code=422, detail="current_context is required")
    return await _orchestrator().explain(request, request.current_context)
