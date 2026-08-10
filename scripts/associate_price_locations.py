from dataclasses import asdict

from collectors.hospital_prices.location_association import associate_verified_locations
from packages.database import session_factory


def main() -> None:
    with session_factory() as session:
        print(asdict(associate_verified_locations(session)))


if __name__ == "__main__":
    main()
