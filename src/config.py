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

# ── Paths (local — only used during ingestion as temp workspace) ───────────────
PROJECT_ROOT    = Path(__file__).parent.parent
DATA_DIR        = PROJECT_ROOT / "data"
# Temp dir for page images extracted during PDF processing (not committed to git)
PAGE_IMAGES_DIR = DATA_DIR / "page_images"

for d in [DATA_DIR, PAGE_IMAGES_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# ── Supabase (cloud storage + database + vectors) ──────────────────────────────
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")   # service_role key (server-side only)
SUPABASE_BUCKET = os.getenv("SUPABASE_BUCKET", "documents")

# ── LLM Settings ───────────────────────────────────────────────────────────────
def _get_api_key() -> str:
    """Read Gemini API key from: env var → .env → streamlit secrets (at runtime)."""
    key = os.getenv("GEMINI_API_KEY", "")
    if not key:
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
EMBEDDING_DIM   = 384   # dimension of all-MiniLM-L6-v2 output

# ── Retrieval Settings ─────────────────────────────────────────────────────────
RETRIEVAL_TOP_K    = 20   # candidates before reranking
RERANK_TOP_K       = 6    # chunks fed to LLM
HYBRID_ALPHA       = 0.6  # weight for semantic (1-alpha = BM25)

# ── Chunking Settings ──────────────────────────────────────────────────────────
CHUNK_SIZE    = 500   # measured in characters
CHUNK_OVERLAP = 80    # measured in characters

# ── OCR / Confidence Settings ──────────────────────────────────────────────────
LOW_CONFIDENCE_THRESHOLD = 0.70

# ── Conversation Settings ──────────────────────────────────────────────────────
MAX_HISTORY_TURNS = 10   # rolling window for conversation memory

# ── Supabase table names ────────────────────────────────────────────────────────
TABLE_DOCUMENTS     = "documents"
TABLE_CHUNKS        = "chunks"
TABLE_CONVERSATIONS = "conversations"
TABLE_SESSIONS      = "sessions"
