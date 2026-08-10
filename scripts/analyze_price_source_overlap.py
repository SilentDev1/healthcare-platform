import argparse
import uuid

from collectors.hospital_prices.overlap import analyze_facility_sources
from packages.database import session_factory


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("facility_id", type=uuid.UUID)
    args = parser.parse_args()
    with session_factory() as session:
        print({"analyses": analyze_facility_sources(session, args.facility_id)})


if __name__ == "__main__":
    main()
