from __future__ import annotations

import json
import time
import uuid

from sqlalchemy.orm import Session

from services.ai.formatter import format_grounded
from services.ai.guardrails import validate_grounded_output
from services.ai.intent import extract_intent
from services.ai.prompts import PROMPT_VERSION, SYSTEM_PROMPT
from services.ai.provider import AIProvider, ProviderRequest
from services.ai.schemas import AIRequest, AIResponse, CareveroAIContext
from services.ai.telemetry import SafeTrace, record


class CareveroAIOrchestrator:
    def __init__(
        self,
        *,
        provider: AIProvider | None = None,
        model: str = "",
        max_output_tokens: int = 500,
        timeout_seconds: float = 12,
    ) -> None:
        self.provider = provider
        self.model = model
        self.max_output_tokens = max_output_tokens
        self.timeout_seconds = timeout_seconds

    async def interpret(self, session: Session, request: AIRequest) -> AIResponse:
        trace_id = str(uuid.uuid4())
        intent = extract_intent(session, request.message, request.locale)
        return AIResponse(
            intent=intent,
            clarification_needed=intent.procedure_clarification_needed,
            clarification_question=intent.clarification_question,
            prompt_version=PROMPT_VERSION,
            trace_id=trace_id,
        )

    async def explain(self, request: AIRequest, context: CareveroAIContext) -> AIResponse:
        started = time.perf_counter()
        trace_id = str(uuid.uuid4())
        fallback = format_grounded(context, request.locale)
        answer = fallback
        fallback_used = self.provider is None
        if self.provider is not None:
            try:
                data = context.model_dump_json(exclude_none=True)
                # JSON delimiters mark every source string as data; the system prompt
                # explicitly prevents data from changing assistant instructions.
                prompt = (
                    f"ACTIVE_LOCALE={request.locale}\n"
                    f"USER_QUESTION={json.dumps(request.message)}\n"
                    f"<CAREVERO_DATA>{data}</CAREVERO_DATA>"
                )
                candidate = await self.provider.generate(
                    ProviderRequest(
                        system_prompt=SYSTEM_PROMPT,
                        user_prompt=prompt,
                        model=self.model,
                        max_output_tokens=self.max_output_tokens,
                        timeout_seconds=self.timeout_seconds,
                    )
                )
                if validate_grounded_output(candidate, context):
                    answer = candidate
                    fallback_used = False
                else:
                    fallback_used = True
            except Exception:
                fallback_used = True
        record(
            SafeTrace(
                trace_id=trace_id,
                task="explanation",
                locale=request.locale,
                provider=(
                    type(self.provider).__name__ if self.provider else "deterministic_fallback"
                ),
                success=True,
                fallback_used=fallback_used,
                clarification_needed=False,
                facility_count=len(context.facilities),
                duration_ms=round((time.perf_counter() - started) * 1000, 2),
            )
        )
        return AIResponse(
            answer=answer,
            context=context,
            fallback_used=fallback_used,
            prompt_version=PROMPT_VERSION,
            trace_id=trace_id,
        )
