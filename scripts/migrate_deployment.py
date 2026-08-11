"""Fail-closed deployment migration command with import lock verification."""

import subprocess
import sys

from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import func, select

from packages.database import ImportRun, session_factory
from packages.database.models import ImportStatus
from packages.database.session import engine
from packages.runtime import runtime_settings


def main() -> None:
    if not runtime_settings.is_deployed:
        raise SystemExit("APP_ENV must be beta or production")
    with session_factory() as session:
        active = (
            session.scalar(
                select(func.count(ImportRun.id)).where(ImportRun.status == ImportStatus.RUNNING)
            )
            or 0
        )
    if active:
        raise SystemExit(f"migration blocked: {active} import run(s) active")
    result = subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], check=False)
    if result.returncode:
        raise SystemExit(result.returncode)
    expected_heads = set(ScriptDirectory.from_config(Config("alembic.ini")).get_heads())
    with engine.connect() as connection:
        current_heads = set(MigrationContext.configure(connection).get_current_heads())
    if current_heads != expected_heads:
        raise SystemExit(
            f"migration head verification failed: current={sorted(current_heads)} "
            f"expected={sorted(expected_heads)}"
        )


if __name__ == "__main__":
    main()
