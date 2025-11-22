import importlib

import pytest


def test_get_conn_calls_psycopg(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost/db")
    module = importlib.import_module("app.db.sync")
    importlib.reload(module)

    captured = {}

    def fake_connect(dsn, autocommit=True):
        captured["dsn"] = dsn
        captured["autocommit"] = autocommit
        class DummyConn: ...
        return DummyConn()

    monkeypatch.setattr(module.psycopg, "connect", fake_connect)
    module.get_conn()
    assert captured["dsn"].endswith("/db")
    assert captured["autocommit"] is True


def test_missing_database_url_raises(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    module = importlib.import_module("app.db.sync")
    with pytest.raises(RuntimeError):
        importlib.reload(module)
