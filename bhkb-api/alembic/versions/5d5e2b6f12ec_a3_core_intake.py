"""A3: core intake schema."""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg

# revision identifiers, used by Alembic.
revision = "5d5e2b6f12ec"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp";')
    op.execute('CREATE EXTENSION IF NOT EXISTS pgcrypto;')

    op.create_table(
        "tenant",
        sa.Column("id", pg.UUID(as_uuid=False), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("slug", sa.Text(), nullable=False, unique=True),
        sa.Column("name", sa.Text()),
    )

    op.create_table(
        "case_file",
        sa.Column("id", pg.UUID(as_uuid=False), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", pg.UUID(as_uuid=False), sa.ForeignKey("tenant.id", ondelete="CASCADE")),
        sa.Column("label", sa.Text()),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("idx_case_tenant", "case_file", ["tenant_id"])

    op.create_table(
        "artifact",
        sa.Column("id", pg.UUID(as_uuid=False), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", pg.UUID(as_uuid=False), sa.ForeignKey("tenant.id", ondelete="CASCADE")),
        sa.Column("case_id", pg.UUID(as_uuid=False), sa.ForeignKey("case_file.id", ondelete="CASCADE"), nullable=False),
        sa.Column("drop_id", pg.UUID(as_uuid=False)),
        sa.Column("filename", sa.Text()),
        sa.Column("src_path", sa.Text()),
        sa.Column("s3_uri", sa.Text(), nullable=False),
        sa.Column("mime_type", sa.Text()),
        sa.Column("sha256", sa.Text(), nullable=False),
        sa.Column("size_bytes", sa.BigInteger()),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("idx_artifact_tenant_case", "artifact", ["tenant_id", "case_id"])
    op.create_unique_constraint("uq_artifact_case_sha", "artifact", ["case_id", "sha256"])

    op.create_table(
        "ingest_task",
        sa.Column("id", pg.UUID(as_uuid=False), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("artifact_id", pg.UUID(as_uuid=False), sa.ForeignKey("artifact.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("last_error", sa.Text()),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("status IN ('pending','running','success','failed','dlq')", name="ck_ingest_status"),
    )
    op.create_index("idx_ingest_task_status", "ingest_task", ["status"])

    op.create_table(
        "dead_letter",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("target", sa.Text()),
        sa.Column("failed_activity", sa.Text()),
        sa.Column("last_error", sa.Text()),
        sa.Column("error_blob", pg.JSONB()),
        sa.Column("failed_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    op.create_table(
        "normalized_record",
        sa.Column("id", pg.UUID(as_uuid=False), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("artifact_id", pg.UUID(as_uuid=False), sa.ForeignKey("artifact.id", ondelete="CASCADE"), nullable=False),
        sa.Column("row_index", sa.Integer()),
        sa.Column("payload", pg.JSONB(), nullable=False),
        sa.Column("schema_version", sa.Text(), nullable=False),
        sa.Column("valid", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("idx_record_artifact", "normalized_record", ["artifact_id"])
    op.create_index("idx_record_schema", "normalized_record", ["schema_version"])

    op.create_table(
        "lineage",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("artifact_id", pg.UUID(as_uuid=False)),
        sa.Column("record_id", pg.UUID(as_uuid=False)),
        sa.Column("run_id", sa.Text()),
        sa.Column("action", sa.Text()),
        sa.Column("at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("notes", sa.Text()),
    )
    op.create_index("idx_lineage_artifact", "lineage", ["artifact_id"])

    op.create_table(
        "research_finding",
        sa.Column("id", pg.UUID(as_uuid=False), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", pg.UUID(as_uuid=False), sa.ForeignKey("tenant.id", ondelete="CASCADE")),
        sa.Column("case_id", pg.UUID(as_uuid=False), sa.ForeignKey("case_file.id", ondelete="CASCADE"), nullable=False),
        sa.Column("url", sa.Text()),
        sa.Column("title", sa.Text()),
        sa.Column("snippet", sa.Text()),
        sa.Column("captured_s3_uri", sa.Text()),
        sa.Column("domain", sa.Text()),
        sa.Column("allowlisted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("fetched_at", sa.TIMESTAMP(timezone=True)),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("idx_finding_tenant_case", "research_finding", ["tenant_id", "case_id"])


def downgrade() -> None:
    op.drop_index("idx_finding_tenant_case", table_name="research_finding")
    op.drop_table("research_finding")

    op.drop_index("idx_lineage_artifact", table_name="lineage")
    op.drop_table("lineage")

    op.drop_index("idx_record_schema", table_name="normalized_record")
    op.drop_index("idx_record_artifact", table_name="normalized_record")
    op.drop_table("normalized_record")

    op.drop_table("dead_letter")

    op.drop_index("idx_ingest_task_status", table_name="ingest_task")
    op.drop_table("ingest_task")

    op.drop_constraint("uq_artifact_case_sha", "artifact", type_="unique")
    op.drop_index("idx_artifact_tenant_case", table_name="artifact")
    op.drop_table("artifact")

    op.drop_index("idx_case_tenant", table_name="case_file")
    op.drop_table("case_file")

    op.drop_table("tenant")
