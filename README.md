# Study Workspace — Complete Setup & Usage Guide

## 🚀 Quick Start

### 1. Install dependencies
```bash
cd "study-tool"
pip install -r requirements.txt
```

### 2. Set your Gemini API key
```bash
copy .env.example .env
# Edit .env and add your GEMINI_API_KEY
```
Or set it in the Streamlit sidebar when the app launches.

### 3. Generate the synthetic corpus
```bash
python corpus/generate_corpus.py
```
This creates:
- `corpus/lectures/` — 3 PDF lecture documents (Arrays, Trees, Sorting)
- `corpus/slides/` — 2 PDF slide decks
- `corpus/notes/study_notes.md` — comprehensive markdown notes
- `corpus/handwritten/handwritten_clean.png` — legible handwritten notes
- `corpus/handwritten/handwritten_hard.png` — difficult/messy scan simulation

### 4. Launch the app
```bash
streamlit run src/app/main.py
```

### 5. Ingest the corpus (first time)
In the app → **📁 Materials** tab → click **🚀 Run Ingestion**

---

## 📐 Architecture

```
User Query
    │
    ▼
Query Expander          ← resolves "it", "that algorithm" from conversation history
    │
    ▼
Hybrid Search
  ├── Semantic (ChromaDB + sentence-transformers)
  └── Sparse (BM25/rank_bm25)
    │
    ▼  Reciprocal Rank Fusion
Cross-encoder Reranker  ← ms-marco-MiniLM-L-6-v2
    │
    ▼
Context Assembly        ← chunks with source/page/OCR metadata
    │
    ▼
Gemini 1.5 Pro          ← System prompt: answer ONLY from context, cite every claim
    │
    ▼
Citation Parser         ← extracts [source:page] refs
Grounding Checker       ← validates each citation against retrieved chunks
    │
    ▼
Streamlit UI
  ├── Ask tab           ← grounded answer + citation badges + evidence cards
  ├── Study Thread      ← persistent conversation + pinning + comparison
  ├── Review            ← concept cards + quiz mode + syllabus coverage
  └── Evaluation        ← 30-question benchmark + accuracy/citation/refusal metrics
```

---

## 📂 Project Structure

```
study-tool/
├── requirements.txt
├── .env.example           ← copy to .env and add GEMINI_API_KEY
├── corpus/
│   ├── generate_corpus.py ← generates synthetic course materials
│   ├── lectures/          ← PDF lecture notes
│   ├── slides/            ← PDF slide decks
│   ├── notes/             ← Markdown notes
│   └── handwritten/       ← handwritten note images
├── evaluation/
│   ├── questions.json     ← 30-question test set (auto-generated)
│   ├── eval_runner.py     ← CLI evaluation runner
│   └── results/           ← saved evaluation reports
├── src/
│   ├── config.py
│   ├── ingestion/
│   │   ├── pdf_parser.py
│   │   ├── text_loader.py
│   │   ├── ocr_pipeline.py   ← Gemini Vision OCR
│   │   ├── chunker.py
│   │   └── indexer.py        ← run this to ingest corpus
│   ├── retrieval/
│   │   ├── embeddings.py
│   │   ├── vector_store.py   ← ChromaDB
│   │   ├── bm25_index.py
│   │   ├── hybrid_search.py  ← RRF fusion
│   │   └── reranker.py       ← cross-encoder
│   ├── generation/
│   │   ├── prompts.py        ← system prompt with citation + refusal instructions
│   │   ├── generator.py      ← Gemini API call
│   │   ├── citation_parser.py
│   │   └── grounding_check.py
│   ├── conversation/
│   │   ├── memory.py         ← SQLite conversation history
│   │   ├── session.py        ← session state + concept cards
│   │   └── query_expander.py ← coreference resolution
│   └── app/
│       ├── main.py           ← streamlit run src/app/main.py
│       ├── ui_ask.py
│       ├── ui_thread.py
│       ├── ui_review.py
│       ├── ui_materials.py
│       └── ui_evaluation.py
└── tests/
```

---

## 🔑 Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| **Pages as first-class objects** | Every chunk carries `(source_file, page_number, page_image_path)` — citations always point to a viewable page |
| **Gemini Vision for OCR** | No Tesseract required; vision LLM handles even difficult handwriting |
| **Inline citations on claims** | LLM prompted to cite `[doc:page]` immediately after each claim, not in a footer |
| **NOT_IN_MATERIALS refusal** | Prominent, structured refusal state — the system explicitly says what it searched |
| **RRF hybrid retrieval** | Combines semantic (conceptual) + BM25 (keyword) retrieval for better coverage |
| **SQLite persistence** | All sessions, pinned evidence, and evaluation results survive restarts |
| **Conversation context** | Query expander resolves "it", "this", "that algorithm" from conversation history |

---

## 📊 Evaluation

The 30-question test set covers:
- **10 single-doc** questions (one source page per answer)
- **10 multi-doc** questions (cross-document synthesis required)
- **10 unanswerable** questions (in-scope topics not covered in corpus)

### CLI evaluation
```bash
python evaluation/eval_runner.py --report
python evaluation/eval_runner.py --subset unanswerable --report
```

### Metrics reported
- Single-doc answer accuracy (X/10)
- Multi-doc answer accuracy (X/10)
- Refusal rate on unanswerable (X/10)
- Citation precision (% of cited pages that are correct)

---

## 📋 Adding Your Own Materials

1. Drop your files into `corpus/lectures/`, `corpus/slides/`, `corpus/notes/`, or `corpus/handwritten/`
2. In the app → **📁 Materials** tab → click **Run Ingestion**
3. The system automatically detects file types and routes to the correct parser

Supported formats:
- `.pdf` (text-based — lectures, slides)
- `.md`, `.txt` (markdown, plain text)
- `.png`, `.jpg`, `.jpeg` (handwritten scans → Gemini Vision OCR)

---

## ⚠️ Troubleshooting

**"No module named 'google'"**
```bash
pip install google-generativeai
```

**"No module named 'fitz'"**
```bash
pip install PyMuPDF
```

**ChromaDB SQLite error on Python 3.10+**
```bash
pip install pysqlite3-binary
```
Then add to `src/config.py`:
```python
__import__('pysqlite3')
import sys
sys.modules['sqlite3'] = sys.modules.pop('pysqlite3')
```

**OCR returns empty text**
- Verify `GEMINI_API_KEY` is set in `.env`
- Check image file is readable (not corrupted)
- Vision model requires a valid Gemini Pro key
