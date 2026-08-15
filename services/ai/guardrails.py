from __future__ import annotations

import re

from services.ai.schemas import CareveroAIContext

_MONEY = re.compile(r"\$\s*([0-9][0-9,]*(?:\.\d{1,2})?)")
_MILES = re.compile(r"\b([0-9]+(?:\.\d+)?)\s+miles?\b", re.I)
_PROHIBITED = re.compile(
    r"\b(?:definitely\s+)?(?:in[- ]network|covered|accepts? your insurance|best hospital)\b",
    re.I,
)


def validate_grounded_output(text: str, context: CareveroAIContext) -> bool:
    """Reject factual provider prose that contains values absent from the fact package."""
    allowed_money: set[str] = set()
    allowed_miles: set[str] = set()
    for item in context.facilities:
        for value in (
            item.comparable_cash_price,
            item.selected_insurance_price_min,
            item.selected_insurance_price_max,
            item.savings_difference,
        ):
            if value is not None:
                allowed_money.add(f"{value:,.2f}")
                allowed_money.add(f"{value:,.0f}")
        if item.distance_miles is not None:
            allowed_miles.add(str(item.distance_miles))
    found_money = {match.replace(",", "") for match in _MONEY.findall(text)}
    normalized_allowed_money = {value.replace(",", "") for value in allowed_money}
    if not found_money.issubset(normalized_allowed_money):
        return False
    if not set(_MILES.findall(text)).issubset(allowed_miles):
        return False
    return _PROHIBITED.search(text) is None
