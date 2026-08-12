"""Deterministic offline geocoding and distance from bundled Census centroids.

Origin resolution and distance are fully deterministic (no external service, no
AI). Coordinates come from the public-domain U.S. Census Gazetteer bundled at
``data/fixtures/zip_city_centroids.json``. The schema is state-neutral and
US-ready; distance works across state lines because it is computed purely from
latitude/longitude, never from a state boundary.
"""

from __future__ import annotations

import json
import math
from functools import lru_cache
from pathlib import Path

_CENTROIDS_PATH = (
    Path(__file__).resolve().parents[1] / "data" / "fixtures" / "zip_city_centroids.json"
)
_EARTH_RADIUS_MILES = 3958.7613


@lru_cache(maxsize=1)
def _centroids() -> dict[str, dict[str, list[float]]]:
    data: dict[str, dict[str, list[float]]] = json.loads(
        _CENTROIDS_PATH.read_text(encoding="utf-8")
    )
    return data


def resolve_origin(
    *,
    postal_code: str | None = None,
    city: str | None = None,
    state: str | None = None,
) -> tuple[float, float] | None:
    """Resolve a consumer origin to (latitude, longitude), or None.

    A 5-digit postal code is the most precise and is tried first. A city falls
    back to a state-qualified lookup, then to an unambiguous single match across
    states. Ambiguous or unknown inputs return None (the caller shows no
    distance rather than guessing).
    """
    data = _centroids()
    if postal_code:
        digits = "".join(ch for ch in postal_code if ch.isdigit())[:5]
        if len(digits) == 5:
            coord = data["zips"].get(digits)
            if coord:
                return (coord[0], coord[1])
    if city:
        name = city.strip().lower()
        if state:
            coord = data["cities"].get(f"{state.strip().lower()}|{name}")
            if coord:
                return (coord[0], coord[1])
        matches = [coord for key, coord in data["cities"].items() if key.split("|", 1)[1] == name]
        if len(matches) == 1:
            return (matches[0][0], matches[0][1])
    return None


def haversine_miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in statute miles (deterministic)."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return 2 * _EARTH_RADIUS_MILES * math.asin(math.sqrt(a))
