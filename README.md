# Course Companion

A **citation-first AI study workspace** built on Streamlit + Supabase + Gemini. Upload your course materials — PDFs, slides, notes, handwritten scans — and get grounded answers with exact `[source:page]` citations. Every claim is traceable. Nothing is hallucinated.

---

## What it does

- **Ask questions → get cited answers** — Gemini answers only from *your* uploaded documents; every claim is tagged `[filename:page]`
- **Hybrid RAG pipeline** — semantic (pgvector) + keyword (BM25) search combined via Reciprocal Rank Fusion, then reranked by a cross-encoder
- **Handwritten note OCR** — Gemini Vision reads your messy handwritten scans
- **Refusal instead of hallucination** — if the answer isn't in your materials, the app says so explicitly
- **Conversation memory** — multi-turn study threads with full history persisted in Supabase
- **Revision cards** — save key concepts from answers to a personal concept board
- **Pinned answers** — pin any answer for quick revision access

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Streamlit |
| LLM | Gemini 2.5 Flash (answers + OCR) |
| Vector store | Supabase pgvector |
| Database | Supabase PostgreSQL |
| File storage | Supabase Storage |
| Embeddings | `all-MiniLM-L6-v2` (sentence-transformers) |
| Keyword search | BM25 (rank-bm25) |
| Reranker | `ms-marco-MiniLM-L-6-v2` (cross-encoder) |
| PDF parsing | PyMuPDF |

---

## Prerequisites

- Python 3.10+
- A [Supabase](https://supabase.com) project (free tier works)
- A [Gemini API key](https://aistudio.google.com/app/apikey) (free tier works)

---

## 🚀 Quick Start (Local Mode - Zero Setup)

Want to run the app right now without setting up a database? The app has a built-in **Local Mode** that uses SQLite and ChromaDB entirely on your local machine.

```bash
git clone <repo-url>
cd study-tool
pip install -r requirements.txt
cp .env.example .env
```

Edit `.env` and add **only** your `GEMINI_API_KEY`. Leave the Supabase variables empty.

```bash
streamlit run src/app/main.py
```
*That's it.* The app will detect the missing Supabase URL and automatically run using local disk storage!

---

## ☁️ Production Setup (Supabase)

When you're ready to deploy or want cloud-persistent data across devices, you can switch to the Supabase backend.

### 1. Create your Supabase project

1. Go to [supabase.com](https://supabase.com) → New project
2. Enable the **pgvector** extension:
   ```sql
   create extension if not exists vector;
   ```
3. Run the schema below in the Supabase SQL editor

### 3. Supabase schema

```sql
-- Conversation turns
create table conversations (
  id          text primary key,
  user_id     text not null,
  session_id  text not null,
  role        text not null,
  content     text not null,
  citations   jsonb default '[]',
  timestamp   timestamptz default now(),
  is_pinned   boolean default false
);

-- Study sessions
create table sessions (
  session_id     text primary key,
  user_id        text not null,
  name           text,
  created_at     timestamptz default now(),
  topics         jsonb default '[]',
  docs_discussed jsonb default '[]'
);

-- Document registry
create table documents (
  id           bigserial primary key,
  user_id      text not null,
  source_file  text not null,
  format       text,
  page_count   int,
  chunk_count  int,
  storage_path text,
  created_at   timestamptz default now()
);

-- Vector chunks
create table chunks (
  id             bigserial primary key,
  user_id        text not null,
  source_file    text not null,
  page_number    int,
  chunk_index    int,
  text           text,
  embedding      vector(384),
  ocr_confidence float,
  format         text,
  page_image_path text,
  metadata       jsonb default '{}'
);

-- Similarity search function
create or replace function match_chunks(
  query_embedding vector(384),
  match_user_id   text,
  match_count     int default 20
)
returns table (
  id              bigint,
  source_file     text,
  page_number     int,
  text            text,
  ocr_confidence  float,
  format          text,
  page_image_path text,
  metadata        jsonb,
  similarity      float
)
language sql stable as $$
  select
    id, source_file, page_number, text,
    ocr_confidence, format, page_image_path, metadata,
    1 - (embedding <=> query_embedding) as similarity
  from chunks
  where user_id = match_user_id
  order by embedding <=> query_embedding
  limit match_count;
$$;
```

4. Create a **Storage bucket** named `documents` (or whatever you set in `.env`)

### 4. Configure environment

```bash
cp .env.example .env
```

Edit `.env`:
```env
GEMINI_API_KEY=AIza...
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-service-role-key
SUPABASE_BUCKET=documents
```

> **Important:** Use the **service role** key from Supabase → Settings → API (not the anon key).

### 5. Run the app

```bash
streamlit run src/app/main.py
```

Open [http://localhost:8501](http://localhost:8501)

---

## First use

1. **Set your Gemini API key** in the sidebar (or in `.env` before launching)
2. Go to **📄 Materials** → Upload your files (PDF, MD, TXT, PNG/JPG)
3. Click **Index uploaded files** — this runs OCR, chunking, embedding, and uploads to Supabase
4. Go to **💬 Ask** → type your question
5. Every answer comes with `[filename:page]` citation chips

---

## Supported file types

| Format | Extension | Parser |
|--------|-----------|--------|
| PDF lectures / slides | `.pdf` | PyMuPDF text extraction |
| Markdown notes | `.md` | Direct text load |
| Plain text | `.txt` | Direct text load |
| Handwritten scans | `.png` `.jpg` `.jpeg` | Gemini Vision OCR |

---

## Pages

| Page | What it does |
|------|-------------|
| 💬 **Ask** | Type a question → grounded answer with citation chips, evidence panel, grounding score |
| 📄 **Materials** | Upload, index, and delete documents. Shows page/chunk counts per document |
| 💭 **Study Thread** | Full multi-turn conversation history. Pin answers, switch sessions, follow-up questions |
| 🔖 **Saved** | All pinned answers in one place for quick revision |
| 📋 **Revision** | Personal concept card board — save key definitions from any answer |

---

## RAG Pipeline

```
Your Question
      │
      ▼
Query Expander        ← resolves "it", "that algorithm" from conversation history
      │
      ▼
Hybrid Search
  ├── Semantic        ← Supabase pgvector + all-MiniLM-L6-v2 embeddings
  └── Sparse (BM25)  ← keyword matching via rank-bm25
      │
      ▼  Reciprocal Rank Fusion
Cross-encoder Reranker  ← ms-marco-MiniLM-L-6-v2, top 6 chunks
      │
      ▼
Gemini 2.5 Flash      ← "Answer ONLY from context. Cite every claim as [file:page]."
      │
      ▼
Citation Parser       ← extracts [source:page] refs from generated text
Grounding Checker     ← scores each citation against retrieved chunks
      │
      ▼
Streamlit UI          ← answer + chips + evidence cards + grounding status
```

---

## Project structure

```
study-tool/
├── .env.example
├── requirements.txt
├── src/
│   ├── config.py                    ← env vars, paths, model settings
│   ├── app/
│   │   ├── main.py                  ← streamlit run src/app/main.py
│   │   ├── sidebar.py               ← nav, corpus status, recent threads
│   │   └── page_ask.py              ← all page renderers + RAG pipeline caller
│   ├── ingestion/
│   │   ├── pdf_parser.py            ← PyMuPDF text + page image extraction
│   │   ├── text_loader.py           ← markdown / plain text loader
│   │   ├── ocr_pipeline.py          ← Gemini Vision OCR for handwritten images
│   │   ├── chunker.py               ← text → overlapping chunks
│   │   └── indexer.py               ← orchestrates ingestion + Supabase upload
│   ├── retrieval/
│   │   ├── embeddings.py            ← all-MiniLM-L6-v2 sentence embeddings
│   │   ├── hybrid_search.py         ← RRF fusion of semantic + BM25
│   │   └── reranker.py              ← cross-encoder reranking
│   ├── generation/
│   │   ├── prompts.py               ← system prompt (citation + refusal instructions)
│   │   ├── generator.py             ← Gemini API call → GenerationResult
│   │   ├── citation_parser.py       ← regex extraction of [file:page] refs
│   │   └── grounding_check.py       ← validates citations against chunks
│   ├── conversation/
│   │   ├── session.py               ← SessionManager: concept cards, comparison queue
│   │   └── query_expander.py        ← coreference resolution for follow-up queries
│   └── storage/
│       ├── supabase_client.py       ← Supabase client singleton
│       ├── memory_supa.py           ← SupabaseConversationMemory
│       ├── vector_store_supa.py     ← pgvector CRUD + similarity search
│       ├── registry_supa.py         ← document registry (Supabase PostgreSQL)
│       └── file_store.py            ← Supabase Storage upload/download/delete
└── tests/
```

---

## Key design decisions

| Decision | Rationale |
|----------|-----------|
| **Refusal over hallucination** | LLM is instructed to output `NOT_IN_MATERIALS` when evidence is insufficient — the app shows a clear refusal card, never a fabricated answer |
| **Inline citations** | Each claim is cited `[doc:page]` immediately — not a footer list — so you can trace exactly which sentence maps to which page |
| **Gemini Vision OCR** | No Tesseract dependency; the same LLM that answers questions also reads handwritten scans |
| **Supabase for everything** | pgvector (vectors) + PostgreSQL (memory, registry) + Storage (files) in one platform — zero local state between sessions |
| **BM25 + semantic fusion** | Keyword search catches exact term matches (algorithm names, formula notation); semantic search catches paraphrased concepts |
| **User-scoped data** | Every Supabase query is filtered by `user_id` UUID — multiple users can run on the same Supabase project without data leakage |

---

## Environment variables reference

| Variable | Required | Description |
|----------|----------|-------------|
| `GEMINI_API_KEY` | ✅ | Gemini API key from Google AI Studio |
| `SUPABASE_URL` | ✅ | Your Supabase project URL |
| `SUPABASE_KEY` | ✅ | Service role key (not anon key) |
| `SUPABASE_BUCKET` | ✅ | Storage bucket name (default: `documents`) |
| `GEMINI_MODEL` | optional | Model name (default: `gemini-2.5-flash`) |
| `EMBEDDING_MODEL` | optional | Embedding model (default: `all-MiniLM-L6-v2`) |

---

## Troubleshooting

**`No module named 'google'`**
```bash
pip install google-generativeai
```

**`No module named 'fitz'`**
```bash
pip install PyMuPDF
```

**Supabase connection error**
- Make sure you're using the **service role key**, not the anon key
- Check that `pgvector` extension is enabled in your Supabase project
- Verify the `match_chunks` function was created successfully

**OCR returns empty / garbled text**
- Verify `GEMINI_API_KEY` is set and valid
- Image must be readable (not corrupted) — try opening it locally first
- Gemini Vision requires at least a Gemini API free-tier key

**BM25 index not building**
- This is rebuilt in-session from Supabase chunk texts on first query
- If it fails, check Supabase connectivity and that the `chunks` table has rows
