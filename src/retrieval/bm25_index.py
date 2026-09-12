"""
BM25 sparse-retrieval index with pickle persistence.
"""
from __future__ import annotations

import pickle
import re
from pathlib import Path
from typing import Any, Optional

from rank_bm25 import BM25Okapi


class BM25Index:
    """BM25 index over chunk texts."""

    def __init__(self) -> None:
        self._bm25: Optional[BM25Okapi] = None
        self._chunk_ids: list[str] = []
        self._corpus: list[list[str]] = []

    def tokenize(self, text: str) -> list[str]:
        return [tok for tok in re.sub(r"[^a-z0-9\s]", " ", text.lower()).split() if tok]

    def build(self, chunks: list[dict[str, Any]]) -> None:
        """Build BM25 index from list of {chunk_id, text} dicts."""
        if not chunks:
            self._bm25 = None
            self._chunk_ids = []
            self._corpus = []
            return
        self._chunk_ids = [c["chunk_id"] for c in chunks]
        self._corpus = [self.tokenize(c["text"]) for c in chunks]
        self._bm25 = BM25Okapi(self._corpus)

    def add_chunks(self, chunks: list[Any]) -> None:
        """Add Chunk objects to the index (rebuilds from scratch with new chunks appended)."""
        existing = [{"chunk_id": cid, "text": " ".join(toks)}
                    for cid, toks in zip(self._chunk_ids, self._corpus)]
        new_chunks = [{"chunk_id": c.chunk_id, "text": c.text} for c in chunks]
        self.build(existing + new_chunks)

    def search(self, query: str, top_k: int = 20) -> list[dict[str, Any]]:
        """Return top_k {chunk_id, score} dicts sorted by BM25 score desc."""
        if self._bm25 is None or not self._chunk_ids:
            return []
        tokenized = self.tokenize(query)
        if not tokenized:
            return []
        scores: list[float] = self._bm25.get_scores(tokenized).tolist()
        paired = sorted(zip(self._chunk_ids, scores), key=lambda x: x[1], reverse=True)
        return [{"chunk_id": cid, "score": score} for cid, score in paired[:top_k]]

    def save(self, path: Path) -> None:
        with open(path, "wb") as f:
            pickle.dump({"bm25": self._bm25, "chunk_ids": self._chunk_ids, "corpus": self._corpus}, f,
                        protocol=pickle.HIGHEST_PROTOCOL)

    def load(self, path: Path) -> None:
        with open(path, "rb") as f:
            state = pickle.load(f)
        self._bm25 = state["bm25"]
        self._chunk_ids = state["chunk_ids"]
        self._corpus = state["corpus"]


_bm25: Optional[BM25Index] = None


def get_bm25_index() -> BM25Index:
    global _bm25
    if _bm25 is None:
        _bm25 = BM25Index()
    return _bm25
