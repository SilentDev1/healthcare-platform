import argparse
import json
from dataclasses import asdict
from pathlib import Path

from collectors.cms_quality.config import quality_settings
from collectors.cms_quality.importer import run_quality_imports
from packages.database import session_factory
from packages.runtime.safety import require_fixture_safe
from services.api.app.logging import configure_logging


def main() -> None:
    parser = argparse.ArgumentParser(description="Import focused CMS hospital quality datasets")
    parser.add_argument("--fixtures-dir", type=Path, help="Use the five offline quality fixtures")
    args = parser.parse_args()
    fixtures = None
    if args.fixtures_dir:
        require_fixture_safe("CMS quality fixture import", args.fixtures_dir)
        fixtures = {
            dataset.key: args.fixtures_dir / f"{dataset.key}.csv"
            for dataset in quality_settings.datasets()
        }
    configure_logging("INFO")
    with session_factory() as session:
        summary = run_quality_imports(session, fixtures=fixtures)
    print(json.dumps(asdict(summary), indent=2))


if __name__ == "__main__":
    main()
