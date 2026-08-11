"""Read-only, reproducible audit of consumer-published price observations."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from sqlalchemy import or_, select

from packages.database import (
    Facility,
    FacilityLocation,
    FacilityPriceSource,
    FacilityProcedurePriceObservation,
    HospitalPriceRateDetail,
    HospitalPriceRecord,
    PayerEntity,
    PriceRecordProcedureMapping,
    Procedure,
    SourceFile,
    session_factory,
)
from packages.price_accuracy import AUDIT_VERSION, audit_observation, sha256_file


@dataclass(frozen=True)
class AuditRow:
    observation: Any
    record: Any
    rate: Any
    mapping: Any
    source_file: Any
    facility: Any
    location: Any
    procedure: Any
    price_source: Any


def _rank(identifier: object, seed: int) -> str:
    return hashlib.sha256(f"{seed}:{identifier}".encode()).hexdigest()


def _sample(rows: list[Any], size: int, seed: int) -> list[Any]:
    """Round-robin facilities, price types, and categories before deterministic fill."""
    ranked = sorted(rows, key=lambda row: _rank(row.observation.id, seed))
    selected: list[Any] = []
    seen: set[object] = set()
    groups: dict[tuple[object, ...], list[Any]] = defaultdict(list)
    for row in ranked:
        groups[(row.facility.id, row.observation.price_type, row.procedure.category_id)].append(row)
    buckets = list(groups.values())
    while buckets and len(selected) < size:
        remaining: list[list[Any]] = []
        for bucket in buckets:
            if bucket and len(selected) < size:
                row = bucket.pop(0)
                selected.append(row)
                seen.add(row.observation.id)
            if bucket:
                remaining.append(bucket)
        buckets = remaining
    for row in ranked:
        if len(selected) >= size:
            break
        if row.observation.id not in seen:
            selected.append(row)
    return selected


def run(args: argparse.Namespace) -> dict[str, object]:
    with session_factory() as session:
        statement = (
            select(
                FacilityProcedurePriceObservation,
                HospitalPriceRecord,
                HospitalPriceRateDetail,
                PriceRecordProcedureMapping,
                SourceFile,
                Facility,
                FacilityLocation,
                Procedure,
                FacilityPriceSource,
            )
            .join(
                HospitalPriceRecord,
                HospitalPriceRecord.id
                == FacilityProcedurePriceObservation.hospital_price_record_id,
            )
            .outerjoin(
                HospitalPriceRateDetail,
                HospitalPriceRateDetail.id
                == FacilityProcedurePriceObservation.hospital_price_rate_detail_id,
            )
            .join(
                PriceRecordProcedureMapping,
                (PriceRecordProcedureMapping.hospital_price_record_id == HospitalPriceRecord.id)
                & (
                    PriceRecordProcedureMapping.procedure_id
                    == FacilityProcedurePriceObservation.procedure_id
                ),
            )
            .join(SourceFile, SourceFile.id == HospitalPriceRecord.source_file_id)
            .join(Facility, Facility.id == FacilityProcedurePriceObservation.facility_id)
            .join(
                FacilityLocation,
                FacilityLocation.id == FacilityProcedurePriceObservation.facility_location_id,
            )
            .join(Procedure, Procedure.id == FacilityProcedurePriceObservation.procedure_id)
            .outerjoin(FacilityPriceSource, FacilityPriceSource.source_file_id == SourceFile.id)
            .where(
                FacilityProcedurePriceObservation.publication_status == "publishable",
                FacilityLocation.state == args.state.upper(),
            )
        )
        if args.facility:
            statement = statement.where(
                or_(
                    Facility.cms_certification_number == args.facility,
                    Facility.display_name.ilike(f"%{args.facility}%"),
                )
            )
        if args.procedure:
            statement = statement.where(
                or_(
                    Procedure.slug == args.procedure,
                    Procedure.consumer_name.ilike(f"%{args.procedure}%"),
                )
            )
        if args.payer:
            statement = statement.join(
                PayerEntity,
                PayerEntity.id == FacilityProcedurePriceObservation.payer_entity_id,
            ).where(
                or_(
                    PayerEntity.slug == args.payer,
                    PayerEntity.canonical_name.ilike(f"%{args.payer}%"),
                )
            )
        rows = [AuditRow(*row) for row in session.execute(statement)]
        audited = rows if args.full else _sample(rows, min(args.sample_size, len(rows)), args.seed)
        results: list[dict[str, object]] = []
        for row in audited:
            path = Path(row.source_file.storage_path)
            if not path.is_file():
                raw_root = Path(os.environ.get("HOSPITAL_PRICE_RAW_DIR", "/nonexistent"))
                path = raw_root / path.name
            raw_available = path.is_file()
            checksum_ok = raw_available and sha256_file(path) == row.source_file.checksum_sha256
            outcome = audit_observation(
                row.observation,
                row.record,
                row.rate,
                row.mapping,
                row.source_file,
                raw_source_available=raw_available,
                raw_checksum_verified=checksum_ok,
                source_location_id=(
                    None if row.price_source is None else row.price_source.facility_location_id
                ),
            )
            results.append(
                {
                    "observation_id": str(row.observation.id),
                    "facility": row.facility.display_name,
                    "location": row.location.location_name or row.location.city,
                    "procedure": row.procedure.consumer_name,
                    "price_type": row.observation.price_type,
                    "payer": None if row.rate is None else row.rate.source_payer_name,
                    "plan": None if row.rate is None else row.rate.source_plan_name,
                    **outcome.serializable(),
                }
            )
    statuses = Counter(str(item["status"]) for item in results)
    summary: dict[str, object] = {
        "audit_version": AUDIT_VERSION,
        "read_only": True,
        "state": args.state.upper(),
        "seed": args.seed,
        "candidate_observations": len(rows),
        "sample_size": len(results),
        "facilities": len({item["facility"] for item in results}),
        "locations": len({(item["facility"], item["location"]) for item in results}),
        "procedures": len({item["procedure"] for item in results}),
        "cash_count": sum(item["price_type"] == "discounted_cash" for item in results),
        "negotiated_count": sum(item["price_type"] == "payer_negotiated" for item in results),
        "status_counts": dict(sorted(statuses.items())),
        "exact_value_matches": sum(item["difference"] == "0.000000" for item in results),
        "semantic_matches": sum(
            all(cast(dict[str, bool], item["semantic_checks"]).values()) for item in results
        ),
        "provenance_matches": sum(
            all(
                cast(dict[str, bool], item["provenance_checks"])[key]
                for key in (
                    "source_file_present",
                    "source_url_present",
                    "source_checksum_present",
                    "source_record_identifier_present",
                    "source_payload_hash_present",
                    "bounded_source_payload_present",
                    "parser_version_present",
                )
            )
            for item in results
        ),
    }
    report = summary | {"results": results}
    print("AUDIT_SUMMARY=" + json.dumps(summary, sort_keys=True))
    golden = [
        {
            "facility": item["facility"],
            "location": item["location"],
            "procedure": item["procedure"],
            "price_type": item["price_type"],
            "payer": item["payer"],
            "plan": item["plan"],
            "carevero_value": item["normalized_amount"],
            "source_value": item["source_amount"],
            "source_identifier": cast(dict[str, object], item["evidence"])["record_locator"],
            "review_result": item["status"],
        }
        for item in results[:50]
    ]
    print("GOLDEN_SAMPLE=" + json.dumps(golden, separators=(",", ":")))
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state", default="NH")
    parser.add_argument("--sample-size", type=int, default=100)
    parser.add_argument("--facility")
    parser.add_argument("--procedure")
    parser.add_argument("--payer")
    parser.add_argument("--full", action="store_true")
    parser.add_argument("--seed", type=int, default=4700)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = run(args)
    payload = json.dumps(report, indent=2, sort_keys=True)
    if args.output:
        args.output.write_text(payload + "\n")
    print(payload)


if __name__ == "__main__":
    main()
