"""Non-hospital published-price ingestion: real prices, NON-PUBLIC, exact-map, provenance."""

from __future__ import annotations

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from packages.database import (
    Base,
    Facility,
    FacilityLocation,
    Organization,
    Procedure,
    ProcedureCategory,
)
from packages.database.pricing_models import FacilityProcedurePriceSummary
from scripts.ingest_nonhospital_published_prices import CANDIDATE_STATUS, _load_data_ok, ingest


def _session() -> Session:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    return Session(engine)


DATA = {
    "organizations": [
        {
            "organization": "Derry Imaging",
            "source_url": "https://derryimaging.com/prices",
            "source_format": "HTML",
            "retrieval_date": "2026-08-16",
            "price_scope": "org-wide",
            "service_setting": "outpatient",
            "prices": [
                {"published_description": "X-Ray (Chest)", "canonical_slug": "chest-x-ray",
                 "cash_price": 95, "component_scope": "global", "mapping_confidence": "exact_name"},
                {"published_description": "MRI Brain", "canonical_slug": "no-such-canonical",
                 "cash_price": 800, "component_scope": "global", "mapping_confidence": "x"},
            ],
        }
    ]
}


def _fixture(session: Session) -> None:
    org = Organization(canonical_name="Derry Imaging", display_name="Derry Imaging",
                       organization_type="imaging_center", active=True)
    session.add(org)
    session.flush()
    for i in range(2):  # org-wide price attaches to every location
        f = Facility(legal_name=f"DI {i}", display_name=f"DI {i}", facility_type="Imaging Center",
                     active=True, organization_id=org.id)
        session.add(f)
        session.flush()
        session.add(FacilityLocation(
            facility_id=f.id, location_name=f"DI {i}", location_type="service_location", active=True,
            address_line_1=f"{i} Main St", city="Derry", state="NH",
            postal_code="03038"))
    cat = ProcedureCategory(slug="imaging", name="Imaging", description="d", sort_order=0)
    session.add(cat)
    session.flush()
    session.add(Procedure(
        slug="chest-x-ray", consumer_name="Chest X-ray", short_description="s",
        long_description="l", category_id=cat.id, service_setting="outpatient",
        complexity="low", active=True,
    ))
    session.commit()


def test_writes_nonpublic_candidate_prices_at_every_location() -> None:
    session = _session()
    _fixture(session)
    result = ingest(session, data=DATA)
    # chest-x-ray maps -> 1 candidate per location (2 locations); MRI has no canonical -> unmatched
    assert result["candidate_summaries"] == 2
    assert result["unmatched_procedures"] == 1
    rows = list(session.scalars(select(FacilityProcedurePriceSummary)))
    assert len(rows) == 2
    for r in rows:
        assert r.publication_status == CANDIDATE_STATUS
        assert r.publication_status != "publishable"  # never consumer-visible
        assert float(r.cash_price_min) == 95.0
        assert r.source_file_id is not None  # provenance
        assert "NON-PUBLIC candidate" in (r.notes or "")


def test_rejects_zero_or_missing_price() -> None:
    session = _session()
    _fixture(session)
    bad = {"organizations": [dict(DATA["organizations"][0], prices=[
        {"published_description": "X", "canonical_slug": "chest-x-ray", "cash_price": 0,
         "component_scope": "g", "mapping_confidence": "x"}])]}
    try:
        ingest(session, data=bad)
        raise AssertionError("should have rejected $0 price")
    except ValueError:
        pass


def test_idempotent() -> None:
    session = _session()
    _fixture(session)
    ingest(session, data=DATA)
    second = ingest(session, data=DATA)
    assert second["candidate_summaries"] == 0


def test_dry_run_persists_nothing() -> None:
    session = _session()
    _fixture(session)
    ingest(session, data=DATA, dry_run=True)
    assert session.scalar(select(func.count()).select_from(FacilityProcedurePriceSummary)) == 0


def test_shipped_data_file_is_valid() -> None:
    assert _load_data_ok()
