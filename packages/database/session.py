from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from packages.database.settings import database_settings
from packages.runtime import runtime_settings

engine = create_engine(
    database_settings.database_url,
    pool_pre_ping=True,
    pool_size=runtime_settings.db_pool_size,
    max_overflow=runtime_settings.db_max_overflow,
    pool_recycle=runtime_settings.db_pool_recycle_seconds,
)
session_factory = sessionmaker(bind=engine, expire_on_commit=False)


def get_session() -> Generator[Session, None, None]:
    with session_factory() as session:
        yield session
