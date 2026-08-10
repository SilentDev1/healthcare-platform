import argparse
import json
from dataclasses import asdict
from pathlib import Path

from collectors.cms_hospitals.importer import run_import
from packages.database import session_factory
from packages.runtime.safety import require_fixture_safe
from services.api.app.logging import configure_logging


def main() -> None:
    parser = argparse.ArgumentParser(description="Import New Hampshire hospitals from CMS")
    parser.add_argument(
        "--source-file", type=Path, help="Use a local CSV/JSON file instead of downloading"
    )
    parser.add_argument("--source-url", help="Override the configured CMS URL")
    args = parser.parse_args()
    if args.source_file:
        require_fixture_safe("local CMS hospital import", args.source_file)
    configure_logging("INFO")
    with session_factory() as session:
        summary = run_import(session, source_path=args.source_file, source_url=args.source_url)
    print(json.dumps(asdict(summary), indent=2))


if __name__ == "__main__":
    main()
