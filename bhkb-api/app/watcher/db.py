from __future__ import annotations

import psycopg
from psycopg import sql
from psycopg.errors import UniqueViolation
from psycopg.types.json import Json


def open_conn(dsn: str) -> psycopg.Connection:
    return psycopg.connect(dsn)


def fetch_tenant_by_slug(conn: psycopg.Connection, slug: str) -> str | None:
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM tenant WHERE slug = %s", (slug,))
        row = cur.fetchone()
    return row[0] if row else None


def authorize_case(conn: psycopg.Connection, case_id: str, tenant_id: str) -> bool:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT 1 FROM case_file WHERE id = %s AND (tenant_id = %s OR tenant_id IS NULL)",
            (case_id, tenant_id),
        )
        return cur.fetchone() is not None


def upsert_artifact_and_task(
    conn: psycopg.Connection,
    *,
    tenant_id: str,
    case_id: str,
    drop_id: str,
    filename: str,
    src_path: str,
    s3_uri: str,
    sha256: str,
    size_bytes: int,
) -> tuple[str | None, str | None]:
    """Insert artifact and task transactionally.

    Returns (artifact_id, task_id). Artifact_id is None when upsert hit a conflict.
    """
    try:
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute(
                    (
                        "INSERT INTO artifact (tenant_id, case_id, drop_id, filename, src_path, s3_uri, sha256, size_bytes) "
                        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s) "
                        "ON CONFLICT (case_id, sha256) DO NOTHING RETURNING id"
                    ),
                    (tenant_id, case_id, drop_id, filename, src_path, s3_uri, sha256, size_bytes),
                )
                # TODO: add mime_type when type allowlist is implemented (post-MVP).
                row = cur.fetchone()
                if not row:
                    return None, None
                artifact_id = row[0]

                cur.execute(
                    "INSERT INTO ingest_task (artifact_id, status) VALUES (%s, 'pending') RETURNING id",
                    (artifact_id,),
                )
                task_row = cur.fetchone()
                return artifact_id, task_row[0] if task_row else None
    except UniqueViolation:
        conn.rollback()
        return None, None


def write_dead_letter(
    conn: psycopg.Connection,
    *,
    target: str,
    failed_activity: str,
    last_error: str | None,
    error_blob: dict | None,
) -> None:
    payload = Json(error_blob) if error_blob is not None else None
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO dead_letter (target, failed_activity, last_error, error_blob) VALUES (%s,%s,%s,%s)",
            (target, failed_activity, last_error, payload),
        )
    conn.commit()
