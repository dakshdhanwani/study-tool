"""
Grounding verification: checks that LLM citations map to real retrieved chunks.
"""
from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Optional

from src.generation.citation_parser import Citation

_NON_ALNUM = re.compile(r"[^a-z0-9]")


def _normalise(s: str) -> str:
    return _NON_ALNUM.sub("", s.lower())


def _names_match(cited: str, chunk: str) -> bool:
    nc, nk = _normalise(cited), _normalise(chunk)
    if not nc or not nk:
        return False
    if nc == nk or nc in nk or nk in nc:
        return True
    return SequenceMatcher(None, nc, nk).ratio() >= 0.75


def _pages_match(cited: str, chunk_page) -> bool:
    return str(cited).strip().lower() == str(chunk_page).strip().lower()


def find_chunk_by_citation(
    citation: Citation,
    chunks: list[dict],
) -> Optional[dict]:
    """Find the retrieved chunk that best matches a citation."""
    # Exact filename + page match
    for chunk in chunks:
        meta = chunk.get("metadata", chunk)
        if (_names_match(citation.source_file, str(meta.get("source_file", ""))) and
                _pages_match(citation.page_number, meta.get("page_number", ""))):
            return chunk
    return None


def check_citations_grounded(
    citations: list[Citation],
    chunks: list[dict],
) -> list[dict]:
    """Verify each citation against retrieved chunks.

    Returns
    -------
    list of {citation, grounded: bool, matched_chunk: dict|None}
    """
    results: list[dict] = []
    for citation in citations:
        matched = find_chunk_by_citation(citation, chunks)
        grounded = matched is not None
        results.append({"citation": citation, "grounded": grounded, "matched_chunk": matched})
    return results


def compute_grounding_score(grounding_results: list[dict]) -> float:
    """Fraction of citations that are grounded (0.0–1.0)."""
    if not grounding_results:
        return 1.0
    return sum(1 for r in grounding_results if r["grounded"]) / len(grounding_results)
