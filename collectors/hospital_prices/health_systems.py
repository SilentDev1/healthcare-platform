"""Health system discovery and source propagation.

Populates FacilityRelationship records for known health systems and
propagates discovered MRF sources from one system member to siblings.
This module is state-agnostic; health systems may span multiple states.
"""

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from collectors.hospital_prices.inventory import (
    HealthSystemEntry,
    HospitalInventory,
    load_inventory,
)
from packages.database import (
    Facility,
    FacilityPriceSource,
    FacilityRelationship,
)


def populate_facility_relationships(
    session: Session,
    inventory: HospitalInventory | None = None,
) -> dict[str, int]:
    """Create FacilityRelationship records for all health systems in inventory.

    Returns {system_name: relationships_created}.
    """
    inv = inventory or load_inventory()
    results: dict[str, int] = {}

    for system_name, system in inv.health_systems.items():
        created = _populate_system(session, system_name, system)
        results[system_name] = created

    session.flush()
    return results


def _populate_system(session: Session, system_name: str, system: HealthSystemEntry) -> int:
    """Create parent-child relationships for a single health system."""
    # Find the first member as the "parent" (flagship facility)
    member_facilities: list[Facility] = []
    for member_name in system.members:
        facility = session.scalar(select(Facility).where(Facility.legal_name == member_name))
        if facility:
            member_facilities.append(facility)

    if len(member_facilities) < 2:
        return 0

    parent = member_facilities[0]
    created = 0
    for child in member_facilities[1:]:
        existing = session.scalar(
            select(FacilityRelationship).where(
                FacilityRelationship.parent_facility_id == parent.id,
                FacilityRelationship.child_facility_id == child.id,
                FacilityRelationship.relationship_type == "health_system",
            )
        )
        if not existing:
            session.add(
                FacilityRelationship(
                    parent_facility_id=parent.id,
                    child_facility_id=child.id,
                    relationship_type="health_system",
                    active=True,
                    confidence_score=1,
                )
            )
            created += 1
    return created


def propagate_system_sources(
    session: Session,
    inventory: HospitalInventory | None = None,
) -> dict[str, int]:
    """Copy discovered MRF sources from one system member to siblings lacking sources.

    Returns {system_name: sources_propagated}.
    """
    inv = inventory or load_inventory()
    results: dict[str, int] = {}

    for system_name, system in inv.health_systems.items():
        propagated = _propagate_for_system(session, system_name, system)
        results[system_name] = propagated

    session.commit()
    return results


def _propagate_for_system(session: Session, system_name: str, system: HealthSystemEntry) -> int:
    """Propagate sources within a single health system."""
    member_facilities: list[Facility] = []
    for member_name in system.members:
        facility = session.scalar(select(Facility).where(Facility.legal_name == member_name))
        if facility:
            member_facilities.append(facility)

    if not member_facilities:
        return 0

    # Collect all active sources from all members
    all_sources: list[FacilityPriceSource] = []
    members_with_sources: set[object] = set()
    for facility in member_facilities:
        sources = list(
            session.scalars(
                select(FacilityPriceSource).where(
                    FacilityPriceSource.facility_id == facility.id,
                    FacilityPriceSource.active.is_(True),
                )
            )
        )
        if sources:
            all_sources.extend(sources)
            members_with_sources.add(facility.id)

    if not all_sources:
        return 0

    # Propagate to members without sources
    propagated = 0
    for facility in member_facilities:
        if facility.id in members_with_sources:
            continue
        for source in all_sources:
            existing = session.scalar(
                select(FacilityPriceSource).where(
                    FacilityPriceSource.facility_id == facility.id,
                    FacilityPriceSource.machine_readable_file_url
                    == source.machine_readable_file_url,
                )
            )
            if not existing:
                session.add(
                    FacilityPriceSource(
                        facility_id=facility.id,
                        source_type="hospital_mrf",
                        source_page_url=source.source_page_url,
                        machine_readable_file_url=source.machine_readable_file_url,
                        cms_hpt_txt_url=source.cms_hpt_txt_url,
                        active=True,
                        discovery_method="health_system_propagation",
                        health_system_name=system_name,
                        first_seen_at=datetime.now(UTC),
                        last_seen_at=datetime.now(UTC),
                    )
                )
                propagated += 1
    return propagated
