from __future__ import annotations

import re
from typing import Iterable, List, Tuple


def split_clauses(text: str) -> List[Tuple[str, str]]:
    """
    Split legal text into clause tuples using markers like 'Član 1'.

    Returns a list of (title, body) tuples preserving order.
    """
    pattern = re.compile(r"(član\s+\d+)", flags=re.IGNORECASE)
    matches = list(pattern.finditer(text))
    if not matches:
        return [("", text)]

    clauses: list[tuple[str, str]] = []
    for idx, match in enumerate(matches):
        start = match.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
        title = match.group().strip()
        body = text[start:end].strip()
        clauses.append((title, body))
    return clauses


def token_chunks(text: str, target_tokens: int = 200, overlap_ratio: float = 0.1) -> List[str]:
    """
    Break text into overlapping token chunks of roughly target_tokens length.
    """
    words = text.split()
    if not words:
        return []

    overlap = int(target_tokens * overlap_ratio)
    step = max(1, target_tokens - overlap)

    chunks: list[str] = []
    for start in range(0, len(words), step):
        chunk_words = words[start : start + target_tokens]
        if not chunk_words:
            break
        chunks.append(" ".join(chunk_words))
        if start + step >= len(words):
            break
    return chunks
