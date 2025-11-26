import pytest

from app.routers import search as search_module


@pytest.mark.asyncio
async def test_search_endpoint(monkeypatch):
    async def fake_keyword_search(pool, q, limit):
        assert pool == "pool"
        assert q == "pravila"
        assert limit == 5
        return [{"chunk_id": 1, "text": "Tekst"}]

    monkeypatch.setattr(search_module, "keyword_search", fake_keyword_search)
    response = await search_module.search(q="pravila", limit=5, pool="pool")
    assert response.query == "pravila"
    assert response.results[0].chunk_id == 1
