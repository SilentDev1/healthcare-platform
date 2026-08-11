from services.api.app.coverage import (
    LIMITED_PRICING,
    PRICING_AVAILABLE,
    PRICING_NOT_AVAILABLE_YET,
    consumer_pricing_status,
    pricing_status_matches,
)


def test_consumer_status_is_based_on_published_procedure_count() -> None:
    assert consumer_pricing_status(0) == PRICING_NOT_AVAILABLE_YET
    assert consumer_pricing_status(1) == LIMITED_PRICING
    assert consumer_pricing_status(9) == LIMITED_PRICING
    assert consumer_pricing_status(10) == PRICING_AVAILABLE


def test_legacy_map_filter_aliases_remain_compatible() -> None:
    assert pricing_status_matches(LIMITED_PRICING, "publishable")
    assert pricing_status_matches(PRICING_AVAILABLE, "publishable")
    assert pricing_status_matches(LIMITED_PRICING, "partial")
    assert pricing_status_matches(PRICING_NOT_AVAILABLE_YET, "no_data")
    assert not pricing_status_matches(PRICING_NOT_AVAILABLE_YET, "publishable")
