from pathlib import Path

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from collectors.cms_quality.config import QualityCollectorSettings
from collectors.cms_quality.importer import run_quality_imports
from packages.database import (
    Base,
    Facility,
    FacilityQualityMeasureObservation,
    FacilitySourceObservation,
    ImportRun,
    SourceFile,
    UnmatchedSourceRecord,
)
from packages.database.models import SourceStatus

FIXTURES = Path("data/fixtures/cms_quality")


def test_quality_import_matches_exact_ccn_tracks_unmatched_and_skips_unchanged(
    tmp_path: Path,
) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'quality.db'}")
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    settings = QualityCollectorSettings(
        cms_quality_raw_data_dir=tmp_path / "raw",
        cms_quality_rejected_data_dir=tmp_path / "rejected",
    )
    fixtures = {dataset.key: FIXTURES / f"{dataset.key}.csv" for dataset in settings.datasets()}
    with sessions() as session:
        source = SourceFile(
            source_name="facility fixture",
            source_url="fixture://facilities",
            source_type="csv",
            storage_path="fixture.csv",
            checksum_sha256="a" * 64,
            file_size=1,
            parser_version="test",
            status=SourceStatus.COMPLETED,
        )
        session.add(source)
        session.flush()
        session.add(
            Facility(
                cms_certification_number="300001",
                legal_name="Concord General Hospital",
                display_name="Concord General Hospital",
                source_file_id=source.id,
            )
        )
        session.commit()

        first = run_quality_imports(session, settings, fixtures=fixtures)
        assert first.datasets_imported == 5
        assert first.observations_inserted == 6
        assert first.unmatched_records == 1
        assert session.scalar(select(func.count(FacilityQualityMeasureObservation.id))) == 6
        assert session.scalar(select(func.count(FacilitySourceObservation.id))) == 6
        unmatched = session.scalar(select(UnmatchedSourceRecord))
        assert unmatched is not None
        assert unmatched.supplied_cms_certification_number == "399999"
        assert unmatched.review_status == "pending"

        second = run_quality_imports(session, settings, fixtures=fixtures)
        assert second.datasets_imported == 0
        assert second.datasets_skipped == 5
        assert session.scalar(select(func.count(FacilityQualityMeasureObservation.id))) == 6
        assert session.scalar(select(func.count(ImportRun.id))) == 5
    engine.dispose()
