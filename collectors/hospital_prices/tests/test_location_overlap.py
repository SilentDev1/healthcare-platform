import uuid

from collectors.hospital_prices.location_association import _normalized_address
from collectors.hospital_prices.overlap import SourceProfile, classify_profiles
from collectors.hospital_prices.projections import consumer_summary_key
from collectors.hospital_prices.source_facility_association import filename_identifies_facility
from packages.database import FacilityProcedurePriceObservation


def _profile(
    *,
    location: uuid.UUID | None,
    checksum: str,
    codes: set[tuple[str, str]],
    descriptions: set[str],
    prices: set[tuple[str | None, ...]],
) -> SourceProfile:
    return SourceProfile(
        source_file_id=uuid.uuid4(),
        location_id=location,
        checksum=checksum,
        record_count=100,
        code_systems={"CPT": len(codes)},
        codes=codes,
        descriptions=descriptions,
        price_tuples=prices,
        payer_plans={(uuid.uuid4(), None)},
    )


def test_same_ccn_sources_at_different_locations_preserve_location_identity() -> None:
    codes = {("CPT", str(code)) for code in range(100)}
    descriptions = {f"service {code}" for code in range(100)}
    left = _profile(
        location=uuid.uuid4(),
        checksum="a" * 64,
        codes=codes,
        descriptions=descriptions,
        prices={("100", "80", None, None, "outpatient", "facility")},
    )
    right = _profile(
        location=uuid.uuid4(),
        checksum="b" * 64,
        codes=codes,
        descriptions=descriptions,
        prices={("100", "80", None, None, "outpatient", "facility")},
    )
    classification, metrics = classify_profiles(left, right)
    assert classification == "DISTINCT_LOCATION_OVERLAPPING_SCHEDULE"
    assert metrics["exact_code_overlap"] == 1.0
    assert metrics["same_location"] is False


def test_same_npi_family_does_not_collapse_distinct_locations() -> None:
    location_a, location_b = uuid.uuid4(), uuid.uuid4()
    codes = {("HCPCS", "99284")}
    descriptions = {"emergency department visit"}
    left = _profile(
        location=location_a,
        checksum="c" * 64,
        codes=codes,
        descriptions=descriptions,
        prices={("500", None, None, None, "outpatient", "facility")},
    )
    right = _profile(
        location=location_b,
        checksum="d" * 64,
        codes=codes,
        descriptions=descriptions,
        prices={("600", None, None, None, "outpatient", "facility")},
    )
    assert classify_profiles(left, right)[0] == "DISTINCT_LOCATION_OVERLAPPING_SCHEDULE"


def test_exact_duplicate_checksum_is_source_version_duplicate() -> None:
    location = uuid.uuid4()
    left = _profile(
        location=location,
        checksum="e" * 64,
        codes={("CPT", "70551")},
        descriptions={"mri brain"},
        prices={("100", None, None, None, "outpatient", "facility")},
    )
    right = _profile(
        location=location,
        checksum="e" * 64,
        codes=left.codes,
        descriptions=left.descriptions,
        prices=left.price_tuples,
    )
    assert classify_profiles(left, right)[0] == "DUPLICATE_SOURCE_VERSION"


def test_ambiguous_location_source_remains_reviewable() -> None:
    left = _profile(
        location=None,
        checksum="f" * 64,
        codes={("LOCAL", "1")},
        descriptions={"unknown service"},
        prices={("10", None, None, None, "unknown", "unknown")},
    )
    right = _profile(
        location=None,
        checksum="0" * 64,
        codes={("LOCAL", "2")},
        descriptions={"different service"},
        prices={("20", None, None, None, "unknown", "unknown")},
    )
    assert classify_profiles(left, right)[0] == "UNKNOWN_REVIEW_REQUIRED"


def test_location_ids_are_not_reused_across_state_scopes() -> None:
    nh_location = uuid.uuid4()
    ma_location = uuid.uuid4()
    assert nh_location != ma_location


def test_consumer_identity_ignores_source_but_separates_locations() -> None:
    facility_id, procedure_id = uuid.uuid4(), uuid.uuid4()
    location_a, location_b = uuid.uuid4(), uuid.uuid4()

    def observation(
        location_id: uuid.UUID, record_id: uuid.UUID
    ) -> FacilityProcedurePriceObservation:
        return FacilityProcedurePriceObservation(
            facility_id=facility_id,
            facility_location_id=location_id,
            procedure_id=procedure_id,
            hospital_price_record_id=record_id,
            price_type="discounted_cash",
            amount=100,
            service_setting="outpatient",
            included_component_scope="facility",
            source_confidence=1,
            mapping_confidence=1,
            publication_status="publishable",
        )

    first = observation(location_a, uuid.uuid4())
    overlapping_source = observation(location_a, uuid.uuid4())
    distinct_location = observation(location_b, uuid.uuid4())
    assert consumer_summary_key(first) == consumer_summary_key(overlapping_source)
    assert consumer_summary_key(first) != consumer_summary_key(distinct_location)


def test_filename_facility_association_requires_complete_exact_name() -> None:
    url = "https://hospital.example/851443782_concord-hospital-laconia_standardcharges.csv"
    assert filename_identifies_facility(url, "CONCORD HOSPITAL- LACONIA")
    assert not filename_identifies_facility(url, "CONCORD HOSPITAL")
    assert not filename_identifies_facility(url, "CONCORD HOSPITAL- FRANKLIN")


def test_equivalent_address_suffixes_do_not_create_locations() -> None:
    assert _normalized_address("1 PARKLAND DRIVE") == _normalized_address("1 Parkland Dr")
