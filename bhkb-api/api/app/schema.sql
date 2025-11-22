CREATE EXTENSION IF NOT EXISTS vector;  -- harmless if not installed yet

CREATE TABLE IF NOT EXISTS document (
  id BIGSERIAL PRIMARY KEY,
  url TEXT,
  title TEXT,
  issuer TEXT,
  jurisdiction TEXT CHECK (jurisdiction IN ('BIH','FBIH','RS','BD')),
  doc_type TEXT,
  lang TEXT,
  effective_from DATE,
  effective_to DATE
);

CREATE TABLE IF NOT EXISTS clause (
  id BIGSERIAL PRIMARY KEY,
  document_id BIGINT REFERENCES document(id) ON DELETE CASCADE,
  article_label TEXT,
  clause_index INT,
  text TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS chunk (
  id BIGSERIAL PRIMARY KEY,
  clause_id BIGINT REFERENCES clause(id) ON DELETE CASCADE,
  chunk_index INT,
  text TEXT NOT NULL,
  tsv tsvector GENERATED ALWAYS AS (to_tsvector('simple', coalesce(text,''))) STORED
);
CREATE INDEX IF NOT EXISTS idx_chunk_tsv ON chunk USING gin(tsv);

-- vector table is optional initially; enables dense retrieval later
CREATE TABLE IF NOT EXISTS embedding (
  chunk_id BIGINT PRIMARY KEY REFERENCES chunk(id) ON DELETE CASCADE,
  model TEXT NOT NULL,
  vec vector(1024) NOT NULL
);
