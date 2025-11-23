from psycopg_pool import AsyncConnectionPool  # type: ignore
from fastapi import Request


async def create_pool(dsn: str) -> AsyncConnectionPool:
    """
    Create and open an async connection pool without using the deprecated constructor-open path.
    """
    pool = AsyncConnectionPool(dsn, min_size=1, max_size=10, open=False)
    await pool.open()
    return pool


def get_pool(request: Request) -> AsyncConnectionPool:
    pool: AsyncConnectionPool = request.app.state.db_pool
    return pool
