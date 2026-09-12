"""Tests for retrieval pipeline."""
import sys
from pathlib import Path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def test_bm25_build_and_search():
    from src.retrieval.bm25_index import BM25Index

    index = BM25Index()
    chunks = [
        {"chunk_id": "c1", "text": "Dijkstra algorithm shortest path non-negative weights"},
        {"chunk_id": "c2", "text": "Bellman-Ford handles negative edges and detects negative cycles"},
        {"chunk_id": "c3", "text": "Merge sort is stable and runs in O(n log n) time"},
    ]
    index.build(chunks)

    results = index.search("Dijkstra shortest path")
    assert len(results) > 0
    assert results[0]["chunk_id"] == "c1"
    assert results[0]["score"] > 0


def test_bm25_empty_query():
    from src.retrieval.bm25_index import BM25Index
    index = BM25Index()
    index.build([{"chunk_id": "x", "text": "some text here"}])
    results = index.search("")
    assert results == []


def test_bm25_save_and_load(tmp_path):
    from src.retrieval.bm25_index import BM25Index
    index = BM25Index()
    index.build([{"chunk_id": "c1", "text": "dynamic programming optimal substructure"}])

    pkl = tmp_path / "test.pkl"
    index.save(pkl)

    index2 = BM25Index()
    index2.load(pkl)
    results = index2.search("dynamic programming")
    assert len(results) > 0
    assert results[0]["chunk_id"] == "c1"


def test_chunker_basic():
    from src.ingestion.chunker import chunk_text
    text = "This is a sentence. This is another sentence. And one more. Yes, another."
    chunks = chunk_text(text, chunk_size=50, overlap=10)
    assert len(chunks) > 0
    for chunk in chunks:
        assert chunk.strip()


def test_rrf_fusion():
    from src.retrieval.hybrid_search import reciprocal_rank_fusion

    list1 = ["a", "b", "c"]
    list2 = ["b", "a", "d"]
    fused = reciprocal_rank_fusion([list1, list2])

    fused_ids = [item[0] for item in fused]
    # 'a' and 'b' appear in both → should rank higher than 'c' and 'd'
    assert fused_ids.index("a") < fused_ids.index("c")
    assert fused_ids.index("b") < fused_ids.index("d")
