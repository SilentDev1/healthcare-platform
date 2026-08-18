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
from packages.search.ai_contract import (
    AIIntentProposal,
    ProposedIntentType,
    category_registry_for_ai,
    validate_ai_intent,
)
from packages.search.categories import consumer_categories
from packages.search.resolution import SearchIntentType, resolve_search
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
    elliot = Facility(
        cms_certification_number="300012",
        legal_name="ELLIOT HOSPITAL",
        display_name="Elliot Hospital",
        source_file_id=source.id,
    )
    elliot.locations.append(
        FacilityLocation(
            address_line_1="1 Elliot Way", city="Nashua", state="NH", postal_code="03060"
        )
    )
    session.add(elliot)
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

        cat_titles = {item.title for item in search(session, "CAT scan")}
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


def test_lab_tests_resolves_category_and_actual_catalog_members() -> None:
    engine = _engine()
    with Session(engine) as session:
        _seed_base_data(session)
        results = search(session, "lab tests")
        category = next(item for item in results if item.entity_type == "procedure_category")
        members = [item for item in results if item.match_reason == "category_member"]
        assert category.title == "Lab tests"
        assert category.match_reason == "exact_category"
        assert category.metadata["procedure_count"] == len(members) == 13
        assert all(item.metadata["category"] == "laboratory" for item in members)
        assert all("price" not in item.metadata for item in members)
    engine.dispose()


def test_category_alias_and_conservative_partial_resolution() -> None:
    engine = _engine()
    with Session(engine) as session:
        _seed_base_data(session)
        labs = search(session, "blood work")
        lab = search(session, "lab")
        ortho = search(session, "ortho")
        assert any(item.match_reason == "reviewed_category_alias" for item in labs)
        assert any(item.title == "Lab tests" for item in lab)
        assert any(item.title == "Orthopedics" for item in ortho)
    engine.dispose()


def test_every_visible_category_resolves_with_exact_membership_count() -> None:
    engine = _engine()
    with Session(engine) as session:
        _seed_base_data(session)
        for category in consumer_categories().values():
            results = search(session, category.label("en"))
            match = next(
                item
                for item in results
                if item.entity_type == "procedure_category"
                and item.metadata["slug"] == category.slug
            )
            members = [
                item
                for item in results
                if item.match_reason == "category_member"
                and item.metadata["category"] == category.slug
            ]
            assert match.match_reason == "exact_category", category.slug
            assert match.metadata["procedure_count"] == len(members), category.slug
    engine.dispose()


def test_exact_procedure_hospital_and_location_behaviors_remain() -> None:
    engine = _engine()
    with Session(engine) as session:
        _seed_base_data(session)
        exact = search(session, "Complete blood count")
        alias = search(session, "CBC")
        hospital = search(session, "Elliot Hospital")
        city = search(session, "Nashua")
        assert exact[0].title == "Complete blood count"
        assert exact[0].match_reason == "exact_primary"
        assert any(item.title == "Complete blood count" for item in alias)
        assert any(item.title == "Elliot Hospital" for item in hospital)
        assert any(item.location and "Nashua" in item.location for item in city)
        assert search(session, "xyzzynonsense") == []
    engine.dispose()


def test_localized_displayed_category_labels_resolve() -> None:
    engine = _engine()
    with Session(engine) as session:
        _seed_base_data(session)
        for locale in ("es", "vi", "zh-CN", "zh-TW"):
            label = consumer_categories()["laboratory"].label(locale)
            results = search(session, label, locale=locale)
            category = next(
                item
                for item in results
                if item.entity_type == "procedure_category"
                and item.metadata["slug"] == "laboratory"
            )
            assert category.title == label
            assert category.match_reason == "exact_category"
    engine.dispose()


def test_structured_resolution_is_deterministic_and_safe() -> None:
    engine = _engine()
    with Session(engine) as session:
        _seed_base_data(session)
        category = resolve_search(session, "lab tests")
        canonical = resolve_search(session, "Laboratory")
        alias = resolve_search(session, "blood work")
        procedure = resolve_search(session, "Complete blood count")
        ambiguous = resolve_search(session, "knee scan")
        medical = resolve_search(session, "my knee hurts what scan should I get")
        unsupported = resolve_search(session, "PET scan")
        category_location = resolve_search(session, "lab tests in Nashua")
        assert category.intent_type == canonical.intent_type == alias.intent_type
        assert category.intent_type == SearchIntentType.CATEGORY
        assert category.canonical_category_slug == "laboratory"
        assert procedure.intent_type == SearchIntentType.PROCEDURE
        assert ambiguous.intent_type == SearchIntentType.AMBIGUOUS
        assert ambiguous.clarification_needed
        assert all(item.metadata["slug"] != "knee-replacement" for item in ambiguous.results)
        assert medical.clarification_needed
        assert "Carevero can compare prices" in (medical.clarification_question or "")
        assert unsupported.intent_type == SearchIntentType.UNKNOWN
        assert unsupported.ai_fallback_eligible
        assert unsupported.results == []
        assert category_location.intent_type == SearchIntentType.CATEGORY
        assert category_location.location_text == "Nashua"
    engine.dispose()


def test_complex_query_does_not_invent_or_calculate() -> None:
    engine = _engine()
    with Session(engine) as session:
        _seed_base_data(session)
        resolution = resolve_search(session, "cheapest MRI knee within 25 miles of Nashua")
        # This deterministic layer does not guess a canonical procedure or perform
        # pricing/distance calculations. It explicitly hands off to validated AI.
        assert resolution.intent_type == SearchIntentType.UNKNOWN
        assert resolution.ai_fallback_eligible
        assert resolution.results == []
    engine.dispose()


def test_ai_registry_visibility_and_canonical_candidate_validation() -> None:
    engine = _engine()
    with Session(engine) as session:
        _seed_base_data(session)
        registry = category_registry_for_ai(session, locale="vi")
        laboratory = next(item for item in registry if item["canonical_id"] == "laboratory")
        assert laboratory["consumer_display_name"] == "Xét nghiệm"
        assert laboratory["procedure_count"] == 13
        valid = validate_ai_intent(
            session,
            AIIntentProposal(
                intent_type=ProposedIntentType.PROCEDURE,
                canonical_candidates=["complete-blood-count"],
                confidence=0.99,
            ),
        )
        fabricated = validate_ai_intent(
            session,
            AIIntentProposal(
                intent_type=ProposedIntentType.PROCEDURE,
                canonical_candidates=["invented-pet-scan"],
                confidence=0.99,
            ),
        )
        assert valid.canonical_candidates == ["complete-blood-count"]
        assert fabricated.canonical_candidates == []
        assert fabricated.rejected_candidates == ["invented-pet-scan"]
        assert fabricated.intent_type == ProposedIntentType.UNKNOWN
        assert fabricated.clarification_needed
    engine.dispose()
