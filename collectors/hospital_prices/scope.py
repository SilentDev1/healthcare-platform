import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from collectors.hospital_prices.inventory import load_inventory
from packages.database import Facility, FacilityLocation


def active_consumer_facility_ids(session: Session, state_code: str) -> set[uuid.UUID]:
    """Return the documented consumer denominator for a state without duplicating locations."""
    statement = (
        select(Facility.id)
        .distinct()
        .join(FacilityLocation)
        .where(FacilityLocation.state == state_code.upper(), Facility.active.is_(True))
    )
    if state_code.upper() == "NH":
        active_ccns = {entry.cms_ccn for entry in load_inventory().active_hospitals}
        state_ids = set(session.scalars(statement))
        # Apply the reviewed statewide inventory only when the canonical NH dataset is present.
        # Small test or partial-state databases retain their represented active denominator.
        if len(state_ids) >= len(active_ccns):
            return set(
                session.scalars(statement.where(Facility.cms_certification_number.in_(active_ccns)))
            )
        return state_ids
    return set(session.scalars(statement))
