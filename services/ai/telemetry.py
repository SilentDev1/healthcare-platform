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


def record(trace: SafeTrace) -> None:
    """Record metadata only: no prompt, query, conversation, or health information."""
    logger.info("ai_request", **trace.__dict__)
