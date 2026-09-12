"""
Cross-encoder reranker for the final retrieval stage.
"""
from __future__ import annotations

from typing import Any, Optional

from sentence_transformers import CrossEncoder

RERANKER_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"


class Reranker:
    """Lazy-loading cross-encoder reranker."""

    def __init__(self, model_name: str = RERANKER_MODEL) -> None:
        self._model_name = model_name
        self._model: Optional[CrossEncoder] = None

    @property
    def model(self) -> CrossEncoder:
        if self._model is None:
            self._model = CrossEncoder(self._model_name)
        return self._model

    def rerank(
        self,
        query: str,
        candidates: list[dict[str, Any]],
        top_k: int = 6,
    ) -> list[dict[str, Any]]:
        """Score candidates against query and return top_k sorted by score.

        Each candidate dict must have a 'text' key. Adds 'rerank_score' to each.
        """
        if not candidates:
            return []
        pairs = [(query, c["text"]) for c in candidates]
        raw_scores: list[float] = self.model.predict(pairs).tolist()
        scored = [{**c, "rerank_score": s} for c, s in zip(candidates, raw_scores)]
        scored.sort(key=lambda x: x["rerank_score"], reverse=True)
        return scored[:top_k]


_reranker: Optional[Reranker] = None


def get_reranker() -> Reranker:
    global _reranker
    if _reranker is None:
        _reranker = Reranker()
    return _reranker
