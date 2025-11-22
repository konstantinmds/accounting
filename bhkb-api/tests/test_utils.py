from app.utils import split_clauses, token_chunks


def test_split_clauses_detects_articles():
    text = "Član 1 Ovaj zakon... Član 2 Nastavlja se..."
    clauses = split_clauses(text)
    assert len(clauses) == 2
    assert clauses[0][0].lower().startswith("član")
    assert "Ovaj zakon" in clauses[0][1]


def test_token_chunks_overlap():
    text = " ".join(str(i) for i in range(100))
    chunks = token_chunks(text, target_tokens=20, overlap_ratio=0.25)
    assert chunks  # not empty
    assert all(len(chunk.split()) <= 20 for chunk in chunks)
    assert len(chunks) > 1
