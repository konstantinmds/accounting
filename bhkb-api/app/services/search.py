from __future__ import annotations

from typing import Any


async def keyword_search(pool: Any, q: str, limit: int = 10) -> list[dict[str, Any]]:
    """
    Run a simple keyword search against stored chunks.

    This implementation is intentionally lightweight for testing: it executes a
    parameterized query through the provided pool and trims returned text to
    500 characters.
    """
    async with pool.connection() as conn:
        cursor = await conn.execute(
            "SELECT id, text FROM chunk_search(:q, :limit)",
            {"q": q, "limit": limit},
        )
        rows = await cursor.fetchall()

    results: list[dict[str, Any]] = []
    for chunk_id, text in rows:
        trimmed = text if len(text) <= 500 else text[:500]
        results.append({"chunk_id": chunk_id, "text": trimmed})
    return results
