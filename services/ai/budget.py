"""Daily AI budget guard + cost/usage tracking.

Protects against runaway OpenAI spend and automated abuse: once the per-day cost ceiling
is reached, the LLM path is denied and the assistant falls back to deterministic Carevero
search — the site NEVER goes down because OpenAI is unavailable or the budget is spent.

Usage/cost are tracked per UTC day and per model. This is an in-process tracker: with
multiple Cloud Run instances each holds its own counter, so the effective ceiling scales
with instance count. That is acceptable for private beta; a shared store (Redis/Cloud SQL)
is the documented production hardening. No prompt, query, or health text is ever stored.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import UTC, datetime


def _today() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%d")


@dataclass
class _DayUsage:
    day: str
    calls: int = 0
    primary_calls: int = 0
    escalation_calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    estimated_cost_usd: float = 0.0
    by_model: dict[str, int] = field(default_factory=dict)


def estimate_cost_usd(
    input_tokens: int,
    output_tokens: int,
    *,
    input_per_million: float,
    output_per_million: float,
) -> float:
    return round(
        (input_tokens / 1_000_000) * input_per_million
        + (output_tokens / 1_000_000) * output_per_million,
        6,
    )


class AIBudgetTracker:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._usage = _DayUsage(day=_today())

    def _current(self) -> _DayUsage:
        today = _today()
        if self._usage.day != today:
            self._usage = _DayUsage(day=today)
        return self._usage

    def allowed(self, daily_budget_usd: float) -> bool:
        """True if another LLM call is permitted under today's budget.

        A non-positive budget means "no LLM spend permitted" (fail-closed), so an
        unconfigured budget never silently authorizes unbounded spend.
        """
        if daily_budget_usd <= 0:
            return False
        with self._lock:
            return self._current().estimated_cost_usd < daily_budget_usd

    def record(
        self,
        *,
        model: str,
        input_tokens: int,
        output_tokens: int,
        cost_usd: float,
        escalated: bool,
    ) -> None:
        with self._lock:
            usage = self._current()
            usage.calls += 1
            if escalated:
                usage.escalation_calls += 1
            else:
                usage.primary_calls += 1
            usage.input_tokens += max(0, input_tokens)
            usage.output_tokens += max(0, output_tokens)
            usage.estimated_cost_usd = round(usage.estimated_cost_usd + max(0.0, cost_usd), 6)
            usage.by_model[model] = usage.by_model.get(model, 0) + 1

    def snapshot(self) -> dict[str, object]:
        with self._lock:
            usage = self._current()
            return {
                "day": usage.day,
                "calls": usage.calls,
                "primary_calls": usage.primary_calls,
                "escalation_calls": usage.escalation_calls,
                "input_tokens": usage.input_tokens,
                "output_tokens": usage.output_tokens,
                "estimated_cost_usd": usage.estimated_cost_usd,
                "by_model": dict(usage.by_model),
                "escalation_rate": (
                    round(usage.escalation_calls / usage.calls, 4) if usage.calls else 0.0
                ),
            }

    def reset(self) -> None:
        """Test-only: clear counters."""
        with self._lock:
            self._usage = _DayUsage(day=_today())


# Process-wide singleton.
ai_budget = AIBudgetTracker()
