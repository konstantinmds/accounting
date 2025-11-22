from typing import List, Dict, Any
from psycopg_pool import AsyncConnectionPool 

async def keyword_search(pool: AsyncConnectionPool, q: str, limit: int = 10) -> List[Dict[str, Any]]:
    """
    Perform a keyword search on the documents table using full-text search.

    Args:
        pool (AsyncConnectionPool): The database connection pool.
        q (str): The search query string.
        limit (int, optional): The maximum number of results to return. Defaults to 10.

    Returns:
        List of tuples containing document ID and title for matching documents.
    """
    query = """
    SELECT c.id, c.text
    FROM chunk c
    WHERE c.tsv @@ plainto_tsquery('simple', %s)
    ORDER BY ts_rank_cd(c.tsv, plainto_tsquery('simple', %s)) DESC
    LIMIT %s
    """
    async with pool.connection() as conn:
        cur = await conn.execute(query, (q, q, limit))
        rows = await cur.fetchall()
    return [{"chunk_id": r[0], "text": r[1][:500]} for r in rows]
                
