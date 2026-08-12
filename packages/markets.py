"""Supported-market (state) registry — data, not hardcoded UI logic.

The consumer hospital directory derives its state dropdown from the
`consumer_visible` markets here. Launching a new state is a config change
(flip `consumer_visible` / add an entry), never a React or route rewrite.

`status`:
  - "active"     — consumer pricing is live for this state.
  - "preparing"  — data is being ingested/validated; NOT shown to consumers.

Do NOT set MA `consumer_visible=True` until Phase 5 ingestion/validation gates
pass.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Market:
    code: str  # USPS two-letter state code
    name: str  # canonical English name (localized in the web layer)
    consumer_visible: bool
    status: str  # "active" | "preparing"


# Ordered by launch. Extend this list to add states; the API + web adapt.
SUPPORTED_MARKETS: tuple[Market, ...] = (
    Market("NH", "New Hampshire", consumer_visible=True, status="active"),
    Market("MA", "Massachusetts", consumer_visible=False, status="preparing"),
    Market("ME", "Maine", consumer_visible=False, status="preparing"),
    Market("VT", "Vermont", consumer_visible=False, status="preparing"),
    Market("RI", "Rhode Island", consumer_visible=False, status="preparing"),
    Market("CT", "Connecticut", consumer_visible=False, status="preparing"),
)

_BY_CODE: dict[str, Market] = {market.code: market for market in SUPPORTED_MARKETS}


def consumer_visible_markets() -> list[Market]:
    return [market for market in SUPPORTED_MARKETS if market.consumer_visible]


def consumer_visible_codes() -> set[str]:
    return {market.code for market in SUPPORTED_MARKETS if market.consumer_visible}


def market_name(code: str) -> str:
    market = _BY_CODE.get(code.upper())
    return market.name if market else code.upper()


def is_consumer_visible(code: str | None) -> bool:
    if not code:
        return False
    market = _BY_CODE.get(code.upper())
    return bool(market and market.consumer_visible)
