"""Daily AI budget guard + cost estimation."""

from __future__ import annotations

from services.ai.budget import AIBudgetTracker, estimate_cost_usd


def test_estimate_cost() -> None:
    # 1M input @ $1, 0.5M output @ $2 = 1 + 1 = 2.0
    assert (
        estimate_cost_usd(1_000_000, 500_000, input_per_million=1.0, output_per_million=2.0) == 2.0
    )


def test_zero_budget_is_fail_closed() -> None:
    tracker = AIBudgetTracker()
    # A non-positive budget authorizes no spend, so an unconfigured budget never leaks.
    assert tracker.allowed(0.0) is False
    assert tracker.allowed(-5.0) is False


def test_budget_blocks_after_ceiling() -> None:
    tracker = AIBudgetTracker()
    assert tracker.allowed(10.0) is True
    tracker.record(
        model="gpt-5.6-luna", input_tokens=100, output_tokens=50, cost_usd=9.99, escalated=False
    )
    assert tracker.allowed(10.0) is True  # still under
    tracker.record(
        model="gpt-5.6-luna", input_tokens=100, output_tokens=50, cost_usd=0.02, escalated=False
    )
    assert tracker.allowed(10.0) is False  # ceiling reached


def test_snapshot_tracks_models_and_escalation() -> None:
    tracker = AIBudgetTracker()
    tracker.record(
        model="gpt-5.6-luna", input_tokens=100, output_tokens=20, cost_usd=0.1, escalated=False
    )
    tracker.record(
        model="gpt-5.6-terra", input_tokens=200, output_tokens=40, cost_usd=0.3, escalated=True
    )
    snap = tracker.snapshot()
    assert snap["calls"] == 2
    assert snap["primary_calls"] == 1
    assert snap["escalation_calls"] == 1
    assert snap["input_tokens"] == 300
    assert snap["output_tokens"] == 60
    assert snap["estimated_cost_usd"] == 0.4
    assert snap["by_model"] == {"gpt-5.6-luna": 1, "gpt-5.6-terra": 1}
    assert snap["escalation_rate"] == 0.5
