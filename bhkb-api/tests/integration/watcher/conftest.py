from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path
from urllib.parse import urlparse, urlunparse

import pytest
import psycopg
from psycopg import sql, OperationalError
from alembic import command
from alembic.config import Config


ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _swap_db(url: str, dbname: str) -> str:
    parsed = urlparse(url)
    return urlunparse(parsed._replace(path=f"/{dbname}"))


@pytest.fixture(scope="function")
def temp_db_url() -> str:
    base_url = os.getenv("DATABASE_URL", "postgresql://postgres:devpassword@localhost:5432/postgres")
    admin_url = _swap_db(base_url, "postgres")
    dbname = f"watcher_{uuid.uuid4().hex[:8]}"
    test_url = _swap_db(base_url, dbname)

    try:
        with psycopg.connect(admin_url) as conn:
            conn.autocommit = True
            conn.execute(sql.SQL("CREATE DATABASE {}" ).format(sql.Identifier(dbname)))
    except OperationalError:
        pytest.skip("PostgreSQL not available for watcher tests")

    try:
        yield test_url
    finally:
        with psycopg.connect(admin_url) as conn:
            conn.autocommit = True
            conn.execute(sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(dbname)))


@pytest.fixture(scope="function")
def alembic_cfg(temp_db_url: str) -> Config:
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "alembic"))
    cfg.set_main_option("sqlalchemy.url", temp_db_url)
    return cfg


@pytest.fixture(scope="function")
def migrated_db(alembic_cfg: Config, temp_db_url: str) -> str:
    command.upgrade(alembic_cfg, "head")
    yield temp_db_url
    command.downgrade(alembic_cfg, "base")


@pytest.fixture(scope="function")
def seeded_tenant_case(migrated_db: str):
    with psycopg.connect(migrated_db) as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO tenant (slug, name) VALUES (%s,%s) RETURNING id", ("acme", "Acme"))
            tenant_id = cur.fetchone()[0]
            cur.execute(
                "INSERT INTO case_file (tenant_id, label) VALUES (%s,%s) RETURNING id",
                (tenant_id, "Case A"),
            )
            case_id = cur.fetchone()[0]
        conn.commit()
    return migrated_db, tenant_id, case_id
