import re
from dataclasses import dataclass
from urllib.parse import unquote, urlparse

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from packages.database import (
    Facility,
    FacilityPriceSource,
    FacilitySourceObservation,
    HospitalPriceRecord,
)


def _tokens(value: str) -> tuple[str, ...]:
    return tuple(re.findall(r"[a-z0-9]+", value.lower()))


def filename_identifies_facility(url: str, facility_name: str) -> bool:
    """Require the complete ordered facility name in the URL filename; never fuzzy-match."""
    filename = unquote(urlparse(url).path.rsplit("/", 1)[-1])
    facility_tokens = _tokens(facility_name)
    filename_tokens = list(_tokens(filename))
    if len(facility_tokens) < 2:
        return False
    if filename_tokens and filename_tokens[0].isdigit():
        filename_tokens.pop(0)
    while filename_tokens and filename_tokens[-1] in {"csv", "json", "standardcharges"}:
        filename_tokens.pop()
    return tuple(filename_tokens) == facility_tokens


@dataclass(frozen=True)
class FacilityAssociationResult:
    urls_reconciled: int
    sources_deactivated: int
    records_reassigned: int
    observations_reassigned: int


def reconcile_filename_facility_associations(session: Session) -> FacilityAssociationResult:
    """Reconcile system-propagated URLs only when one filename is an exact name match."""
    rows = session.execute(
        select(FacilityPriceSource, Facility).join(
            Facility, Facility.id == FacilityPriceSource.facility_id
        )
    ).all()
    by_url: dict[str, list[tuple[FacilityPriceSource, Facility]]] = {}
    for source, facility in rows:
        by_url.setdefault(source.machine_readable_file_url, []).append((source, facility))

    reconciled = deactivated = records = observations = 0
    for candidates in by_url.values():
        if len(candidates) < 2:
            continue
        matches = [
            pair
            for pair in candidates
            if filename_identifies_facility(pair[0].machine_readable_file_url, pair[1].display_name)
        ]
        if len(matches) != 1:
            continue
        target_source, target_facility = matches[0]
        file_ids = {
            source.source_file_id
            for source, _facility in candidates
            if source.source_file_id is not None
        }
        if len(file_ids) != 1:
            continue
        source_file_id = file_ids.pop()
        target_source.source_file_id = source_file_id
        for source, facility in candidates:
            if facility.id != target_facility.id:
                source.active = False
                deactivated += 1
        records += session.execute(
            update(HospitalPriceRecord)
            .where(HospitalPriceRecord.source_file_id == source_file_id)
            .values(facility_id=target_facility.id)
        ).rowcount
        observations += session.execute(
            update(FacilitySourceObservation)
            .where(FacilitySourceObservation.source_file_id == source_file_id)
            .values(facility_id=target_facility.id)
        ).rowcount
        reconciled += 1
    session.flush()
    return FacilityAssociationResult(reconciled, deactivated, records, observations)
