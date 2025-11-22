import re
from typing import Optional, Tuple, List

ARTICLE_RE = re.compile(r'\b(Član(?:ak)?|Čl\.)\s*\d+\b', re.IGNORECASE)

def split_clauses(text: str) -> List[Tuple[str, str]]:
    """
    Returns list of (article_label, clause_text).
    If no matches, treat whole doc as a single clause.
    """
    positions = [(m.start(), m.group(0)) for m in ARTICLE_RE.finditer(text)]
    if not positions:
        return [("Dokument", text.strip())]
    
    pieces = []
    for i, (start, label) in enumerate(positions):
        end = positions[i + 1][0] if (i + 1) < len(positions) else len(text)
        clause_text = text[start:end].strip()
        pieces.append((label, clause_text))
    return pieces

def token_chunks(text: str, target_tokens=700, overlap_ratio=0.1) -> List[str]:
    """
    Extremely simple tokenizer: split by whitespace ~ approximates tokens.
    Good enough for MVP; you’ll swap to tiktoken later if you want.
    """
    words = text.split()
    step = max(1, int(target_tokens * (1 - overlap_ratio)))
    out = []
    i = 0
    while i < len(words):
        out.append(" ".join(words[i:i+target_tokens]))
        i += step
    return [s for s in out if s.strip()]
