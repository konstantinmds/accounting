import asyncio
import os
from typing import Iterable, List, Optional, Sequence, Tuple

from .db import get_conn
from .embeddings import embed_voyage
from .exctract import extract_text, fetch_bytes
from .meta import extract_effective_from, guess_jurisdiction
from .schemas import IngestResult
from .utils import split_clauses, token_chunks

USE_FALLBACK_EMBEDDING = os.getenv("VOYAGE_API_KEY") is None

Clause = Tuple[str, str]
ChunkRow = Tuple[int, str]


def cheap_embed(texts: Sequence[str]) -> List[List[float]]:
    """Deterministic pseudo embeddings used when Voyage API is unavailable."""
    import hashlib
    import numpy as np

    vectors: List[List[float]] = []
    for text in texts:
        digest = hashlib.sha256(text.encode("utf-8", errors="ignore")).digest()
        seed = int(np.frombuffer(digest[:8], dtype=np.uint64)[0])
        rng = np.random.default_rng(seed)
        vec = rng.standard_normal(1024).astype("float32")
        vec /= max(1e-6, np.linalg.norm(vec))
        vectors.append(vec.tolist())
    return vectors


async def ingest_url(url: str, title: Optional[str] = None, issuer: Optional[str] = None) -> IngestResult:
    data, content_type = await fetch_bytes(url)
    text = extract_text(data, content_type)
    if not text.strip() or len(text) < 100:
        raise ValueError("Extracted text is empty or too short")

    jurisdiction = guess_jurisdiction(url, text)
    effective_from = extract_effective_from(text)

    document_id = await asyncio.to_thread(
        _insert_document,
        url,
        title or url,
        issuer,
        jurisdiction,
        effective_from,
    )

    clauses = split_clauses(text)
    chunk_rows = await asyncio.to_thread(_persist_clauses_and_chunks, document_id, clauses)

    chunk_ids = [chunk_id for chunk_id, _ in chunk_rows]
    chunk_texts = [chunk_text for _, chunk_text in chunk_rows]

    if chunk_ids:
        vectors = (
            cheap_embed(chunk_texts)
            if USE_FALLBACK_EMBEDDING
            else await embed_voyage(chunk_texts)
        )
        await asyncio.to_thread(_insert_embeddings, chunk_ids, vectors)

    return IngestResult(document_id=document_id, clauses=len(clauses), chunks=len(chunk_rows))


def _insert_document(
    url: str,
    title: str,
    issuer: Optional[str],
    jurisdiction: Optional[str],
    effective_from: Optional[str],
) -> int:
    with get_conn() as conn:
        cursor = conn.execute(
            """
            INSERT INTO document (url, title, issuer, jurisdiction, doc_type, lang, effective_from)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (url, title, issuer, jurisdiction, "guidance", "bs", effective_from),
        )
        row = cursor.fetchone()
        if row is None:
            raise RuntimeError("Failed to insert document")
        return row[0]


def _persist_clauses_and_chunks(document_id: int, clauses: Sequence[Clause]) -> List[ChunkRow]:
    chunk_rows: List[ChunkRow] = []
    with get_conn() as conn:
        for index, (label, clause_text) in enumerate(clauses):
            cursor = conn.execute(
                """
                INSERT INTO clause (document_id, article_label, clause_index, text)
                VALUES (%s, %s, %s, %s)
                RETURNING id
                """,
                (document_id, label, index, clause_text),
            )
            clause_row = cursor.fetchone()
            if clause_row is None:
                raise RuntimeError("Failed to insert clause")
            clause_id = clause_row[0]
            for chunk_index, chunk_text in enumerate(token_chunks(clause_text, 700, 0.1)):
                chunk_cursor = conn.execute(
                    """
                    INSERT INTO chunk (clause_id, chunk_index, text)
                    VALUES (%s, %s, %s)
                    RETURNING id
                    """,
                    (clause_id, chunk_index, chunk_text),
                )
                chunk_row = chunk_cursor.fetchone()
                if chunk_row is None:
                    raise RuntimeError("Failed to insert chunk")
                chunk_id = chunk_row[0]
                chunk_rows.append((chunk_id, chunk_text))
    return chunk_rows


def _insert_embeddings(chunk_ids: Sequence[int], vectors: Iterable[Sequence[float]]) -> None:
    with get_conn() as conn:
        for chunk_id, vector in zip(chunk_ids, vectors):
            conn.execute(
                """
                INSERT INTO embedding (chunk_id, model, vec)
                VALUES (%s, %s, %s)
                """,
                (chunk_id, "voyage-context-3", vector),
            )
