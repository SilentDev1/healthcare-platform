import argparse

from sqlalchemy import select

from collectors.hospital_prices.downloader import download_price_source
from packages.database import FacilityPriceSource, session_factory


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Download a bounded set of discovered hospital MRFs"
    )
    parser.add_argument("--limit", type=int, default=3)
    args = parser.parse_args()
    if not 1 <= args.limit <= 10:
        raise SystemExit("limit must be between 1 and 10")
    downloaded = skipped = failed = 0
    with session_factory() as session:
        sources = session.scalars(
            select(FacilityPriceSource)
            .where(
                FacilityPriceSource.active.is_(True),
                FacilityPriceSource.machine_readable_file_url.startswith("https://"),
                FacilityPriceSource.source_file_id.is_(None),
            )
            .order_by(FacilityPriceSource.id)
            .limit(args.limit)
        ).all()
        for source in sources:
            try:
                result = download_price_source(session, source)
                skipped += int(result.skipped_unchanged)
                downloaded += int(not result.skipped_unchanged)
            except (RuntimeError, ValueError) as exc:
                failed += 1
                print(f"failed source={source.id} reason={exc}")
    print(f"downloaded={downloaded} skipped_unchanged={skipped} failed={failed}")


if __name__ == "__main__":
    main()
