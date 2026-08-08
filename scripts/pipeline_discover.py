"""Pipeline step: discover price sources for NH hospitals."""

import argparse
import json
import time

from collectors.hospital_prices.discovery import discover_sources
from packages.database import session_factory


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state", default="NH")
    args = parser.parse_args()

    started = time.perf_counter()
    with session_factory() as session:
        summary = discover_sources(session)
        session.commit()
    elapsed = round(time.perf_counter() - started, 2)

    result = {
        "step": "discover",
        "state": args.state,
        "facilities_examined": summary.facilities_examined,
        "sources_found": summary.sources_found,
        "sources_updated": summary.sources_updated,
        "elapsed_sec": elapsed,
    }
    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
