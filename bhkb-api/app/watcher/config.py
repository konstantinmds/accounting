from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class WatcherSettings(BaseSettings):
    DATABASE_URL: str
    S3_ENDPOINT: str | None = None
    S3_ACCESS_KEY: str | None = None
    S3_SECRET_KEY: str | None = None
    INBOX_ROOT: Path = Path("./inbox")
    SCAN_INTERVAL_SECONDS: int = 5
    FILE_STABLE_SECONDS: int = 2
    MAX_CONCURRENCY: int = 4
    MAX_FILE_BYTES: int = 50 * 1024 * 1024  # 50 MB
    MINIO_BUCKET_RAW: str = "raw"
    IGNORE_GLOB: str = "**/*.part,**/~$*,**/*.tmp"
    PROM_PORT: int = 8002
    SNAPSHOT_RETRIES: int = 2
    SNAPSHOT_BACKOFF: float = 0.1
    FILE_CHANGE_ATTEMPT_LIMIT: int = 3
    PROCESSED_DIR_NAME: str = ".processed"

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False)
