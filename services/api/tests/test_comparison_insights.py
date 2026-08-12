"""Distance, billing-component comparability, and savings tests (Phase 4.8)."""

import uuid
from decimal import Decimal

from packages.geo import haversine_miles, resolve_origin
from services.api.app.comparison_insights import (
    DIRECTLY_COMPARABLE,
    NOT_COMPARABLE,
    annotate,
    summarize_cash_components,
)


def _item(
    name: str,
    cash_min: int | None,
    cash_max: int | None,
    loc: uuid.UUID | None = None,
    *,
    setting: str = "outpatient",
    scope: str | None = "facility",
    status: str = DIRECTLY_COMPARABLE,
) -> dict[str, object]:
    return {
        "facility_id": uuid.uuid4(),
        "facility_name": name,
        "facility_location_id": loc or uuid.uuid4(),
        "cash_price_min": cash_min,
        "cash_price_max": cash_max,
        "primary_service_setting": setting,
        "primary_billing_scope": scope,
        "comparability_status": status,
    }


# --- geo -------------------------------------------------------------------


def test_haversine_zero_and_known_distance() -> None:
    assert haversine_miles(42.75, -71.49, 42.75, -71.49) == 0.0
    nashua_to_boston = haversine_miles(42.749074, -71.490544, 42.338551, -71.018253)
    assert 30 < nashua_to_boston < 45


def test_resolve_origin_zip_and_city_cross_state() -> None:
    assert resolve_origin(postal_code="03060") is not None
    assert resolve_origin(city="Boston", state="MA") is not None
    nh = resolve_origin(postal_code="03060")
    ma = resolve_origin(city="Lowell", state="MA")
    assert nh and ma
    assert haversine_miles(nh[0], nh[1], ma[0], ma[1]) > 0


def test_resolve_origin_unknown_returns_none() -> None:
    assert resolve_origin(postal_code="99999") is None
    assert resolve_origin(city="Nowhereville", state="NH") is None


# --- billing-component comparability (the Cheshire case) -------------------


def test_facility_and_professional_are_separated_not_ranged() -> None:
    # Cheshire MRI brain: $1,356 facility fee + $175 professional fee.
    summary = summarize_cash_components(
        [
            (Decimal("1355.99"), "outpatient", "facility"),
            (Decimal("1355.99"), "inpatient", "facility"),
            (Decimal("174.98"), "outpatient", "professional"),
            (Decimal("174.98"), "inpatient", "professional"),
        ]
    )
    # The comparable primary is the outpatient facility fee, NOT a $175-$1356 range.
    assert summary["cash_price_min"] == "1355.99"
    assert summary["cash_price_max"] == "1355.99"
    assert summary["primary_billing_scope"] == "facility"
    assert summary["primary_service_setting"] == "outpatient"
    assert summary["comparability_status"] == DIRECTLY_COMPARABLE
    scopes = {p["billing_scope"] for p in summary["additional_published_prices"]}
    assert "professional" in scopes  # the $175 is listed separately, not ranged


def test_professional_only_is_not_comparable() -> None:
    summary = summarize_cash_components([(Decimal("174.98"), "outpatient", "professional")])
    assert summary["comparability_status"] == NOT_COMPARABLE
    assert summary["primary_billing_scope"] is None


def test_no_cash_is_unknown() -> None:
    summary = summarize_cash_components([])
    assert summary["cash_price_min"] is None


# --- savings guardrails ----------------------------------------------------


def test_cash_to_cash_difference_and_lowest() -> None:
    a = _item("A", 389, 389)
    b = _item("B", 625, 625)
    annotate([a, b], coords={}, origin=None)
    assert a["is_lowest_comparable_cash"] is True
    assert b["published_price_difference"] == "236"
    option = b["lower_priced_nearby_option"]
    assert isinstance(option, dict) and option["facility_name"] == "A"


def test_facility_is_never_compared_to_professional() -> None:
    facility = _item("Facility", 1356, 1356, scope="facility")
    professional = _item("ProfessionalOnly", 175, 175, scope=None, status=NOT_COMPARABLE)
    annotate([facility, professional], coords={}, origin=None)
    # No cohort forms: professional is not comparable, facility is alone.
    assert facility["published_price_difference"] is None
    assert professional["published_price_difference"] is None


def test_different_billing_scope_not_compared() -> None:
    facility = _item("A", 1356, 1356, scope="facility")
    globalfee = _item("B", 1600, 1600, scope="global")
    annotate([facility, globalfee], coords={}, origin=None)
    assert facility["published_price_difference"] is None
    assert globalfee["published_price_difference"] is None


def test_different_setting_not_compared() -> None:
    out = _item("A", 389, 389, setting="outpatient")
    inp = _item("B", 625, 625, setting="inpatient")
    annotate([out, inp], coords={}, origin=None)
    assert out["published_price_difference"] is None
    assert inp["published_price_difference"] is None


def test_cash_range_never_produces_savings() -> None:
    a = _item("A", 350, 428)  # range -> not a single comparable value
    b = _item("B", 625, 625)
    annotate([a, b], coords={}, origin=None)
    assert a["comparable_cash_price"] is None
    assert b["published_price_difference"] is None  # alone -> no claim


def test_distance_and_radius_filter() -> None:
    loc_a, loc_b, loc_c = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    a = _item("Near", 389, 389, loc=loc_a)
    b = _item("Far", 625, 625, loc=loc_b)
    c = _item("Unknown", 500, 500, loc=loc_c)
    origin = (42.749074, -71.490544)
    coords = {loc_a: (42.75, -71.46), loc_b: (43.6, -71.5)}
    out = annotate([a, b, c], coords=coords, origin=origin, radius_miles=25)
    names = {item["facility_name"] for item in out}
    assert "Near" in names and "Unknown" in names
    assert "Far" not in names
    distance_a = a["distance_miles"]
    assert isinstance(distance_a, float) and distance_a < 25
    assert c["distance_miles"] is None
