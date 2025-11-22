from psycopg_pool import AsyncConnectionPool  # type: ignore
from fastapi import Request

def create_pool(dsn: str) -> AsyncConnectionPool:
    """        
    dsn (str): Database connection string (Data Source Name) containing connection parameters
                  like host, port, database name, user, and password.

    Returns:
        AsyncConnectionPool: An initialized connection pool with the following configurations:
            - min_size: 1 (minimum number of connections kept in the pool)
            - max_size: 10 (maximum number of connections the pool can create)
            - open: True (pool is immediately opened and ready to use)
    """
    return AsyncConnectionPool(dsn, min_size=1, max_size=10, open=True)

def get_pool(request: Request) -> AsyncConnectionPool:
    pool: AsyncConnectionPool = request.app.state.db_pool
    return pool
