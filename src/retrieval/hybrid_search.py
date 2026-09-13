"""
Hybrid search combining semantic (pgvector) and sparse (BM25) retrieval
via Reciprocal Rank Fusion (RRF).
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any

from src.config import RETRIEVAL_TOP_K
from src.retrieval.bm25_index import BM25Index


def reciprocal_rank_fusion(
    ranked_lists: list[list[str]],
    k: int = 60,
) -> list[tuple[str, float]]:
    """Fuse multiple ranked lists of chunk IDs using RRF.

    Parameters
    ----------
    ranked_lists: Each inner list is a ranked sequence of chunk IDs (best first).
    k:            Smoothing constant (default 60).

    Returns
    -------
    List of (chunk_id, rrf_score) sorted by score descending.
    """
    scores: dict[str, float] = defaultdict(float)
    for ranked in ranked_lists:
        for rank, doc_id in enumerate(ranked, start=1):
            scores[doc_id] += 1.0 / (k + rank)
    return sorted(scores.items(), key=lambda x: x[1], reverse=True)


def hybrid_search(
    query: str,
    vector_store: Any,
    bm25_index: BM25Index,
    top_k: int = RETRIEVAL_TOP_K,
) -> list[dict[str, Any]]:
    """Run hybrid retrieval and return fused, enriched results.

    Parameters
    ----------
    query:        Query string.
    vector_store: Initialised VectorStore.
    bm25_index:   Built BM25Index.
    top_k:        Number of results to return.

    Returns
    -------
    list of {chunk_id, text, metadata, rrf_score, semantic_score, bm25_score}
    """
    candidate_k = top_k * 2

    semantic_results = vector_store.search(query, top_k=candidate_k)
    bm25_results = bm25_index.search(query, top_k=candidate_k)

    semantic_scores = {r["chunk_id"]: r["score"] for r in semantic_results}
    bm25_scores = {r["chunk_id"]: r["score"] for r in bm25_results}

    semantic_ids = [r["chunk_id"] for r in semantic_results]
    bm25_ids = [r["chunk_id"] for r in bm25_results]

    fused = reciprocal_rank_fusion([semantic_ids, bm25_ids])

    output: list[dict[str, Any]] = []
    for chunk_id, rrf_score in fused[:top_k]:
        chunk = vector_store.get_chunk_by_id(chunk_id)
        if chunk is None:
            continue
        output.append({
            "chunk_id":       chunk_id,
            "text":           chunk["text"],
            "metadata":       chunk["metadata"],
            "source_file":    chunk["metadata"].get("source_file", ""),
            "page_number":    chunk["metadata"].get("page_number", 0),
            "format":         chunk["metadata"].get("format", ""),
            "ocr_confidence": chunk["metadata"].get("ocr_confidence", 1.0),
            "page_image_path": chunk["metadata"].get("page_image_path", ""),
            "section_title":  chunk["metadata"].get("section_title", ""),
            "rrf_score":      rrf_score,
            "semantic_score": semantic_scores.get(chunk_id, 0.0),
            "bm25_score":     bm25_scores.get(chunk_id, 0.0),
        })

    return output
