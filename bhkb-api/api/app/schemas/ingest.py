from __future__ import annotations

from pydantic import BaseModel


class IngestResult(BaseModel):
    document_id: int
    clauses: int
    chunks: int
