"""Consumer-facing pricing coverage semantics."""

PRICING_NOT_AVAILABLE_YET = "pricing_not_available_yet"
LIMITED_PRICING = "limited_pricing"
PRICING_AVAILABLE = "pricing_available"


def consumer_pricing_status(published_procedure_count: int) -> str:
    """Classify actual consumer-usable procedure coverage.

    The current NH distribution has a natural gap between facilities with at
    most four published procedures and those with at least seventeen. Ten is
    therefore a stable boundary between limited and meaningful coverage.
    """
    if published_procedure_count <= 0:
        return PRICING_NOT_AVAILABLE_YET
    if published_procedure_count < 10:
        return LIMITED_PRICING
    return PRICING_AVAILABLE


def pricing_status_matches(actual: str, requested: str | None) -> bool:
    """Match current statuses while preserving the old map filter aliases."""
    if not requested:
        return True
    aliases = {
        "publishable": {LIMITED_PRICING, PRICING_AVAILABLE},
        "partial": {LIMITED_PRICING},
        "no_data": {PRICING_NOT_AVAILABLE_YET},
    }
    return actual in aliases.get(requested, {requested})
