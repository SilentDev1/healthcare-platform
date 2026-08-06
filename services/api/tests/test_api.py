import uuid
from collections.abc import Generator

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from packages.database import Base, Facility, FacilityLocation, SourceFile
from packages.database.models import SourceStatus
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
