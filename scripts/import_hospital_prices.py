import argparse

from sqlalchemy import select

from collectors.hospital_prices.importer import import_price_source
from packages.database import FacilityPriceSource, session_factory


def main() -> None:
    parser = argparse.ArgumentParser(description="Import bounded downloaded hospital MRFs")
    parser.add_argument("--limit", type=int, default=3)
    args = parser.parse_args()
    if not 1 <= args.limit <= 10:
        raise SystemExit("limit must be between 1 and 10")
    with session_factory() as session:
        sources = session.scalars(
            select(FacilityPriceSource)
            .where(
                FacilityPriceSource.source_file_id.is_not(None),
                FacilityPriceSource.active.is_(True),
                FacilityPriceSource.machine_readable_file_url.startswith("https://"),
            )
            .order_by(FacilityPriceSource.id)
            .limit(args.limit)
        ).all()
        for source in sources:
            print(source.id, import_price_source(session, source))


if __name__ == "__main__":
    main()
