from unittest.mock import MagicMock, patch

from sqlalchemy import text
from sqlalchemy.pool import StaticPool

from data_recorder.core import config
from data_recorder.core.database import (
    Base,
    get_db_session,
    get_engine,
    init_db,
    reset_engine_cache,
)
from data_recorder.models import (
    Etf,
)


def test_database_engine_and_session(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    config.get_settings.cache_clear()
    reset_engine_cache()

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

    reset_engine_cache()
    config.get_settings.cache_clear()


def test_database_multi_schema_engines(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("DB_HOST", "192.168.2.125")
    monkeypatch.setenv("DB_USER", "synology_user")
    monkeypatch.setenv("DB_PASSWORD", "secret")
    config.get_settings.cache_clear()
    reset_engine_cache()

    with patch("data_recorder.core.database.create_engine") as mock_create_engine:
        mock_engine_verbrauch = MagicMock()
        mock_engine_wertpapiere = MagicMock()
        mock_create_engine.side_effect = [
            mock_engine_verbrauch,
            mock_engine_wertpapiere,
        ]

        # Engine for verbrauch
        engine_verbrauch = get_engine("verbrauch")
        assert engine_verbrauch == mock_engine_verbrauch
        call_url_v, kwargs_v = mock_create_engine.call_args_list[0]
        assert (
            "mysql+pymysql://synology_user:secret@192.168.2.125:3306/verbrauch"
            in str(call_url_v[0])
        )
        assert kwargs_v["pool_size"] == 5
        assert kwargs_v["max_overflow"] == 10
        assert kwargs_v["pool_recycle"] == 3600
        assert kwargs_v["pool_pre_ping"] is True

        # Engine for wertpapiere
        engine_wertpapiere = get_engine("wertpapiere")
        assert engine_wertpapiere == mock_engine_wertpapiere
        call_url_w, _ = mock_create_engine.call_args_list[1]
        assert (
            "mysql+pymysql://synology_user:secret@192.168.2.125:3306/wertpapiere"
            in str(call_url_w[0])
        )

        # Caching: requesting verbrauch again returns cached engine
        engine_cached = get_engine("verbrauch")
        assert engine_cached == mock_engine_verbrauch
        assert mock_create_engine.call_count == 2

    reset_engine_cache()
    config.get_settings.cache_clear()


def test_sqlite_fallback_and_init_db(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    config.get_settings.cache_clear()
    reset_engine_cache()

    engine = get_engine("verbrauch")
    # Verify poolclass is StaticPool for in-memory sqlite
    assert engine.pool.__class__ == StaticPool

    # Test init_db creates all tables without error across both schemas
    init_db(engine)

    # Verify tables exist in metadata
    assert "verbrauch.zaehler" in Base.metadata.tables
    assert "verbrauch.messwerte" in Base.metadata.tables
    assert "verbrauch.waermepumpe_stundenwert" in Base.metadata.tables
    assert "verbrauch.heizoel_preis" in Base.metadata.tables
    assert "wertpapiere.etf" in Base.metadata.tables
    assert "wertpapiere.wkn_invest_datum" in Base.metadata.tables
    assert "wertpapiere.wkn_wert_datum" in Base.metadata.tables
    assert "wertpapiere.wkn_ertrag_datum" in Base.metadata.tables

    # Verify session for wertpapiere works on sqlite
    session_gen = get_db_session("wertpapiere")
    session = next(session_gen)
    session.add(Etf(wkn="TEST01"))
    session.commit()
    result = session.execute(text("SELECT wkn FROM etf WHERE wkn = 'TEST01'")).scalar()
    assert result == "TEST01"

    try:
        next(session_gen)
    except StopIteration:
        pass

    reset_engine_cache()
    config.get_settings.cache_clear()
