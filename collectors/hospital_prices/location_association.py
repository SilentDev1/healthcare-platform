import json
import re
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from packages.database import Facility, FacilityLocation, FacilityPriceSource, HospitalPriceRecord


@dataclass(frozen=True)
class LocationAssociationResult:
    locations_created: int
    sources_associated: int
    records_associated: int
    unresolved_sources: int


def _normalized_address(value: str) -> str:
    tokens = re.findall(r"[a-z0-9]+", value.lower())
    aliases = {"drive": "dr", "avenue": "ave", "road": "rd", "street": "st"}
    return " ".join(aliases.get(token, token) for token in tokens)


def _unambiguous_source_locations(
    rows: Iterable[tuple[object, object]],
) -> dict[object, object]:
    locations_by_source_file: dict[object, set[object]] = defaultdict(set)
    for source_file_id, location_id in rows:
        locations_by_source_file[source_file_id].add(location_id)
    return {
        source_file_id: next(iter(location_ids))
        for source_file_id, location_ids in locations_by_source_file.items()
        if len(location_ids) == 1
    }


def associate_verified_locations(
    session: Session, seed_path: Path = Path("data/fixtures/verified_price_locations.json")
) -> LocationAssociationResult:
    payload = json.loads(seed_path.read_text())
    entries = payload.get("locations", [])
    created = associated = records = 0
    for entry in entries:
        facility = session.scalar(
            select(Facility).where(Facility.cms_certification_number == str(entry["facility_ccn"]))
        )
        if facility is None:
            continue
        facility_locations = list(
            session.scalars(
                select(FacilityLocation).where(FacilityLocation.facility_id == facility.id)
            )
        )
        normalized_seed_address = _normalized_address(str(entry["address_line_1"]))
        equivalent_locations = [
            candidate
            for candidate in facility_locations
            if _normalized_address(candidate.address_line_1) == normalized_seed_address
            and candidate.city.lower() == str(entry["city"]).lower()
            and candidate.state.upper() == str(entry["state"]).upper()
        ]
        location = next(
            (
                candidate
                for candidate in equivalent_locations
                if candidate.address_line_1 == str(entry["address_line_1"])
            ),
            equivalent_locations[0] if equivalent_locations else None,
        )
        if location is None:
            location = FacilityLocation(
                facility_id=facility.id,
                location_name=str(entry["location_name"]),
                location_type=str(entry["location_type"]),
                active=True,
                address_line_1=str(entry["address_line_1"]),
                city=str(entry["city"]).upper(),
                state=str(entry["state"]).upper(),
                postal_code=str(entry["postal_code"]),
            )
            session.add(location)
            session.flush()
            created += 1
        else:
            location.location_name = str(entry["location_name"])
            location.location_type = str(entry["location_type"])
            location.active = True
            for duplicate in equivalent_locations:
                if duplicate.id != location.id:
                    duplicate.active = False
        token = str(entry["source_filename_token"]).lower()
        for source in session.scalars(
            select(FacilityPriceSource).where(
                FacilityPriceSource.facility_id == facility.id,
                FacilityPriceSource.active.is_(True),
            )
        ):
            if token not in source.machine_readable_file_url.lower():
                continue
            source.facility_location_id = location.id
            source.location_association_status = "verified"
            source.location_association_evidence = {
                "method": "exact_source_filename_token",
                "token": entry["source_filename_token"],
                "facility_ccn": entry["facility_ccn"],
                "evidence_url": entry["evidence_url"],
                "seed_version": payload.get("version"),
            }
            associated += 1

    # A facility with exactly one active physical location is deterministic.
    for facility in session.scalars(select(Facility).where(Facility.active.is_(True))):
        locations = list(
            session.scalars(
                select(FacilityLocation).where(
                    FacilityLocation.facility_id == facility.id,
                    FacilityLocation.active.is_(True),
                )
            )
        )
        if len(locations) != 1:
            continue
        location = locations[0]
        for source in session.scalars(
            select(FacilityPriceSource).where(
                FacilityPriceSource.facility_id == facility.id,
                FacilityPriceSource.active.is_(True),
                FacilityPriceSource.facility_location_id.is_(None),
            )
        ):
            source.facility_location_id = location.id
            source.location_association_status = "verified"
            source.location_association_evidence = {
                "method": "only_active_location",
                "facility_id": str(facility.id),
            }
            associated += 1
    session.flush()
    # Migration 0008 added record-level location identity after many source files
    # had already been imported. A verified source-to-location association is
    # authoritative evidence for deterministically backfilling those records.
    verified_sources = session.execute(
        select(
            FacilityPriceSource.source_file_id,
            FacilityPriceSource.facility_location_id,
        ).where(
            FacilityPriceSource.source_file_id.is_not(None),
            FacilityPriceSource.facility_location_id.is_not(None),
            FacilityPriceSource.location_association_status == "verified",
            FacilityPriceSource.active.is_(True),
        )
    ).all()
    verified_pairs = [
        (source_file_id, location_id)
        for source_file_id, location_id in verified_sources
        if source_file_id is not None and location_id is not None
    ]
    for source_file_id, location_id in _unambiguous_source_locations(verified_pairs).items():
        result = session.execute(
            update(HospitalPriceRecord)
            .where(
                HospitalPriceRecord.source_file_id == source_file_id,
                HospitalPriceRecord.facility_location_id.is_(None),
            )
            .values(facility_location_id=location_id)
        )
        records += int(result.rowcount or 0)
    unresolved_count = (
        session.scalar(
            select(func.count(FacilityPriceSource.id)).where(
                FacilityPriceSource.active.is_(True),
                FacilityPriceSource.facility_location_id.is_(None),
            )
        )
        or 0
    )
    session.commit()
    return LocationAssociationResult(created, associated, records, unresolved_count)
