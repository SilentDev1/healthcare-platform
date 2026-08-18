import uuid
from collections.abc import Generator
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select, update
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from collectors.hospital_prices.pipeline import run_fixture_pipeline
from collectors.hospital_prices.projections import rebuild_price_summaries
from packages.data_health import evaluate_data_health
from packages.database import (
    Base,
    Facility,
    FacilityLocation,
    FacilityQualityMeasureObservation,
    FacilitySourceObservation,
    ImportRun,
    Procedure,
    QualityMeasureDefinition,
    SourceFile,
    UnmatchedSourceRecord,
)
from packages.database.models import ImportStatus, SourceStatus
from packages.database.pricing_models import (
    FacilityProcedurePriceSummary,
    FacilityProcedurePriceSummarySource,
)
from packages.database.session import get_session
from packages.search import rebuild_index
from scripts.seed_procedure_catalog import seed_catalog
from services.api.app.main import _rate_windows, app
from services.api.app.settings import api_settings

engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
TestingSession = sessionmaker(bind=engine, expire_on_commit=False)


def override_session() -> Generator[Session, None, None]:
    with TestingSession() as session:
        yield session


app.dependency_overrides[get_session] = override_session
client = TestClient(app)


def setup_function() -> None:
    _rate_windows.clear()
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with TestingSession.begin() as session:
        source = SourceFile(
            source_name="test",
            source_url="https://example.test/data.csv",
            source_type="csv",
            storage_path="fixture.csv",
            checksum_sha256="a" * 64,
            file_size=1,
            parser_version="test",
            status=SourceStatus.COMPLETED,
        )
        session.add(source)
        session.flush()
        facility = Facility(
            id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
            cms_certification_number="300001",
            legal_name="Test Hospital",
            display_name="Test Hospital",
            facility_type="Acute Care Hospitals",
            ownership_type="Voluntary non-profit",
            phone="6035550100",
            active=True,
            source_file_id=source.id,
        )
        facility.locations.append(
            FacilityLocation(
                address_line_1="1 Main St", city="Concord", state="NH", postal_code="03301"
            )
        )
        session.add(facility)
        session.flush()
        run = ImportRun(
            importer_name="cms_quality:overall_rating",
            status=ImportStatus.COMPLETED,
            source_file_id=source.id,
            rows_read=1,
            rows_inserted=1,
        )
        definition = QualityMeasureDefinition(
            cms_measure_id="OVERALL_RATING",
            measure_name="Overall hospital rating",
            consumer_name="Overall hospital rating",
            category="overall_rating",
            unit="stars",
            directionality="higher_is_better",
            data_type="numeric",
        )
        session.add_all([run, definition])
        session.flush()
        session.add_all(
            [
                FacilitySourceObservation(
                    facility_id=facility.id,
                    source_file_id=source.id,
                    import_run_id=run.id,
                    source_record_identifier="300001|OVERALL_RATING||",
                    source_payload_hash="b" * 64,
                    raw_payload={"Facility ID": "300001", "rating": "4"},
                    observed_at=source.downloaded_at,
                ),
                FacilityQualityMeasureObservation(
                    facility_id=facility.id,
                    quality_measure_definition_id=definition.id,
                    source_file_id=source.id,
                    import_run_id=run.id,
                    source_record_identifier="300001|OVERALL_RATING||",
                    raw_value="4",
                    numeric_value=4,
                    text_value="4",
                    score="4",
                    observed_at=source.downloaded_at,
                ),
                UnmatchedSourceRecord(
                    source_file_id=source.id,
                    import_run_id=run.id,
                    source_record_identifier="399999|OVERALL_RATING||",
                    supplied_cms_certification_number="399999",
                    supplied_facility_name="Unmatched Hospital",
                    reason_unmatched="No facility with exact CMS certification number",
                    raw_payload={"Facility ID": "399999"},
                ),
            ]
        )
        session.flush()
        seed_catalog(session)
        rebuild_index(session)
        evaluate_data_health(session)
    with TestingSession() as session:
        run_fixture_pipeline(session)
        session.execute(
            update(SourceFile)
            .where(SourceFile.source_url.like("file://%"))
            .values(source_url="https://hospital.example.test/standardcharges.csv")
        )
        rebuild_price_summaries(session)
        session.commit()


def teardown_module() -> None:
    engine.dispose()


def test_health_and_ready() -> None:
    assert client.get("/health").json() == {"status": "ok"}
    assert client.get("/ready").json() == {"status": "ready"}


def test_facility_list_filters_and_paginates() -> None:
    response = client.get("/api/v1/facilities?state=nh&page=1&page_size=10")
    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert response.json()["items"][0]["cms_certification_number"] == "300001"


def test_facility_detail_and_not_found() -> None:
    found = client.get("/api/v1/facilities/00000000-0000-0000-0000-000000000001")
    assert found.status_code == 200
    missing = client.get("/api/v1/facilities/00000000-0000-0000-0000-000000000002")
    assert missing.status_code == 404


def test_public_quality_endpoints() -> None:
    measures = client.get("/api/v1/quality-measures?category=overall_rating")
    assert measures.status_code == 200
    assert measures.json()["items"][0]["cms_measure_id"] == "OVERALL_RATING"
    quality = client.get("/api/v1/facilities/00000000-0000-0000-0000-000000000001/quality")
    assert quality.status_code == 200
    assert quality.json()["items"][0]["score"] == "4"


def test_admin_read_endpoints() -> None:
    dashboard = client.get("/api/v1/admin/dashboard")
    assert dashboard.status_code == 200
    assert dashboard.json()["facilities_with_quality"] == 1
    for path in (
        "/api/v1/admin/import-runs?status=COMPLETED",
        "/api/v1/admin/source-files?source_type=csv",
        "/api/v1/admin/unmatched-records?status=pending",
        "/api/v1/admin/facilities?state=NH",
    ):
        response = client.get(path)
        assert response.status_code == 200
        assert response.json()["total"] == 1
    detail = client.get("/api/v1/admin/facilities/00000000-0000-0000-0000-000000000001")
    assert detail.status_code == 200
    assert detail.json()["quality_measure_count"] == 1
    quality = client.get("/api/v1/admin/facilities/00000000-0000-0000-0000-000000000001/quality")
    assert quality.status_code == 200


def test_phase_3_public_and_admin_endpoints() -> None:
    procedures = client.get("/api/v1/procedures?category=imaging")
    assert procedures.status_code == 200
    assert procedures.json()["total"] >= 10
    detail = client.get("/api/v1/procedures/mri-brain-without-contrast")
    assert detail.status_code == 200
    assert "multiple services" in detail.json()["billing_notice"]
    exact = client.get("/api/v1/search?q=MRI%20brain%20without%20contrast")
    assert exact.status_code == 200
    assert exact.json()["items"][0]["match_reason"] == "exact_primary"
    assert client.get("/api/v1/search?q=Concor&state=NH").json()["total"] == 1
    assert client.get("/api/v1/search?q=03060").json()["total"] == 0
    assert client.get("/api/v1/search/suggestions?q=MRI").status_code == 200
    for path in (
        "/api/v1/procedure-categories",
        "/api/v1/admin/identity-candidates",
        "/api/v1/admin/data-health",
        "/api/v1/admin/data-health/facilities",
        "/api/v1/admin/data-health/sources",
        "/api/v1/admin/pipeline-status",
    ):
        assert client.get(path).status_code == 200


def test_search_category_semantics_and_safe_clarification() -> None:
    category = client.get("/api/v1/search?q=lab%20tests&page_size=50")
    assert category.status_code == 200
    payload = category.json()
    assert payload["intent_type"] == "category"
    assert payload["deterministic_match"] is True
    assert payload["canonical_category_slug"] == "laboratory"
    category_item = next(
        item for item in payload["items"] if item["entity_type"] == "procedure_category"
    )
    members = [item for item in payload["items"] if item["match_reason"] == "category_member"]
    assert category_item["title"] == "Lab tests"
    assert category_item["metadata"]["procedure_count"] == len(members) == 11
    assert not any("price" in item["metadata"] for item in members)

    clarification = client.get("/api/v1/search?q=knee%20scan")
    assert clarification.status_code == 200
    clarified = clarification.json()
    assert clarified["intent_type"] == "ambiguous"
    assert clarified["clarification_needed"] is True
    assert all(item["metadata"]["slug"] != "knee-replacement" for item in clarified["items"])


def test_phase_4_pricing_endpoints_are_filtered_and_paginated() -> None:
    coverage = client.get("/api/v1/pricing/coverage")
    assert coverage.status_code == 200
    assert coverage.json()["facilities_with_publishable_prices"] == 1
    prices = client.get("/api/v1/procedures/mri-brain-without-contrast/prices?state=NH&page_size=5")
    assert prices.status_code == 200
    assert prices.json()["total"] >= 1
    assert "raw_payload" not in prices.text
    assert "final bill" in prices.json()["items"][0]["disclaimer"]
    comparison = client.get("/api/v1/procedures/mri-brain-without-contrast/comparison?state=NH")
    assert comparison.status_code == 200
    assert comparison.json()["active_facilities"] == 1
    assert comparison.json()["facilities_with_prices"] == 1
    assert comparison.json()["items"][0]["cms_overall_rating"] == "4"
    assert comparison.json()["items"][0]["price_available"] is True
    comparison_item = comparison.json()["items"][0]
    assert comparison_item["cash_price_value_count"] >= 1
    assert comparison_item["data_completeness"] in {
        "high_data_completeness",
        "some_details_unavailable",
    }
    assert comparison_item["source_count"] >= 1
    details = client.get(
        "/api/v1/procedures/mri-brain-without-contrast/locations/"
        f"{comparison_item['facility_location_id']}/price-details"
    )
    assert details.status_code == 200
    assert details.json()["records"]
    assert {record["semantic_type"] for record in details.json()["records"]} >= {
        "cash_self_pay",
        "gross_charge",
    }
    assert "raw_payload" not in details.text
    assert all(record["source_url"].startswith("https://") for record in details.json()["records"])
    facility_prices = client.get("/api/v1/facilities/00000000-0000-0000-0000-000000000001/prices")
    assert facility_prices.status_code == 200
    overview = client.get(
        "/api/v1/facilities/00000000-0000-0000-0000-000000000001/procedure-overview"
    )
    assert overview.status_code == 200
    assert overview.json()["procedure_count"] >= 1
    assert len(overview.json()["items"]) >= overview.json()["procedure_count"]
    assert overview.json()["items"][0]["summary_count"] >= 1
    assert "raw_payload" not in overview.text
    payer_response = client.get("/api/v1/pricing/payers")
    assert payer_response.status_code == 200
    payer_slug = payer_response.json()[0]["slug"]
    plan_response = client.get(f"/api/v1/pricing/plans?payer={payer_slug}")
    assert plan_response.status_code == 200
    assert plan_response.json()
    plan_id = plan_response.json()[0]["id"]
    insured_comparison = client.get(
        "/api/v1/procedures/mri-brain-without-contrast/comparison"
        f"?state=NH&payer={payer_slug}&plan={plan_id}"
    )
    assert insured_comparison.status_code == 200
    insured_item = insured_comparison.json()["items"][0]
    assert insured_item["selected_payer_name"]
    assert insured_item["selected_plan_name"]
    assert insured_item["matching_negotiated_rate_count"] >= 1
    insured_details = client.get(
        "/api/v1/procedures/mri-brain-without-contrast/locations/"
        f"{comparison_item['facility_location_id']}/price-details"
        f"?payer={payer_slug}&plan={plan_id}"
    ).json()["records"]
    assert insured_item["matching_negotiated_rate_count"] == sum(
        record["semantic_type"].startswith("negotiated_") for record in insured_details
    )
    for path in (
        "/api/v1/admin/pricing/sources",
        "/api/v1/admin/pricing/source-discovery-runs",
        "/api/v1/admin/pricing/source-discovery-observations",
        "/api/v1/admin/pricing/import-runs",
        "/api/v1/admin/pricing/records",
        "/api/v1/admin/pricing/rates",
        "/api/v1/admin/pricing/unmatched",
        "/api/v1/admin/pricing/anomalies",
        "/api/v1/admin/pricing/procedure-candidates",
        "/api/v1/admin/pricing/payers",
        "/api/v1/admin/pricing/plans",
        "/api/v1/admin/pricing/facility-procedure-summaries",
    ):
        response = client.get(path)
        assert response.status_code == 200, (path, response.text)


def test_phase_4_2_scorecard_endpoint() -> None:
    scorecard = client.get("/api/v1/pricing/scorecard")
    assert scorecard.status_code == 200
    data = scorecard.json()
    assert "overall_readiness" in data
    assert "component_scores" in data
    components = data["component_scores"]
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


def test_phase_4_2_freshness_endpoint() -> None:
    freshness = client.get("/api/v1/pricing/freshness")
    assert freshness.status_code == 200
    data = freshness.json()
    assert "items" in data


def test_phase_4_2_facility_scores_endpoint() -> None:
    scores = client.get("/api/v1/pricing/facility-scores?page=1&page_size=10")
    assert scores.status_code == 200
    data = scores.json()
    assert "items" in data
    assert "total" in data
    assert "page" in data


def test_phase_4_2_facility_scores_sorting() -> None:
    by_score = client.get("/api/v1/pricing/facility-scores?sort=overall_score")
    assert by_score.status_code == 200
    by_name = client.get("/api/v1/pricing/facility-scores?sort=facility_name")
    assert by_name.status_code == 200


def test_phase_4_2_facility_pricing_health() -> None:
    fid = "00000000-0000-0000-0000-000000000001"
    health = client.get(f"/api/v1/facilities/{fid}/pricing-health")
    assert health.status_code == 200
    data = health.json()
    assert "overall_score" in data


def test_phase_4_2_facility_pricing_health_not_found() -> None:
    fid = "00000000-0000-0000-0000-000000000099"
    health = client.get(f"/api/v1/facilities/{fid}/pricing-health")
    assert health.status_code == 404


def test_phase_4_2_map_data_endpoint() -> None:
    map_data = client.get("/api/v1/facilities/map-data")
    assert map_data.status_code == 200
    data = map_data.json()
    assert data["type"] == "FeatureCollection"
    assert "features" in data


def test_phase_4_2_map_data_with_filter() -> None:
    filtered = client.get("/api/v1/facilities/map-data?pricing_status=publishable")
    assert filtered.status_code == 200
    data = filtered.json()
    assert data["type"] == "FeatureCollection"


def test_phase_4_2_price_filtering() -> None:
    prices = client.get(
        "/api/v1/procedures/mri-brain-without-contrast/prices?state=NH&service_setting=outpatient"
    )
    assert prices.status_code == 200
    prices_class = client.get(
        "/api/v1/procedures/mri-brain-without-contrast/prices?state=NH&billing_class=facility"
    )
    assert prices_class.status_code == 200


def test_operational_headers_and_version_are_safe() -> None:
    response = client.get("/health", headers={"x-request-id": "qa-request"})
    assert response.status_code == 200
    assert response.headers["x-request-id"] == "qa-request"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    version = client.get("/version").json()
    assert set(version) == {"service", "version", "build", "environment"}


def test_admin_can_be_removed_from_public_service(monkeypatch: object) -> None:
    from pytest import MonkeyPatch

    assert isinstance(monkeypatch, MonkeyPatch)
    monkeypatch.setattr(api_settings, "admin_api_enabled", False)
    response = client.get("/api/v1/admin/dashboard")
    assert response.status_code == 404


def test_public_pricing_emergency_disable(monkeypatch: object) -> None:
    from pytest import MonkeyPatch

    assert isinstance(monkeypatch, MonkeyPatch)
    monkeypatch.setattr(api_settings, "public_pricing_enabled", False)
    response = client.get("/api/v1/pricing/coverage")
    assert response.status_code == 503
    assert response.json()["detail"] == "pricing is temporarily unavailable"


def test_rate_limit_rejects_abuse_without_affecting_health(monkeypatch: object) -> None:
    from pytest import MonkeyPatch

    assert isinstance(monkeypatch, MonkeyPatch)
    monkeypatch.setattr(api_settings, "rate_limit_requests", 1)
    first = client.get("/api/v1/search?q=MRI")
    second = client.get("/api/v1/search?q=MRI")
    assert first.status_code == 200
    assert second.status_code == 429
    assert client.get("/health").status_code == 200


def test_comparison_is_provider_neutral_for_nonhospital_published_price() -> None:
    """A non-hospital service location with a publishable, real-sourced provider price
    (no HospitalPriceRecord observations) must appear in the comparison with its cash
    price surfaced from the summary itself — qualifying on price publishability, not on
    location_type == hospital. A sibling location without a summary stays unpriced."""
    proc_slug = "abdominal-ultrasound"
    with TestingSession.begin() as session:
        procedure = session.scalar(select(Procedure).where(Procedure.slug == proc_slug))
        assert procedure is not None
        source = SourceFile(
            source_name="Derry Imaging (published cash prices)",
            source_url="https://www.derryimaging.example/cost-savings",
            source_type="provider_published_price",
            storage_path="provenance/derry",
            checksum_sha256="c" * 64,
            file_size=0,
            parser_version="nonhospital-published-prices-manual",
            status=SourceStatus.COMPLETED,
        )
        session.add(source)
        session.flush()
        facility = Facility(
            legal_name="Derry Imaging",
            display_name="Derry Imaging",
            facility_type="Imaging Center",
            active=True,
            source_file_id=source.id,
        )
        priced = FacilityLocation(
            address_line_1="10 Tsienneto Rd",
            city="Derry",
            state="NH",
            postal_code="03038",
            location_type="imaging_center",
        )
        unpriced = FacilityLocation(
            address_line_1="1 Roulston Rd",
            city="Windham",
            state="NH",
            postal_code="03087",
            location_type="imaging_center",
        )
        facility.locations.append(priced)
        facility.locations.append(unpriced)
        session.add(facility)
        session.flush()
        summary = FacilityProcedurePriceSummary(
            facility_id=facility.id,
            facility_location_id=priced.id,
            procedure_id=procedure.id,
            service_setting="outpatient",
            included_component_scope="global",
            cash_price_min=Decimal("325"),
            cash_price_max=Decimal("325"),
            cash_price_median=Decimal("325"),
            record_count=1,
            source_file_id=source.id,
            publication_status="publishable",
            completeness_score=Decimal("1.0"),
        )
        session.add(summary)
        session.flush()
        session.add(
            FacilityProcedurePriceSummarySource(
                summary_id=summary.id, source_file_id=source.id, observation_count=1
            )
        )

    body = client.get(f"/api/v1/procedures/{proc_slug}/comparison?state=NH").json()
    derry = [item for item in body["items"] if item["facility_name"] == "Derry Imaging"]
    priced_items = [item for item in derry if item["price_available"]]
    assert len(priced_items) == 1
    item = priced_items[0]
    assert item["city"] == "Derry"
    # Cash price surfaced from the summary (no observations), comparable as a complete
    # global outpatient charge — never fabricated hospital/CMS fields.
    assert Decimal(item["cash_price_min"]) == Decimal("325")
    assert Decimal(item["cash_price_max"]) == Decimal("325")
    assert item["primary_billing_scope"] == "global"
    assert item["comparability_status"] == "directly_comparable"
    assert item["cms_overall_rating"] is None
    # The priced Derry location is counted among facilities-with-prices.
    assert body["facilities_with_prices"] >= 1


def test_search_resolves_self_pay_lab_intent() -> None:
    # P0 regression: the reported production defect. The full natural sentence must
    # resolve to the Laboratory category (never "no match") and expose self-pay context.
    resp = client.get(
        "/api/v1/search",
        params={"q": "I need a blood test without insurance", "locale": "en"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["intent_type"] == "category"
    assert body["canonical_category_slug"] == "laboratory"
    assert body["payment_context"] == "self_pay"
    assert body["total"] >= 1
    # A bare procedure/category query carries no payment context.
    plain = client.get("/api/v1/search", params={"q": "mri brain", "locale": "en"}).json()
    assert plain["payment_context"] is None


def test_dtc_options_endpoint_serves_verified_lab_options() -> None:
    # Lab procedure returns verified org/product-level DTC options (never per-location).
    resp = client.get("/api/v1/procedures/complete-blood-count/dtc-options")
    assert resp.status_code == 200
    body = resp.json()
    assert body["procedure_slug"] == "complete-blood-count"
    assert body["disclaimer"]
    orgs = {o["organization"] for o in body["options"]}
    assert {"Quest Diagnostics", "Labcorp OnDemand"} <= orgs
    for opt in body["options"]:
        assert opt["scope"] == "national_dtc"
        assert opt["fee_included"] is True
        assert Decimal(opt["total"]) > 0
    # HbA1c already exists as canonical `a1c-test` (not a gap); it also carries DTC options.
    a1c = client.get("/api/v1/procedures/a1c-test/dtc-options").json()
    a1c_orgs = {o["organization"] for o in a1c["options"]}
    assert {"Quest Diagnostics", "Labcorp OnDemand"} <= a1c_orgs
    # A non-lab procedure has no DTC options (empty, not an error).
    imaging = client.get("/api/v1/procedures/mri-brain-without-contrast/dtc-options")
    assert imaging.status_code == 200
    assert imaging.json()["options"] == []
    # Unknown procedure → 404.
    assert client.get("/api/v1/procedures/not-a-real-procedure/dtc-options").status_code == 404
