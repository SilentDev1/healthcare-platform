import argparse
import json
from dataclasses import asdict
from pathlib import Path

from collectors.hospital_prices.pipeline import run_fixture_pipeline
from packages.database import session_factory


def main() -> None:
    parser = argparse.ArgumentParser(description="Run bounded hospital price fixture pipeline")
    parser.add_argument("--fixtures-dir", type=Path, default=Path("data/fixtures/hospital_prices"))
    args = parser.parse_args()
    with session_factory() as session:
        print(json.dumps(asdict(run_fixture_pipeline(session, args.fixtures_dir)), indent=2))


if __name__ == "__main__":
    main()
