"""Carevero AI intent resolution: deterministic-first, LLM-assisted, canonical-validated.

Flow (defense in depth):

    classify_domain (Layer 1)
        out_of_scope / medical_advice -> fixed localized response, NO LLM call
    deterministic resolve_search
        confident (category / exact procedure / clarification) -> return, NO LLM call
    primary model (Luna) — only if allowed, provider configured, and under budget
        structured intent -> Layer-3 domain re-check -> canonical validation
    escalation model (Terra) — only for a genuinely ambiguous in-domain result
        same validation; never broader permissions
    deterministic fallback
        clarification, never a fabricated entity

The model NEVER becomes the source of truth: every candidate slug must be an active
Carevero catalog entity or it is rejected. Obvious requests ("lab tests", "CBC",
"MRI knee", "Nashua", "03060") resolve deterministically and cost nothing.
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from packages.search.ai_contract import (
    AIIntentProposal,
    ProposedDomain,
    category_registry_for_ai,
    intent_json_schema,
    parse_intent_proposal,
    validate_ai_intent,
)
from packages.search.resolution import SearchIntentType, resolve_search
from services.ai.budget import AIBudgetTracker, ai_budget, estimate_cost_usd
from services.ai.domain import DomainClass, classify_domain, response_for
from services.ai.prompts import INTENT_PROMPT_VERSION, INTENT_SYSTEM_PROMPT
from services.ai.provider import AIProvider, ProviderRequest
from services.ai.telemetry import IntentTrace, record_intent


@dataclass(frozen=True)
class ResolverConfig:
    enabled: bool = False
    primary_model: str = "gpt-5.6-luna"
    escalation_model: str = "gpt-5.6-terra"
    max_output_tokens: int = 400
    timeout_seconds: float = 10.0
    daily_budget_usd: float = 0.0
    cost_input_per_million: float = 0.0
    cost_output_per_million: float = 0.0


@dataclass
class ResolvedIntent:
    domain: DomainClass
    intent_type: str
    candidate_slugs: list[str] = field(default_factory=list)
    clarification_needed: bool = False
    clarification_question: str | None = None
    refusal_message: str | None = None
    source: str = "deterministic"  # deterministic|primary_model|escalation_model|fallback|refused
    used_llm: bool = False
    escalated: bool = False
    prompt_version: str = INTENT_PROMPT_VERSION
    trace_id: str = ""


class CareveroIntentResolver:
    def __init__(
        self,
        *,
        provider: AIProvider | None = None,
        config: ResolverConfig | None = None,
        budget: AIBudgetTracker | None = None,
    ) -> None:
        self._provider = provider
        self._config = config or ResolverConfig()
        self._budget = budget or ai_budget

    # ---- public API -----------------------------------------------------------------

    async def resolve(self, session: Session, message: str, locale: str) -> ResolvedIntent:
        started = time.perf_counter()
        trace_id = str(uuid.uuid4())

        # Layer 1: cheap deterministic domain lock. Refusals never reach the LLM.
        domain = classify_domain(message)
        if domain != DomainClass.CAREVERO:
            result = ResolvedIntent(
                domain=domain,
                intent_type="out_of_scope"
                if domain == DomainClass.OUT_OF_SCOPE
                else "medical_advice",
                refusal_message=response_for(domain, locale),
                source="refused",
                trace_id=trace_id,
            )
            self._trace(
                result,
                started,
                model=None,
                in_tok=0,
                out_tok=0,
                cost=0.0,
                rejected=0,
                budget_exhausted=False,
                timed_out=False,
            )
            return result

        # Deterministic resolver handles obvious requests with no LLM cost.
        deterministic = self._deterministic(session, message, locale, trace_id)
        if deterministic is not None:
            self._trace(
                deterministic,
                started,
                model=None,
                in_tok=0,
                out_tok=0,
                cost=0.0,
                rejected=0,
                budget_exhausted=False,
                timed_out=False,
            )
            return deterministic

        # LLM-assisted path — only when explicitly enabled, provider present, and budgeted.
        if not (self._config.enabled and self._provider is not None):
            return self._fallback(locale, trace_id, started, budget_exhausted=False)
        if not self._budget.allowed(self._config.daily_budget_usd):
            return self._fallback(locale, trace_id, started, budget_exhausted=True)

        return await self._llm_resolve(session, message, locale, trace_id, started)

    # ---- deterministic ----------------------------------------------------------------

    def _deterministic(
        self, session: Session, message: str, locale: str, trace_id: str
    ) -> ResolvedIntent | None:
        det = resolve_search(session, message, locale=locale)
        if det.intent_type == SearchIntentType.CATEGORY and det.canonical_category_slug:
            return ResolvedIntent(
                domain=DomainClass.CAREVERO,
                intent_type="category",
                candidate_slugs=[det.canonical_category_slug],
                source="deterministic",
                trace_id=trace_id,
            )
        if det.intent_type == SearchIntentType.PROCEDURE and det.deterministic_match:
            slugs = [
                str(item.metadata["slug"])
                for item in det.results
                if item.entity_type == "procedure" and item.metadata.get("slug")
            ]
            if slugs:
                return ResolvedIntent(
                    domain=DomainClass.CAREVERO,
                    intent_type="procedure",
                    candidate_slugs=slugs,
                    source="deterministic",
                    trace_id=trace_id,
                )
        if det.clarification_needed:
            slugs = [
                str(item.metadata["slug"])
                for item in det.results
                if item.entity_type == "procedure" and item.metadata.get("slug")
            ]
            return ResolvedIntent(
                domain=DomainClass.CAREVERO,
                intent_type="clarification",
                candidate_slugs=slugs,
                clarification_needed=True,
                clarification_question=det.clarification_question,
                source="deterministic",
                trace_id=trace_id,
            )
        return None

    # ---- LLM path ---------------------------------------------------------------------

    async def _llm_resolve(
        self, session: Session, message: str, locale: str, trace_id: str, started: float
    ) -> ResolvedIntent:
        catalog = category_registry_for_ai(session, locale)
        user_prompt = (
            f"ACTIVE_LOCALE={locale}\n"
            f"USER_MESSAGE={json.dumps(message)}\n"
            f"<CAREVERO_CATALOG>{json.dumps(catalog)}</CAREVERO_CATALOG>"
        )

        proposal, in_tok, out_tok, timed_out = await self._call_model(
            self._config.primary_model, user_prompt
        )
        cost = self._record_cost(self._config.primary_model, in_tok, out_tok, escalated=False)

        # Layer 3: the model's own declared domain is re-checked in application logic.
        if proposal is not None and proposal.domain != ProposedDomain.CAREVERO:
            refused = ResolvedIntent(
                domain=(
                    DomainClass.MEDICAL_ADVICE
                    if proposal.domain == ProposedDomain.MEDICAL_ADVICE
                    else DomainClass.OUT_OF_SCOPE
                ),
                intent_type=str(proposal.domain.value),
                refusal_message=response_for(
                    DomainClass.MEDICAL_ADVICE
                    if proposal.domain == ProposedDomain.MEDICAL_ADVICE
                    else DomainClass.OUT_OF_SCOPE,
                    locale,
                ),
                source="primary_model",
                used_llm=True,
                trace_id=trace_id,
            )
            self._trace(
                refused,
                started,
                model=self._config.primary_model,
                in_tok=in_tok,
                out_tok=out_tok,
                cost=cost,
                rejected=0,
                budget_exhausted=False,
                timed_out=timed_out,
            )
            return refused

        result, rejected = self._from_proposal(
            session, proposal, locale, trace_id, source="primary_model"
        )

        # Escalate to Terra ONLY for a genuine in-domain ambiguity the stronger model may
        # resolve — never merely because Luna was low-confidence, and never with broader
        # permissions. Terra output is validated identically.
        if self._should_escalate(proposal, result) and self._budget.allowed(
            self._config.daily_budget_usd
        ):
            esc_proposal, e_in, e_out, e_timed = await self._call_model(
                self._config.escalation_model, user_prompt
            )
            cost += self._record_cost(self._config.escalation_model, e_in, e_out, escalated=True)
            in_tok += e_in
            out_tok += e_out
            timed_out = timed_out or e_timed
            if esc_proposal is not None and esc_proposal.domain == ProposedDomain.CAREVERO:
                esc_result, esc_rejected = self._from_proposal(
                    session, esc_proposal, locale, trace_id, source="escalation_model"
                )
                esc_result.escalated = True
                if esc_result.candidate_slugs:
                    result, rejected = esc_result, esc_rejected

        if not result.candidate_slugs and not result.refusal_message:
            result.clarification_needed = True
            if not result.clarification_question:
                result.clarification_question = _generic_clarification(locale)

        self._trace(
            result,
            started,
            model=self._config.primary_model,
            in_tok=in_tok,
            out_tok=out_tok,
            cost=cost,
            rejected=rejected,
            budget_exhausted=False,
            timed_out=timed_out,
        )
        return result

    def _from_proposal(
        self,
        session: Session,
        proposal: AIIntentProposal | None,
        locale: str,
        trace_id: str,
        *,
        source: str,
    ) -> tuple[ResolvedIntent, int]:
        if proposal is None:
            return (
                ResolvedIntent(
                    domain=DomainClass.CAREVERO,
                    intent_type="unknown",
                    clarification_needed=True,
                    clarification_question=_generic_clarification(locale),
                    source=source,
                    used_llm=True,
                    trace_id=trace_id,
                ),
                0,
            )
        validated = validate_ai_intent(session, proposal)
        return (
            ResolvedIntent(
                domain=DomainClass.CAREVERO,
                intent_type=str(proposal.intent_type.value),
                candidate_slugs=validated.canonical_candidates,
                clarification_needed=validated.clarification_needed,
                clarification_question=validated.clarification_question,
                source=source,
                used_llm=True,
                trace_id=trace_id,
            ),
            len(validated.rejected_candidates),
        )

    @staticmethod
    def _should_escalate(proposal: AIIntentProposal | None, result: ResolvedIntent) -> bool:
        if proposal is None:
            return True
        # In-domain, deterministic already failed; escalate on multi-candidate ambiguity
        # or when no valid candidate was found and the model asked to clarify.
        return len(result.candidate_slugs) > 1 or (
            not result.candidate_slugs and result.clarification_needed
        )

    async def _call_model(
        self, model: str, user_prompt: str
    ) -> tuple[AIIntentProposal | None, int, int, bool]:
        assert self._provider is not None
        request = ProviderRequest(
            system_prompt=INTENT_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            model=model,
            max_output_tokens=self._config.max_output_tokens,
            timeout_seconds=self._config.timeout_seconds,
            json_schema=intent_json_schema(),
        )
        try:
            provider_result = await self._provider.generate_result(request)
        except Exception:
            # Any provider failure (timeout, 429, 5xx, malformed) -> deterministic fallback.
            return None, 0, 0, True
        proposal = parse_intent_proposal(provider_result.text)
        return proposal, provider_result.input_tokens, provider_result.output_tokens, False

    def _record_cost(self, model: str, in_tok: int, out_tok: int, *, escalated: bool) -> float:
        cost = estimate_cost_usd(
            in_tok,
            out_tok,
            input_per_million=self._config.cost_input_per_million,
            output_per_million=self._config.cost_output_per_million,
        )
        self._budget.record(
            model=model,
            input_tokens=in_tok,
            output_tokens=out_tok,
            cost_usd=cost,
            escalated=escalated,
        )
        return cost

    def _fallback(
        self, locale: str, trace_id: str, started: float, *, budget_exhausted: bool
    ) -> ResolvedIntent:
        result = ResolvedIntent(
            domain=DomainClass.CAREVERO,
            intent_type="unknown",
            clarification_needed=True,
            clarification_question=_generic_clarification(locale),
            source="fallback",
            trace_id=trace_id,
        )
        self._trace(
            result,
            started,
            model=None,
            in_tok=0,
            out_tok=0,
            cost=0.0,
            rejected=0,
            budget_exhausted=budget_exhausted,
            timed_out=False,
        )
        return result

    def _trace(
        self,
        result: ResolvedIntent,
        started: float,
        *,
        model: str | None,
        in_tok: int,
        out_tok: int,
        cost: float,
        rejected: int,
        budget_exhausted: bool,
        timed_out: bool,
    ) -> None:
        record_intent(
            IntentTrace(
                trace_id=result.trace_id,
                locale="",  # locale is UI context, not logged as free text here
                domain=str(result.domain.value),
                source=result.source,
                used_llm=result.used_llm,
                escalated=result.escalated,
                model=model,
                input_tokens=in_tok,
                output_tokens=out_tok,
                estimated_cost_usd=cost,
                candidate_count=len(result.candidate_slugs),
                rejected_candidate_count=rejected,
                clarification_needed=result.clarification_needed,
                budget_exhausted=budget_exhausted,
                timed_out=timed_out,
                duration_ms=round((time.perf_counter() - started) * 1000, 2),
            )
        )


_GENERIC_CLARIFICATION = {
    "en": "Which healthcare service or procedure are you looking for?",
    "es": "¿Qué servicio o procedimiento de salud está buscando?",
    "vi": "Bạn đang tìm dịch vụ hoặc thủ thuật y tế nào?",
    "zh-CN": "您在寻找哪项医疗服务或医疗项目？",
    "zh-TW": "您在尋找哪一項醫療服務或醫療項目？",
}


def _generic_clarification(locale: str) -> str:
    return _GENERIC_CLARIFICATION.get(locale, _GENERIC_CLARIFICATION["en"])
