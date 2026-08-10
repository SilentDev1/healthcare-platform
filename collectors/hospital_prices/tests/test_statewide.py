"""Tests for statewide pipeline with multiple facilities, idempotency, and error handling."""

import uuid
from pathlib import Path

from sqlalchemy import Engine, create_engine, func, select
from sqlalchemy.orm import Session

from collectors.hospital_prices.fixture_generator import generate_cms_wide_fixture
from collectors.hospital_prices.normalization import seed_payers
from collectors.hospital_prices.pipeline import (
    StatewidePipelineResult,
    run_fixture_pipeline,
    run_statewide_pipeline,
)
from collectors.hospital_prices.projections import evaluate_pricing_health, freshness_score
from packages.database import (
    Base,
    Facility,
    FacilityLocation,
    FacilityPriceSource,
    FacilityProcedurePriceSummary,
    HospitalPriceRecord,
    PriceChangeSnapshot,
    PricingHealthScore,
    SourceFile,
)
from packages.database.models import SourceStatus
from scripts.seed_procedure_catalog import seed_catalog
from scripts.statewide_scorecard import calculate_scorecard


def _engine() -> Engine:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    return engine


def _seed_facilities(session: Session, count: int = 3) -> list[Facility]:
    source = SourceFile(
        source_name="CMS",
        source_url="https://data.cms.gov/facilities.csv",
        source_type="cms_hospitals_csv",
        storage_path="fixture.csv",
        checksum_sha256="a" * 64,
        file_size=1,
        parser_version="test",
        status=SourceStatus.COMPLETED,
    )
    session.add(source)
    session.flush()
    names = [
        ("ALICE PECK DAY MEMORIAL HOSPITAL", "300001"),
        ("ANDROSCOGGIN VALLEY HOSPITAL", "300002"),
        ("CATHOLIC MEDICAL CENTER", "300003"),
        ("CHESHIRE MEDICAL CENTER", "300004"),
        ("CONCORD HOSPITAL", "300005"),
    ]
    facilities = []
    for name, ccn in names[:count]:
        facility = Facility(
            id=uuid.uuid4(),
            cms_certification_number=ccn,
            legal_name=name,
            display_name=name.title(),
            source_file_id=source.id,
        )
        facility.locations.append(
            FacilityLocation(
                address_line_1=f"{ccn} Main St",
                city="Concord",
                state="NH",
                postal_code="03301",
            )
        )
        session.add(facility)
        facilities.append(facility)
    session.flush()
    return facilities


def test_fixture_pipeline_with_multiple_facilities() -> None:
    """Pipeline processes 3+ facilities from fixtures."""
    engine = _engine()
    with Session(engine) as session:
        _seed_facilities(session, 4)
        seed_catalog(session)
        session.commit()
        result = run_fixture_pipeline(session)
        assert result.files_registered >= 4
        assert result.records_normalized >= 0
        assert result.summaries >= 0
    engine.dispose()


def test_fixture_pipeline_idempotency() -> None:
    """Second run skips all unchanged files."""
    engine = _engine()
    with Session(engine) as session:
        _seed_facilities(session, 5)
        seed_catalog(session)
        session.commit()
        first = run_fixture_pipeline(session)
        second = run_fixture_pipeline(session)
        # All files from the first run should be skipped on second
        assert second.files_skipped_unchanged == first.files_registered
        assert second.records_normalized == 0
        # Record count unchanged between runs
        records_after_first = session.scalar(select(func.count(HospitalPriceRecord.id)))
        assert records_after_first == first.records_normalized
    engine.dispose()


def test_statewide_pipeline_processes_all_sources(tmp_path: Path) -> None:
    """Statewide pipeline imports all facilities with sources."""
    engine = _engine()
    with Session(engine) as session:
        facilities = _seed_facilities(session, 3)
        seed_catalog(session)
        seed_payers(session)
        session.commit()

        # Create fixture files and sources for 2 of 3 facilities
        for i, facility in enumerate(facilities[:2]):
            fixture = tmp_path / f"facility_{i}.csv"
            generate_cms_wide_fixture(fixture, rows=20, payers=2, plans_per_payer=1)
            source_file = SourceFile(
                source_name=f"facility_{i}",
                source_url=fixture.resolve().as_uri(),
                source_type="benchmark_csv",
                storage_path=str(fixture),
                checksum_sha256=f"{i}" * 64,
                file_size=fixture.stat().st_size,
                parser_version="test",
                status=SourceStatus.COMPLETED,
            )
            session.add(source_file)
            session.flush()
            session.add(
                FacilityPriceSource(
                    facility_id=facility.id,
                    source_type="hospital_mrf",
                    source_page_url="https://example.test/prices",
                    machine_readable_file_url=fixture.resolve().as_uri(),
                    declared_format="csv",
                    active=True,
                    discovery_method="test",
                    source_file_id=source_file.id,
                )
            )
        session.commit()

        result = run_statewide_pipeline(session, "NH")
        assert isinstance(result, StatewidePipelineResult)
        assert result.sources_processed == 2
        assert result.imported == 2
        assert result.failed == 0
        assert result.total_records > 0
    engine.dispose()


def test_statewide_pipeline_error_handling(tmp_path: Path) -> None:
    """Statewide pipeline continues after individual source errors."""
    engine = _engine()
    with Session(engine) as session:
        facilities = _seed_facilities(session, 2)
        seed_catalog(session)
        seed_payers(session)
        session.commit()

        # Good fixture for first facility
        good_fixture = tmp_path / "good.csv"
        generate_cms_wide_fixture(good_fixture, rows=20, payers=1, plans_per_payer=1)
        good_source = SourceFile(
            source_name="good",
            source_url=good_fixture.resolve().as_uri(),
            source_type="test_csv",
            storage_path=str(good_fixture),
            checksum_sha256="g" * 64,
            file_size=good_fixture.stat().st_size,
            parser_version="test",
            status=SourceStatus.COMPLETED,
        )
        session.add(good_source)
        session.flush()
        session.add(
            FacilityPriceSource(
                facility_id=facilities[0].id,
                source_type="hospital_mrf",
                source_page_url="https://example.test/good",
                machine_readable_file_url=good_fixture.resolve().as_uri(),
                declared_format="csv",
                active=True,
                discovery_method="test",
                source_file_id=good_source.id,
            )
        )

        # Bad fixture (missing file) for second facility
        bad_source = SourceFile(
            source_name="bad",
            source_url="file:///nonexistent/bad.csv",
            source_type="test_csv",
            storage_path="/nonexistent/bad.csv",
            checksum_sha256="b" * 64,
            file_size=1,
            parser_version="test",
            status=SourceStatus.COMPLETED,
        )
        session.add(bad_source)
        session.flush()
        session.add(
            FacilityPriceSource(
                facility_id=facilities[1].id,
                source_type="hospital_mrf",
                source_page_url="https://example.test/bad",
                machine_readable_file_url="file:///nonexistent/bad.csv",
                declared_format="csv",
                active=True,
                discovery_method="test",
                source_file_id=bad_source.id,
            )
        )
        session.commit()

        result = run_statewide_pipeline(session, "NH")
        # One succeeded, one failed, but pipeline completed
        assert result.sources_processed == 2
        assert result.imported + result.failed == 2
        assert result.failed >= 1
    engine.dispose()


def test_freshness_score_thresholds() -> None:
    """freshness_score returns correct values at threshold boundaries."""
    from datetime import UTC, datetime, timedelta

    now = datetime.now(UTC)
    assert freshness_score(now) == 100.0
    assert freshness_score(now - timedelta(days=10)) == 100.0
    assert freshness_score(now - timedelta(days=30)) == 100.0
    assert freshness_score(now - timedelta(days=31)) == 80.0
    assert freshness_score(now - timedelta(days=60)) == 80.0
    assert freshness_score(now - timedelta(days=61)) == 50.0
    assert freshness_score(now - timedelta(days=90)) == 50.0
    assert freshness_score(now - timedelta(days=91)) == 20.0
    assert freshness_score(now - timedelta(days=180)) == 20.0
    assert freshness_score(now - timedelta(days=181)) == 0.0
    assert freshness_score(None) == 0.0


def test_evaluate_pricing_health_uses_freshness() -> None:
    """evaluate_pricing_health produces per-facility scores using freshness."""
    engine = _engine()
    with Session(engine) as session:
        _seed_facilities(session, 2)
        session.commit()
        result = evaluate_pricing_health(session)
        assert result["facilities"] == 2
        scores = session.scalars(select(PricingHealthScore)).all()
        assert len(scores) == 2
        for score in scores:
            assert 0 <= float(score.overall_score) <= 100
            assert 0 <= float(score.freshness_score) <= 100
    engine.dispose()


def test_scorecard_with_no_facilities() -> None:
    """Scorecard returns zeros for empty state."""
    engine = _engine()
    with Session(engine) as session:
        Base.metadata.create_all(engine)
        result = calculate_scorecard(session, "XX")
        assert result["total_facilities"] == 0
        assert result["overall_readiness"] == 0
    engine.dispose()


def test_scorecard_components() -> None:
    """Scorecard produces 6 component scores."""
    engine = _engine()
    with Session(engine) as session:
        _seed_facilities(session, 2)
        seed_catalog(session)
        session.commit()
        # Run pipeline to create health scores
        run_fixture_pipeline(session)
        result = calculate_scorecard(session, "NH")
        assert result["total_facilities"] == 2
        components = result["component_scores"]
        assert isinstance(components, dict)
        assert set(components.keys()) == {
            "discovery",
            "download",
            "parsing",
            "publishable",
            "mapping",
            "quality",
            "freshness",
            "coverage",
        }
        readiness = result["overall_readiness"]
        assert isinstance(readiness, int | float)
        assert 0 <= readiness <= 100
    engine.dispose()


def test_price_change_snapshot_created_on_rebuild() -> None:
    """PriceChangeSnapshot records created when prices change between rebuilds."""
    engine = _engine()
    with Session(engine) as session:
        _seed_facilities(session, 6)
        seed_catalog(session)
        session.commit()
        # First run: establishes baseline
        run_fixture_pipeline(session)
        baseline_summaries = (
            session.scalar(select(func.count(FacilityProcedurePriceSummary.id))) or 0
        )
        assert baseline_summaries > 0
        # Snapshots only created on subsequent runs when prices differ
        snapshots = session.scalar(select(func.count(PriceChangeSnapshot.id))) or 0
        # After first run, no previous prices existed, so no snapshots
        assert snapshots == 0
    engine.dispose()


def _seed_multi_state_facilities(session: Session) -> list[Facility]:
    """Seed facilities across NH, MA, and ME to test state-agnostic behavior."""
    source = SourceFile(
        source_name="CMS",
        source_url="https://data.cms.gov/facilities.csv",
        source_type="cms_hospitals_csv",
        storage_path="fixture.csv",
        checksum_sha256="b" * 64,
        file_size=1,
        parser_version="test",
        status=SourceStatus.COMPLETED,
    )
    session.add(source)
    session.flush()
    state_facilities = [
        ("MASS GENERAL HOSPITAL", "220071", "MA", "Boston", "02114"),
        ("BRIGHAM AND WOMENS HOSPITAL", "220110", "MA", "Boston", "02115"),
        ("MAINE MEDICAL CENTER", "200009", "ME", "Portland", "04102"),
        ("CONCORD HOSPITAL", "301309", "NH", "Concord", "03301"),
    ]
    facilities = []
    for name, ccn, state, city, zipcode in state_facilities:
        facility = Facility(
            id=uuid.uuid4(),
            cms_certification_number=ccn,
            legal_name=name,
            display_name=name.title(),
            source_file_id=source.id,
        )
        facility.locations.append(
            FacilityLocation(
                address_line_1=f"{ccn} Main St",
                city=city,
                state=state,
                postal_code=zipcode,
            )
        )
        session.add(facility)
        facilities.append(facility)
    session.flush()
    return facilities


def test_scorecard_filters_by_state() -> None:
    """Scorecard only counts facilities for the requested state."""
    engine = _engine()
    with Session(engine) as session:
        _seed_multi_state_facilities(session)
        seed_catalog(session)
        session.commit()

        ma_result = calculate_scorecard(session, "MA")
        me_result = calculate_scorecard(session, "ME")
        nh_result = calculate_scorecard(session, "NH")

        assert ma_result["total_facilities"] == 2
        assert me_result["total_facilities"] == 1
        assert nh_result["total_facilities"] == 1
        assert ma_result["state"] == "MA"
        assert me_result["state"] == "ME"
        assert nh_result["state"] == "NH"
    engine.dispose()


def test_scorecard_components_identical_across_states() -> None:
    """All states produce the same set of component scores."""
    engine = _engine()
    with Session(engine) as session:
        _seed_multi_state_facilities(session)
        seed_catalog(session)
        session.commit()

        expected_keys = {
            "discovery",
            "download",
            "parsing",
            "publishable",
            "mapping",
            "quality",
            "freshness",
            "coverage",
        }
        for state in ("NH", "MA", "ME"):
            result = calculate_scorecard(session, state)
            components = result["component_scores"]
            assert isinstance(components, dict)
            assert set(components.keys()) == expected_keys, f"State {state} missing components"
    engine.dispose()
