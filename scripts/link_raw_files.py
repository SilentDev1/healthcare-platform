"""Link on-disk raw files to DB FacilityPriceSource records."""

import json
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from collectors.hospital_prices.config import hospital_price_settings
from collectors.hospital_prices.downloader import register_local_file
from packages.database import FacilityPriceSource, session_factory


def link_raw_files(session: Session) -> dict[str, int]:
    """Match UUID-named dirs under data/raw/hospital_prices/nh/ to FacilityPriceSource records."""
    raw_dir = hospital_price_settings.hospital_price_raw_dir
    linked = 0
    skipped = 0
    missing_source = 0
    errors = 0

    if not raw_dir.exists():
        print(f"Raw directory does not exist: {raw_dir}")
        return {"linked": 0, "skipped": 0, "missing_source": 0, "errors": 0}

    for uuid_dir in sorted(raw_dir.iterdir()):
        if not uuid_dir.is_dir():
            continue
        source_id_str = uuid_dir.name
        price_source = session.scalar(
            select(FacilityPriceSource).where(FacilityPriceSource.id == source_id_str)
        )
        if price_source is None:
            missing_source += 1
            continue
        if price_source.source_file_id is not None:
            skipped += 1
            continue

        # Find the most recent file in the date subdirectories
        data_files: list[Path] = []
        for date_dir in sorted(uuid_dir.iterdir(), reverse=True):
            if not date_dir.is_dir():
                continue
            for file_path in date_dir.iterdir():
                if file_path.name.startswith(".") or file_path.name == "metadata.json":
                    continue
                data_files.append(file_path)
            if data_files:
                break

        if not data_files:
            continue

        file_path = data_files[0]
        try:
            result = register_local_file(session, price_source, file_path)
            if not result.skipped_unchanged:
                linked += 1
            else:
                skipped += 1
        except Exception as exc:
            errors += 1
            print(f"  Error linking {file_path}: {type(exc).__name__}: {exc}")

    return {
        "linked": linked,
        "skipped": skipped,
        "missing_source": missing_source,
        "errors": errors,
    }


def main() -> None:
    with session_factory() as session:
        result = link_raw_files(session)
        session.commit()
    print("\n=== Link Raw Files ===")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
