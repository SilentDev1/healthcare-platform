from collectors.hospital_prices.source_facility_association import (
    reconcile_filename_facility_associations,
)
from packages.database import session_factory


def main() -> None:
    with session_factory() as session:
        result = reconcile_filename_facility_associations(session)
        session.commit()
    print(result)


if __name__ == "__main__":
    main()
