from __future__ import annotations

import os
import uuid
from pathlib import Path
from urllib.parse import urlparse, urlunparse

import pytest
import psycopg
from psycopg import sql
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError

ROOT = Path(__file__).resolve().parents[1]


def _swap_db(url: str, dbname: str) -> str:
    parsed = urlparse(url)
    return urlunparse(parsed._replace(path=f"/{dbname}"))


@pytest.fixture(scope="function")
def temp_db_url() -> str:
    base_url = os.getenv("DATABASE_URL", "postgresql://postgres:devpassword@localhost:5432/postgres")
    admin_url = _swap_db(base_url, "postgres")
    dbname = f"intake_{uuid.uuid4().hex[:8]}"
    test_url = _swap_db(base_url, dbname)

    with psycopg.connect(admin_url) as conn:
        conn.autocommit = True
        conn.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(dbname)))

    try:
        yield test_url
    finally:
        with psycopg.connect(admin_url) as conn:
            conn.autocommit = True
            conn.execute(
                sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(
                    sql.Identifier(dbname)
                )
            )


@pytest.fixture
def alembic_cfg(temp_db_url: str) -> Config:
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "alembic"))
    cfg.set_main_option("sqlalchemy.url", temp_db_url)
    return cfg


def test_upgrade_and_downgrade_apply_cleanly(alembic_cfg: Config, temp_db_url: str) -> None:
    command.upgrade(alembic_cfg, "head")

    engine = create_engine(temp_db_url)
    inspector = inspect(engine)
    expected_tables = {
        "tenant",
        "case_file",
        "artifact",
        "ingest_task",
        "dead_letter",
        "normalized_record",
        "lineage",
        "research_finding",
    }
    assert expected_tables.issubset(set(inspector.get_table_names()))

    normalized_indexes = {idx["name"] for idx in inspector.get_indexes("normalized_record")}
    assert "idx_record_artifact" in normalized_indexes
    assert "idx_record_schema" in normalized_indexes

    command.downgrade(alembic_cfg, "-1")

    inspector = inspect(create_engine(temp_db_url))
    remaining_tables = set(inspector.get_table_names())
    for table in expected_tables:
        assert table not in remaining_tables


def test_constraints_enforced(alembic_cfg: Config, temp_db_url: str) -> None:
    command.upgrade(alembic_cfg, "head")
    engine = create_engine(temp_db_url)

    with engine.begin() as conn:
        tenant_id = conn.execute(
            text("INSERT INTO tenant (slug, name) VALUES (:slug, :name) RETURNING id"),
            {"slug": "t1", "name": "Tenant 1"},
        ).scalar_one()

        case_id = conn.execute(
            text(
                "INSERT INTO case_file (tenant_id, label) "
                "VALUES (:tenant_id, :label) RETURNING id"
            ),
            {"tenant_id": tenant_id, "label": "Case A"},
        ).scalar_one()

        artifact_params = {
            "tenant_id": tenant_id,
            "case_id": case_id,
            "s3_uri": "s3://bucket/file",
            "sha256": "abc123",
        }
        conn.execute(
            text(
                "INSERT INTO artifact (tenant_id, case_id, s3_uri, sha256) "
                "VALUES (:tenant_id, :case_id, :s3_uri, :sha256)"
            ),
            artifact_params,
        )

        with pytest.raises(IntegrityError):
            conn.execute(
                text(
                    "INSERT INTO artifact (tenant_id, case_id, s3_uri, sha256) "
                    "VALUES (:tenant_id, :case_id, :s3_uri, :sha256)"
                ),
                artifact_params,
            )

        with pytest.raises(IntegrityError):
            conn.execute(
                text(
                    "INSERT INTO artifact (case_id, s3_uri, sha256) "
                    "VALUES (:case_id, :s3_uri, :sha256)"
                ),
                {
                    "case_id": "00000000-0000-0000-0000-000000000001",
                    "s3_uri": "s3://bucket/other",
                    "sha256": "def456",
                },
            )
