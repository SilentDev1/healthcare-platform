from collectors.hospital_prices.projections import rebuild_price_summaries
from packages.database import session_factory


def main() -> None:
    with session_factory() as session:
        print(rebuild_price_summaries(session))


if __name__ == "__main__":
    main()
