"""
Session state and manager for the study workspace.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from src.conversation.memory import ConversationMemory

_STOP = frozenset({"The", "This", "That", "In", "It", "A", "An", "I", "We",
                   "You", "He", "She", "They", "Is", "Are", "Was", "Were"})


@dataclass
class SessionState:
    """In-memory snapshot of a study session."""
    session_id: str
    active_topics: list[str] = field(default_factory=list)
    docs_referenced: list[str] = field(default_factory=list)
    comparison_queue: list[dict] = field(default_factory=list)
    concept_cards: list[dict] = field(default_factory=list)
    last_answer_chunks: list[dict] = field(default_factory=list)


class SessionManager:
    """Coordinates SessionState updates and persistence."""

    _CAP_RE = re.compile(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b")
    _BRACKET_RE = re.compile(r"\[([^\]]+)\]")
    _BOLD_RE = re.compile(r"\*\*([^*]+)\*\*")
    _ACRONYM_RE = re.compile(r"\b([A-Z]{2,6})\b")

    def __init__(self, memory: "ConversationMemory") -> None:
        self.memory = memory
        self.state = SessionState(session_id=memory.session_id)

    def _extract_topics(self, text: str) -> list[str]:
        candidates = []
        for pattern in (self._BOLD_RE, self._BRACKET_RE):
            for m in pattern.finditer(text):
                t = m.group(1).strip()
                if t and t not in _STOP:
                    candidates.append(t)
        for m in self._CAP_RE.finditer(text):
            t = m.group(1)
            if t not in _STOP and len(t) > 2:
                candidates.append(t)
        for m in self._ACRONYM_RE.finditer(text):
            candidates.append(m.group(1))
        return candidates

    def _merge_unique(self, existing: list[str], new: list[str]) -> list[str]:
        es = set(existing)
        for item in new:
            if item not in es:
                existing.append(item)
                es.add(item)
        return existing

    def update_from_answer(
        self, query: str, answer: str, chunks: list[dict], citations: list
    ) -> None:
        """Update state after receiving an answer; persists topics to memory."""
        new_topics = self._extract_topics(query + " " + answer)
        self.state.active_topics = self._merge_unique(self.state.active_topics, new_topics)

        new_docs: list[str] = []
        for chunk in chunks:
            meta = chunk.get("metadata", chunk)
            src = meta.get("source_file", chunk.get("source_file", ""))
            if src and src not in new_docs:
                new_docs.append(src)
        self.state.docs_referenced = self._merge_unique(self.state.docs_referenced, new_docs)
        self.state.last_answer_chunks = chunks

        self.memory.update_session_topics(
            topics=self.state.active_topics,
            docs=self.state.docs_referenced,
        )

    def add_to_comparison(self, label: str, text: str, source: str) -> None:
        self.state.comparison_queue.append({"label": label, "text": text, "source": source})

    def save_concept_card(self, title: str, definition: str, sources: list[str]) -> None:
        card = {"title": title, "definition": definition, "sources": sources}
        self.state.concept_cards.append(card)
        content = f"**Concept Card – {title}**\n\n{definition}\n\n*Sources: {', '.join(sources)}*"
        turn_id = self.memory.add_turn("assistant", content, [{"source": s} for s in sources])
        self.memory.pin_turn(turn_id)

    def get_comparison_table(self) -> str:
        if not self.state.comparison_queue:
            return "_Comparison queue is empty._"
        header = "| # | Label | Source | Excerpt |\n|---|-------|--------|---------|\n"
        rows = []
        for i, item in enumerate(self.state.comparison_queue, 1):
            excerpt = item.get("text", "")[:120].replace("|", "\\|")
            if len(item.get("text", "")) > 120:
                excerpt += "…"
            rows.append(f"| {i} | {item.get('label','')} | {item.get('source','')} | {excerpt} |")
        return header + "\n".join(rows)

    def clear_comparison(self) -> None:
        self.state.comparison_queue = []
