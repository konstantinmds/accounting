import pytest

from app.services.search import keyword_search


class DummyCursor:
    async def fetchall(self):
        return [(1, "Prvi tekst"), (2, "Drugi tekst" * 10)]


class DummyConnection:
    def __init__(self):
        self.executed = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def execute(self, query, params):
        self.executed = (query, params)
        return DummyCursor()


class DummyPool:
    def __init__(self):
        self.conn = DummyConnection()

    def connection(self):
        return self.conn


@pytest.mark.asyncio
async def test_keyword_search_returns_trimmed_text():
    pool = DummyPool()
    results = await keyword_search(pool, "porez", limit=5)
    assert len(results) == 2
    assert results[0]["chunk_id"] == 1
    assert len(results[1]["text"]) <= 500
