"""Tests for grounding and citation parsing."""
import sys
from pathlib import Path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def test_parse_citations_basic():
    from src.generation.citation_parser import parse_citations

    text = "Quicksort is fast [lecture.pdf:5]. Mergesort is stable [notes.md:3][lecture.pdf:8]."
    citations = parse_citations(text)
    assert len(citations) == 3
    assert citations[0].source_file == "lecture.pdf"
    assert citations[0].page_number == "5"


def test_parse_citations_dedup():
    from src.generation.citation_parser import parse_citations
    text = "Same citation [lecture.pdf:5] appears twice [lecture.pdf:5]."
    citations = parse_citations(text)
    assert len(citations) == 1


def test_is_refusal():
    from src.generation.citation_parser import is_refusal
    assert is_refusal("NOT_IN_MATERIALS: searched but not found")
    assert not is_refusal("Dijkstra runs in O((V+E)logV) [lecture.pdf:7].")


def test_extract_answer_refusal():
    from src.generation.citation_parser import extract_answer_and_citations
    text = "NOT_IN_MATERIALS: Cook-Levin theorem not in materials."
    answer, citations, is_ref = extract_answer_and_citations(text)
    assert is_ref
    assert citations == []
    assert "NOT_IN_MATERIALS" in answer


def test_grounding_check_found():
    from src.generation.citation_parser import Citation
    from src.generation.grounding_check import find_chunk_by_citation, compute_grounding_score, check_citations_grounded

    chunks = [
        {"source_file": "lecture.pdf", "page_number": 5, "text": "Some content"},
        {"source_file": "notes.md", "page_number": 3, "text": "Other content"},
    ]
    citation = Citation(source_file="lecture.pdf", page_number="5", raw="[lecture.pdf:5]")

    found = find_chunk_by_citation(citation, chunks)
    assert found is not None
    assert found["source_file"] == "lecture.pdf"

    results = check_citations_grounded([citation], chunks)
    assert results[0]["grounded"] is True

    score = compute_grounding_score(results)
    assert score == 1.0


def test_grounding_check_not_found():
    from src.generation.citation_parser import Citation
    from src.generation.grounding_check import find_chunk_by_citation

    chunks = [{"source_file": "slides.pdf", "page_number": 10, "text": "content"}]
    citation = Citation(source_file="missing_doc.pdf", page_number="99", raw="[missing_doc.pdf:99]")

    found = find_chunk_by_citation(citation, chunks)
    assert found is None
