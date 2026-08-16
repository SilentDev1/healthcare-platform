"""Multi-state hospital directory: filtering, search, pagination, and scale.

Seeds synthetic (non-production) fixtures across multiple states to prove the
directory is state-neutral and scales past NH before Massachusetts is added.
"""

from __future__ import annotations

import time
import uuid
from datetime import UTC, date, datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from packages.database import (
    Base,
    Facility,
    FacilityLocation,
    FacilityProcedurePriceSummary,
    FacilityQualityMeasureObservation,
    ImportRun,
    LocationCapability,
    Organization,
    QualityMeasureDefinition,
    SourceFile,
)
from packages.database.models import ImportStatus, SourceStatus
from services.api.app.main import facilities_directory
from services.api.app.schemas import FacilityDirectoryResponse

_TYPES = ["Acute Care Hospitals", "Critical Access Hospitals"]
# Distinct publishable procedures per facility -> pricing_status buckets:
#   0 -> not_available_yet, 5 -> limited, 15 -> available
_PRICE_BUCKETS = [0, 5, 15]


def _engine() -> Session:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)()


def _seed(session: Session, count: int, states: list[str]) -> None:
    source = SourceFile(
        source_name="fixture",
        source_url="https://example.test/prices.json",  # non-fixture (not file://)
        source_type="json",
        storage_path="p",
        checksum_sha256="a" * 64,
        file_size=1,
        parser_version="t",
        status=SourceStatus.COMPLETED,
    )
    session.add(source)
    session.flush()
    run = ImportRun(
        importer_name="fixture", status=ImportStatus.COMPLETED, source_file_id=source.id
    )
    session.add(run)
    rating_def = QualityMeasureDefinition(
        cms_measure_id="OVERALL_RATING",
        measure_name="Overall",
        category="summary",
        directionality="higher_is_better",
        data_type="ordinal",
    )
    session.add(rating_def)
    session.flush()

    for index in range(count):
        facility = Facility(
            cms_certification_number=str(300000 + index),
            legal_name=f"Hospital {index:04d} LLC",
            display_name=f"Hospital {index:04d}",
            facility_type=_TYPES[index % len(_TYPES)],
        )
        session.add(facility)
        session.flush()
        state = states[index % len(states)]
        session.add(
            FacilityLocation(
                facility_id=facility.id,
                location_name=None,
                location_type="hospital_campus",
                address_line_1="1 Rd",
                city=f"City{index % 20:02d}",
                state=state,
                postal_code=f"{3000 + (index % 900):05d}",
            )
        )
        for _ in range(_PRICE_BUCKETS[index % len(_PRICE_BUCKETS)]):
            session.add(
                FacilityProcedurePriceSummary(
                    facility_id=facility.id,
                    procedure_id=uuid.uuid4(),
                    service_setting="outpatient",
                    record_count=1,
                    source_file_id=source.id,
                    publication_status="publishable",
                    completeness_score=1,
                )
            )
        if index % 4 == 0:
            session.add(
                FacilityQualityMeasureObservation(
                    facility_id=facility.id,
                    quality_measure_definition_id=rating_def.id,
                    source_file_id=source.id,
                    import_run_id=run.id,
                    source_record_identifier=str(index),
                    score="4",
                    reporting_period_end=date(2026, 1, 1),
                    observed_at=datetime.now(UTC),
                )
            )
    session.commit()


def _dir(session: Session, **kwargs: object) -> FacilityDirectoryResponse:
    params: dict[str, object] = {
        "page": 1,
        "page_size": 24,
        "state_code": None,
        "city": None,
        "search": None,
        "pricing_status": None,
        "facility_type": None,
        "sort": "name",
    }
    params.update(kwargs)
    return facilities_directory(session, **params)  # type: ignore[arg-type]


def test_directory_150_facilities_two_states() -> None:
    session = _engine()
    _seed(session, 150, ["NH", "MA"])

    all_resp = _dir(session)
    assert all_resp.total == 150
    assert all_resp.total_states == 2
    assert len(all_resp.items) == 24  # page 1 bounded

    nh = _dir(session, state_code="NH")
    assert nh.total == 75
    assert {item.state for item in nh.items} == {"NH"}

    # pagination preserves the state filter and advances.
    page1 = _dir(session, state_code="NH", page=1)
    page4 = _dir(session, state_code="NH", page=4)  # 75 -> 4 pages of 24
    assert len(page4.items) == 75 - 24 * 3
    assert {i.id for i in page1.items}.isdisjoint({i.id for i in page4.items})

    # name sort is ascending
    names = [item.display_name for item in nh.items]
    assert names == sorted(names)

    # pricing filter returns only well-covered facilities
    available = _dir(session, pricing_status="pricing_available")
    assert available.items
    assert all(item.published_procedure_count >= 10 for item in available.items)
    not_yet = _dir(session, pricing_status="pricing_not_available_yet")
    assert all(item.pricing_status == "pricing_not_available_yet" for item in not_yet.items)

    # search by city
    city = _dir(session, search="City03")
    assert city.items
    assert all(item.city == "City03" for item in city.items)

    # a CMS rating is enriched for facilities that have one
    assert any(item.cms_overall_rating == "4" for item in all_resp.items)


def _seed_provider_neutral(session: Session) -> None:
    """A hospital (priced) and an independent lab (no price) in NH."""
    source = SourceFile(
        source_name="fixture",
        source_url="https://example.test/prices.json",
        source_type="json",
        storage_path="p",
        checksum_sha256="b" * 64,
        file_size=1,
        parser_version="t",
        status=SourceStatus.COMPLETED,
    )
    session.add(source)
    session.flush()

    hosp_org = Organization(
        canonical_name="Concord Hospital",
        display_name="Concord Hospital",
        organization_type="hospital_system",
    )
    lab_org = Organization(
        canonical_name="Quest Diagnostics",
        display_name="Quest Diagnostics",
        organization_type="independent_lab",
    )
    session.add_all([hosp_org, lab_org])
    session.flush()

    hosp = Facility(
        cms_certification_number="300001",
        legal_name="Concord Hospital",
        display_name="Concord Hospital",
        facility_type="Acute Care Hospitals",
        organization_id=hosp_org.id,
    )
    lab = Facility(
        legal_name="Quest — Nashua",
        display_name="Quest Diagnostics — Nashua",
        organization_id=lab_org.id,
    )
    session.add_all([hosp, lab])
    session.flush()

    hosp_loc = FacilityLocation(
        facility_id=hosp.id,
        location_type="hospital_campus",
        address_line_1="250 Pleasant St",
        city="Concord",
        state="NH",
        postal_code="03301",
    )
    lab_loc = FacilityLocation(
        facility_id=lab.id,
        location_type="service_location",
        address_line_1="10 Main St",
        city="Nashua",
        state="NH",
        postal_code="03060",
    )
    session.add_all([hosp_loc, lab_loc])
    session.flush()

    session.add_all(
        [
            LocationCapability(facility_location_id=hosp_loc.id, capability="hospital"),
            LocationCapability(facility_location_id=hosp_loc.id, capability="laboratory"),
            LocationCapability(facility_location_id=lab_loc.id, capability="laboratory"),
        ]
    )
    # Only the hospital has published prices; the lab has NONE.
    for _ in range(12):
        session.add(
            FacilityProcedurePriceSummary(
                facility_id=hosp.id,
                facility_location_id=hosp_loc.id,
                procedure_id=uuid.uuid4(),
                service_setting="outpatient",
                record_count=1,
                source_file_id=source.id,
                publication_status="publishable",
                completeness_score=1,
            )
        )
    session.commit()


def test_directory_returns_organization_and_capabilities() -> None:
    session = _engine()
    _seed_provider_neutral(session)

    resp = _dir(session, state_code="NH")
    by_name = {item.display_name: item for item in resp.items}
    assert "Concord Hospital" in by_name
    assert "Quest Diagnostics — Nashua" in by_name

    hosp = by_name["Concord Hospital"]
    assert hosp.organization_type == "hospital_system"
    assert "hospital" in hosp.capabilities
    assert hosp.price_available is True

    lab = by_name["Quest Diagnostics — Nashua"]
    assert lab.organization_name == "Quest Diagnostics"
    assert lab.organization_type == "independent_lab"
    assert lab.capabilities == ["laboratory"]
    # The crux: a verified service location with NO Carevero price still appears.
    assert lab.price_available is False
    assert lab.pricing_status == "pricing_not_available_yet"

    # Response advertises capability options derived from real data.
    caps = {c.capability: c.location_count for c in resp.capabilities}
    assert caps["hospital"] == 1
    assert caps["laboratory"] == 2


def test_capability_filter_is_not_hospital_only() -> None:
    session = _engine()
    _seed_provider_neutral(session)

    labs = _dir(session, state_code="NH", capability="laboratory")
    names = {i.display_name for i in labs.items}
    assert names == {"Concord Hospital", "Quest Diagnostics — Nashua"}  # both have laboratory

    hospitals = _dir(session, state_code="NH", capability="hospital")
    assert {i.display_name for i in hospitals.items} == {"Concord Hospital"}


def test_price_available_filter_does_not_hide_unpriced_by_default() -> None:
    session = _engine()
    _seed_provider_neutral(session)

    default = _dir(session, state_code="NH")
    assert len(default.items) == 2  # unpriced lab included by default

    priced_only = _dir(session, state_code="NH", price_available=True)
    assert {i.display_name for i in priced_only.items} == {"Concord Hospital"}


def test_directory_500_facilities_six_states_scale() -> None:
    session = _engine()
    _seed(session, 500, ["NH", "MA", "ME", "VT", "RI", "CT"])

    start = time.perf_counter()
    resp = _dir(session, state_code="MA", sort="pricing")
    elapsed = time.perf_counter() - start

    assert resp.total == 500 // 6 or resp.total == 500 // 6 + 1
    assert {item.state for item in resp.items} == {"MA"}
    # pricing sort: most-covered first
    counts = [item.published_procedure_count for item in resp.items]
    assert counts == sorted(counts, reverse=True)
    # bounded query stays fast even at 500 facilities / 6 states (SQLite, no cache)
    assert elapsed < 2.0

    full = _dir(session, page_size=60)
    assert full.total_states == 6
    assert len(full.items) == 60
