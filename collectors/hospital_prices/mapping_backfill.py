"""Deterministic approved-code mapping repair for previously imported records."""

from __future__ import annotations

import uuid
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import delete, select
from sqlalchemy.orm import Session, aliased

from packages.database import (
    HospitalPriceRecord,
    PriceRecordProcedureMapping,
    PriceServiceCode,
    ProcedureCodeMapping,
    ProcedureCodeSystem,
)


@dataclass(frozen=True)
class MappingBackfillResult:
    ambiguous_registry_mappings: int
    ambiguous_record_mappings_removed: int
    records_mapped: int
    records_skipped_for_conflict: int


def backfill_approved_code_mappings(
    session: Session, facility_ids: Iterable[uuid.UUID]
) -> MappingBackfillResult:
    """Map old records only when an approved standard code has one meaning."""
    registry_rows = session.execute(
        select(ProcedureCodeMapping, ProcedureCodeSystem)
        .join(ProcedureCodeSystem)
        .where(ProcedureCodeMapping.mapping_status.in_(["approved", "reviewed"]))
    ).all()
    by_code: dict[tuple[str, str], list[ProcedureCodeMapping]] = defaultdict(list)
    for mapping, system in registry_rows:
        by_code[(system.code_system, mapping.code)].append(mapping)

    ambiguous_ids = {
        mapping.id
        for mappings in by_code.values()
        if len({mapping.procedure_id for mapping in mappings}) > 1
        for mapping in mappings
    }
    removed = 0
    if ambiguous_ids:
        result = session.execute(
            delete(PriceRecordProcedureMapping).where(
                PriceRecordProcedureMapping.source_code_mapping_id.in_(ambiguous_ids)
            )
        )
        removed = int(result.rowcount or 0)
        for mapping, _system in registry_rows:
            if mapping.id in ambiguous_ids:
                mapping.mapping_status = "review_required"
    session.flush()

    existing_mapping = aliased(PriceRecordProcedureMapping)
    candidates = session.execute(
        select(
            PriceServiceCode.hospital_price_record_id,
            ProcedureCodeMapping.procedure_id,
            ProcedureCodeMapping.id,
        )
        .join(
            HospitalPriceRecord,
            HospitalPriceRecord.id == PriceServiceCode.hospital_price_record_id,
        )
        .join(
            ProcedureCodeSystem,
            ProcedureCodeSystem.code_system == PriceServiceCode.code_system,
        )
        .join(
            ProcedureCodeMapping,
            (ProcedureCodeMapping.code_system_id == ProcedureCodeSystem.id)
            & (ProcedureCodeMapping.code == PriceServiceCode.code),
        )
        .outerjoin(
            existing_mapping,
            existing_mapping.hospital_price_record_id == PriceServiceCode.hospital_price_record_id,
        )
        .where(
            HospitalPriceRecord.facility_id.in_(set(facility_ids)),
            ProcedureCodeMapping.mapping_status.in_(["approved", "reviewed"]),
            existing_mapping.id.is_(None),
        )
    ).all()
    by_record: dict[uuid.UUID, list[tuple[uuid.UUID, uuid.UUID]]] = defaultdict(list)
    for record_id, procedure_id, mapping_id in candidates:
        by_record[record_id].append((procedure_id, mapping_id))

    mapped = conflicts = 0
    now = datetime.now(UTC)
    for record_id, matches in by_record.items():
        distinct_procedures = {procedure_id for procedure_id, _mapping_id in matches}
        if len(distinct_procedures) != 1:
            conflicts += 1
            continue
        procedure_id, mapping_id = sorted(matches, key=lambda item: str(item[1]))[0]
        session.add(
            PriceRecordProcedureMapping(
                hospital_price_record_id=record_id,
                procedure_id=procedure_id,
                mapping_method="exact_approved_code_backfill",
                confidence_score=1,
                reviewed=True,
                reviewed_by="approved-code-registry-backfill",
                reviewed_at=now,
                source_code_mapping_id=mapping_id,
            )
        )
        mapped += 1
    session.flush()
    return MappingBackfillResult(len(ambiguous_ids), removed, mapped, conflicts)
