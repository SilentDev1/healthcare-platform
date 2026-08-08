"""Hardcoded lat/lng table for NH hospitals. No external API calls."""

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from packages.database import Facility, FacilityLocation, session_factory

# Approximate lat/lng for 26+ NH acute-care hospitals
NH_COORDINATES: dict[str, tuple[float, float]] = {
    "300001": (43.2081, -71.5376),  # Concord Hospital
    "300003": (43.6376, -72.2881),  # Dartmouth-Hitchcock (Mary Hitchcock)
    "300005": (43.5278, -71.4704),  # Concord Hospital-Laconia
    "300010": (42.9916, -71.4644),  # Elliot Hospital
    "300011": (44.3062, -71.7700),  # Littleton Regional Healthcare
    "300012": (43.2050, -71.5550),  # St Joseph Hospital
    "300014": (43.3090, -70.9770),  # Frisbie Memorial Hospital
    "300016": (43.0718, -70.7778),  # Portsmouth Regional Hospital
    "300017": (42.8685, -71.3564),  # Parkland Medical Center
    "300018": (43.1970, -70.8770),  # Wentworth-Douglass Hospital
    "300019": (42.9554, -72.3233),  # Cheshire Medical Center
    "300020": (42.7509, -71.4694),  # Southern NH Medical Center
    "300023": (42.8619, -71.9710),  # Monadnock Community Hospital
    "300024": (42.9824, -70.9555),  # Exeter Hospital
    "300029": (43.6371, -72.3340),  # Alice Peck Day Memorial
    "300034": (42.9886, -71.4698),  # Catholic Medical Center
    "301302": (43.4149, -72.0170),  # New London Hospital
    "301303": (44.3710, -71.4700),  # Weeks Medical Center
    "301304": (43.8058, -71.6851),  # Speare Memorial Hospital
    "301305": (44.0524, -71.1284),  # Memorial Hospital (North Conway)
    "301306": (44.7200, -71.5100),  # Upper Connecticut Valley Hospital
    "301307": (43.4430, -72.0810),  # Valley Regional Hospital
    "301309": (43.4442, -71.6481),  # Concord Hospital-Franklin
    "301310": (44.1550, -72.0400),  # Cottage Hospital
    "301311": (43.5960, -71.2540),  # Huggins Hospital
    "301312": (44.3930, -71.1710),  # Androscoggin Valley Hospital
    "304000": (43.2150, -71.5350),  # New Hampshire Hospital
    "304007": (42.8740, -71.1820),  # Hampstead Hospital (alt CCN)
    # Corrected CCNs for facilities whose CCN differs from initial lookup
    "301301": (44.1550, -72.0400),  # Cottage Hospital (Woodsville)
    "301300": (44.8941, -71.4973),  # Upper Connecticut Valley Hospital (Colebrook)
    "304001": (42.8740, -71.1820),  # Hampstead Hospital
    "301308": (43.3768, -72.3468),  # Valley Regional Hospital (Claremont)
}


def geocode_facilities(session: Session) -> dict[str, int]:
    """Update FacilityLocation with hardcoded lat/lng for NH hospitals."""
    updated = 0
    skipped = 0

    for ccn, (lat, lng) in NH_COORDINATES.items():
        facility = session.scalar(select(Facility).where(Facility.cms_certification_number == ccn))
        if not facility:
            skipped += 1
            continue

        location = session.scalar(
            select(FacilityLocation).where(FacilityLocation.facility_id == facility.id)
        )
        if not location:
            skipped += 1
            continue

        if location.latitude != lat or location.longitude != lng:
            location.latitude = Decimal(str(lat))
            location.longitude = Decimal(str(lng))
            updated += 1

    session.commit()
    return {"updated": updated, "skipped": skipped}


def main() -> None:
    with session_factory() as session:
        result = geocode_facilities(session)
    print(f"Geocoded NH facilities: {result}")


if __name__ == "__main__":
    main()
