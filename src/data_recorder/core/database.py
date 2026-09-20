from collections.abc import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from data_recorder.core.config import get_settings

Base = declarative_base()


def get_engine(schema: str = "verbrauch"):
    """Creates a SQLAlchemy engine for the specified schema."""
    settings = get_settings()
    url = settings.get_database_url(schema)
    return create_engine(url, pool_pre_ping=True)


def get_db_session(schema: str = "verbrauch") -> Generator[Session, None, None]:
    """FastAPI dependency for obtaining a database session."""
    engine = get_engine(schema)
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()
