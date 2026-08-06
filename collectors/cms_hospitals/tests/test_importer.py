from pathlib import Path

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from collectors.cms_hospitals.config import CollectorSettings
from collectors.cms_hospitals.importer import run_import
from packages.database import Base, Facility, ImportRun, SourceFile

FIXTURE = Path("data/fixtures/cms_hospitals.csv")


def test_import_filters_nh_tracks_rejections_and_is_idempotent(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    settings = CollectorSettings(
        cms_rejected_data_dir=tmp_path / "rejected", cms_raw_data_dir=tmp_path / "raw"
    )
    with sessions() as session:
        first = run_import(session, settings, source_path=FIXTURE, source_url="fixture://cms")
        assert (first.rows_read, first.rows_inserted, first.rows_rejected) == (4, 2, 1)
        assert session.scalar(select(func.count(Facility.id))) == 2
        facility = session.scalar(
            select(Facility).where(Facility.cms_certification_number == "300001")
        )
        assert facility is not None
        assert facility.locations[0].state == "NH"
        second = run_import(session, settings, source_path=FIXTURE, source_url="fixture://cms")
        assert second.rows_inserted == 0
        assert second.rows_updated == 2
        assert session.scalar(select(func.count(Facility.id))) == 2
        assert session.scalar(select(func.count(SourceFile.id))) == 2
        assert session.scalar(select(func.count(ImportRun.id))) == 2
