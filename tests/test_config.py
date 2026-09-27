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
    assert (
        url
        == "mysql+pymysql://recorder:mypassword@nas.local:3306/verbrauch?charset=utf8mb4"
    )


def test_get_settings_cached():
    s1 = get_settings()
    s2 = get_settings()
    assert s1 is s2


def test_paperless_and_upload_defaults():
    settings = Settings()
    assert settings.FAILED_UPLOADS_DIR == "data/failed_uploads"
    assert settings.SHARED_UPLOADS_DIR == "data/shared_uploads"
    assert settings.PAPERLESS_TAG == "Zaehlerbeleg"
    assert settings.PAPERLESS_DOCUMENT_TYPE == "Zaehlerbeleg"


def test_paperless_custom_env(monkeypatch):
    monkeypatch.setenv("FAILED_UPLOADS_DIR", "/custom/failed")
    monkeypatch.setenv("PAPERLESS_TAG", "CustomTag")
    monkeypatch.setenv("PAPERLESS_DOCUMENT_TYPE", "CustomType")
    monkeypatch.setenv("PAPERLESS_API_URL", "http://paperless.nas:8000")
    monkeypatch.setenv("PAPERLESS_API_TOKEN", "token_xyz")

    settings = Settings()
    assert settings.FAILED_UPLOADS_DIR == "/custom/failed"
    assert settings.PAPERLESS_TAG == "CustomTag"
    assert settings.PAPERLESS_DOCUMENT_TYPE == "CustomType"
    assert settings.PAPERLESS_API_URL == "http://paperless.nas:8000"
    assert settings.PAPERLESS_API_TOKEN == "token_xyz"


def test_heizoel_settings_defaults():
    settings = Settings()
    assert settings.HEIZOEL_PLZ == "90579"
    assert settings.HEIZOEL_MENGE_LITER == 2500
    assert "esyoil.com" in settings.HEIZOEL_PROVIDER_URL
    assert settings.HEIZOEL_SCRAPER_TIMEOUT == 15.0
    assert "Mozilla" in settings.HEIZOEL_SCRAPER_USER_AGENT


def test_heizoel_settings_custom_env(monkeypatch):
    monkeypatch.setenv("HEIZOEL_PLZ", "90402")
    monkeypatch.setenv("HEIZOEL_MENGE_LITER", "3000")
    monkeypatch.setenv("HEIZOEL_PROVIDER_URL", "https://example.com/oil")
    monkeypatch.setenv("HEIZOEL_SCRAPER_TIMEOUT", "20.5")

    settings = Settings()
    assert settings.HEIZOEL_PLZ == "90402"
    assert settings.HEIZOEL_MENGE_LITER == 3000
    assert settings.HEIZOEL_PROVIDER_URL == "https://example.com/oil"
    assert settings.HEIZOEL_SCRAPER_TIMEOUT == 20.5


