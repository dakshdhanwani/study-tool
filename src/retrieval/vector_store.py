"""
ChromaDB-backed vector store for semantic retrieval (legacy local version).

NOTE: The main app now uses SupabaseVectorStore from src/storage/vector_store_supa.py.
This module is kept for backward-compatibility and local dev/testing.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

import numpy as np

from src.ingestion.chunker import Chunk
from src.retrieval.embeddings import get_embedder

# Local fallbacks (used only if VectorStore is instantiated directly)
_LOCAL_CHROMA_DIR        = Path(__file__).parent.parent.parent / "data" / "chroma"
_LOCAL_CHROMA_COLLECTION = "study_chunks"

_BATCH_SIZE = 64


class VectorStore:
    """Persistent ChromaDB vector store (legacy local)."""

    def __init__(
        self,
        persist_dir: Path = _LOCAL_CHROMA_DIR,
        collection_name: str = _LOCAL_CHROMA_COLLECTION,
    ) -> None:
        self._persist_dir = Path(persist_dir)
        self._collection_name = collection_name
        import chromadb as _chromadb
        self._client = _chromadb.PersistentClient(path=str(self._persist_dir))

        # Prevent Chroma from loading default ONNX embedder
        from chromadb.api.types import EmbeddingFunction
        class DummyEF(EmbeddingFunction):
            def __call__(self, input: list[str]) -> list[list[float]]: return []
            def name(self) -> str: return "default"

        self._collection = self._client.get_or_create_collection(
            name=self._collection_name,
            metadata={"hnsw:space": "cosine"},
            embedding_function=DummyEF(),
        )

    def add_chunks(self, chunks: list[Chunk]) -> None:
        """Embed and upsert chunks into ChromaDB in batches."""
        embedder = get_embedder()
        for start in range(0, len(chunks), _BATCH_SIZE):
            batch = chunks[start: start + _BATCH_SIZE]
            texts = [c.text for c in batch]
            embeddings: np.ndarray = embedder.embed(texts)

            self._collection.upsert(
                ids=[c.chunk_id for c in batch],
                embeddings=embeddings.tolist(),
                documents=texts,
                metadatas=[{
                    "source_file":     str(c.source_file),
                    "page_number":     c.page_number,
                    "format":          c.format,
                    "ocr_confidence":  float(c.ocr_confidence) if c.ocr_confidence is not None else 1.0,
                    "page_image_path": str(c.page_image_path) if c.page_image_path else "",
                    "section_title":   c.section_title or "",
                } for c in batch],
            )

    def search(self, query: str, top_k: int = 20) -> list[dict[str, Any]]:
        """Semantic similarity search. Returns list of {chunk_id, text, metadata, score}."""
        embedder = get_embedder()
        query_vec = embedder.embed_one(query).tolist()
        n = min(top_k, max(self._collection.count(), 1))

        results = self._collection.query(
            query_embeddings=[query_vec],
            n_results=n,
            include=["documents", "metadatas", "distances"],
        )

        output = []
        for chunk_id, text, meta, dist in zip(
            results["ids"][0],
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0],
        ):
            output.append({
                "chunk_id": chunk_id,
                "text": text,
                "metadata": meta,
                "score": 1.0 - dist,   # convert cosine distance to similarity
            })
        return output

    def get_chunk_by_id(self, chunk_id: str) -> Optional[dict[str, Any]]:
        """Fetch a single chunk by ID."""
        try:
            result = self._collection.get(
                ids=[chunk_id],
                include=["documents", "metadatas"],
            )
        except Exception:
            return None
        if not result["ids"]:
            return None
        return {
            "chunk_id": result["ids"][0],
            "text": result["documents"][0],
            "metadata": result["metadatas"][0],
        }

    def collection_size(self) -> int:
        return self._collection.count()

    def reset(self) -> None:
        self._client.delete_collection(self._collection_name)
        self._collection = self._client.get_or_create_collection(
            name=self._collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    def get_all_chunks(self) -> list[dict[str, Any]]:
        """Return all chunks in the collection (for BM25 rebuild)."""
        count = self._collection.count()
        if count == 0:
            return []
        result = self._collection.get(include=["documents", "metadatas"])
        output = []
        for cid, text, meta in zip(result["ids"], result["documents"], result["metadatas"]):
            output.append({"chunk_id": cid, "text": text, "metadata": meta})
        return output

    def delete_chunks_for_document(self, source_file: str) -> None:
        try:
            self._collection.delete(where={"source_file": source_file})
        except Exception:
            pass


_store: Optional[VectorStore] = None


def get_vector_store() -> VectorStore:
    """Return a module-level VectorStore singleton (legacy local ChromaDB version)."""
    global _store
    if _store is None:
        _store = VectorStore()
    return _store
