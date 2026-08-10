"""Run a geographically scoped refresh with a PostgreSQL advisory lock."""

import argparse
import subprocess
import sys

from sqlalchemy import text

from packages.database.session import engine
from packages.runtime import runtime_settings


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state", required=True, help="Two-letter state scope")
    parser.add_argument("--mode", choices=("refresh", "discover", "audit"), default="refresh")
    args = parser.parse_args()
    state = args.state.upper()
    if len(state) != 2 or not state.isalpha():
        raise SystemExit("--state must be a two-letter code")
    if not runtime_settings.scheduler_enabled:
        raise SystemExit("scheduler is disabled; set SCHEDULER_ENABLED=true")

    lock_key = f"carevero:price-refresh:{state}"
    module = {
        "refresh": "scripts.pipeline_full",
        "discover": "scripts.pipeline_discover",
        "audit": "scripts.statewide_scorecard",
    }[args.mode]
    with engine.connect() as connection:
        acquired = connection.scalar(
            text("SELECT pg_try_advisory_lock(hashtext(:key))"), {"key": lock_key}
        )
        if not acquired:
            raise SystemExit(f"refresh already active for {state}")
        try:
            result = subprocess.run(
                [sys.executable, "-m", module, "--state", state],
                check=False,
            )
            raise SystemExit(result.returncode)
        finally:
            connection.execute(text("SELECT pg_advisory_unlock(hashtext(:key))"), {"key": lock_key})


if __name__ == "__main__":
    main()
