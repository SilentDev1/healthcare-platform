from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

from packages.network_foundation import (
    conservative_network_status,
    freshness_status,
    match_facility_by_identifiers,
)
from packages.price_accuracy import audit_observation, parse_source_decimal, reproduce_range


def _objects(price_type: str = "discounted_cash") -> tuple[SimpleNamespace, ...]:
    facility_id, location_id, procedure_id, payer_id, plan_id = (uuid4() for _ in range(5))
    record = SimpleNamespace(
        facility_id=facility_id,
        facility_location_id=location_id,
        gross_charge=Decimal("2000.00"),
        discounted_cash_price=Decimal("1250.00"),
        deidentified_minimum_negotiated_rate=Decimal("900.00"),
        deidentified_maximum_negotiated_rate=Decimal("1500.00"),
        setting="outpatient",
        source_record_identifier="row:12",
        source_line_number=12,
        source_payload_hash="a" * 64,
        raw_payload={"discounted_cash": "$1,250.00"},
        parser_name="cms_hpt_csv",
        parser_version="1.2.3",
    )
    rate = SimpleNamespace(
        negotiated_rate=Decimal("975.00"),
        source_payload={"negotiated_rate": "975.00"},
        payer_entity_id=payer_id,
        insurance_plan_entity_id=plan_id,
    )
    amount = rate.negotiated_rate if price_type == "payer_negotiated" else Decimal("1250.00")
    observation = SimpleNamespace(
        price_type=price_type,
        amount=amount,
        facility_id=facility_id,
        facility_location_id=location_id,
        procedure_id=procedure_id,
        payer_entity_id=payer_id if price_type == "payer_negotiated" else None,
        insurance_plan_entity_id=plan_id if price_type == "payer_negotiated" else None,
        service_setting="outpatient",
    )
    mapping = SimpleNamespace(
        procedure_id=procedure_id,
        mapping_method="exact_approved_code",
        reviewed=True,
    )
    source = SimpleNamespace(
        source_url="https://hospital.example/mrf.csv", checksum_sha256="b" * 64
    )
    return observation, record, rate, mapping, source


def test_exact_price_and_formatted_source_value_are_preserved() -> None:
    assert parse_source_decimal("$1,250.00") == Decimal("1250.00")
    outcome = audit_observation(*_objects(), raw_source_available=False)
    assert outcome.status == "PROVENANCE_VERIFIED"
    assert outcome.difference == 0
    assert outcome.provenance_checks["raw_payload_matches_normalized_record"]


def test_raw_payload_monetary_mismatch_is_detected() -> None:
    observation, record, rate, mapping, source = _objects()
    record.raw_payload["discounted_cash"] = "$1,251.00"
    outcome = audit_observation(observation, record, rate, mapping, source)
    assert outcome.status == "VALUE_MISMATCH"
    assert outcome.difference == Decimal("-1.00")


def test_checksum_mismatch_does_not_claim_full_source_verification() -> None:
    outcome = audit_observation(*_objects(), raw_source_available=True, raw_checksum_verified=False)
    assert outcome.status == "PROVENANCE_VERIFIED"
    assert not outcome.provenance_checks["raw_checksum_verified"]


def test_wrong_semantics_are_detected() -> None:
    observation, record, rate, mapping, source = _objects("payer_negotiated")
    for field in (
        "procedure_id",
        "facility_location_id",
        "payer_entity_id",
        "insurance_plan_entity_id",
    ):
        changed = SimpleNamespace(**vars(observation))
        setattr(changed, field, uuid4())
        assert (
            audit_observation(changed, record, rate, mapping, source).status == "SEMANTIC_MISMATCH"
        )
    changed = SimpleNamespace(**(vars(observation) | {"service_setting": "emergency"}))
    assert audit_observation(changed, record, rate, mapping, source).status == "SEMANTIC_MISMATCH"
    changed = SimpleNamespace(**(vars(observation) | {"price_type": "cash_guess"}))
    assert audit_observation(changed, record, rate, mapping, source).status == "VALUE_MISMATCH"


def test_legacy_record_location_is_verified_from_source_association() -> None:
    observation, record, rate, mapping, source = _objects()
    expected_location = observation.facility_location_id
    record.facility_location_id = None
    outcome = audit_observation(
        observation,
        record,
        rate,
        mapping,
        source,
        source_location_id=expected_location,
    )
    assert outcome.semantic_checks["location_matches"]


def test_unreviewed_mapping_requires_review() -> None:
    observation, record, rate, mapping, source = _objects()
    mapping.mapping_method = "fuzzy_description"
    mapping.reviewed = False
    assert (
        audit_observation(observation, record, rate, mapping, source).status
        == "MAPPING_REVIEW_REQUIRED"
    )


def test_derived_range_is_exactly_reproducible() -> None:
    assert reproduce_range([Decimal("1"), Decimal("2"), Decimal("9")]) == {
        "min": Decimal("1"),
        "max": Decimal("9"),
        "median": Decimal("2"),
    }


def test_missing_bounded_source_returns_source_unavailable() -> None:
    observation, record, rate, mapping, source = _objects()
    record.raw_payload = {}
    assert (
        audit_observation(observation, record, rate, mapping, source).status
        == "SOURCE_FILE_UNAVAILABLE"
    )


def test_negotiated_rate_never_implies_network_participation() -> None:
    assert conservative_network_status(set()) == "NETWORK_STATUS_UNKNOWN"
    assert conservative_network_status({"DIRECTORY_LISTED"}) == "DIRECTORY_LISTED"


def test_plan_specific_conflict_and_staleness() -> None:
    assert (
        conservative_network_status({"IN_NETWORK_VERIFIED", "OUT_OF_NETWORK_VERIFIED"})
        == "CONFLICT_REVIEW_REQUIRED"
    )
    old = datetime.now(UTC) - timedelta(days=100)
    assert freshness_status(old, 30) == "stale"


def test_ambiguous_facility_match_and_multi_state_isolation() -> None:
    candidates = [
        {
            "facility_id": "nh-1",
            "location_id": "nh-loc",
            "state": "NH",
            "identifiers": {"npi": "123"},
        },
        {
            "facility_id": "ma-1",
            "location_id": "ma-loc",
            "state": "MA",
            "identifiers": {"npi": "123"},
        },
    ]
    ambiguous = match_facility_by_identifiers({"npi": "123"}, candidates)
    assert ambiguous.status == "ambiguous_review_required"
    isolated = match_facility_by_identifiers(
        {"npi": "123"}, [item for item in candidates if item["state"] == "NH"]
    )
    assert isolated.facility_id == "nh-1"
