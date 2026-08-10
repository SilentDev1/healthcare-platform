import argparse
import json
from dataclasses import asdict
from pathlib import Path

from collectors.nppes_organizations import run_import
from packages.database import session_factory
from packages.runtime.safety import require_fixture_safe


def main() -> None:
    parser = argparse.ArgumentParser(description="Import bounded NH NPPES organization records")
    parser.add_argument("--source-file", type=Path)
    args = parser.parse_args()
    if args.source_file:
        require_fixture_safe("local NPPES import", args.source_file)
    with session_factory() as session:
        print(json.dumps(asdict(run_import(session, args.source_file)), indent=2))


if __name__ == "__main__":
    main()
