"""Initial schema extracted from schema.sql"""
from __future__ import annotations

from pathlib import Path

from alembic import op

# revision identifiers, used by Alembic.
revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def _statements_from_schema() -> list[str]:
    schema_path = Path(__file__).resolve().parents[2] / "app" / "schema.sql"
    content = schema_path.read_text(encoding="utf-8")
    statements: list[str] = []
    buffer = ""
    for line in content.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("--"):
            continue
        buffer += line + "\n"
        if stripped.endswith(";"):
            statements.append(buffer.strip().rstrip(";"))
            buffer = ""
    if buffer:
        statements.append(buffer.strip())
    return statements


def upgrade() -> None:
    for statement in _statements_from_schema():
        op.execute(statement)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS embedding CASCADE")
    op.execute("DROP TABLE IF EXISTS chunk CASCADE")
    op.execute("DROP TABLE IF EXISTS clause CASCADE")
    op.execute("DROP TABLE IF EXISTS document CASCADE")
