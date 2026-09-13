"""
Ingestion pipeline orchestrator — scans the corpus and builds all indexes.

Usage:
    python -m src.ingestion.indexer              # ingest corpus
    python -m src.ingestion.indexer --force      # force re-ingest all files
"""
from __future__ import annotations

import pickle
import sqlite3
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

try:
    from tqdm import tqdm
except ImportError:
    def tqdm(iterable, **kwargs):  # type: ignore
        return iterable

from src.ingestion.pdf_parser import extract_pdf_pages, extract_slide_pages
from src.ingestion.text_loader import load_markdown_file, load_text_file
from src.ingestion.ocr_pipeline import process_handwritten_image
from src.ingestion.chunker import chunk_all
from src.config import PAGE_IMAGES_DIR

BM25_PICKLE_PATH: Path = Path(__file__).parent.parent.parent / "data" / "bm25_index.pkl"

# Local fallbacks (used only for CLI / legacy local ingestion — NOT the cloud path)
_LOCAL_SQLITE_PATH = Path(__file__).parent.parent.parent / "data" / "study_workspace.db"
_LOCAL_CORPUS_DIR  = Path(__file__).parent.parent.parent / "corpus"


# ── Document Registry (legacy local — kept for CLI use) ───────────────────────

class DocumentRegistry:
    """SQLite-backed registry tracking which files have been ingested (local/legacy)."""

    def __init__(self, db_path: Path = _LOCAL_SQLITE_PATH) -> None:
        db_path = Path(db_path)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL;")
        self._create_schema()

    def _create_schema(self) -> None:
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS documents (
                source_file  TEXT PRIMARY KEY,
                format       TEXT NOT NULL,
                page_count   INTEGER NOT NULL DEFAULT 0,
                chunk_count  INTEGER NOT NULL DEFAULT 0,
                ingested_at  TEXT NOT NULL,
                file_path    TEXT NOT NULL
            );
        """)
        self._conn.commit()

    def register(self, source_file: str, format: str, page_count: int,
                 chunk_count: int, file_path: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        self._conn.execute("""
            INSERT INTO documents (source_file, format, page_count, chunk_count, ingested_at, file_path)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(source_file) DO UPDATE SET
                format=excluded.format, page_count=excluded.page_count,
                chunk_count=excluded.chunk_count, ingested_at=excluded.ingested_at,
                file_path=excluded.file_path
        """, (source_file, format, page_count, chunk_count, now, file_path))
        self._conn.commit()

    def is_ingested(self, source_file: str) -> bool:
        row = self._conn.execute(
            "SELECT 1 FROM documents WHERE source_file = ?", (source_file,)
        ).fetchone()
        return row is not None

    def list_documents(self) -> list[dict]:
        rows = self._conn.execute(
            "SELECT source_file, format, page_count, chunk_count, ingested_at, file_path "
            "FROM documents ORDER BY ingested_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]

    def get_document(self, source_file: str) -> Optional[dict]:
        row = self._conn.execute(
            "SELECT source_file, format, page_count, chunk_count, ingested_at, file_path "
            "FROM documents WHERE source_file = ?", (source_file,)
        ).fetchone()
        return dict(row) if row else None


# ── Ingestion pipeline ────────────────────────────────────────────────────────

def ingest_corpus(corpus_dir: Path = _LOCAL_CORPUS_DIR, force_reingest: bool = False) -> dict:
    """Ingest all documents in *corpus_dir* into vector + BM25 + document registry.

    Parameters
    ----------
    corpus_dir:     Root corpus directory with lectures/, slides/, notes/, handwritten/ subdirs.
    force_reingest: If True, re-ingest even already-registered files.

    Returns
    -------
    dict
        {'total_documents', 'total_chunks', 'formats_found', 'errors'}
    """
    corpus_dir = Path(corpus_dir)
    registry = DocumentRegistry()
    vector_store = VectorStore()
    bm25_chunks_data: list[dict] = []

    # Load existing BM25 index if available (to preserve already-indexed chunks)
    bm25_index = BM25Index()
    if BM25_PICKLE_PATH.exists() and not force_reingest:
        try:
            bm25_index.load(BM25_PICKLE_PATH)
        except Exception:
            bm25_index = BM25Index()

    total_documents = 0
    total_chunks = 0
    formats_found: set[str] = set()
    errors: list[str] = []

    # Collect tasks: (file_path, category)
    tasks: list[tuple[Path, str]] = []

    for subdir, category in [("lectures", "lecture"), ("slides", "slide")]:
        d = corpus_dir / subdir
        if d.exists():
            for pdf in sorted(d.glob("*.pdf")):
                tasks.append((pdf, category))
            # Also handle text fallbacks if PDFs weren't generated
            for txt in sorted(d.glob("*.txt")):
                tasks.append((txt, "note"))

    notes_dir = corpus_dir / "notes"
    if notes_dir.exists():
        for md in sorted(notes_dir.glob("*.md")):
            tasks.append((md, "note"))
        for txt in sorted(notes_dir.glob("*.txt")):
            tasks.append((txt, "note"))

    hw_dir = corpus_dir / "handwritten"
    if hw_dir.exists():
        for ext in ("*.jpg", "*.jpeg", "*.png"):
            for img in sorted(hw_dir.glob(ext)):
                tasks.append((img, "handwritten"))
        # Text fallbacks
        for txt in sorted(hw_dir.glob("*.txt")):
            tasks.append((txt, "note"))

    if not tasks:
        print(f"[WARN] No files found in {corpus_dir}. Run corpus/generate_corpus.py first.",
              file=sys.stderr)
        return {"total_documents": 0, "total_chunks": 0, "formats_found": [], "errors": []}

    for file_path, category in tqdm(tasks, desc="Ingesting corpus", unit="file"):
        source_file = file_path.name

        if not force_reingest and registry.is_ingested(source_file):
            print(f"  [skip] {source_file} (already ingested)")
            continue

        try:
            pages = []
            fmt = file_path.suffix.lstrip(".").lower()

            if category == "lecture" and file_path.suffix.lower() == ".pdf":
                pages = extract_pdf_pages(file_path, output_image_dir=PAGE_IMAGES_DIR)
                fmt = "pdf-lecture"
            elif category == "slide" and file_path.suffix.lower() == ".pdf":
                pages = extract_slide_pages(file_path, output_image_dir=PAGE_IMAGES_DIR)
                fmt = "pdf-slide"
            elif category == "note":
                if file_path.suffix.lower() == ".md":
                    pages = load_markdown_file(file_path)
                    fmt = "markdown"
                else:
                    pages = load_text_file(file_path)
                    fmt = "text"
            elif category == "handwritten":
                pages = process_handwritten_image(
                    file_path, output_image_dir=PAGE_IMAGES_DIR
                )
                fmt = "handwritten"

            if not pages:
                print(f"  [warn] {source_file}: no pages extracted")
                continue

            chunks = chunk_all(pages, source=source_file)
            if not chunks:
                print(f"  [warn] {source_file}: no chunks produced")
                continue

            # Add to vector store (embeddings + ChromaDB)
            vector_store.add_chunks(chunks)

            # Collect for BM25 rebuild
            for c in chunks:
                bm25_chunks_data.append({"chunk_id": c.chunk_id, "text": c.text})

            # Register
            registry.register(
                source_file=source_file,
                format=fmt,
                page_count=len(pages),
                chunk_count=len(chunks),
                file_path=str(file_path),
            )

            total_documents += 1
            total_chunks += len(chunks)
            formats_found.add(fmt)
            print(f"  [ok] {source_file} — {len(pages)} pages, {len(chunks)} chunks")

        except Exception as exc:
            msg = f"{source_file}: {type(exc).__name__}: {exc}"
            errors.append(msg)
            print(f"  [error] {msg}", file=sys.stderr)

    # Rebuild BM25 index with all new chunks
    if bm25_chunks_data:
        bm25_index.build(bm25_chunks_data)
        BM25_PICKLE_PATH.parent.mkdir(parents=True, exist_ok=True)
        bm25_index.save(BM25_PICKLE_PATH)

    return {
        "total_documents": total_documents,
        "total_chunks": total_chunks,
        "formats_found": sorted(formats_found),
        "errors": errors,
    }


def load_index() -> tuple[VectorStore, BM25Index]:
    """Load both retrieval indexes from disk.

    Returns
    -------
    tuple[VectorStore, BM25Index]
    """
    vector_store = VectorStore()

    bm25_index = BM25Index()
    if BM25_PICKLE_PATH.exists():
        try:
            bm25_index.load(BM25_PICKLE_PATH)
        except Exception as exc:
            print(f"[WARN] Could not load BM25 index: {exc}. Will use empty index.",
                  file=sys.stderr)

    return vector_store, bm25_index


# ── Cloud ingestion (Supabase) ────────────────────────────────────────────────

def ingest_single_file_cloud(
    user_id: str,
    storage_path: str,
    category: str,
    filename: str,
) -> dict:
    """Download a file from Supabase Storage and ingest it into pgvector + registry.

    Parameters
    ----------
    user_id:      The visitor's UUID.
    storage_path: Supabase Storage path, e.g. '{user_id}/lectures/notes.pdf'
    category:     'lectures' | 'slides' | 'notes' | 'handwritten'
    filename:     Original filename, e.g. 'notes.pdf'

    Returns
    -------
    dict
        {'source_file', 'page_count', 'chunk_count', 'format', 'error'}
    """
    from src.storage.file_store import download_file
    from src.storage.vector_store_supa import SupabaseVectorStore
    from src.storage.registry_supa import SupabaseDocumentRegistry

    vs  = SupabaseVectorStore(user_id)
    reg = SupabaseDocumentRegistry(user_id)

    # Download file bytes from Supabase Storage into a temp file
    try:
        file_bytes = download_file(storage_path)
    except Exception as exc:
        return {"source_file": filename, "error": f"Download failed: {exc}",
                "page_count": 0, "chunk_count": 0, "format": "unknown"}

    suffix = Path(filename).suffix.lower()

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(file_bytes)
        tmp_path = Path(tmp.name)

    try:
        pages = []
        fmt   = "unknown"

        if category == "lectures" and suffix == ".pdf":
            pages = extract_pdf_pages(tmp_path, output_image_dir=PAGE_IMAGES_DIR)
            fmt = "pdf-lecture"
        elif category == "slides" and suffix == ".pdf":
            pages = extract_slide_pages(tmp_path, output_image_dir=PAGE_IMAGES_DIR)
            fmt = "pdf-slide"
        elif category == "notes":
            if suffix == ".md":
                pages = load_markdown_file(tmp_path)
                fmt = "markdown"
            else:
                pages = load_text_file(tmp_path)
                fmt = "text"
        elif category == "handwritten":
            pages = process_handwritten_image(tmp_path, output_image_dir=PAGE_IMAGES_DIR)
            fmt = "handwritten"

        if not pages:
            return {"source_file": filename, "error": "No pages extracted",
                    "page_count": 0, "chunk_count": 0, "format": fmt}

        chunks = chunk_all(pages, source=filename)
        if not chunks:
            return {"source_file": filename, "error": "No chunks produced",
                    "page_count": len(pages), "chunk_count": 0, "format": fmt}

        # Store vectors in Supabase pgvector
        vs.add_chunks(chunks)

        # Register document in Supabase
        reg.register(
            source_file=filename,
            format=fmt,
            page_count=len(pages),
            chunk_count=len(chunks),
            storage_path=storage_path,
        )

        return {
            "source_file": filename,
            "page_count":  len(pages),
            "chunk_count": len(chunks),
            "format":      fmt,
            "error":       None,
        }

    except Exception as exc:
        return {"source_file": filename, "error": str(exc),
                "page_count": 0, "chunk_count": 0, "format": "unknown"}
    finally:
        tmp_path.unlink(missing_ok=True)


def rebuild_bm25_for_user(user_id: str):
    """Load all chunk texts for a user from Supabase and return a built BM25Index.

    Called once per session and cached in st.session_state['bm25'].
    """
    from src.retrieval.bm25_index import BM25Index
    from src.storage.vector_store_supa import SupabaseVectorStore

    vs = SupabaseVectorStore(user_id)
    chunks = vs.get_all_chunks()
    bm25 = BM25Index()
    bm25.build(chunks)
    return bm25


if __name__ == "__main__":
    force = "--force" in sys.argv
    print(f"Starting corpus ingestion (force={force})...")
    summary = ingest_corpus(force_reingest=force)
    print(f"\nIngestion complete:")
    print(f"  Documents: {summary['total_documents']}")
    print(f"  Chunks:    {summary['total_chunks']}")
    print(f"  Formats:   {summary['formats_found']}")
    if summary["errors"]:
        print(f"  Errors ({len(summary['errors'])}):")
        for e in summary["errors"]:
            print(f"    - {e}")
