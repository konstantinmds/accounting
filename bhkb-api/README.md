# SPEC-1 — BH Accounting Knowledge Base & Scraper

## Background

You want an end‑to‑end system that:

* **Discovers and scrapes authoritative accounting content for Bosnia & Herzegovina (BiH)** across state and entity levels (BiH, Federation of BiH, Republika Srpska, and Brčko District). Sources are expected to include: official gazettes, tax administrations, ministries of finance, and professional bodies.
* **Normalizes and classifies the scraped documents** (laws, bylaws, IFRS translations, guidance, tax circulars, FAQs, forms) by topic (e.g., VAT, CIT, payroll, financial reporting), jurisdiction, and firm size tier (micro/small vs. medium/large) to surface what’s relevant to each audience.
* **Builds a searchable knowledge base** with versioning (historical vs. current rules), multilingual support (Bosnian/Croatian/Serbian and optionally English), and citations back to primary sources.
* **Supports update monitoring** (diffs & alerts when a law or rule changes) and human-in-the-loop curation for summaries and compliance notes.

 **Confirmed** : MVP targets small firms first; big-firm content is low priority but tagged. Launch in BCS; English summaries later.

## Requirements

**Must‑Have (MVP)**

* Crawl/scrape prioritized sources with polite rate limits and change detection.
* Document processing pipeline: HTML/PDF/Docx to clean text; chunking; metadata extraction (jurisdiction, topic, effective dates, article numbers, source URL).
* Controlled taxonomy/ontology for BiH accounting topics (VAT, CIT, payroll, financial reporting, bookkeeping, deadlines, forms) + jurisdiction facets (BiH/FBiH/RS/BD) + audience (micro/small).
* Versioning & temporal validity: effective_from / effective_to per clause; show “current vs. historical”.
* Search & QA via RAG: vector embeddings over chunks + keyword filter on jurisdiction/topic; strict source citation.
* Admin console: source configs, crawl status, manual curation (edit summaries, merge duplicates), publish workflow.
* Evaluation: coverage score (sources × topics), retrieval quality (Top‑k hit rate on a labeled QA set), and hallucination rate (<1% with citation checks).

**Should‑Have**

* Summarization tuned for small firms (plain language, steps, thresholds, deadlines) with disclaimers.
* Alerting: weekly diff digest for changes affecting small firms.
* Multilingual: optional English summaries.

**Could‑Have**

* Extraction of structured fields (rates, thresholds, deadlines) into a rules table.
* API for ERP integrations.

**Won’t-Have (MVP)**

* Full big-firm features (IFRS consolidation specifics) beyond tagging.
* Complex workflow automation (e-filing).

> **MVP mode:** Until we formalize the production rollout, every component runs locally via Docker Compose (Temporal, Postgres/pgvector, Elasticsearch/OpenSearch, MinIO, FastAPI, Next.js). No AWS/GCP/Azure services are provisioned yet; the README documents the local-first architecture we are shipping now.

## Method

> **Stack Decision:** Ship the MVP as a fully local (Docker-first) stack so we can validate crawling, ingestion, retrieval, and reporting workflows without any cloud infrastructure. Cloud lift can come later once the flows are hardened.

### Architecture — Local-first (Docker Compose + Postgres/pgvector + Local Embeddings + Temporal)

* **Frontend** : Next.js 14 (App Router) running locally via Docker (`next dev`/`next start`) behind the compose network.
* **Backend API** : FastAPI (uvicorn) container serving public endpoints on localhost; no API Gateway/WAF yet.
* **Orchestration** : Temporal server + workers running in Docker Compose; workflows manage crawling, parsing, embeddings, upserts, and change reprocessing.
* **Vector/Sparse** : PostgreSQL + pgvector for dense vectors; **Elasticsearch/OpenSearch** for BM25/lexical; fusion via Reciprocal Rank Fusion + MMR inside the API.
* **Sparse Encoder** : FastEmbed SPLADE for sparse vectors.
* **Dense Embeddings** : Local open-weight model (default `BAAI/bge-m3` via GGUF/ONNX service) to avoid external APIs; optionally swap to **Gemini Flash Lite Embedding** when network access is acceptable.
* **Reranking** : Local cross-encoder (`bge-reranker-v2-m3` or similar) with an optional Gemini Flash Lite rerank call if needed.
* **Q&A Model** : Gemini 2.5 Pro for answer synthesis with strict citation injection.
* **Metadata/State DB** : PostgreSQL (single local instance shared by Temporal + app schema).
* **Object Storage** : MinIO (S3-compatible) container for raw files and parsed JSONL.
* **Queueing/Events** : Temporal workflows, signals, and task queues handle scheduling/backpressure; no SQS/EventBridge yet.
* **Secrets** : `.env`/Docker secrets on the dev machine for Gemini and any optional remote services.

### Retrieval Settings (updated)

```
CHUNK_TOKENS = 700           # was 1000
CHUNK_OVERLAP = 0.1          # 10% overlap (~70 tokens)
PREFETCH_LIMIT = 1000        # per vector type (keep)
MMR_DIVERSITY = 0.6
RERANK_TOP_K = 50
FINAL_TOP_K = 12
PGVECTOR_INDEX = "ivfflat"
PGVECTOR_LISTS = 200
PGVECTOR_PROBES = 20
```

CHUNK_TOKENS = 1000

CHUNK_OVERLAP = 0

PREFETCH_LIMIT = 1000        # per vector type

MMR_DIVERSITY = 0.6

RERANK_TOP_K = 50

FINAL_TOP_K = 12

PGVECTOR_INDEX = "ivfflat"

PGVECTOR_LISTS = 200

PGVECTOR_PROBES = 20

```

### BiH‑specific pipeline adaptations
- **Clause splitting** tuned for BCS legal markers: `Član|Čl\.|Članak|Članku`.
- **Date/Efficacy extraction**: regex for phrases like `stupa na snagu`, `primjenjuje se od`, `danom objave`.
- **Jurisdiction tagging** from issuers and headers (BiH/FBiH/RS/BD), fallback to domain mapping.
- **Form/Rate extraction** tables: VAT rates, contribution bases; reviewed in Admin UI.

### Working with Cyrillic & Latin content (Phase 1 focus)
- **Keep original script**: ingest and store documents exactly as published (Bosnian/Serbian/Croatian in Latin or Cyrillic). Do *not* transliterate to English—the source script carries legal nuance and preserves citations.
- **Normalize for search**:
  - Use Unicode-aware lowercasing; strip diacritics only for keyword matching (`č → c`, etc.) while retaining the original text for display.
  - Configure Postgres `tsvector` with the `simple` dictionary and case-folded tokens; for Cyrillic sources consider adding trigram or custom dictionaries once coverage grows.
- **Embeddings**: Local BGE/GTE-style multilingual models handle mixed scripts well; ensure the tokenizer sees normalized whitespace. Gemini Flash Lite embeddings are a lightweight fallback when local GPU/CPU performance lags. Keep deterministic embeddings (e.g., `cheap_embed`) for tests.
- **Metadata**: standardize jurisdiction/topic labels in Latin script, but capture display names in the original script when available. Store multi-script aliases if the same institution publishes in both scripts.
- **QA & summaries**: first release answers in Bosnian/Croatian/Serbian. Add English summaries later via a post-processing step; never overwrite the original snippet.
- **Testing**: include fixtures with Cyrillic (e.g., `Брчко дистрикт`) to avoid regressions in clause splitting, jurisdiction detection, and search scoring.

### Query Flow (concise)
1) Encode query to **dense** (local BGE/GTE or Gemini Flash Lite) + **sparse** (SPLADE).
2) **Postgres/pgvector + Elasticsearch**: run dense cosine search (pgvector) + BM25 (Elasticsearch); fuse via Reciprocal Rank Fusion + MMR → Top 50.
3) **Local reranker** (bge-reranker-v2-m3) or Gemini Flash Lite rerank Top 50 → Top 12.
4) **Answer** with Gemini 2.5 Pro using Top 12 snippets; enforce citation blocks and jurisdiction filters.

### Agentic Patterns (optional for MVP)
Goal: Improve answer accuracy on legal/financial queries without heavy frameworks (no LangChain). Keep Temporal as the main orchestrator; add **lightweight agents** as pure Python modules.

**Where agentic logic helps**
- **ReAct for retrieval**: tool-using loop that can: (a) refine the query (spellings, synonyms), (b) add mandatory filters (jurisdiction/topic/date), (c) re-search if citations are weak.
- **Reflection (self‑critique)**: a short checklist pass to detect missing citations, jurisdiction mismatch, outdated clauses (effective_to < today), or contradictions.
- **Task decomposition**: for multi‑part queries (e.g., “VAT threshold and monthly filing deadlines in FBiH”), split into sub‑questions and merge results with explicit citations per sub‑answer.
- **Routing**: classify intent to one of: {**lookup** (exact article), **how‑to** (procedure), **calc** (rate/threshold), **compare** (entity differences)} and adjust prompts/tools.

**Minimal ReAct loop (sequence)**
```plantuml
@startuml
skinparam componentStyle rectangle
actor Admin
actor User

package "Data Sources" {
  [Official Gazettes]
  [Tax Administrations]
  [Ministries of Finance]
  [Professional Bodies]
}

component "Temporal Server" as Temporal
component "Workers (Crawl/Parse/Embed/Upsert)" as Workers
component "Headless Crawler" as Crawler
component "Doc Fetcher" as Fetcher
component "Text & OCR" as Extractor
component "Cleaner & Deduper" as Cleaner
component "Metadata & NER" as Metadata
component "Versioning & Diff" as Versioning
component "Indexer (PG FTS + pgvector)" as Indexer
component "RAG Service" as RAG
component "Admin UI" as AdminUI
component "KB API" as API

database "PostgreSQL (pgvector + FTS)" as PG
database "Object Storage (S3/MinIO)" as S3

Admin --> AdminUI
User --> API

[Official Gazettes] --> Crawler
[Tax Administrations] --> Crawler
[Ministries of Finance] --> Crawler
[Professional Bodies] --> Crawler

Temporal <--> Workers
AdminUI --> Temporal
Temporal --> Crawler
Crawler --> Fetcher
Fetcher --> S3
Fetcher --> Extractor
Extractor --> Cleaner
Cleaner --> Metadata
Metadata --> PG
Cleaner --> Versioning
Versioning --> PG

PG --> Indexer
S3 --> Indexer
IndexER --> PG
PG --> RAG
RAG --> API
@enduml
```

**Implementation notes (no LangChain)**

* **Controller** : a small Python class with a finite-state machine (pydantic for IO schemas). Tools are plain functions: `search_hybrid()` (pgvector + Elasticsearch), `rerank_local()`, `generate_gemini()`, `reflect()`.
* **Stop conditions** : (a) at least N=3 unique sources, (b) all snippets have `effective_to IS NULL OR >= today`, (c) jurisdiction matches, (d) confidence ≥ threshold.
* **Temporal integration** : the controller runs inside the API process; no need to model it as a Temporal workflow.

**Pros**

* Higher accuracy and fewer “wrong jurisdiction” answers.
* Robust to vague queries; auto-adds filters.
* Auditable: logs the chain of thoughts as **actions/observations** (not model internals).

**Cons**

* Extra latency (one more search/regenerate loop when reflection fails).
* Slightly higher cost from reruns.

**MVP recommendation**

* Enable **ReAct + Reflection** behind a feature flag.
* Keep **single-agent** (controller) now; consider multi-agent later (e.g., a **Compliance Reviewer** agent) if needed.

### Financial Data Knowledge Strategy

To support automated financial reporting (beyond regulatory QA), we will extend the pipeline with the following stages. Each stage maps to a Temporal workflow/activity and feeds both the knowledge graph and the RAG layer.

1. **Semantic Chunking** — reuse the clause/chunk pipeline but add semantic boundaries (topic-aware chunker, max 700 tokens) so every block captures a single accounting concept. Store embeddings + metadata for RAG and feed the same chunks into fact extraction.
2. **Atomic Fact Extraction** — LLM (or deterministic parser) converts each chunk into structured facts: subject, predicate, object, jurisdiction, effective dates, citation URI. Persist as `fact` rows referencing the source chunk for traceability.
3. **Entity Resolution** — maintain canonical entity tables (companies, authorities, forms, thresholds). Use fuzzy/embedding matching to merge aliases (e.g., “UPFBiH”, “Poreska uprava FBiH”). Temporal periodically runs resolution jobs so downstream reports don’t double-count.
4. **Temporal Invalidation** — when new clauses arrive, diff fact values, set `valid_to` on superseded facts, and emit `change_event` entries. Downstream agents always query `valid_now = TRUE` but auditors can inspect history.
5. **Knowledge Graph Construction** — load resolved entities + atomic facts into a property graph (initially Postgres tables emulating edges; later optional Neo4j/Neptune). Nodes: entities, regulations, financial measures. Edges encode relationships (e.g., “Company uses Rule”, “Rule sets Threshold”).
6. **Optimized Knowledge Base** — expose both (a) the hybrid text index (pgvector + Elasticsearch) and (b) the fact/graph API. Financial AI workers first query the graph for deterministic numbers, then retrieve supporting text for narrative + citations.

**Recommended additions**
- **Data lineage & audit logging**: capture provenance (source doc, chunk, extraction model version) per fact so financial statements are audit-ready.
- **Validation harness**: synthetic/real test suites that compare extracted facts against known filings to catch drift in the extraction pipeline.
- **PII/financial data safeguards**: classify and mask sensitive customer data before it enters the knowledge graph; track access via Temporal audit logs.

> **Stack Decision:** Run this variant locally as well; Postgres/pgvector, Temporal, Gemini, and the local embedding services all live inside Docker until we intentionally migrate to cloud infra.

### Architecture — Local-first + Postgres/pgvector + Local Embeddings + Temporal (Selected)

* **Frontend** : Next.js 14 (App Router) container served locally; static build can sit on the dev machine.
* **Backend API** : FastAPI (uvicorn/gunicorn) container exposed on localhost; no API Gateway/WAF layer yet.
* **Orchestration** : Temporal server + workers via docker-compose; workflows manage crawling, parsing, embeddings, upserts, and reprocessing on change.
* **Vector/Sparse** : Postgres + pgvector for dense vectors plus Elasticsearch/OpenSearch for BM25; fusion handled inside the API.
* **Sparse Encoder** : FastEmbed SPLADE for sparse vectors.
* **Dense Embeddings** : Local open-weight encoder (default `BAAI/bge-m3`) with optional Gemini Flash Lite embeddings if the workstation lacks GPU acceleration.
* **Reranking** : Local cross-encoder (`bge-reranker-v2-m3` or similar) with an optional Gemini Flash Lite rerank endpoint.
* **Q&A Model** : Gemini 2.5 Pro for answer synthesis with strict citation injection.
* **Metadata/State DB** : PostgreSQL container (also stores Temporal visibility tables).
* **Object Storage** : MinIO (S3-compatible) container for raw files and parsed JSONL.
* **Queueing/Events** : Temporal task queues/signals/backoffs; no SQS/EventBridge until cloud migration.
* **Secrets** : `.env` files or Docker secrets on the dev workstation.

### Why this stack fits

* **Postgres + pgvector** keep metadata and dense vectors in one database; **Elasticsearch/OpenSearch** handles the heavy BM25 work and scales horizontally when the corpus grows.
* **BAAI/bge-m3** (or similar multilingual local encoders) handle Bosnian/Croatian/Serbian text offline; they run on CPU/GPU and keep embeddings on the workstation.
* **FastEmbed SPLADE** provides strong sparse signals and integrates cleanly with Postgres FTS for hybrid retrieval.
* **Temporal**’s Python SDK delivers durable, retryable workflows so failed steps resume at the activity level—critical for flaky public sources.
* **Next.js 14** remains a stable baseline for the admin + user apps.
* **Gemini Flash Lite Embedding** and **Gemini 2.5 Pro** give us hosted fallbacks for embeddings, reranking, and narrative answers when we want extra quality without managing heavier models locally.

### Retrieval Settings (adopted from your tests)

```
CHUNK_TOKENS = 1000
CHUNK_OVERLAP = 0
PREFETCH_LIMIT = 1000        # per vector type
MMR_DIVERSITY = 0.6
RERANK_TOP_K = 50
FINAL_TOP_K = 12
PGVECTOR_INDEX = "ivfflat"
PGVECTOR_LISTS = 200
PGVECTOR_PROBES = 20
```

### BiH‑specific pipeline adaptations

* **Clause splitting** tuned for BCS legal markers: `Član|Čl\.|Članak|Članku`.
* **Date/Efficacy extraction** : regex for phrases like `stupa na snagu`, `primjenjuje se od`, `danom objave`.
* **Jurisdiction tagging** from issuers and headers (BiH/FBiH/RS/BD), fallback to domain mapping.
* **Form/Rate extraction** tables: VAT rates, contribution bases; reviewed in Admin UI.

### Query Flow (concise)

1. Encode query to **dense** (local BGE/GTE or Gemini Flash Lite) + **sparse** (SPLADE).
2. **Postgres/pgvector + Elasticsearch** : dense cosine search + BM25 → RRF/MMR → Top 50.
3. **Local reranker** (bge-reranker-v2-m3) or Gemini Flash Lite rerank Top 50 → Top 12.
4. **Answer** with Gemini 2.5 Pro using Top 12 snippets; enforce citation blocks and jurisdiction filters.

### System Overview

* **Crawler Layer** : Scheduled site crawlers (HTTP + headless browser) fetch HTML/PDF/DOCX from prioritized public sources. Respect robots.txt and add per‑domain throttling.
* **Ingestion & Normalization** : Convert to canonical text; detect language; OCR images/PDF scans; clean boilerplate; deduplicate by content hash.
* **Metadata & Taxonomy** : Extract jurisdiction (BiH/FBiH/RS/BD), topic (VAT, CIT, Payroll, Financial Reporting, Bookkeeping, Deadlines/Forms), document type (law/bylaw/guidance/form/FAQ), effective dates, article numbers, issuer, and audience tag (micro/small).
* **Versioning & Change Detection** : Track each source page’s last_etag/last_hash; if changed, diff previous vs new at the clause level and mark effective_from/effective_to.
* **Search & QA (RAG)** : Hybrid retrieval (BM25 + vector). Re‑rank top‑k, then synthesize an answer with strict citations and jurisdictional disclaimers.
* **Admin Console** : Manage source configs, crawl status, taxonomy, dedup/merge, editorial summaries, and publish workflow.

### Reference Architecture (PlantUML)

```plantuml
@startuml
skinparam componentStyle rectangle
actor Admin
actor User

package "Data Sources" {
  [Official Gazettes]
  [Tax Administrations]
  [Ministries of Finance]
  [Professional Bodies]
}

component "Temporal Server" as Temporal
component "Workers (Crawl/Parse/Embed/Upsert)" as Workers
component "Headless Crawler" as Crawler
component "Doc Fetcher" as Fetcher
component "Text & OCR" as Extractor
component "Cleaner & Deduper" as Cleaner
component "Metadata & NER" as Metadata
component "Versioning & Diff" as Versioning
component "Indexer (pgvector + FTS)" as Indexer
component "RAG Service" as RAG
component "Admin UI" as AdminUI
component "KB API" as API

database "PostgreSQL (+pgvector for ops)" as PG
database "Object Storage (S3 raw)" as S3
component "Elasticsearch/OpenSearch" as ES

Admin --> AdminUI
User --> API

[Official Gazettes] --> Crawler
[Tax Administrations] --> Crawler
[Ministries of Finance] --> Crawler
[Professional Bodies] --> Crawler

Temporal <--> Workers
AdminUI --> Temporal
Temporal --> Crawler
Crawler --> Fetcher
Fetcher --> S3
Fetcher --> Extractor
Extractor --> Cleaner
Cleaner --> Metadata
Metadata --> PG
Cleaner --> Versioning
Versioning --> PG

PG --> Indexer
S3 --> Indexer
IndexER --> PG
IndexER --> ES
PG --> RAG
ES --> RAG
RAG --> API
@enduml
```

### Data Model (relational, MVP)

```sql
-- Jurisdictions & taxonomy
CREATE TABLE jurisdiction (
  id SERIAL PRIMARY KEY,
  code TEXT UNIQUE NOT NULL CHECK (code IN ('BIH','FBIH','RS','BD')),
  name TEXT NOT NULL
);
CREATE TABLE topic (
  id SERIAL PRIMARY KEY,
  code TEXT UNIQUE NOT NULL, -- VAT, CIT, PAYROLL, FR, BOOKKEEPING, DEADLINES
  name TEXT NOT NULL
);

-- Sources & documents
CREATE TABLE source (
  id SERIAL PRIMARY KEY,
  name TEXT NOT NULL,
  base_url TEXT NOT NULL,
  robots_cache JSONB,
  crawl_interval_hours INT DEFAULT 24,
  enabled BOOLEAN DEFAULT TRUE
);
CREATE TABLE document (
  id BIGSERIAL PRIMARY KEY,
  source_id INT REFERENCES source(id),
  url TEXT NOT NULL,
  content_hash TEXT NOT NULL,
  retrieved_at TIMESTAMPTZ NOT NULL,
  file_uri TEXT,               -- path in object storage
  mime_type TEXT,
  lang TEXT,                   -- bs/hr/sr/en
  doc_type TEXT,               -- law/bylaw/guidance/form/faq
  title TEXT,
  issuer TEXT,
  jurisdiction_id INT REFERENCES jurisdiction(id),
  effective_from DATE,
  effective_to DATE,
  is_active BOOLEAN GENERATED ALWAYS AS (effective_to IS NULL OR effective_to >= CURRENT_DATE) STORED
);

-- Clauses & chunks for retrieval
CREATE TABLE clause (
  id BIGSERIAL PRIMARY KEY,
  document_id BIGINT REFERENCES document(id) ON DELETE CASCADE,
  article_label TEXT,          -- e.g., "Član 23"
  clause_index INT,
  text TEXT NOT NULL
);
CREATE TABLE chunk (
  id BIGSERIAL PRIMARY KEY,
  clause_id BIGINT REFERENCES clause(id) ON DELETE CASCADE,
  chunk_index INT,
  text TEXT NOT NULL
);

-- Vector search (pgvector)
CREATE EXTENSION IF NOT EXISTS vector;
CREATE TABLE embedding (
  chunk_id BIGINT PRIMARY KEY REFERENCES chunk(id) ON DELETE CASCADE,
  model TEXT NOT NULL,
  vec vector(1024) NOT NULL
);
CREATE INDEX ON embedding USING ivfflat (vec vector_cosine_ops);

-- Topic & audience tags
CREATE TABLE document_topic (
  document_id BIGINT REFERENCES document(id) ON DELETE CASCADE,
  topic_id INT REFERENCES topic(id),
  PRIMARY KEY (document_id, topic_id)
);
CREATE TABLE audience_tag (
  document_id BIGINT REFERENCES document(id) ON DELETE CASCADE,
  tag TEXT CHECK (tag IN ('micro','small','medium','large')),
  PRIMARY KEY (document_id, tag)
);

-- Change tracking
CREATE TABLE change_event (
  id BIGSERIAL PRIMARY KEY,
  document_id BIGINT REFERENCES document(id) ON DELETE CASCADE,
  detected_at TIMESTAMPTZ NOT NULL,
  change_type TEXT,            -- new, updated, removed
  prev_content_hash TEXT,
  new_content_hash TEXT,
  summary TEXT
);
```

### Core Algorithms (concise)

1. **Polite Crawl** : per‑domain queue with tokens/sec cap; obey robots.txt; prefer sitemaps; cache ETags/Last‑Modified; skip unchanged.
2. **Parsing Pipeline** : Detect file type; extract text (PDF/DOCX/HTML); OCR if low text ratio; normalize whitespace, headings; split into **clauses** by article patterns (e.g., `Član|Čl.`) then **chunks** (by tokens ~700–1,000) with sentence boundaries preserved.
3. **Metadata Extraction** : Regex + lightweight NER to capture  **jurisdiction** ,  **article numbers** , **rates/thresholds** (VAT %, turnover thresholds), **effective dates** (look for “stupa na snagu”, “primjenjuje se od”). Human editor confirms in Admin UI.
4. **Versioning & Diff** : When a URL changes or a new consolidated text appears, align clauses by article label, run diff; if semantics change above threshold, create `change_event` and set previous `effective_to`.
5. **Hybrid Retrieval** : BM25 over `chunk.text` + vector search over `embedding.vec`. Merge via reciprocal rank fusion; re‑rank top 50 with a cross‑encoder; pass top 8 to LLM with **jurisdiction filter** at query time.
6. **Answer Guardrails** : Always return cited chunks (URLs, article labels). Refuse to answer beyond supported topics; suggest manual read if confidence < threshold.

### Technology Choices (MVP, pragmatic)

* **Crawler** : Python + Playwright (JavaScript rendering) supplemented by `requests` for static pages; orchestrated by **Temporal Workflows** (schedules, retries, backoff).
* **Parsing** : PyMuPDF / pdfminer.six; `python-docx`; `readability-lxml` for HTML; **Tesseract OCR** for scans.
* **Storage** : PostgreSQL 15 with  **pgvector** ; object storage (S3‑compatible or MinIO) for raw files.
* **Search** : Postgres full‑text (tsvector) for BM25‑like ranking + pgvector for embeddings. (Option to upgrade to OpenSearch later.)
* **Embeddings** : Multilingual model suitable for BCS (e.g., "bge-m3" or equivalent) stored as 1024‑d vectors.
* **Re‑ranker** : Cross‑encoder (e.g., "bge‑reranker‑v2‑m3" or equivalent open‑source) for precision.
* **Admin UI & API** : FastAPI backend; React/Next.js admin.

### Seed Source Types (examples; configure per‑domain)

* Official gazettes and consolidated laws.
* Tax administration portals (state/entity/district).
* Ministries of Finance announcements.
* Professional chambers/guilds and IFRS local translations.
* Public FAQ pages and forms download centers.

## Implementation

### High‑impact tweaks applied

* **Chunking** : 700 tokens with ~10% overlap to reduce false negatives and “partial article” misses.
* **Anchors in citations** : store and return `article_label`, `page_number`, and `heading_path`.
* **Temporal filters** : enforce `(effective_to IS NULL OR effective_to >= CURRENT_DATE)` during retrieval.
* **Reflection checklist** : ensure jurisdiction match, date validity, and prefer consolidated laws over base when both are available.
* **Sparse baseline** : keep **BM25 (tsvector)** as default with **optional SPLADE** fusion path (feature flag).
* **Embeddings fallback** : add optional **bge-m3** path for offline/dev runs.
* **Clause-level versioning** : track `effective_from/to` per clause.
* **Structured rules** : add tiny `rule` table for VAT/CIT thresholds and deadlines.
* **PDF fidelity** : persist `page_number`, OCR confidence, and image hash per chunk.
* **Agent loop limits** : 1 refine pass, +6s extra latency, log refinements.
* **Evaluator set** : curate 50–100 labeled Q/A across VAT/CIT/Payroll/Deadlines before M4.
* **Compliance** : per‑source `redistributable` flag; avoid bulk storing restricted datasets.

### Schema deltas (apply on top of existing)

```sql
-- 1) Anchors & fidelity on chunk
ALTER TABLE chunk ADD COLUMN IF NOT EXISTS page_number INT;
ALTER TABLE chunk ADD COLUMN IF NOT EXISTS heading_path TEXT;     -- e.g. "Glava II > Član 23"
ALTER TABLE chunk ADD COLUMN IF NOT EXISTS ocr_confidence REAL;   -- 0..1, NULL if not OCR
ALTER TABLE chunk ADD COLUMN IF NOT EXISTS image_hash TEXT;       -- for scanned PDFs

-- 2) Clause-level versioning
ALTER TABLE clause ADD COLUMN IF NOT EXISTS effective_from DATE;
ALTER TABLE clause ADD COLUMN IF NOT EXISTS effective_to DATE;

-- 3) Consolidation preference
ALTER TABLE document ADD COLUMN IF NOT EXISTS is_consolidated BOOLEAN DEFAULT FALSE;
CREATE INDEX IF NOT EXISTS idx_doc_consolidated ON document(is_consolidated);

-- 4) Rules table (structured facts)
CREATE TABLE IF NOT EXISTS rule (
  id BIGSERIAL PRIMARY KEY,
  rule_type TEXT CHECK (rule_type IN ('VAT_THRESHOLD','VAT_RATE','CIT_RATE','PAYROLL_RATE','DEADLINE')),
  jurisdiction TEXT CHECK (jurisdiction IN ('BIH','FBIH','RS','BD')),
  value NUMERIC(18,4),
  currency TEXT,
  valid_from DATE,
  valid_to DATE,
  source_doc_id BIGINT REFERENCES document(id) ON DELETE SET NULL,
  article_label TEXT,
  notes TEXT
);
CREATE INDEX IF NOT EXISTS idx_rule_lookup ON rule(rule_type, jurisdiction, valid_from, valid_to);

-- 5) Sources compliance
ALTER TABLE source ADD COLUMN IF NOT EXISTS redistributable BOOLEAN DEFAULT TRUE;
```

### Retrieval query changes (joins + temporal filter)

```sql
-- Dense ranking with temporal guard and consolidation preference
WITH vecq AS (SELECT :qvec::vector AS v)
SELECT c.id, row_number() OVER (ORDER BY e.vec <=> (SELECT v FROM vecq)) AS r
FROM embedding e
JOIN chunk c ON c.id = e.chunk_id
JOIN clause cl ON cl.id = c.clause_id
JOIN document d ON d.id = cl.document_id
WHERE e.model = 'bge-m3'
  AND (coalesce(cl.effective_to, d.effective_to) IS NULL OR coalesce(cl.effective_to, d.effective_to) >= CURRENT_DATE)
ORDER BY r
LIMIT 1000;

-- After fusion, when tie-breaking, sort consolidated first
ORDER BY rrf.score DESC, d.is_consolidated DESC
```

### Local‑first MVP (no cloud costs)

Run everything on a single dev machine with Docker. This validates crawling, ingestion, hybrid search, and Q&A before paying for infra.

### Local‑first MVP (no cloud costs)

Run everything on a single dev machine with Docker. This validates crawling, ingestion, hybrid search, and Q&A before paying for infra.

#### Services (docker‑compose)

* **Temporal Server** + Web UI
* **PostgreSQL** (Temporal persistence + app metadata + pgvector)
* **MinIO** (S3‑compatible object storage)
* **FastAPI** (backend API)
* **Worker** (Temporal workers) — separate container for scale‑out
* **Next.js 14** (admin + search UI)

**compose snippet (pgvector, high‑level)**

```yaml
version: "3.9"
services:
  postgres:
    image: postgres:15
    environment:
      POSTGRES_PASSWORD: devpass
    ports: ["5432:5432"]
    volumes: ["pgdata:/var/lib/postgresql/data"]

  temporal:
    image: temporalio/auto:1.23
    environment:
      - DB=postgresql
      - DB_PORT=5432
      - POSTGRES_USER=postgres
      - POSTGRES_PWD=devpass
      - POSTGRES_SEEDS=postgres
    depends_on: [postgres]
    ports: ["7233:7233", "8233:8233"] # 8233 web

  minio:
    image: minio/minio
    command: server /data --console-address :9001
    environment:
      MINIO_ROOT_USER: minio
      MINIO_ROOT_PASSWORD: minio123
    ports: ["9000:9000", "9001:9001"]
    volumes: ["minio_data:/data"]

  opensearch:
    image: opensearchproject/opensearch:2.11.0
    environment:
      - discovery.type=single-node
      - OPENSEARCH_SECURITY_ENABLED=false
      - bootstrap.memory_lock=true
      - "OPENSEARCH_JAVA_OPTS=-Xms1g -Xmx1g"
    ulimits:
      memlock:
        soft: -1
        hard: -1
    ports: ["9200:9200", "9600:9600"]
    volumes: ["os_data:/usr/share/opensearch/data"]

  api:
    build: ./api
    environment:
      - S3_ENDPOINT=http://minio:9000
      - S3_ACCESS_KEY=minio
      - S3_SECRET_KEY=minio123
      - DATABASE_URL=postgresql://postgres:devpass@postgres:5432/postgres
      - TEMPORAL_TARGET=temporal:7233
      - EMBED_PROVIDER=local
      - EMBED_MODEL_NAME=BAAI/bge-m3
      - GEMINI_API_KEY=${GEMINI_API_KEY}
      - GEMINI_EMBED_MODEL=text-embedding-004  # Gemini Flash Lite embedding
      - ELASTICSEARCH_URL=http://opensearch:9200
    depends_on: [temporal, minio, postgres, opensearch]
    ports: ["8000:8000"]

  worker:
    build: ./api
    command: ["python","-m","workers.run"]
    environment:
      - DATABASE_URL=postgresql://postgres:devpass@postgres:5432/postgres
      - TEMPORAL_TARGET=temporal:7233
      - S3_ENDPOINT=http://minio:9000
      - S3_ACCESS_KEY=minio
      - S3_SECRET_KEY=minio123
      - EMBED_PROVIDER=local
      - EMBED_MODEL_NAME=BAAI/bge-m3
      - GEMINI_API_KEY=${GEMINI_API_KEY}
      - GEMINI_EMBED_MODEL=text-embedding-004
      - ELASTICSEARCH_URL=http://opensearch:9200
    depends_on: [temporal, postgres, minio, opensearch]

  web:
    build: ./web
    environment:
      - NEXT_PUBLIC_API_BASE=http://localhost:8000
    depends_on: [api]
    ports: ["3000:3000"]

volumes:
  pgdata:
  minio_data:
  os_data:
```

#### Initialization

1. `docker compose up -d`.
2. In API startup, run: `CREATE EXTENSION IF NOT EXISTS vector;` and create tables/indexes from the **Data Model** and  **Postgres retrieval schema** .
3. Create MinIO bucket `raw-docs` and bootstrap the Elasticsearch index (e.g., `chunks`) with the analyzer/mapping you need for BCS text.
4. In web UI or via API, run `POST /ingest/upload` with a pilot PDF.
5. Try `GET /search?q=PDV prag za registraciju`.

# Tutor Plan (hands‑on steps)

1. **Clone & boot** : add these files, set `EMBED_PROVIDER`/`EMBED_MODEL_NAME`, `ELASTICSEARCH_URL` (if running remote), and `GEMINI_API_KEY` if you want hosted embeddings; then `docker compose up -d`.
2. **Seed data** : we’ll ingest one PDF next session and populate `document/clause/chunk/embedding` with a tiny script.
3. **Test** : hit `http://localhost:8000/search?q=PDV%20prag%20registracije&j=FBIH`.
4. **Add SPLADE fusion** : we’ll store SPLADE tokens per chunk in a small `sparse_index` table or compute on‑the‑fly and mix into BM25 (kept optional behind a flag).

Next, I’ll generate the **ingest script** and **SPLADE+BM25 fusion** code when you’re ready.
