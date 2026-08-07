from dataclasses import asdict

from collectors.hospital_prices.discovery import discover_sources
from packages.database import session_factory


def main() -> None:
    with session_factory() as session:
        print(asdict(discover_sources(session)))


if __name__ == "__main__":
    main()
