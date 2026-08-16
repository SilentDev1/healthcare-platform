"""Provider-neutral capability search: registry, term matching, real-data-only resolution.

Proves capability terms resolve to canonical capability ids, that verified locations are
returned ONLY from location_capabilities (never fabricated), that a service location with
no price stays discoverable, and that existing procedure/category search is unaffected.
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from packages.database import (
    Base,
    Facility,
    FacilityLocation,
    LocationCapability,
    Organization,
)
from packages.search.location_capabilities import (
    SUPPORTED_LOCALES,
    consumer_location_capabilities,
    match_capability,
    resolve_capability_locations,
)
from packages.search.resolution import resolve_search
from packages.search.service import rebuild_index
from scripts.seed_procedure_catalog import seed_catalog


@pytest.fixture()
def session() -> Session:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    s = Session(engine)
    seed_catalog(s)
    s.commit()
    rebuild_index(s)
    s.commit()
    return s


def test_registry_defines_every_locale_and_is_unique() -> None:
    registry = consumer_location_capabilities()
    assert registry
    seen: set[str] = set()
    for capability in registry.values():
        assert set(capability.labels) == set(SUPPORTED_LOCALES)
        assert capability.capability not in seen
        seen.add(capability.capability)


@pytest.mark.parametrize(
    "query,expected",
    [
        ("urgent care", "urgent_care"),
        ("ER", "emergency_department"),
        ("emergency room", "emergency_department"),
        ("imaging", "imaging"),
        ("physical therapy", "physical_therapy"),
        ("rehab", "rehabilitation"),
        ("chiropractor", "chiropractic"),
        ("lab", "laboratory"),
        ("hospital", "hospital"),
        ("surgery center", "ambulatory_surgery"),
    ],
)
def test_match_capability(query: str, expected: str) -> None:
    assert match_capability(query) == expected


def test_non_capability_terms_do_not_match() -> None:
    # Procedure/category queries must NOT be captured as capabilities.
    assert match_capability("lab tests") is None
    assert match_capability("blood work") is None
    assert match_capability("cbc") is None
    assert match_capability("mri knee") is None
    assert match_capability("") is None


def _lab(session: Session, priced: bool = False) -> FacilityLocation:
    org = Organization(
        canonical_name="Quest", display_name="Quest", organization_type="independent_lab"
    )
    fac = Facility(legal_name="Quest — Nashua", display_name="Quest — Nashua", organization=org)
    loc = FacilityLocation(
        facility=fac,
        location_type="service_location",
        address_line_1="10 Main",
        city="Nashua",
        state="NH",
        postal_code="03060",
    )
    session.add_all([org, fac, loc])
    session.flush()
    session.add(LocationCapability(facility_location_id=loc.id, capability="laboratory"))
    session.commit()
    return loc


def test_capability_resolves_verified_locations_only(session: Session) -> None:
    # No lab-capable locations yet -> real-data-only means empty (no fabrication).
    assert resolve_capability_locations(session, "laboratory") == []

    loc = _lab(session)
    results = resolve_capability_locations(session, "laboratory", state="NH")
    assert len(results) == 1
    result = results[0]
    assert result.entity_type == "facility"
    assert result.metadata["capability"] == "laboratory"
    assert result.metadata["organization_type"] == "independent_lab"
    assert result.metadata["facility_location_id"] == str(loc.id)


def test_service_location_without_price_is_still_discoverable(session: Session) -> None:
    # The lab has a laboratory capability but NO price summary — it must still resolve.
    _lab(session, priced=False)
    results = resolve_capability_locations(session, "laboratory", state="NH")
    assert [r.title for r in results] == ["Quest — Nashua"]


def test_absent_capability_returns_nothing(session: Session) -> None:
    # Nobody has urgent_care capability -> no fabricated results.
    assert resolve_capability_locations(session, "urgent_care") == []


def test_existing_procedure_category_search_unaffected(session: Session) -> None:
    # Adding capability machinery must not change deterministic procedure/category search.
    assert resolve_search(session, "lab tests").canonical_category_slug == "laboratory"
    assert resolve_search(session, "blood work").canonical_category_slug == "laboratory"
    cbc = resolve_search(session, "cbc")
    assert cbc.intent_type.value == "procedure"
    assert any(
        x.entity_type == "procedure" and x.metadata.get("slug") == "complete-blood-count"
        for x in cbc.results
    )
