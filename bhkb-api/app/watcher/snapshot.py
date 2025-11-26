from __future__ import annotations

import time
from minio import Minio


class SnapshotError(RuntimeError):
    """Raised when a snapshot to object storage fails after retries."""


def build_raw_key(sha256: str) -> str:
    prefix = sha256[:2]
    return f"{prefix}/{sha256}"


def snapshot_file(
    client: Minio,
    bucket: str,
    key: str,
    src_path: str,
    retries: int = 2,
    backoff: float = 0.1,
) -> str:
    """Upload a file to MinIO with simple retry; returns the s3 uri."""
    attempt = 0
    while True:
        try:
            client.fput_object(bucket, key, src_path)
            return f"s3://{bucket}/{key}"
        except Exception as exc:  # pragma: no cover - specific exceptions vary
            attempt += 1
            if attempt > retries:
                raise SnapshotError(str(exc))
            time.sleep(backoff)
