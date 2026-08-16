"""Provider-neutral coverage metrics — read-only, SEPARATE from hospital MRF coverage.

The NH hospital metric (`facilities_with_publishable_prices` = X/26) keeps its exact
meaning and is NOT redefined here. This reports the new provider-neutral dimensions so
non-hospital expansion is measured on its own axes:

    organizations, service locations, locations-by-capability, verified service
    availability, services with/without published prices, price sources by class.

"Service offered" and "price available" are reported as distinct numbers and never
collapsed; a location that offers a service with no Carevero price is counted as
offered-without-price, never as $0 or as missing.

Run: python -m scripts.provider_neutral_coverage
"""

from __future__ import annotations

import json

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from packages.database import (
    FacilityLocation,
    FacilityPriceSource,
    FacilityProcedurePriceSummary,
    LocationCapability,
    LocationServiceAvailability,
    Organization,
    get_session,
)


def provider_coverage(session: Session | None = None) -> dict[str, object]:
    if session is None:
        session = next(get_session())

    organizations_total = session.scalar(
        select(func.count()).select_from(Organization).where(Organization.active.is_(True))
    )
    organizations_by_type = {
        str(row[0]): int(row[1])
        for row in session.execute(
            select(Organization.organization_type, func.count())
            .where(Organization.active.is_(True))
            .group_by(Organization.organization_type)
        )
    }
    service_locations_total = session.scalar(
        select(func.count()).select_from(FacilityLocation).where(FacilityLocation.active.is_(True))
    )
    # Distinct LOCATIONS holding each capability (not raw capability rows).
    locations_by_capability = {
        str(row[0]): int(row[1])
        for row in session.execute(
            select(
                LocationCapability.capability,
                func.count(func.distinct(LocationCapability.facility_location_id)),
            )
            .where(LocationCapability.active.is_(True))
            .group_by(LocationCapability.capability)
        )
    }

    # Verified service availability, by status — evidence-backed "offered here".
    availability_by_status = {
        str(row[0]): int(row[1])
        for row in session.execute(
            select(LocationServiceAvailability.availability_status, func.count())
            .where(LocationServiceAvailability.active.is_(True))
            .group_by(LocationServiceAvailability.availability_status)
        )
    }
    services_offered = availability_by_status.get("offered", 0)

    # Distinct (location, procedure) cells that have a publishable price.
    priced_cells = {
        (fid, pid)
        for fid, pid in session.execute(
            select(
                FacilityProcedurePriceSummary.facility_location_id,
                FacilityProcedurePriceSummary.procedure_id,
            )
            .where(FacilityProcedurePriceSummary.publication_status == "publishable")
            .distinct()
        )
    }
    # Offered cells (from the availability table) split by whether we hold a price —
    # the offered != priced separation, as explicit counts (never collapsed to $0).
    offered_cells = list(
        session.execute(
            select(
                LocationServiceAvailability.facility_location_id,
                LocationServiceAvailability.procedure_id,
            ).where(
                LocationServiceAvailability.active.is_(True),
                LocationServiceAvailability.availability_status == "offered",
            )
        )
    )
    offered_with_price = sum(1 for cell in offered_cells if (cell[0], cell[1]) in priced_cells)
    offered_without_price = len(offered_cells) - offered_with_price

    price_sources_by_class = {
        str(row[0]) if row[0] is not None else "UNCLASSIFIED": int(row[1])
        for row in session.execute(
            select(FacilityPriceSource.source_class, func.count())
            .where(FacilityPriceSource.active.is_(True))
            .group_by(FacilityPriceSource.source_class)
        )
    }

    return {
        "organizations_total": int(organizations_total or 0),
        "organizations_by_type": organizations_by_type,
        "service_locations_total": int(service_locations_total or 0),
        "locations_by_capability": locations_by_capability,
        "service_availability_by_status": availability_by_status,
        "services_verified_offered": services_offered,
        "offered_services_with_published_price": offered_with_price,
        "offered_services_without_published_price": offered_without_price,
        "price_sources_by_class": price_sources_by_class,
        # Reminder that the audited hospital metric is a SEPARATE number.
        "note": "hospital MRF coverage (X/26) is a separate metric; see /api/v1/pricing/coverage",
    }


def main() -> None:
    result = provider_coverage()
    print("PROVIDER_NEUTRAL_COVERAGE=" + json.dumps(result, default=str, separators=(",", ":")))


if __name__ == "__main__":
    main()
