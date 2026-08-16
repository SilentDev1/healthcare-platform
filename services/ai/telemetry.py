from __future__ import annotations

from dataclasses import dataclass

import structlog

logger = structlog.get_logger(service="carevero_ai")


@dataclass(frozen=True)
class SafeTrace:
    trace_id: str
    task: str
    locale: str
    provider: str
    success: bool
    fallback_used: bool
    clarification_needed: bool
    facility_count: int
    duration_ms: float


@dataclass(frozen=True)
class IntentTrace:
    """Intent-resolution telemetry: metadata + cost only, never query or health text."""

    trace_id: str
    locale: str
    domain: str
    source: str  # deterministic | primary_model | escalation_model | fallback | refused
    used_llm: bool
    escalated: bool
    model: str | None
    input_tokens: int
    output_tokens: int
    estimated_cost_usd: float
    candidate_count: int
    rejected_candidate_count: int
    clarification_needed: bool
    budget_exhausted: bool
    timed_out: bool
    duration_ms: float


def record(trace: SafeTrace) -> None:
    """Record metadata only: no prompt, query, conversation, or health information."""
    logger.info("ai_request", **trace.__dict__)


def record_intent(trace: IntentTrace) -> None:
    """Record intent-resolution metadata + estimated cost; never the message text."""
    logger.info("ai_intent", **trace.__dict__)
