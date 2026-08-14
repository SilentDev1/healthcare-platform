"""Tests for stage_local_mrf: manual-staging import of a Cloudflare-blocked MRF.

Load-bearing guarantees:
  * the authoritative HTTPS source_url is preserved (never becomes file://), so the
    staged file publishes like any downloaded MRF rather than a review-only fixture;
  * validation fails safe before any production mutation;
  * reruns are idempotent (checksum dedup + completed-run skip).
"""

import json
from pathlib import Path

from sqlalchemy import Engine, create_engine, func, select
from sqlalchemy.orm import Session

from packages.database import (
    Base,
    Facility,
    FacilityLocation,
    HospitalPriceRecord,
    Procedure,
    ProcedureCategory,
    ProcedureCodeMapping,
    ProcedureCodeSystem,
    SourceFile,
)
from scripts.stage_local_mrf import stage_local_mrf, validate_local_file

_CSV = (
    "hospital_name,last_updated_on,version\n"
    "TEST HOSPITAL,2026-01-01,3.0.0\n"
    "description,code|1,code|1|type,setting,standard_charge|gross,standard_charge|discounted_cash\n"
    "COMPLETE BLOOD COUNT,85025,CPT,outpatient,50,40\n"
    "COMPREHENSIVE METABOLIC PANEL,80053,CPT,outpatient,80,60\n"
)


def _engine() -> Engine:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    return engine


def _registry(tmp_path: Path, *, ccn: str = "990001", name: str = "TEST HOSPITAL") -> Path:
    payload = {
        "version": "test",
        "sources": [
            {
                "ccn": ccn,
                "facility_name": name,
                "source_page_url": "https://hospital.example/prices",
                "machine_readable_file_url": (
                    "https://hospital.example/020999999_test_hospital_standardcharges.csv"
                ),
                "declared_format": "csv",
                "vendor_name": None,
                "health_system_name": None,
                "evidence": "official page link",
            }
        ],
    }
    path = tmp_path / "registry.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _mrf(tmp_path: Path, content: str = _CSV, name: str = "020999999_test_hospital.csv") -> Path:
    path = tmp_path / name
    path.write_text(content, encoding="utf-8")
    return path


def _seed_catalog(session: Session) -> None:
    category = ProcedureCategory(slug="labs", name="Labs", description="labs")
    session.add(category)
    session.flush()
    cpt = ProcedureCodeSystem(code_system="CPT", display_name="CPT", licensing_notes="n/a")
    session.add(cpt)
    session.flush()
    for slug, name, code in (
        ("complete-blood-count", "Complete Blood Count", "85025"),
        ("comprehensive-metabolic-panel", "Comprehensive Metabolic Panel", "80053"),
    ):
        proc = Procedure(
            slug=slug,
            consumer_name=name,
            short_description=name,
            long_description=name,
            category_id=category.id,
            service_setting="outpatient",
            complexity="low",
        )
        session.add(proc)
        session.flush()
        session.add(
            ProcedureCodeMapping(
                procedure_id=proc.id,
                code_system_id=cpt.id,
                code=code,
                mapping_status="approved",
            )
        )
    session.flush()


def _seed_facility(session: Session, ccn: str = "990001", name: str = "TEST HOSPITAL") -> Facility:
    facility = Facility(cms_certification_number=ccn, legal_name=name, display_name=name)
    facility.locations.append(
        FacilityLocation(
            address_line_1="1 Test St", city="Concord", state="NH", postal_code="03301"
        )
    )
    session.add(facility)
    session.flush()
    return facility


def _counts(session: Session) -> tuple[int, int]:
    sources = session.scalar(select(func.count(SourceFile.id))) or 0
    records = session.scalar(select(func.count(HospitalPriceRecord.id))) or 0
    return sources, records


# --------------------------------------------------------------------------- #


def test_valid_stage_imports_and_preserves_https_provenance(tmp_path: Path) -> None:
    reg = _registry(tmp_path)
    mrf = _mrf(tmp_path)
    engine = _engine()
    with Session(engine) as session:
        _seed_catalog(session)
        _seed_facility(session)
        session.commit()

        result = stage_local_mrf(session, "990001", mrf, registry_path=reg, state="NH")

        assert result["status"] == "imported"
        assert result["import"]["records_normalized"] == 2
        assert result["retrieval_method"] == "manual_stage_automated_fetch_blocked"
        # Provenance: HTTPS source_url preserved, NEVER file://.
        assert result["source_url"] == (
            "https://hospital.example/020999999_test_hospital_standardcharges.csv"
        )
        staged = session.scalars(
            select(SourceFile).where(SourceFile.source_type == "hospital_price_mrf")
        ).all()
        assert len(staged) == 1
        assert staged[0].source_url.startswith("https://")
        assert not staged[0].source_url.startswith("file://")
        assert "manually staged" in staged[0].source_name
        # Checksum was recorded on the provenance record.
        assert staged[0].checksum_sha256 == result["checksum_sha256"]
        # The staged file publishes (not a review-only fixture): coverage rose.
        assert result["coverage_after"]["facilities_with_publishable_prices"] == 1
        assert result["coverage_before"]["facilities_with_publishable_prices"] == 0
    engine.dispose()


def test_dry_run_validates_without_mutation(tmp_path: Path) -> None:
    reg = _registry(tmp_path)
    mrf = _mrf(tmp_path)
    engine = _engine()
    with Session(engine) as session:
        _seed_catalog(session)
        _seed_facility(session)
        session.commit()

        result = stage_local_mrf(
            session, "990001", mrf, registry_path=reg, state="NH", dry_run=True
        )

        assert result["status"] == "dry_run_ok"
        assert result["would_stage"]["source_url"].startswith("https://")
        assert result["would_stage"]["checksum_sha256"]
        # No mutation.
        sources, records = _counts(session)
        assert sources == 0 and records == 0
    engine.dispose()


def test_unknown_ccn_in_registry_errors_without_mutation(tmp_path: Path) -> None:
    reg = _registry(tmp_path, ccn="990001")
    mrf = _mrf(tmp_path)
    engine = _engine()
    with Session(engine) as session:
        _seed_catalog(session)
        _seed_facility(session)
        session.commit()

        result = stage_local_mrf(session, "999999", mrf, registry_path=reg, state="NH")

        assert result["status"] == "error"
        assert result["reason"] == "no_registry_entry"
        assert _counts(session) == (0, 0)
    engine.dispose()


def test_facility_absent_from_db_errors_without_mutation(tmp_path: Path) -> None:
    reg = _registry(tmp_path, ccn="990001")
    mrf = _mrf(tmp_path)
    engine = _engine()
    with Session(engine) as session:
        _seed_catalog(session)
        # No facility seeded.
        session.commit()

        result = stage_local_mrf(session, "990001", mrf, registry_path=reg, state="NH")

        assert result["status"] == "error"
        assert result["reason"] == "facility_not_found_or_name_mismatch"
        assert _counts(session) == (0, 0)
    engine.dispose()


def test_mismatched_hospital_file_fails_safe(tmp_path: Path) -> None:
    reg = _registry(tmp_path, ccn="990001", name="TEST HOSPITAL")
    # File belongs to a different hospital — identity token "test" absent.
    other = _CSV.replace("TEST HOSPITAL", "SOMEWHERE ELSE INFIRMARY")
    mrf = _mrf(tmp_path, content=other)
    engine = _engine()
    with Session(engine) as session:
        _seed_catalog(session)
        _seed_facility(session)
        session.commit()

        result = stage_local_mrf(session, "990001", mrf, registry_path=reg, state="NH")

        assert result["status"] == "invalid_artifact"
        names = {c["name"]: c["ok"] for c in result["validation"]["checks"]}
        assert names["identity_name_match"] is False
        # Failed validation must never have touched the database.
        assert _counts(session) == (0, 0)
    engine.dispose()


def test_html_challenge_page_is_rejected(tmp_path: Path) -> None:
    reg = _registry(tmp_path)
    # Simulate a saved Cloudflare "Just a moment" page instead of the real CSV.
    html = "<!DOCTYPE html><html><head><title>Just a moment...</title></head><body>x</body></html>"
    mrf = _mrf(tmp_path, content=html, name="challenge.csv")
    engine = _engine()
    with Session(engine) as session:
        _seed_catalog(session)
        _seed_facility(session)
        session.commit()

        result = stage_local_mrf(session, "990001", mrf, registry_path=reg, state="NH")

        assert result["status"] == "invalid_artifact"
        assert _counts(session) == (0, 0)
    engine.dispose()


def test_rerun_is_idempotent(tmp_path: Path) -> None:
    reg = _registry(tmp_path)
    mrf = _mrf(tmp_path)
    engine = _engine()
    with Session(engine) as session:
        _seed_catalog(session)
        _seed_facility(session)
        session.commit()

        first = stage_local_mrf(session, "990001", mrf, registry_path=reg, state="NH")
        assert first["status"] == "imported"
        sources_1, records_1 = _counts(session)

        second = stage_local_mrf(session, "990001", mrf, registry_path=reg, state="NH")
        assert second["status"] == "imported"
        # No duplicate source file or records on rerun.
        assert second["download_skipped_unchanged"] is True
        assert second["import"]["skipped_unchanged"] is True
        assert _counts(session) == (sources_1, records_1)
    engine.dispose()


def test_checksum_matches_file_contents(tmp_path: Path) -> None:
    import hashlib

    reg = _registry(tmp_path)
    mrf = _mrf(tmp_path)
    entry = {
        "ccn": "990001",
        "facility_name": "TEST HOSPITAL",
        "machine_readable_file_url": (
            "https://hospital.example/020999999_test_hospital_standardcharges.csv"
        ),
        "declared_format": "csv",
    }
    report = validate_local_file(entry, mrf)  # type: ignore[arg-type]
    assert report.ok is True
    assert report.checksum_sha256 == hashlib.sha256(mrf.read_bytes()).hexdigest()
    # No DB touched by validation at all — it takes no session.
    assert reg.exists()
