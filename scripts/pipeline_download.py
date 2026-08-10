"""Pipeline step: download all price sources for a state."""

import argparse
import json
import time

from packages.database import session_factory
from scripts.download_all_nh_sources import download_all_sources


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state", default="NH")
    args = parser.parse_args()

    started = time.perf_counter()
    with session_factory() as session:
        result = download_all_sources(session, args.state)
        session.commit()
    elapsed = round(time.perf_counter() - started, 2)

    output = {"step": "download", "state": args.state, **result, "elapsed_sec": elapsed}
    print(json.dumps(output, indent=2, default=str))


if __name__ == "__main__":
    main()
