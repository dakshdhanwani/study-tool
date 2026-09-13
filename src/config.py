"""
Configuration module for the Study Workspace.
Loads settings from environment variables / .env file, with optional
fallback from Streamlit secrets.toml.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from project root
load_dotenv(Path(__file__).parent.parent / ".env")

# ── Paths ──────────────────────────────────────────────────────────────────────
PROJECT_ROOT    = Path(__file__).parent.parent
CORPUS_DIR      = PROJECT_ROOT / "corpus"
DATA_DIR        = PROJECT_ROOT / "data"
UPLOADS_DIR     = DATA_DIR / "uploads"       # where UI-uploaded files are saved
CHROMA_DIR      = DATA_DIR / os.getenv("CHROMA_PATH", "chroma")
SQLITE_PATH     = DATA_DIR / os.getenv("SQLITE_PATH", "study_workspace.db")
PAGE_IMAGES_DIR = DATA_DIR / "page_images"

# Create required directories on import (uploads, chroma, page_images only)
for d in [DATA_DIR, UPLOADS_DIR, CHROMA_DIR, PAGE_IMAGES_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# ── LLM Settings ───────────────────────────────────────────────────────────────
def _get_api_key() -> str:
    """Read Gemini API key from: env var → .env → streamlit secrets (at runtime)."""
    key = os.getenv("GEMINI_API_KEY", "")
    if not key:
        # Try Streamlit secrets if running inside Streamlit
        try:
            import streamlit as st
            key = st.secrets.get("GEMINI_API_KEY", "")
        except Exception:
            pass
    return key

GEMINI_API_KEY       = _get_api_key()
GEMINI_MODEL         = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
GEMINI_VISION_MODEL  = os.getenv("GEMINI_VISION_MODEL", "gemini-2.5-flash")

# ── Embedding Settings ─────────────────────────────────────────────────────────
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")

# ── Retrieval Settings ─────────────────────────────────────────────────────────
RETRIEVAL_TOP_K    = 20   # candidates before reranking
RERANK_TOP_K       = 6    # chunks fed to LLM
HYBRID_ALPHA       = 0.6  # weight for semantic (1-alpha = BM25)

# ── Chunking Settings ──────────────────────────────────────────────────────────
CHUNK_SIZE    = 500   # measured in characters
CHUNK_OVERLAP = 80    # measured in characters

# ── OCR / Confidence Settings ──────────────────────────────────────────────────
LOW_CONFIDENCE_THRESHOLD = 0.70  # (0.0 to 1.0) chunks below this trigger warning

# ── Conversation Settings ──────────────────────────────────────────────────────
MAX_HISTORY_TURNS = 10   # rolling window for conversation memory

# ── ChromaDB Collection ────────────────────────────────────────────────────────
CHROMA_COLLECTION = "study_chunks"

# ── Evaluation ─────────────────────────────────────────────────────────────────
EVAL_QUESTIONS_PATH = PROJECT_ROOT / "evaluation" / "questions.json"
EVAL_RESULTS_DIR    = PROJECT_ROOT / "evaluation" / "results"
EVAL_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
