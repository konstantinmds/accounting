from __future__ import annotations

import uuid

import psycopg

from app.watcher.db import (
    authorize_case,
    fetch_tenant_by_slug,
    open_conn,
    upsert_artifact_and_task,
    write_dead_letter,
)


def test_upsert_and_duplicate(seeded_tenant_case):
    dsn, tenant_id, case_id = seeded_tenant_case
    conn = open_conn(dsn)
    try:
        tenant = fetch_tenant_by_slug(conn, "acme")
        assert tenant == tenant_id

        artifact_id, task_id = upsert_artifact_and_task(
            conn,
            tenant_id=tenant_id,
            case_id=case_id,
            drop_id=str(uuid.uuid4()),
            filename="file.txt",
            src_path="inbox/acme/case/drop/file.txt",
            s3_uri="s3://raw/aa/bb",
            sha256="a" * 64,
            size_bytes=10,
        )
        assert artifact_id is not None and task_id is not None

        dup_artifact, dup_task = upsert_artifact_and_task(
            conn,
            tenant_id=tenant_id,
            case_id=case_id,
            drop_id=str(uuid.uuid4()),
            filename="file.txt",
            src_path="inbox/acme/case/drop/file.txt",
            s3_uri="s3://raw/aa/bb",
            sha256="a" * 64,
            size_bytes=10,
        )
        assert dup_artifact is None and dup_task is None
    finally:
        conn.close()


def test_authorize_case_mismatch(seeded_tenant_case):
    dsn, tenant_id, case_id = seeded_tenant_case
    other_tenant = str(uuid.uuid4())
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO tenant (id, slug) VALUES (%s,%s)", (other_tenant, "other"))
        conn.commit()

    conn = open_conn(dsn)
    try:
        assert authorize_case(conn, case_id, tenant_id) is True
        assert authorize_case(conn, case_id, other_tenant) is False
    finally:
        conn.close()


def test_dead_letter_write(seeded_tenant_case):
    dsn, _, _ = seeded_tenant_case
    conn = open_conn(dsn)
    try:
        write_dead_letter(
            conn,
            target="inbox/acme/bad",
            failed_activity="invalid_path",
            last_error="oops",
            error_blob={"detail": "bad"},
        )
        with conn.cursor() as cur:
            cur.execute("SELECT target, failed_activity, last_error FROM dead_letter")
            row = cur.fetchone()
            assert row[0] == "inbox/acme/bad"
            assert row[1] == "invalid_path"
            assert row[2] == "oops"
    finally:
        conn.close()
