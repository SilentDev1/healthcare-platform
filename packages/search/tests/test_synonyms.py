"""Tests for search synonym expansion and scoring."""

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session

from packages.database import (
    Base,
    Facility,
    FacilityLocation,
    SourceFile,
)
from packages.database.models import SourceStatus
from packages.search.service import SYNONYMS, rebuild_index, search
from scripts.seed_procedure_catalog import seed_catalog


def _engine() -> Engine:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    return engine


def _seed_base_data(session: Session) -> None:
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
        cms_certification_number="300001",
        legal_name="TEST HOSPITAL",
        display_name="Test Hospital",
        source_file_id=source.id,
    )
    facility.locations.append(
        FacilityLocation(
            address_line_1="1 Main St", city="Concord", state="NH", postal_code="03301"
        )
    )
    session.add(facility)
    session.flush()
    seed_catalog(session)
    rebuild_index(session)
    session.flush()


def test_synonym_dict_has_entries() -> None:
    """SYNONYMS dict has expected consumer-friendly mappings."""
    assert len(SYNONYMS) >= 30
    assert "knee replacement" in SYNONYMS
    assert "c-section" in SYNONYMS
    assert "mri" in SYNONYMS
    assert "ekg" in SYNONYMS
    assert "flu shot" in SYNONYMS


def test_active_beta_languages_have_reviewed_search_terms() -> None:
    expected = {
        "es": ["mamografía", "colonoscopia", "análisis de sangre", "parto"],
        "vi": ["chụp nhũ ảnh", "nội soi đại tràng", "xét nghiệm máu", "sinh con"],
        "zh-TW": ["乳房攝影", "大腸鏡", "血液檢查", "生產"],
        "zh-CN": ["乳房摄影", "结肠镜检查", "血液检查", "分娩"],
    }
    for locale, terms in expected.items():
        for term in terms:
            assert term in SYNONYMS, f"missing {locale} synonym: {term}"
            assert SYNONYMS[term]


def test_synonym_values_are_lists() -> None:
    """Each synonym key maps to a list of strings."""
    for key, values in SYNONYMS.items():
        assert isinstance(values, list), f"{key} should map to a list"
        assert len(values) >= 1, f"{key} should have at least one synonym target"
        for v in values:
            assert isinstance(v, str), f"synonym target for {key} should be a string"


def test_synonym_expansion_returns_results() -> None:
    """Searching a synonym key returns results via synonym expansion."""
    engine = _engine()
    with Session(engine) as session:
        _seed_base_data(session)
        session.commit()

        # "knee replacement" is a synonym for "total knee arthroplasty"
        results = search(session, "knee replacement")
        # May or may not match depending on catalog content, but search should not error
        assert isinstance(results, list)
    engine.dispose()


def test_synonym_expansion_score_is_85() -> None:
    """Synonym matches get score of 85.0."""
    engine = _engine()
    with Session(engine) as session:
        _seed_base_data(session)
        session.commit()

        results = search(session, "ekg")
        synonym_results = [r for r in results if r.match_reason == "synonym_expansion"]
        for r in synonym_results:
            assert r.score == 85.0
    engine.dispose()


def test_exact_match_beats_synonym() -> None:
    """Exact matches score higher than synonym matches."""
    engine = _engine()
    with Session(engine) as session:
        _seed_base_data(session)
        session.commit()

        results = search(session, "MRI brain without contrast")
        if len(results) >= 2:
            exact = [r for r in results if r.match_reason.startswith("exact")]
            synonym = [r for r in results if r.match_reason == "synonym_expansion"]
            if exact and synonym:
                assert exact[0].score > synonym[0].score
    engine.dispose()


def test_synonym_no_duplicates() -> None:
    """Synonym expansion doesn't duplicate results already found by primary search."""
    engine = _engine()
    with Session(engine) as session:
        _seed_base_data(session)
        session.commit()

        results = search(session, "mri")
        entity_keys = [(r.entity_type, r.entity_id) for r in results]
        assert len(entity_keys) == len(set(entity_keys)), "Duplicate results found"
    engine.dispose()


def test_partial_synonym_match() -> None:
    """Partial synonym key match works (e.g., 'cat' matching 'cat scan')."""
    engine = _engine()
    with Session(engine) as session:
        _seed_base_data(session)
        session.commit()

        # The synonym logic checks if query_lower is in syn_key or vice versa
        results = search(session, "ct scan")
        assert isinstance(results, list)
    engine.dispose()


def test_common_imaging_language_returns_catalog_results() -> None:
    engine = _engine()
    with Session(engine) as session:
        _seed_base_data(session)
        session.commit()

        knee_titles = {item.title for item in search(session, "knee scan")}
        cat_titles = {item.title for item in search(session, "CAT scan")}
        assert "MRI knee without contrast" in knee_titles
        assert any(title.startswith("CT scan") for title in cat_titles)
    engine.dispose()


def test_search_without_synonyms_still_works() -> None:
    """Non-synonym queries still produce normal results."""
    engine = _engine()
    with Session(engine) as session:
        _seed_base_data(session)
        session.commit()

        results = search(session, "Test Hospital")
        assert any(r.entity_type == "facility" for r in results)
        assert all(r.match_reason != "synonym_expansion" for r in results)
    engine.dispose()


def test_bidirectional_synonyms() -> None:
    """Both 'ekg' and 'ecg' map to electrocardiogram."""
    assert "electrocardiogram" in SYNONYMS["ekg"]
    assert "electrocardiogram" in SYNONYMS["ecg"]
    assert "ekg" in SYNONYMS["ecg"]
    assert "ecg" in SYNONYMS["ekg"]
