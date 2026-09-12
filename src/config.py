"""
Configuration module for the Study Workspace.
Loads settings from environment variables / .env file.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from project root
load_dotenv(Path(__file__).parent.parent / ".env")

# ── Paths ──────────────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).parent.parent
CORPUS_DIR   = PROJECT_ROOT / "corpus"
DATA_DIR     = PROJECT_ROOT / "data"
CHROMA_DIR   = DATA_DIR / os.getenv("CHROMA_PATH", "chroma")
SQLITE_PATH  = DATA_DIR / os.getenv("SQLITE_PATH", "study_workspace.db")
PAGE_IMAGES_DIR = DATA_DIR / "page_images"

# Create data directories on import
for d in [DATA_DIR, CHROMA_DIR, PAGE_IMAGES_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# ── LLM Settings ───────────────────────────────────────────────────────────────
GEMINI_API_KEY       = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL         = os.getenv("GEMINI_MODEL", "gemini-1.5-pro")
GEMINI_VISION_MODEL  = os.getenv("GEMINI_VISION_MODEL", "gemini-1.5-pro")

# ── Embedding Settings ─────────────────────────────────────────────────────────
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")

# ── Retrieval Settings ─────────────────────────────────────────────────────────
RETRIEVAL_TOP_K    = 20   # candidates before reranking
RERANK_TOP_K       = 6    # chunks fed to LLM
HYBRID_ALPHA       = 0.6  # weight for semantic (1-alpha = BM25)

# ── Chunking Settings ──────────────────────────────────────────────────────────
CHUNK_SIZE    = 500   # tokens (approximate, measured in chars ÷ 4)
CHUNK_OVERLAP = 80

# ── OCR Settings ───────────────────────────────────────────────────────────────
OCR_CONFIDENCE_THRESHOLD = 60  # below this → send to vision LLM

# ── Conversation Settings ──────────────────────────────────────────────────────
MAX_HISTORY_TURNS = 10   # rolling window for conversation memory

# ── ChromaDB Collection ────────────────────────────────────────────────────────
CHROMA_COLLECTION = "study_chunks"

# ── Evaluation ─────────────────────────────────────────────────────────────────
EVAL_QUESTIONS_PATH = PROJECT_ROOT / "evaluation" / "questions.json"
EVAL_RESULTS_DIR    = PROJECT_ROOT / "evaluation" / "results"
EVAL_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
