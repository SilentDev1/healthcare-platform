"""Deterministic distance, billing-component comparability, and savings.

These helpers never fabricate savings and never use AI. Two records may both map
to the same consumer procedure yet still not be price-comparable: a facility fee
and a professional (physician) fee are different billing components. A price
difference is only ever computed between prices that share:

* the SAME canonical procedure (every item here is one procedure), AND
* a compatible service setting, AND
* a compatible billing scope (complete facility charge, not a partial
  professional/technical component), AND
* a single exact published cash / self-pay price on each side.

Never compared: cash vs negotiated, cross-procedure, incompatible setting,
facility vs professional/technical/component, or a published cash *range*. Cash
ranges and unknown scopes are surfaced, never collapsed into a savings claim.
Missing pricing is never a savings input and never implies the hospital lacks
the service.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from packages.geo import haversine_miles

Item = dict[str, Any]
Coords = dict[Any, tuple[float, float]]

# Comparability status values (deterministic, auditable — never AI-generated).
DIRECTLY_COMPARABLE = "directly_comparable"
PARTIALLY_COMPARABLE = "partially_comparable"
NOT_COMPARABLE = "not_comparable"
UNKNOWN = "unknown"

# Billing scopes that represent a complete facility charge a self-pay consumer
# can compare across hospitals. Partial components are shown but never compared.
_COMPARABLE_SCOPES = ("global", "combined", "facility", "bundled")
_SETTING_RANK = {
    "outpatient": 0,
    "ambulatory_surgical_center": 1,
    "emergency_department": 2,
    "inpatient": 3,
}
_SCOPE_RANK = {"global": 0, "combined": 1, "facility": 2, "bundled": 3}


def summarize_cash_components(
    cash_details: list[tuple[Any, str, str]],
) -> dict[str, Any]:
    """Group published cash prices by (service setting, billing scope).

    ``cash_details`` is an iterable of (amount, service_setting, billing_scope).
    Returns the single comparable primary cash price (when a complete facility
    charge exists), every published component listed separately, and a
    deterministic comparability status. Never min/maxes across components.
    """
    groups: dict[tuple[str, str], list[Decimal]] = {}
    for amount, setting, scope in cash_details:
        if amount is None:
            continue
        key = (setting or "unknown", (scope or "unknown").lower())
        groups.setdefault(key, []).append(Decimal(str(amount)))

    def entry(key: tuple[str, str]) -> dict[str, Any]:
        amounts = groups[key]
        return {
            "service_setting": key[0],
            "billing_scope": key[1],
            "amount_min": str(min(amounts)),
            "amount_max": str(max(amounts)),
        }

    base: dict[str, Any] = {
        "cash_price_min": None,
        "cash_price_max": None,
        "primary_service_setting": None,
        "primary_billing_scope": None,
        "comparability_status": UNKNOWN,
        "comparability_reason": None,
        "additional_published_prices": [],
    }
    if not groups:
        return base

    comparable_keys = [key for key in groups if key[1] in _COMPARABLE_SCOPES]
    has_unknown_scope = any(key[1] == "unknown" for key in groups)

    if comparable_keys:
        primary = min(
            comparable_keys,
            key=lambda key: (_SETTING_RANK.get(key[0], 9), _SCOPE_RANK.get(key[1], 9)),
        )
        amounts = groups[primary]
        others = [entry(key) for key in groups if key != primary]
        status = DIRECTLY_COMPARABLE if len(set(amounts)) == 1 else PARTIALLY_COMPARABLE
        reason = (
            "Additional published prices represent other settings or billing components."
            if others
            else None
        )
        return {
            "cash_price_min": str(min(amounts)),
            "cash_price_max": str(max(amounts)),
            "primary_service_setting": primary[0],
            "primary_billing_scope": primary[1],
            "comparability_status": status,
            "comparability_reason": reason,
            "additional_published_prices": others,
        }

    # No complete facility charge — only partial components (professional /
    # technical / component) or unknown scope. Surface the prices but never treat
    # them as a comparable facility price, and exclude them from savings.
    all_amounts = [amount for amounts in groups.values() for amount in amounts]
    return {
        "cash_price_min": str(min(all_amounts)),
        "cash_price_max": str(max(all_amounts)),
        "primary_service_setting": None,
        "primary_billing_scope": None,
        "comparability_status": UNKNOWN if has_unknown_scope else NOT_COMPARABLE,
        "comparability_reason": (
            "Only partial billing components are published; not a directly "
            "comparable facility price."
        ),
        "additional_published_prices": [entry(key) for key in groups],
    }


def _comparable_single_cash(item: Item) -> Decimal | None:
    """The comparable cash value for savings, or None.

    Requires a directly comparable primary (complete facility charge, known
    setting and scope) and a single exact cash amount. Ranges, partial
    components, and unknown scopes never qualify.
    """
    if item.get("comparability_status") != DIRECTLY_COMPARABLE:
        return None
    if not item.get("primary_service_setting") or not item.get("primary_billing_scope"):
        return None
    minimum = item.get("cash_price_min")
    maximum = item.get("cash_price_max")
    if minimum is None or maximum is None:
        return None
    low = Decimal(str(minimum))
    high = Decimal(str(maximum))
    if low != high:
        return None
    return low


def annotate(
    items: list[Item],
    *,
    coords: Coords,
    origin: tuple[float, float] | None,
    radius_miles: float | None = None,
) -> list[Item]:
    """Attach distance and deterministic comparable-cash difference fields."""
    for item in items:
        distance = None
        if origin is not None:
            coord = coords.get(item["facility_location_id"])
            if coord is not None:
                distance = round(haversine_miles(origin[0], origin[1], coord[0], coord[1]), 1)
        item["distance_miles"] = distance

    kept = items
    if origin is not None and radius_miles is not None:
        kept = [
            item
            for item in items
            if item["distance_miles"] is None or item["distance_miles"] <= radius_miles
        ]

    for item in kept:
        item["comparable_cash_price"] = None
        item["published_price_difference"] = None
        item["difference_basis"] = None
        item["is_lowest_comparable_cash"] = False
        item["comparable_cash_facility_count"] = 0
        item["lower_priced_nearby_option"] = None

    # Cohorts require the SAME setting AND billing scope — facility is never
    # compared against professional, and outpatient never against inpatient.
    cohorts: dict[tuple[str, str], list[Item]] = {}
    for item in kept:
        cash = _comparable_single_cash(item)
        if cash is None:
            continue
        item["comparable_cash_price"] = str(cash)
        cohort_key = (item["primary_service_setting"], item["primary_billing_scope"])
        cohorts.setdefault(cohort_key, []).append(item)

    for cohort in cohorts.values():
        if len(cohort) < 2:
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
