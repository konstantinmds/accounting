from importlib import reload

from app.core import config


def test_settings_reads_environment(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost/db")
    monkeypatch.setenv("APP_NAME", "Custom")
    reload(config)
    settings = config.Settings()
    assert settings.DATABASE_URL.endswith("/db")
    assert settings.APP_NAME == "Custom"


def test_settings_optional_fields(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost/db")
    monkeypatch.delenv("S3_ENDPOINT", raising=False)
    reload(config)
    settings = config.Settings()
    assert settings.S3_ENDPOINT is None
