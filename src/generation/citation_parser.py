"""
Citation parser: extract [source:page] inline citations from LLM responses.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

_CITATION_PATTERN = re.compile(r"\[([^\[\]]+?):(\d+|[A-Za-z][\w\-]*)\]")
_NOT_IN_MATERIALS_PREFIX = "NOT_IN_MATERIALS:"


@dataclass(frozen=True)
class Citation:
    """A single inline citation parsed from an LLM response.

    Attributes
    ----------
    source_file:  Document identifier (filename as written in the citation).
    page_number:  Page or section label (string to support both '12' and 'slide-3').
    raw:          Complete original citation string e.g. '[lecture.pdf:12]'.
    """
    source_file: str
    page_number: str
    raw: str


def parse_citations(text: str) -> list[Citation]:
    """Extract all unique [filename:page] citations from *text*."""
    seen: set[tuple[str, str]] = set()
    results: list[Citation] = []
    for match in _CITATION_PATTERN.finditer(text):
        src = match.group(1).strip()
        page = match.group(2).strip()
        key = (src.lower(), page.lower())
        if key not in seen:
            seen.add(key)
            results.append(Citation(source_file=src, page_number=page, raw=match.group(0)))
    return results


def is_refusal(text: str) -> bool:
    return text.strip().startswith(_NOT_IN_MATERIALS_PREFIX)


def get_refusal_reason(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith(_NOT_IN_MATERIALS_PREFIX):
        return stripped[len(_NOT_IN_MATERIALS_PREFIX):].strip()
    return ""


def extract_answer_and_citations(
    llm_response: str,
) -> tuple[str, list[Citation], bool]:
    """Parse an LLM response into answer, citations, and refusal flag.

    Returns
    -------
    (answer_text, citations, is_refusal_flag)
    """
    if is_refusal(llm_response):
        return llm_response.strip(), [], True
    citations = parse_citations(llm_response)
    return llm_response.strip(), citations, False
