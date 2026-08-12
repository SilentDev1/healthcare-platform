"""Deterministic distance and comparable published-price insights.

These helpers never fabricate savings and never use AI. A price difference is
only ever computed between semantically comparable published prices:

* the SAME canonical procedure (every item here is one procedure), AND
* a compatible service setting (same primary setting), AND
* a single exact published cash / self-pay price on each side.

A published cash *range* (min != max) signals laterality/bundle variation and is
never collapsed into one number for a savings claim (addendum §22, §23). Cash is
never compared against negotiated rates (§7, §11). Missing pricing is never a
savings input and never implies the hospital lacks the service (§21).
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from packages.geo import haversine_miles

Item = dict[str, Any]
Coords = dict[Any, tuple[float, float]]


def _single_cash(item: Item) -> Decimal | None:
    """The one comparable published cash value, or None for ranges/missing."""
    minimum = item.get("cash_price_min")
    maximum = item.get("cash_price_max")
    if minimum is None or maximum is None:
        return None
    low = Decimal(str(minimum))
    high = Decimal(str(maximum))
    if low != high:
        return None
    return low


def _primary_setting(item: Item) -> str | None:
    settings = item.get("service_settings") or []
    return settings[0] if settings else None


def annotate(
    items: list[Item],
    *,
    coords: Coords,
    origin: tuple[float, float] | None,
    radius_miles: float | None = None,
) -> list[Item]:
    """Attach distance and deterministic comparable-cash difference fields.

    Returns the (possibly radius-filtered) items. Fields added per item:
      distance_miles, comparable_cash_price, published_price_difference,
      difference_basis, is_lowest_comparable_cash, comparable_cash_facility_count,
      lower_priced_nearby_option.
    """
    # 1. Distance (deterministic; None when origin or location coordinates are
    #    unknown — the UI then shows no distance rather than a guess).
    for item in items:
        distance = None
        if origin is not None:
            coord = coords.get(item["facility_location_id"])
            if coord is not None:
                distance = round(haversine_miles(origin[0], origin[1], coord[0], coord[1]), 1)
        item["distance_miles"] = distance

    # 2. Radius filter only drops items with a KNOWN distance beyond the radius.
    #    Unknown-distance items stay visible so we never imply unavailability.
    kept = items
    if origin is not None and radius_miles is not None:
        kept = [
            item
            for item in items
            if item["distance_miles"] is None or item["distance_miles"] <= radius_miles
        ]

    # 3. Comparable cash cohorts, grouped by compatible primary service setting.
    for item in kept:
        item["comparable_cash_price"] = None
        item["published_price_difference"] = None
        item["difference_basis"] = None
        item["is_lowest_comparable_cash"] = False
        item["comparable_cash_facility_count"] = 0
        item["lower_priced_nearby_option"] = None

    cohorts: dict[str | None, list[Item]] = {}
    for item in kept:
        cash = _single_cash(item)
        if cash is None:
            continue
        item["comparable_cash_price"] = str(cash)
        cohorts.setdefault(_primary_setting(item), []).append(item)

    for cohort in cohorts.values():
        if len(cohort) < 2:
            # A single comparable price is not a comparison; leave no claim.
            for item in cohort:
                item["comparable_cash_facility_count"] = 1
            continue
        lowest = min(Decimal(str(item["comparable_cash_price"])) for item in cohort)
        lowest_item = min(cohort, key=lambda entry: Decimal(str(entry["comparable_cash_price"])))
        for item in cohort:
            cash = Decimal(str(item["comparable_cash_price"]))
            item["comparable_cash_facility_count"] = len(cohort)
            item["published_price_difference"] = str(cash - lowest)
            item["difference_basis"] = "vs_lowest_comparable_published_cash"
            item["is_lowest_comparable_cash"] = cash == lowest
            if cash > lowest:
                item["lower_priced_nearby_option"] = {
                    "facility_id": str(lowest_item["facility_id"]),
                    "facility_name": lowest_item["facility_name"],
                    "facility_location_id": str(lowest_item["facility_location_id"]),
                    "comparable_cash_price": lowest_item["comparable_cash_price"],
                    "published_price_difference": str(cash - lowest),
                    "distance_miles": lowest_item.get("distance_miles"),
                }
    return kept
