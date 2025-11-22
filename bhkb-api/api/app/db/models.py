"""SQLAlchemy models representing the core database entities."""
from __future__ import annotations

from datetime import date

from sqlalchemy import BigInteger, CheckConstraint, Date, ForeignKey, Integer, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Document(Base):
    __tablename__ = "document"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    url: Mapped[str | None] = mapped_column(Text)
    title: Mapped[str | None] = mapped_column(Text)
    issuer: Mapped[str | None] = mapped_column(Text)
    jurisdiction: Mapped[str | None] = mapped_column(
        Text,
        CheckConstraint("jurisdiction IN ('BIH','FBIH','RS','BD')"),
    )
    doc_type: Mapped[str | None] = mapped_column(Text)
    lang: Mapped[str | None] = mapped_column(Text)
    effective_from: Mapped[date | None] = mapped_column(Date)
    effective_to: Mapped[date | None] = mapped_column(Date)

    clauses: Mapped[list[Clause]] = relationship(back_populates="document")


class Clause(Base):
    __tablename__ = "clause"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    document_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("document.id", ondelete="CASCADE"), index=True
    )
    article_label: Mapped[str | None] = mapped_column(Text)
    clause_index: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text, nullable=False)

    document: Mapped[Document] = relationship(back_populates="clauses")
    chunks: Mapped[list[Chunk]] = relationship(back_populates="clause")


class Chunk(Base):
    __tablename__ = "chunk"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    clause_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("clause.id", ondelete="CASCADE"), index=True
    )
    chunk_index: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text, nullable=False)

    clause: Mapped[Clause] = relationship(back_populates="chunks")
    embedding: Mapped[Embedding | None] = relationship(back_populates="chunk", uselist=False)


class Embedding(Base):
    __tablename__ = "embedding"

    chunk_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("chunk.id", ondelete="CASCADE"), primary_key=True
    )
    model: Mapped[str] = mapped_column(Text, nullable=False)
    vec: Mapped[list[float]] = mapped_column(Text, nullable=False)

    chunk: Mapped[Chunk] = relationship(back_populates="embedding")
