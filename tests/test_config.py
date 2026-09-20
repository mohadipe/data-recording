import os
import pytest
from data_recorder.core.config import Settings, get_settings


def test_default_settings():
    settings = Settings()
    assert settings.APP_NAME == "data-recorder"
    assert settings.APP_VERSION == "0.1.0"
    assert settings.PORT == 9015
    assert settings.DB_PORT == 3306
    assert settings.DB_HOST == "localhost"
    assert settings.DB_USER == "root"


def test_settings_custom_env(monkeypatch):
    monkeypatch.setenv("DB_HOST", "192.168.2.125")
    monkeypatch.setenv("DB_PORT", "3307")
    monkeypatch.setenv("DB_USER", "recorder_user")
    monkeypatch.setenv("DB_PASSWORD", "secret123")
    monkeypatch.setenv("PORT", "8000")

    settings = Settings()
    assert settings.DB_HOST == "192.168.2.125"
    assert settings.DB_PORT == 3307
    assert settings.DB_USER == "recorder_user"
    assert settings.DB_PASSWORD == "secret123"
    assert settings.PORT == 8000


def test_database_url_generation():
    settings = Settings(
        DB_HOST="nas.local",
        DB_PORT=3306,
        DB_USER="recorder",
        DB_PASSWORD="mypassword",
        DB_NAME_VERBRAUCH="verbrauch",
    )
    url = settings.get_database_url("verbrauch")
    assert url == "mysql+pymysql://recorder:mypassword@nas.local:3306/verbrauch?charset=utf8mb4"


def test_get_settings_cached():
    s1 = get_settings()
    s2 = get_settings()
    assert s1 is s2
