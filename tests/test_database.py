from unittest.mock import patch
from sqlalchemy import text
from data_recorder.core.database import get_engine, get_db_session
from data_recorder.core.config import Settings


def test_database_engine_and_session(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    # Clear the lru_cache for get_settings so it re-reads environment
    from data_recorder.core import config
    config.get_settings.cache_clear()

    engine = get_engine()
    assert str(engine.url) == "sqlite:///:memory:"

    session_gen = get_db_session()
    session = next(session_gen)
    result = session.execute(text("SELECT 1")).scalar()
    assert result == 1

    # Finish generator
    try:
        next(session_gen)
    except StopIteration:
        pass

    config.get_settings.cache_clear()
