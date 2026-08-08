"""Tests for quality metrics and anomaly auto-triage rules."""

from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import Engine, create_engine, select
from sqlalchemy.orm import Session

from collectors.hospital_prices.quality import (
    HIGH_COST_DRGS,
    generate_quality_scores,
    review_open_anomalies,
)
from packages.database import (
    Base,
    Facility,
    FacilityLocation,
    HospitalPriceRecord,
    ImportRun,
    PricingAnomaly,
    PricingHealthScore,
    SourceFile,
)
from packages.database.models import ImportStatus, SourceStatus


def _engine() -> Engine:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    return engine


_record_counter = 0


def _seed_facility(session: Session, ccn: str = "300001") -> Facility:
    source = SourceFile(
        source_name="test",
        source_url="https://example.test/test.csv",
        source_type="test_csv",
        storage_path="test.csv",
        checksum_sha256="a" * 64,
        file_size=1,
        parser_version="test",
        status=SourceStatus.COMPLETED,
    )
    session.add(source)
    session.flush()
    run = ImportRun(
        importer_name="test",
        status=ImportStatus.COMPLETED,
        source_file_id=source.id,
        rows_read=1,
        rows_inserted=1,
    )
    session.add(run)
    session.flush()
    facility = Facility(
        cms_certification_number=ccn,
        legal_name="TEST HOSPITAL",
        display_name="Test Hospital",
        source_file_id=source.id,
    )
    facility.locations.append(
        FacilityLocation(
            address_line_1="1 Test St", city="Concord", state="NH", postal_code="03301"
        )
    )
    session.add(facility)
    session.flush()
    return facility


def _seed_record(
    session: Session,
    facility: Facility,
    setting: str = "inpatient",
    gross_charge: Decimal | None = Decimal("1000"),
    raw_payload: dict[str, object] | None = None,
) -> HospitalPriceRecord:
    global _record_counter
    _record_counter += 1
    source = session.scalar(select(SourceFile).limit(1))
    run = session.scalar(select(ImportRun).limit(1))
    assert source is not None
    assert run is not None
    record = HospitalPriceRecord(
        facility_id=facility.id,
        source_file_id=source.id,
        import_run_id=run.id,
        source_record_identifier=f"test_record_{_record_counter}",
        source_payload_hash=f"{_record_counter:0>64}",
        raw_description="Test item",
        setting=setting,
        billing_class="facility",
        gross_charge=gross_charge,
        parser_name="cms_hpt_csv",
        parser_version="1.0.0",
        observed_at=datetime.now(UTC),
        raw_payload=raw_payload or {},
    )
    session.add(record)
    session.flush()
    return record


def test_suspicious_zero_on_lab_auto_suppressed() -> None:
    """Rule 1: suspicious_zero on lab items is auto-suppressed."""
    engine = _engine()
    with Session(engine) as session:
        facility = _seed_facility(session)
        record = _seed_record(session, facility, setting="laboratory")
        anomaly = PricingAnomaly(
            hospital_price_record_id=record.id,
            anomaly_type="price_validation",
            rule_key="suspicious_zero",
            severity="warning",
            status="open",
            message="Zero price detected",
            details={},
        )
        session.add(anomaly)
        session.commit()

        result = review_open_anomalies(session)
        assert result["suppressed"] == 1
        assert result["kept_open"] == 0

        updated = session.get(PricingAnomaly, anomaly.id)
        assert updated is not None
        assert updated.status == "auto_suppressed"
        assert updated.resolution_notes is not None and "lab item" in updated.resolution_notes
    engine.dispose()


def test_suspicious_zero_non_lab_kept_open() -> None:
    """suspicious_zero on non-lab items stays open."""
    engine = _engine()
    with Session(engine) as session:
        facility = _seed_facility(session)
        record = _seed_record(session, facility, setting="inpatient")
        anomaly = PricingAnomaly(
            hospital_price_record_id=record.id,
            anomaly_type="price_validation",
            rule_key="suspicious_zero",
            severity="warning",
            status="open",
            message="Zero price detected",
            details={},
        )
        session.add(anomaly)
        session.commit()

        result = review_open_anomalies(session)
        assert result["suppressed"] == 0
        assert result["kept_open"] == 1
    engine.dispose()


def test_blank_payer_with_gross_charge_downgraded() -> None:
    """Rule 2: blank_payer with valid gross_charge is downgraded to warning."""
    engine = _engine()
    with Session(engine) as session:
        facility = _seed_facility(session)
        record = _seed_record(session, facility, gross_charge=Decimal("500"))
        anomaly = PricingAnomaly(
            hospital_price_record_id=record.id,
            anomaly_type="payer_validation",
            rule_key="blank_payer",
            severity="error",
            status="open",
            message="Blank payer",
            details={},
        )
        session.add(anomaly)
        session.commit()

        result = review_open_anomalies(session)
        assert result["downgraded"] == 1
        assert result["kept_open"] == 0

        updated = session.get(PricingAnomaly, anomaly.id)
        assert updated is not None
        assert updated.severity == "warning"
        assert updated.resolution_notes is not None
        assert "valid gross charge" in updated.resolution_notes
    engine.dispose()


def test_extremely_large_price_high_cost_drg_suppressed() -> None:
    """Rule 3: extremely_large_price on known high-cost DRGs is auto-suppressed."""
    engine = _engine()
    with Session(engine) as session:
        facility = _seed_facility(session)
        record = _seed_record(
            session,
            facility,
            gross_charge=Decimal("2000000"),
            raw_payload={"code": "001"},
        )
        anomaly = PricingAnomaly(
            hospital_price_record_id=record.id,
            anomaly_type="price_validation",
            rule_key="extremely_large_price",
            severity="critical",
            status="open",
            message="Price exceeds threshold",
            details={},
        )
        session.add(anomaly)
        session.commit()

        result = review_open_anomalies(session)
        assert result["suppressed"] == 1

        updated = session.get(PricingAnomaly, anomaly.id)
        assert updated is not None
        assert updated.status == "auto_suppressed"
        assert updated.resolution_notes is not None and "DRG 001" in updated.resolution_notes
    engine.dispose()


def test_extremely_large_price_non_drg_kept_open() -> None:
    """extremely_large_price on non-high-cost code stays open."""
    engine = _engine()
    with Session(engine) as session:
        facility = _seed_facility(session)
        record = _seed_record(
            session,
            facility,
            gross_charge=Decimal("2000000"),
            raw_payload={"code": "99213"},
        )
        anomaly = PricingAnomaly(
            hospital_price_record_id=record.id,
            anomaly_type="price_validation",
            rule_key="extremely_large_price",
            severity="critical",
            status="open",
            message="Price exceeds threshold",
            details={},
        )
        session.add(anomaly)
        session.commit()

        result = review_open_anomalies(session)
        assert result["suppressed"] == 0
        assert result["kept_open"] == 1
    engine.dispose()


def test_multiple_anomalies_mixed_rules() -> None:
    """Multiple anomalies with different rules are processed correctly."""
    engine = _engine()
    with Session(engine) as session:
        facility = _seed_facility(session)

        # Lab zero → suppress
        r1 = _seed_record(session, facility, setting="lab")
        a1 = PricingAnomaly(
            hospital_price_record_id=r1.id,
            anomaly_type="price_validation",
            rule_key="suspicious_zero",
            severity="warning",
            status="open",
            message="Zero",
            details={},
        )

        # Blank payer with charge → downgrade
        r2 = _seed_record(session, facility, gross_charge=Decimal("100"))
        a2 = PricingAnomaly(
            hospital_price_record_id=r2.id,
            anomaly_type="payer_validation",
            rule_key="blank_payer",
            severity="error",
            status="open",
            message="Blank",
            details={},
        )

        # Unknown rule → kept open
        r3 = _seed_record(session, facility)
        a3 = PricingAnomaly(
            hospital_price_record_id=r3.id,
            anomaly_type="other",
            rule_key="other_rule",
            severity="warning",
            status="open",
            message="Other",
            details={},
        )

        session.add_all([a1, a2, a3])
        session.commit()

        result = review_open_anomalies(session)
        assert result["suppressed"] == 1
        assert result["downgraded"] == 1
        assert result["kept_open"] == 1
    engine.dispose()


def test_no_open_anomalies_returns_zeros() -> None:
    """No open anomalies → all counts zero."""
    engine = _engine()
    with Session(engine) as session:
        _seed_facility(session)
        session.commit()
        result = review_open_anomalies(session)
        assert result == {"suppressed": 0, "downgraded": 0, "kept_open": 0}
    engine.dispose()


def test_generate_quality_scores_with_health_data() -> None:
    """Quality scores generated from PricingHealthScore records."""
    engine = _engine()
    with Session(engine) as session:
        facility = _seed_facility(session)
        session.add(
            PricingHealthScore(
                facility_id=facility.id,
                source_discovery_score=100,
                download_score=100,
                parse_score=80,
                mapping_score=60,
                payer_normalization_score=70,
                anomaly_score=90,
                freshness_score=50,
                price_coverage_score=40,
                overall_score=73.75,
                details={"records": 100},
            )
        )
        session.commit()

        scores = generate_quality_scores(session)
        assert len(scores) == 1
        assert scores[0]["facility_name"] == "Test Hospital"
        assert scores[0]["overall_score"] == 73.75
        assert "open_anomalies" in scores[0]
    engine.dispose()


def test_high_cost_drgs_set_complete() -> None:
    """HIGH_COST_DRGS contains expected transplant and revision codes."""
    assert "001" in HIGH_COST_DRGS
    assert "652" in HIGH_COST_DRGS
    assert "480" in HIGH_COST_DRGS
    assert "99213" not in HIGH_COST_DRGS
