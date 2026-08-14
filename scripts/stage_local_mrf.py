"""Stage a manually-downloaded official MRF for import when automated fetch is blocked.

Some hospitals host their CMS machine-readable file behind a Cloudflare (or similar)
challenge that the automated importer's HTTP client cannot pass, even though the file
is a legitimate, browser-accessible official source. This tool imports such a file
from a locally-staged copy WITHOUT weakening provenance:

  * the authoritative HTTPS source_url from the verified registry is preserved as the
    public/provenance URL (never replaced with a file:// path — file:// sources are
    treated as non-publishable fixtures by the projection);
  * it reuses the existing register_local_file + resumable import + summary-rebuild
    path (no parallel ingestion mechanism);
  * it validates the local artifact (identity, format, checksum) and FAILS SAFE
    before any production mutation;
  * it records that retrieval was a manual stage because automated fetch was blocked.

Provider-agnostic: works for any CCN already registered in
data/fixtures/verified_hospital_price_sources.json, not just Cottage.

Typical prod use (file first uploaded to the gcsfuse-mounted sources bucket):

    gcloud run jobs execute carevero-beta-price-refresh --region=us-east4 \
        --args="-m,scripts.stage_local_mrf,--ccn,301301,\
--path,/mnt/sources/manual/020223321_cottage_hospital_standardcharges.csv"

Add --dry-run to validate the artifact + provenance without importing.
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from collectors.hospital_prices.config import HospitalPriceSettings, hospital_price_settings
from collectors.hospital_prices.downloader import (
    _stream_checksum_and_size,
    detect_container,
    register_local_file,
    validate_downloaded_file,
)
from collectors.hospital_prices.importer import import_price_source
from collectors.hospital_prices.location_association import associate_verified_locations
from collectors.hospital_prices.projections import evaluate_pricing_health, rebuild_price_summaries
from collectors.hospital_prices.scope import active_consumer_facility_ids
from packages.database import (
    Facility,
    FacilityPriceSource,
    FacilityProcedurePriceSummary,
    SourceFile,
    session_factory,
)
from scripts.register_verified_price_sources import (
    DEFAULT_REGISTRY,
    VerifiedSource,
    load_registry,
    register_sources,
)
from scripts.seed_price_mappings import seed_price_mappings

# Tokens too generic to identify a specific hospital on their own.
_GENERIC_NAME_TOKENS = frozenset(
    {
        "hospital",
        "hospitals",
        "medical",
        "center",
        "centre",
        "health",
        "healthcare",
        "system",
        "services",
        "clinic",
        "care",
        "the",
        "of",
        "and",
        "inc",
        "memorial",
        "regional",
        "community",
        "county",
        "district",
    }
)

# Data container formats a real MRF may legitimately be.
_DATA_FORMATS = frozenset({"csv", "json", "zip", "gzip", "xml"})


@dataclass
class Check:
    name: str
    ok: bool
    detail: str


@dataclass
class ValidationReport:
    ccn: str
    path: str
    ok: bool = True
    checksum_sha256: str | None = None
    file_size: int | None = None
    detected_format: str | None = None
    source_url: str | None = None
    checks: list[Check] = field(default_factory=list)

    def add(self, name: str, ok: bool, detail: str, *, critical: bool = True) -> None:
        self.checks.append(Check(name, ok, detail))
        if critical and not ok:
            self.ok = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "ccn": self.ccn,
            "path": self.path,
            "ok": self.ok,
            "checksum_sha256": self.checksum_sha256,
            "file_size": self.file_size,
            "detected_format": self.detected_format,
            "source_url": self.source_url,
            "checks": [{"name": c.name, "ok": c.ok, "detail": c.detail} for c in self.checks],
        }


def _distinctive_tokens(name: str) -> list[str]:
    tokens = re.findall(r"[a-z0-9]+", name.lower())
    distinctive = [t for t in tokens if len(t) >= 3 and t not in _GENERIC_NAME_TOKENS]
    return distinctive or [t for t in tokens if len(t) >= 3]


def _ein_from_url(url: str) -> str | None:
    match = re.search(r"/0?(\d{9})[_-]", url) or re.search(r"(\d{9,10})", Path(url).name)
    return match.group(1) if match else None


def validate_local_file(
    entry: VerifiedSource,
    path: Path,
    settings: HospitalPriceSettings = hospital_price_settings,
) -> ValidationReport:
    """Read-only validation of the staged artifact. Never mutates anything."""
    report = ValidationReport(ccn=entry["ccn"], path=str(path))
    report.source_url = entry["machine_readable_file_url"]

    if not path.exists() or not path.is_file():
        report.add("file_exists", False, f"no readable file at {path}")
        return report
    report.add("file_exists", True, "present")

    size = path.stat().st_size
    report.file_size = size
    report.add("non_empty", size > 100, f"{size} bytes")
    if size <= 100:
        return report

    # Reject HTML error/challenge pages and other non-data content up front.
    is_valid, reason = validate_downloaded_file(path)
    report.add("looks_like_data", is_valid, reason)

    detected = detect_container(path)
    report.detected_format = detected
    report.add(
        "recognized_format",
        detected in _DATA_FORMATS,
        f"detected {detected}",
    )
    declared = (entry.get("declared_format") or "").lower()
    if declared:
        # A declared csv arriving as a zip/gzip archive of a csv is fine; only flag a
        # detected non-data format against a declared data format.
        report.add(
            "declared_format_consistent",
            detected in _DATA_FORMATS,
            f"declared {declared}, detected {detected}",
            critical=False,
        )

    # Identity: the hospital's distinctive name tokens must appear in the file head,
    # and/or its EIN. Content is authoritative; filename is corroborating only.
    head = path.read_bytes()[:65536].decode("utf-8", errors="replace").lower()
    tokens = _distinctive_tokens(entry["facility_name"])
    present = [t for t in tokens if t in head]
    report.add(
        "identity_name_match",
        bool(tokens) and set(present) == set(tokens),
        f"expected {tokens}, found {present}",
    )
    ein = _ein_from_url(entry["machine_readable_file_url"])
    if ein:
        ein_ok = ein in head or ein in path.name or ein in entry["machine_readable_file_url"]
        report.add(
            "identity_ein_evidence",
            ein_ok,
            f"EIN {ein} {'present' if ein_ok else 'absent'}",
            critical=False,
        )
        report.add(
            "filename_evidence_consistent",
            any(t in path.name.lower() for t in tokens) or ein in path.name,
            f"local filename {path.name}",
            critical=False,
        )

    # Freshness (informational): surface a CMS last_updated_on if present.
    fresh = re.search(r"last[_ ]updated[_ ]on[^0-9]{0,20}(\d{1,4}[-/]\d{1,2}[-/]\d{1,4})", head)
    report.add(
        "freshness_hint",
        True,
        f"last_updated_on={fresh.group(1)}" if fresh else "no last_updated_on marker found",
        critical=False,
    )

    checksum, _ = _stream_checksum_and_size(path, settings.hospital_price_max_bytes)
    report.checksum_sha256 = checksum
    report.add("checksum_computed", True, checksum)
    return report


def _publishing_facility_count(session: Session, facility_ids: set[Any]) -> int:
    return (
        session.scalar(
            select(func.count(func.distinct(FacilityProcedurePriceSummary.facility_id))).where(
                FacilityProcedurePriceSummary.facility_id.in_(facility_ids),
                FacilityProcedurePriceSummary.publication_status == "publishable",
            )
        )
        or 0
    )


def stage_local_mrf(
    session: Session,
    ccn: str,
    path: Path,
    *,
    registry_path: Path = DEFAULT_REGISTRY,
    state: str = "NH",
    dry_run: bool = False,
    settings: HospitalPriceSettings = hospital_price_settings,
) -> dict[str, Any]:
    """Validate then (unless dry_run) stage + import a manually-downloaded MRF.

    Fails safe before any production mutation: a missing registry entry, an unknown
    facility, or a failed artifact validation returns a report and writes nothing.
    """
    entries = {e["ccn"]: e for e in load_registry(registry_path)}
    entry = entries.get(ccn)
    if entry is None:
        return {
            "status": "error",
            "reason": "no_registry_entry",
            "ccn": ccn,
            "detail": f"CCN {ccn} is not in {registry_path}",
        }

    validation = validate_local_file(entry, path, settings)
    if not validation.ok:
        return {"status": "invalid_artifact", "ccn": ccn, "validation": validation.as_dict()}

    # Read-only existence check before ANY mutation.
    facility = session.scalar(select(Facility).where(Facility.cms_certification_number == ccn))
    if facility is None or facility.legal_name != entry["facility_name"]:
        return {
            "status": "error",
            "reason": "facility_not_found_or_name_mismatch",
            "ccn": ccn,
            "expected_name": entry["facility_name"],
            "found_name": facility.legal_name if facility else None,
            "validation": validation.as_dict(),
        }

    facility_ids = active_consumer_facility_ids(session, state.upper())
    coverage_before = _publishing_facility_count(session, facility_ids)

    if dry_run:
        return {
            "status": "dry_run_ok",
            "ccn": ccn,
            "would_stage": {
                "source_url": entry["machine_readable_file_url"],
                "checksum_sha256": validation.checksum_sha256,
                "detected_format": validation.detected_format,
                "retrieval_method": "manual_stage_automated_fetch_blocked",
            },
            "coverage_before": {
                "facilities_with_publishable_prices": coverage_before,
                "state_facilities": len(facility_ids),
            },
            "validation": validation.as_dict(),
        }

    # --- Mutation phase ------------------------------------------------------ #
    registration = register_sources(session, [entry], state=state.upper())
    session.commit()
    price_source = session.scalar(
        select(FacilityPriceSource).where(
            FacilityPriceSource.facility_id == facility.id,
            FacilityPriceSource.machine_readable_file_url == entry["machine_readable_file_url"],
            FacilityPriceSource.active.is_(True),
        )
    )
    if price_source is None:
        return {
            "status": "error",
            "reason": "price_source_registration_failed",
            "ccn": ccn,
            "registration": registration,
        }

    associate_verified_locations(session)
    seed_price_mappings(session)
    session.commit()

    downloaded = register_local_file(session, price_source, path, settings)
    # Record the retrieval method on the provenance record without touching the
    # authoritative HTTPS source_url.
    staged_source = session.get(SourceFile, downloaded.source_file_id)
    if staged_source is not None:
        staged_source.source_name = (
            f"Hospital MRF (manually staged; automated fetch blocked): {price_source.id}"
        )
        session.commit()

    imported = import_price_source(session, price_source, settings)
    projection = rebuild_price_summaries(session)
    health = evaluate_pricing_health(session)

    coverage_after = _publishing_facility_count(session, facility_ids)
    return {
        "status": "imported",
        "ccn": ccn,
        "hospital": facility.display_name,
        "source_url": staged_source.source_url if staged_source else None,
        "retrieval_method": "manual_stage_automated_fetch_blocked",
        "checksum_sha256": downloaded.checksum,
        "download_skipped_unchanged": downloaded.skipped_unchanged,
        "import": {
            "records_normalized": imported.records_normalized,
            "records_rejected": imported.records_rejected,
            "rate_details": imported.rate_details,
            "exact_mappings": imported.exact_procedure_mappings,
            "skipped_unchanged": imported.skipped_unchanged,
            "interrupted": imported.interrupted,
        },
        "projection": projection,
        "health": health,
        "coverage_before": {"facilities_with_publishable_prices": coverage_before},
        "coverage_after": {
            "facilities_with_publishable_prices": coverage_after,
            "state_facilities": len(facility_ids),
        },
        "validation": validation.as_dict(),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ccn", required=True)
    parser.add_argument("--path", required=True, type=Path)
    parser.add_argument("--state", default="NH")
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate the artifact + provenance without importing (no mutation).",
    )
    args = parser.parse_args()
    with session_factory() as session:
        result = stage_local_mrf(
            session,
            args.ccn,
            args.path,
            registry_path=args.registry,
            state=args.state,
            dry_run=args.dry_run,
        )
    print("STAGE_LOCAL_MRF=" + json.dumps(result, default=str, separators=(",", ":")))


if __name__ == "__main__":
    main()
