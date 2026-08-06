import uuid
from collections.abc import Generator

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from packages.database import (
    Base,
    Facility,
    FacilityLocation,
    FacilityQualityMeasureObservation,
    FacilitySourceObservation,
    ImportRun,
    QualityMeasureDefinition,
    SourceFile,
    UnmatchedSourceRecord,
)
from packages.database.models import ImportStatus, SourceStatus
from packages.database.session import get_session
from services.api.app.main import app

engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
TestingSession = sessionmaker(bind=engine, expire_on_commit=False)


def override_session() -> Generator[Session, None, None]:
    with TestingSession() as session:
        yield session


app.dependency_overrides[get_session] = override_session
client = TestClient(app)


def setup_function() -> None:
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
