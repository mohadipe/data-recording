import contextlib
import sqlite3
from collections.abc import Generator
from typing import Any

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import StaticPool

from data_recorder.core.config import get_settings


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy 2.0 ORM models."""


# Global engine cache to support connection pooling and singleton engines
_engines: dict[str, Engine] = {}


@event.listens_for(Engine, "connect")
def _on_sqlite_connect(dbapi_connection: Any, connection_record: Any) -> None:
    """Automatically attaches 'verbrauch' and 'wertpapiere' schemas for SQLite connections."""
    if dbapi_connection.__class__.__module__.startswith("sqlite3"):
        cursor = dbapi_connection.cursor()
        with contextlib.suppress(sqlite3.Error):
            cursor.execute("ATTACH DATABASE ':memory:' AS verbrauch")
        with contextlib.suppress(sqlite3.Error):
            cursor.execute("ATTACH DATABASE ':memory:' AS wertpapiere")
        cursor.close()


def get_engine(schema: str = "verbrauch") -> Engine:
    """Creates or returns a cached SQLAlchemy engine with connection pooling.

    Supports MySQL (via pymysql) and SQLite fallback (for automated tests).
    Multi-schema support is provided for 'verbrauch', 'wertpapiere', etc.
    """
    settings = get_settings()
    url = settings.get_database_url(schema)

    if url in _engines:
        return _engines[url]

    if url.startswith("sqlite"):
        engine_kwargs: dict[str, Any] = {
            "connect_args": {"check_same_thread": False},
            "execution_options": {
                "schema_translate_map": {
                    "verbrauch": None,
                    "wertpapiere": None,
                    "hibiscus": None,
                }
            },
        }
        if ":memory:" in url or url == "sqlite://":
            engine_kwargs["poolclass"] = StaticPool
        engine = create_engine(url, **engine_kwargs)
    else:
        # MySQL Engine with connection pooling and pre-ping
        engine = create_engine(
            url,
            pool_size=5,
            max_overflow=10,
            pool_recycle=3600,
            pool_pre_ping=True,
        )

    _engines[url] = engine
    return engine


def get_db_session(schema: str = "verbrauch") -> Generator[Session, None, None]:
    """FastAPI dependency for obtaining a database session for the given schema."""
    engine = get_engine(schema)
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


def reset_engine_cache() -> None:
    """Disposes all active cached engines and clears the cache (useful for tests)."""
    for engine in _engines.values():
        engine.dispose()
    _engines.clear()


def init_db(engine: Engine | None = None) -> None:
    """Initializes database schema by creating all defined tables."""
    if engine is None:
        engine = get_engine()
    Base.metadata.create_all(bind=engine)
