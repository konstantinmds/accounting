from __future__ import annotations
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    CheckConstraint, ForeignKey, Index, UniqueConstraint, text
)
from sqlalchemy.dialects.postgresql import UUID, JSONB, BIGINT
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy import Text, Integer, Boolean, TIMESTAMP

class Base(DeclarativeBase):
    pass


"""
A file lands → 
we register an artifact (the raw file) 
under a case_file (the work unit) belonging to a tenant.
We enqueue an ingest_task to parse it into normalized_record rows.
Any bad inputs go to dead_letter.
Every important step writes a lineage event. 
Separately, the research agent stores links in research_finding (kept apart from customer data).
"""

class Tenant(Base):
    __tablename__ = "tenant"
    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, server_default=text("gen_random_uuid()"))
    slug: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    name: Mapped[Optional[str]] = mapped_column(Text)

    cases: Mapped[list[CaseFile]] = relationship(back_populates="tenant", cascade="all,delete-orphan")
    

class CaseFile(Base):
    __tablename__ = "case_file"
    __table_args__ = (
        Index("idx_case_tenant", "tenant_id"),
        Index("idx_case_filters", "tenant_id", "topic", "jurisdiction", "period"),
        CheckConstraint("topic IN ('VAT','CIT','PAYROLL','FR','BOOKKEEPING','DEADLINES')", name="ck_case_topic"),
        CheckConstraint("jurisdiction IN ('BIH','FBIH','RS','BD')", name="ck_case_jurisdiction"),
        CheckConstraint("status IN ('open','closed','archived')", name="ck_case_status"),
    )

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, server_default=text("gen_random_uuid()"))
    tenant_id: Mapped[Optional[str]] = mapped_column(UUID(as_uuid=False), ForeignKey("tenant.id", ondelete="CASCADE"))
    label: Mapped[Optional[str]] = mapped_column(Text)

    # NEW: structured metadata
    topic: Mapped[Optional[str]] = mapped_column(Text)          # 'VAT'|'CIT'|...
    jurisdiction: Mapped[Optional[str]] = mapped_column(Text)   # 'BIH'|'FBIH'|'RS'|'BD'
    period: Mapped[Optional[str]] = mapped_column(Text)         # '2025-10' | '2025' | '2025-Q3'
    status: Mapped[str] = mapped_column(Text, server_default=text("'open'"), nullable=False)

    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text("now()"), nullable=False)

    tenant: Mapped[Optional[Tenant]] = relationship(back_populates="cases")
    artifacts: Mapped[list[Artifact]] = relationship(back_populates="case", cascade="all,delete-orphan")


class Artifact(Base):
    __tablename__ = "artifact"
    __table_args__ = (
        UniqueConstraint("case_id", "sha256", name="uq_artifact_case_sha"),
        Index("idx_artifact_tenant_case", "tenant_id", "case_id"),
    )

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, server_default=text("gen_random_uuid()"))
    tenant_id: Mapped[Optional[str]] = mapped_column(UUID(as_uuid=False), ForeignKey("tenant.id", ondelete="CASCADE"))
    case_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("case_file.id", ondelete="CASCADE"), nullable=False)
    drop_id: Mapped[Optional[str]] = mapped_column(UUID(as_uuid=False))
    filename: Mapped[Optional[str]] = mapped_column(Text)
    src_path: Mapped[Optional[str]] = mapped_column(Text)
    s3_uri: Mapped[str] = mapped_column(Text, nullable=False)
    mime_type: Mapped[Optional[str]] = mapped_column(Text)
    sha256: Mapped[str] = mapped_column(Text, nullable=False)
    size_bytes: Mapped[Optional[int]] = mapped_column(BIGINT)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text("now()"), nullable=False)

    case: Mapped[CaseFile] = relationship(back_populates="artifacts")
    tasks: Mapped[list[IngestTask]] = relationship(back_populates="artifact", cascade="all,delete-orphan")
    records: Mapped[list[NormalizedRecord]] = relationship(back_populates="artifact", cascade="all,delete-orphan")


class IngestTask(Base):
    __tablename__ = "ingest_task"
    __table_args__ = (
        CheckConstraint("status IN ('pending','running','success','failed','dlq')", name="ck_ingest_status"),
        Index("idx_ingest_task_status", "status"),
    )

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, server_default=text("gen_random_uuid()"))
    artifact_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("artifact.id", ondelete="CASCADE"), nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'pending'"))
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    last_error: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text("now()"), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text("now()"), nullable=False)

    artifact: Mapped[Artifact] = relationship(back_populates="tasks")


class DeadLetter(Base):
    __tablename__ = "dead_letter"

    id: Mapped[int] = mapped_column(BIGINT, primary_key=True, autoincrement=True)
    target: Mapped[Optional[str]] = mapped_column(Text)           # path or URL
    failed_activity: Mapped[Optional[str]] = mapped_column(Text)  # WATCHER_VALIDATE / PARSE / ...
    last_error: Mapped[Optional[str]] = mapped_column(Text)
    error_blob: Mapped[Optional[dict]] = mapped_column(JSONB)
    failed_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text("now()"), nullable=False)


class NormalizedRecord(Base):
    __tablename__ = "normalized_record"
    __table_args__ = (
        Index("idx_record_artifact", "artifact_id"),
        Index("idx_record_schema", "schema_version"),
    )

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, server_default=text("gen_random_uuid()"))
    artifact_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("artifact.id", ondelete="CASCADE"), nullable=False)
    row_index: Mapped[Optional[int]] = mapped_column(Integer)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    schema_version: Mapped[str] = mapped_column(Text, nullable=False)  # e.g., 'customer-ledger@1.0'
    valid: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text("now()"), nullable=False)

    artifact: Mapped[Artifact] = relationship(back_populates="records")

class Lineage(Base):
    __tablename__ = "lineage"
    __table_args__ = (Index("idx_lineage_artifact", "artifact_id"),)

    id: Mapped[int] = mapped_column(BIGINT, primary_key=True, autoincrement=True)
    artifact_id: Mapped[Optional[str]] = mapped_column(UUID(as_uuid=False))
    record_id: Mapped[Optional[str]] = mapped_column(UUID(as_uuid=False))
    run_id: Mapped[Optional[str]] = mapped_column(Text)
    action: Mapped[Optional[str]] = mapped_column(Text)  # PARSED/INDEXED_ES/...
    at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text("now()"), nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text)


class ResearchFinding(Base):
    __tablename__ = "research_finding"
    __table_args__ = (Index("idx_finding_tenant_case", "tenant_id", "case_id"),)

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, server_default=text("gen_random_uuid()"))
    tenant_id: Mapped[Optional[str]] = mapped_column(UUID(as_uuid=False), ForeignKey("tenant.id", ondelete="CASCADE"))
    case_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("case_file.id", ondelete="CASCADE"), nullable=False)
    url: Mapped[Optional[str]] = mapped_column(Text)
    title: Mapped[Optional[str]] = mapped_column(Text)
    snippet: Mapped[Optional[str]] = mapped_column(Text)
    captured_s3_uri: Mapped[Optional[str]] = mapped_column(Text)
    domain: Mapped[Optional[str]] = mapped_column(Text)
    allowlisted: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    fetched_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True))
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text("now()"), nullable=False)
