from types import SimpleNamespace

from fastapi.testclient import TestClient

from app import main


class DummySettings:
    DATABASE_URL = "postgresql://user:pass@localhost/db"
    S3_ENDPOINT = "http://minio:9000"
    S3_ACCESS_KEY = "minio"
    S3_SECRET_KEY = "secret"
    APP_NAME = "TestApp"


class DummyPool:
    def __init__(self):
        self.closed = False

    async def close(self):
        self.closed = True


class DummyAsyncClient:
    def __init__(self, timeout=30):
        self.timeout = timeout
        self.closed = False

    async def aclose(self):
        self.closed = True


class DummyMinio:
    def __init__(self, *args, **kwargs):
        pass


def test_health_smoke(monkeypatch):
    dummy_pool = DummyPool()

    async def fake_create_pool(url: str):
        return dummy_pool

    monkeypatch.setattr(main, "Settings", lambda: DummySettings())
    monkeypatch.setattr(main, "run_migrations", lambda url: None)
    monkeypatch.setattr(main, "create_pool", fake_create_pool)
    monkeypatch.setattr(main, "httpx", SimpleNamespace(AsyncClient=DummyAsyncClient))
    monkeypatch.setattr(main, "Minio", DummyMinio)

    app = main.create_app()
    with TestClient(app) as client:
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}

    assert dummy_pool.closed is True
