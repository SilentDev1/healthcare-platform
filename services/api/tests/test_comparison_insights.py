"""Deterministic distance + comparable-savings tests (Phase 4.8 addendum §36)."""

import uuid

from packages.geo import haversine_miles, resolve_origin
from services.api.app.comparison_insights import annotate


def _item(
    name: str,
    cash_min: int | None,
    cash_max: int | None,
    settings: list[str],
    loc: uuid.UUID | None = None,
) -> dict[str, object]:
    return {
        "facility_id": uuid.uuid4(),
        "facility_name": name,
        "facility_location_id": loc or uuid.uuid4(),
        "cash_price_min": cash_min,
        "cash_price_max": cash_max,
        "service_settings": settings,
    }


# --- geo -------------------------------------------------------------------


def test_haversine_zero_and_known_distance() -> None:
    assert haversine_miles(42.75, -71.49, 42.75, -71.49) == 0.0
    nashua_to_boston = haversine_miles(42.749074, -71.490544, 42.338551, -71.018253)
    assert 30 < nashua_to_boston < 45  # ~37 miles


def test_resolve_origin_zip_and_city_cross_state() -> None:
    assert resolve_origin(postal_code="03060") is not None  # Nashua NH
    assert resolve_origin(city="Boston", state="MA") is not None  # cross-state MA
    nh = resolve_origin(postal_code="03060")
    ma = resolve_origin(city="Lowell", state="MA")
    assert nh and ma
    assert haversine_miles(nh[0], nh[1], ma[0], ma[1]) > 0


def test_resolve_origin_unknown_returns_none() -> None:
    assert resolve_origin(postal_code="99999") is None
    assert resolve_origin(city="Nowhereville", state="NH") is None
    assert resolve_origin() is None


# --- comparable cash savings ----------------------------------------------


def test_cash_to_cash_difference_and_lowest() -> None:
    a = _item("A", 389, 389, ["outpatient"])
    b = _item("B", 625, 625, ["outpatient"])
    annotate([a, b], coords={}, origin=None)
    assert a["is_lowest_comparable_cash"] is True
    assert a["published_price_difference"] == "0"
    assert b["published_price_difference"] == "236"
    assert b["difference_basis"] == "vs_lowest_comparable_published_cash"
    option = b["lower_priced_nearby_option"]
    assert isinstance(option, dict) and option["facility_name"] == "A"
    assert a["comparable_cash_facility_count"] == 2


def test_cash_range_never_produces_savings() -> None:
    a = _item("A", 350, 428, ["outpatient"])  # range -> not comparable
    b = _item("B", 625, 625, ["outpatient"])
    annotate([a, b], coords={}, origin=None)
    assert a["comparable_cash_price"] is None
    assert a["published_price_difference"] is None
    assert b["published_price_difference"] is None  # alone -> no claim
    assert b["is_lowest_comparable_cash"] is False


def test_different_settings_are_not_compared() -> None:
    a = _item("A", 389, 389, ["outpatient"])
    b = _item("B", 625, 625, ["inpatient"])
    annotate([a, b], coords={}, origin=None)
    assert a["published_price_difference"] is None
    assert b["published_price_difference"] is None


def test_negotiated_only_item_is_never_a_cash_comparison() -> None:
    a = _item("A", None, None, ["outpatient"])
    a["negotiated_price_min"] = 250
    a["negotiated_price_max"] = 5000
    b = _item("B", 389, 389, ["outpatient"])
    annotate([a, b], coords={}, origin=None)
    assert a["comparable_cash_price"] is None
    assert a["published_price_difference"] is None
    assert b["published_price_difference"] is None  # alone -> no claim


def test_distance_and_radius_filter() -> None:
    loc_a, loc_b, loc_c = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    a = _item("Near", 389, 389, ["outpatient"], loc=loc_a)
    b = _item("Far", 625, 625, ["outpatient"], loc=loc_b)
    c = _item("Unknown", 500, 500, ["outpatient"], loc=loc_c)  # no coords
    origin = (42.749074, -71.490544)  # Nashua
    coords = {
        loc_a: (42.75, -71.46),  # ~1.5 mi
        loc_b: (43.6, -71.5),  # ~59 mi
    }
    out = annotate([a, b, c], coords=coords, origin=origin, radius_miles=25)
    names = {item["facility_name"] for item in out}
    assert "Near" in names and "Unknown" in names  # unknown distance stays visible
    assert "Far" not in names  # known distance beyond radius dropped
    distance_a = a["distance_miles"]
    assert isinstance(distance_a, float) and distance_a < 25
    assert c["distance_miles"] is None


def test_no_origin_means_no_distance() -> None:
    a = _item("A", 389, 389, ["outpatient"])
    annotate([a], coords={}, origin=None)
    assert a["distance_miles"] is None
