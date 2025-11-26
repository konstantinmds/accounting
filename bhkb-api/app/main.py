"""
Main FastAPI application module that handles application lifecycle, configuration,
and router registration.

This module is responsible for:
1. Setting up the FastAPI application
2. Managing application state and dependencies
3. Initializing database connections, HTTP clients, and S3/MinIO storage
4. Defining application lifecycle events
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
import httpx
from minio import Minio

from app.core.config import Settings
from app.core.logging import setup_logging
from app.db.session import create_pool
from app.db.migrations import run_migrations
from app.routers.search import router as search_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manages the application lifecycle and state initialization/cleanup.
    
    The lifespan context manager handles:
    - Logging setup
    - Database connection pool creation
    - HTTP client initialization
    - MinIO/S3 client setup
    - Database schema initialization
    - Cleanup of resources on shutdown
    
    Args:
        app (FastAPI): The FastAPI application instance

    Notes:
        app.state is FastAPI's built-in state management that stores:
        - settings: Application configuration
        - db_pool: PostgreSQL connection pool
        - http: Async HTTP client for external requests
        - minio: S3/MinIO client for object storage
    """
    setup_logging()
    settings = Settings()
    app.state.settings = settings

    run_migrations(settings.DATABASE_URL)

    # Initialize DB pool for PostgreSQL connections
    app.state.db_pool = await create_pool(settings.DATABASE_URL)

    # Create HTTP client with 30s timeout
    app.state.http = httpx.AsyncClient(timeout=30)

    # Initialize MinIO/S3 client if credentials are provided
    if settings.S3_ENDPOINT and settings.S3_ACCESS_KEY and settings.S3_SECRET_KEY:
        app.state.minio = Minio(
            settings.S3_ENDPOINT.replace("http://", "").replace("https://", ""),
            access_key=settings.S3_ACCESS_KEY,
            secret_key=settings.S3_SECRET_KEY,
            secure=settings.S3_ENDPOINT.startswith("https"),
        )
    else:
        app.state.minio = None

    try:
        yield  # Application runs here
    finally:
        # Cleanup resources when application shuts down
        await app.state.http.aclose()
        await app.state.db_pool.close()

def create_app() -> FastAPI:
    """
    Creates and configures the FastAPI application instance.
    
    Returns:
        FastAPI: Configured application instance with:
        - Application settings
        - Lifespan event handler
        - Registered routers
        - Health check endpoint
    """
    settings = Settings()
    app = FastAPI(
        title=settings.APP_NAME, 
        version="0.1.0", 
        lifespan=lifespan
    )
    
    # Register routers
    app.include_router(search_router, prefix="/search", tags=["search"])

    @app.get("/health")
    async def health():
        """Simple health check endpoint."""
        return {"status": "ok"}
    
    return app


app = create_app()
