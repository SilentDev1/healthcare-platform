"""Standalone command to rebuild facility procedure price summaries."""

from collectors.hospital_prices.projections import rebuild_price_summaries
from packages.database import get_session


def main() -> None:
    session = next(get_session())
    result = rebuild_price_summaries(session)
    print(f"Rebuilt: {result['observations']} observations, {result['summaries']} summaries")


if __name__ == "__main__":
    main()
