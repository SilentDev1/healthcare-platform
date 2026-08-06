import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from collectors.nppes_organizations.config import NppesSettings, nppes_settings
from packages.database import (
    Facility,
    FacilityAlias,
    FacilityIdentifier,
    FacilityIdentityCandidate,
    FacilitySourceObservation,
    ImportRun,
    SourceFile,
)
from packages.database.models import ImportStatus, SourceStatus
from packages.identity import IdentityInput, match_facility, normalize_identifier, normalize_name

INSTITUTIONAL_TAXONOMY_PREFIXES = (
    "261Q",
    "261U",
    "261X",
    "273R",
    "282N",
    "282N00000X",
    "283Q",
    "2873",
    "291U",
)


@dataclass
class NppesImportSummary:
    rows_examined: int = 0
    nh_organizations_processed: int = 0
    facilities_matched: int = 0
    new_facilities_created: int = 0
    candidates_created: int = 0
    identifiers_inserted: int = 0
    aliases_inserted: int = 0
    observations_inserted: int = 0
    skipped_unchanged: bool = False


def _load(source_path: Path | None, settings: NppesSettings) -> tuple[bytes, str]:
    if source_path:
        return source_path.read_bytes(), source_path.resolve().as_uri()
    response = httpx.get(
        settings.nppes_source_url,
        follow_redirects=True,
        timeout=settings.nppes_http_timeout_seconds,
    )
    response.raise_for_status()
    content = response.content
    if len(content) > settings.nppes_download_max_bytes:
        raise ValueError("NPPES response exceeds configured maximum")
    return content, settings.nppes_source_url


def _rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    if payload.get("Errors"):
        raise ValueError(f"NPPES API rejected the query: {payload['Errors']}")
    results = payload.get("results", payload.get("records", []))
    return [item for item in results if isinstance(item, dict)]


def _value(row: dict[str, Any]) -> dict[str, Any]:
    basic = row.get("basic", {})
    addresses = row.get("addresses", [])
    location = next(
        (item for item in addresses if item.get("address_purpose") == "LOCATION"),
        addresses[0] if addresses else {},
    )
    taxonomies = row.get("taxonomies", [])
    name = basic.get("organization_name") or row.get("organization_name") or ""
    return {
        "npi": str(row.get("number") or row.get("npi") or ""),
        "name": str(name),
        "address": str(location.get("address_1") or row.get("address") or ""),
        "city": str(location.get("city") or row.get("city") or ""),
        "state": str(location.get("state") or row.get("state") or ""),
        "postal": str(location.get("postal_code") or row.get("postal_code") or "")[:5],
        "phone": str(location.get("telephone_number") or row.get("phone") or ""),
        "taxonomies": [str(item.get("code", "")) for item in taxonomies]
        or list(row.get("taxonomy_codes", [])),
    }


def _relevant(item: dict[str, Any]) -> bool:
    return item["state"].upper() == "NH" and any(
        code.startswith(INSTITUTIONAL_TAXONOMY_PREFIXES) for code in item["taxonomies"]
    )


def backfill_cms_identifiers(session: Session) -> int:
    inserted = 0
    for facility in session.scalars(
        select(Facility).where(Facility.cms_certification_number.is_not(None))
    ):
        normalized = normalize_identifier("CMS_CCN", facility.cms_certification_number or "")
        if (
            session.scalar(
                select(FacilityIdentifier.id).where(
                    FacilityIdentifier.identifier_type == "CMS_CCN",
                    FacilityIdentifier.normalized_value == normalized,
                )
            )
            is None
        ):
            session.add(
                FacilityIdentifier(
                    facility_id=facility.id,
                    identifier_type="CMS_CCN",
                    identifier_value=facility.cms_certification_number or "",
                    normalized_value=normalized,
                    issuing_authority="Centers for Medicare & Medicaid Services",
                    source_file_id=facility.source_file_id,
                    confidence_score=1,
                )
            )
            inserted += 1
    session.flush()
    return inserted


def run_import(
    session: Session, source_path: Path | None = None, settings: NppesSettings = nppes_settings
) -> NppesImportSummary:
    content, source_url = _load(source_path, settings)
    checksum = hashlib.sha256(content).hexdigest()
    summary = NppesImportSummary()
    if session.scalar(
        select(SourceFile.id).where(
            SourceFile.checksum_sha256 == checksum,
            SourceFile.parser_version == settings.nppes_parser_version,
            SourceFile.source_type == "nppes_json",
            SourceFile.status == SourceStatus.COMPLETED,
        )
    ):
        summary.skipped_unchanged = True
        return summary
    settings.nppes_raw_data_dir.mkdir(parents=True, exist_ok=True)
    archive = settings.nppes_raw_data_dir / f"{checksum}.json"
    archive.write_bytes(content)
    source = SourceFile(
        source_name="NPPES organization registry",
        source_url=source_url,
        source_type="nppes_json",
        storage_path=str(archive),
        checksum_sha256=checksum,
        file_size=len(content),
        parser_version=settings.nppes_parser_version,
        status=SourceStatus.PROCESSING,
    )
    session.add(source)
    session.flush()
    run = ImportRun(
        importer_name="nppes_organizations", status=ImportStatus.RUNNING, source_file_id=source.id
    )
    session.add(run)
    session.flush()
    backfill_cms_identifiers(session)
    try:
        for row in _rows(json.loads(content)):
            summary.rows_examined += 1
            item = _value(row)
            if not _relevant(item) or not item["npi"] or not item["name"]:
                continue
            summary.nh_organizations_processed += 1
            result = match_facility(
                session,
                IdentityInput(
                    name=item["name"],
                    address=item["address"],
                    city=item["city"],
                    state=item["state"],
                    postal_code=item["postal"],
                    phone=item["phone"],
                    identifiers={"NPI_ORGANIZATION": item["npi"]},
                ),
            )
            if result.exact and result.facility_id:
                summary.facilities_matched += 1
                normalized_npi = normalize_identifier("NPI_ORGANIZATION", item["npi"])
                if (
                    session.scalar(
                        select(FacilityIdentifier.id).where(
                            FacilityIdentifier.identifier_type == "NPI_ORGANIZATION",
                            FacilityIdentifier.normalized_value == normalized_npi,
                        )
                    )
                    is None
                ):
                    session.add(
                        FacilityIdentifier(
                            facility_id=result.facility_id,
                            identifier_type="NPI_ORGANIZATION",
                            identifier_value=item["npi"],
                            normalized_value=normalized_npi,
                            issuing_authority="NPPES",
                            source_file_id=source.id,
                            confidence_score=1,
                        )
                    )
                    summary.identifiers_inserted += 1
                normalized_alias = normalize_name(item["name"])
                if (
                    session.scalar(
                        select(FacilityAlias.id).where(
                            FacilityAlias.facility_id == result.facility_id,
                            FacilityAlias.normalized_alias == normalized_alias,
                        )
                    )
                    is None
                ):
                    session.add(
                        FacilityAlias(
                            facility_id=result.facility_id,
                            alias_name=item["name"],
                            normalized_alias=normalized_alias,
                            alias_type="source_supplied",
                            source_file_id=source.id,
                        )
                    )
                    summary.aliases_inserted += 1
                session.add(
                    FacilitySourceObservation(
                        facility_id=result.facility_id,
                        source_file_id=source.id,
                        import_run_id=run.id,
                        source_record_identifier=item["npi"],
                        source_payload_hash=hashlib.sha256(
                            json.dumps(row, sort_keys=True).encode()
                        ).hexdigest(),
                        raw_payload=row,
                        observed_at=datetime.now(UTC),
                    )
                )
                summary.observations_inserted += 1
            else:
                session.add(
                    FacilityIdentityCandidate(
                        source_file_id=source.id,
                        import_run_id=run.id,
                        source_record_identifier=item["npi"],
                        candidate_facility_id=result.facility_id,
                        supplied_name=item["name"],
                        supplied_address=item["address"],
                        supplied_city=item["city"],
                        supplied_state=item["state"],
                        supplied_postal_code=item["postal"],
                        supplied_phone=item["phone"],
                        supplied_identifiers={"NPI_ORGANIZATION": item["npi"]},
                        deterministic_method=result.method,
                        score=result.score,
                        reason=result.reason,
                        status="probable_match" if result.facility_id else "pending",
                        raw_payload=row,
                    )
                )
                summary.candidates_created += 1
        run.status = ImportStatus.COMPLETED
        source.status = SourceStatus.COMPLETED
    except Exception as exc:
        run.status = ImportStatus.FAILED
        source.status = SourceStatus.FAILED
        run.error_summary = f"{type(exc).__name__}: {exc}"[:2000]
        raise
    finally:
        run.finished_at = datetime.now(UTC)
        run.rows_read = summary.rows_examined
        run.rows_inserted = (
            summary.identifiers_inserted
            + summary.aliases_inserted
            + summary.observations_inserted
            + summary.candidates_created
        )
        session.commit()
    return summary
