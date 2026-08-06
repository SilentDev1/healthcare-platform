"""Fail if a facility lacks source provenance; suitable for operational smoke checks."""

from sqlalchemy import func, select

from packages.database import Facility, session_factory


def main() -> None:
    with session_factory() as session:
        missing = session.scalar(
            select(func.count(Facility.id)).where(Facility.source_file_id.is_(None))
        )
    if missing:
        raise SystemExit(f"{missing} facilities lack source provenance")


if __name__ == "__main__":
    main()
