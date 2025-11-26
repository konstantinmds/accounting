from types import SimpleNamespace

import pytest

from app.main import create_app, lifespan


def test_create_app(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost/db")
    app = create_app()
    paths = {route.path for route in app.routes}
    assert "/health" in paths


@pytest.mark.asyncio
async def test_lifespan_initializes_resources(monkeypatch):
    class DummySettings(SimpleNamespace):
        DATABASE_URL: str = "postgresql://user:pass@localhost/db"
        S3_ENDPOINT: str = "http://minio:9000"
        S3_ACCESS_KEY: str = "minio"
        S3_SECRET_KEY: str = "secret"
        APP_NAME: str = "Test"

    class DummyHttpClient:
        closed = False

        def __init__(self, timeout=30):
            self.timeout = timeout

        async def aclose(self):
            self.closed = True

    class DummyConnection:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def execute(self, sql):
            self.sql = sql

    class DummyPool:
        closed = False

        def __init__(self):
            self.conn = DummyConnection()

        def connection(self):
            return self.conn

        async def close(self):
            self.closed = True

    dummy_pool = DummyPool()

    monkeypatch.setattr("app.main.run_migrations", lambda url: None)
    monkeypatch.setattr("app.main.Settings", lambda: DummySettings())
    async def fake_create_pool(dsn: str):
        return dummy_pool

    monkeypatch.setattr("app.main.create_pool", fake_create_pool)
    monkeypatch.setattr("app.main.httpx", SimpleNamespace(AsyncClient=DummyHttpClient))

    captured_minio = {}

    class DummyMinio:
        def __init__(self, endpoint, access_key, secret_key, secure):
            captured_minio.update(
                endpoint=endpoint,
                access_key=access_key,
                secret_key=secret_key,
                secure=secure,
            )

    monkeypatch.setattr("app.main.Minio", DummyMinio)

    class DummyState(SimpleNamespace):
        pass

    class DummyApp(SimpleNamespace):
        state: SimpleNamespace = DummyState()

    app = DummyApp()

    async with lifespan(app):
        assert app.state.settings.APP_NAME == "Test"
        assert isinstance(app.state.http, DummyHttpClient)
        assert captured_minio["secure"] is False

    assert dummy_pool.closed is True
    assert app.state.http.closed is True
