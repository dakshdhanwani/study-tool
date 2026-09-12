"""
Query expansion / coreference resolution for multi-turn study dialogues.

Resolves pronouns and vague references (it, this, that algorithm) using
recent conversation context.
"""
from __future__ import annotations

import re
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from src.conversation.session import SessionState

COREFERENCE_WORDS = [
    "the algorithm", "the method", "the approach", "the concept",
    "the first", "the second", "the previous", "the latter", "the former",
    "it", "this", "that", "they", "them", "these", "those",
]

_COREF_PATTERN = re.compile(
    r"\b(" + "|".join(re.escape(w) for w in COREFERENCE_WORDS) + r")\b",
    re.IGNORECASE,
)

_CAP_RE = re.compile(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3})\b")
_BOLD_RE = re.compile(r"\*\*([^*]+)\*\*")
_BACKTICK_RE = re.compile(r"`([^`]+)`")
_BRACKET_RE = re.compile(r"\[([^\]]+)\]")
_ACRONYM_RE = re.compile(r"\b([A-Z]{2,6})\b")

_STOP = frozenset({"The", "This", "That", "In", "It", "A", "An", "I", "We",
                   "You", "How", "What", "When", "Where", "Why", "Which"})

_SHORT_QUERY_LEN = 60


def needs_expansion(query: str) -> bool:
    """Return True if query is short and contains a coreference word."""
    return len(query.strip()) < _SHORT_QUERY_LEN and bool(_COREF_PATTERN.search(query))


def _extract_topics(text: str) -> list[str]:
    candidates = []
    for pattern in (_BOLD_RE, _BACKTICK_RE, _BRACKET_RE):
        for m in pattern.finditer(text):
            t = m.group(1).strip()
            if t and t not in _STOP:
                candidates.append(t)
    for m in _CAP_RE.finditer(text):
        t = m.group(1)
        if t not in _STOP and len(t) > 2:
            candidates.append(t)
    for m in _ACRONYM_RE.finditer(text):
        candidates.append(m.group(1))
    return candidates


def expand_query(
    query: str,
    conversation_history: list[dict],
    session_state: Optional["SessionState"] = None,
) -> str:
    """Resolve coreferences in *query* using recent assistant turns.

    Parameters
    ----------
    query:                The user's query, potentially containing coreferences.
    conversation_history: Prior turns [{role, content}, ...].
    session_state:        Optional session state with active_topics as fallback.

    Returns
    -------
    str  Expanded query with coreferences resolved, or original if no context found.
    """
    if not needs_expansion(query):
        return query

    # Extract topics from last 3 assistant turns
    recent = [t["content"] for t in conversation_history[-6:]
              if t.get("role") in ("assistant", "model")][-3:]

    candidates: list[str] = []
    for text in reversed(recent):
        candidates.extend(_extract_topics(text))

    # Deduplicate while preserving order
    seen: set[str] = set()
    unique: list[str] = []
    for c in candidates:
        if c not in seen:
            seen.add(c)
            unique.append(c)

    if not unique and session_state is not None:
        unique = list(session_state.active_topics)

    if not unique:
        return query

    primary = unique[0]
    expanded, n = _COREF_PATTERN.subn(primary, query, count=1)

    if n > 0:
        return (expanded[0].upper() + expanded[1:]).strip()

    return f"In the context of {primary}: {query}"
