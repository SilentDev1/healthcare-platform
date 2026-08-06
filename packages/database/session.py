from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from packages.database.settings import database_settings

engine = create_engine(database_settings.database_url, pool_pre_ping=True)
session_factory = sessionmaker(bind=engine, expire_on_commit=False)


def get_session() -> Generator[Session, None, None]:
    with session_factory() as session:
        yield session
