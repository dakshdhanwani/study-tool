"""
Page-aware chunker for the study workspace ingestion pipeline.

Splits PageRecord text into overlapping chunks that respect sentence
boundaries, preserving all source metadata for grounded citations.
"""
from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from typing import Union

# ── Chunk size constants ────────────────────────────────────────────────────
CHUNK_SIZE = 500     # characters (≈ 125 tokens for most English text)
OVERLAP = 80         # character overlap between consecutive chunks

# ── Sentence boundary pattern ───────────────────────────────────────────────
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")


@dataclass
class Chunk:
    """A retrievable text chunk with full source provenance.

    Attributes
    ----------
    chunk_id:         UUID string (unique across all documents).
    source_file:      Filename of the originating document.
    page_number:      Page or section number (1-based).
    chunk_index:      0-based index of this chunk within its page.
    text:             Text content of the chunk.
    format:           'pdf', 'slide', 'handwritten', 'markdown', 'text'.
    ocr_confidence:   Float 0.0–1.0.
    page_image_path:  Path to the rendered page image for citation preview.
    section_title:    Section heading, if available.
    """
    chunk_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    source_file: str = ""
    page_number: int = 1
    chunk_index: int = 0
    text: str = ""
    format: str = "pdf"
    ocr_confidence: float = 1.0
    page_image_path: str = ""
    section_title: str = ""


def chunk_text(
    text: str,
    chunk_size: int = CHUNK_SIZE,
    overlap: int = OVERLAP,
) -> list[str]:
    """Split *text* into overlapping chunks that respect sentence boundaries.

    Algorithm
    ---------
    1. Split text at sentence boundaries (``'. '``, ``'! '``, ``'? '``).
    2. Greedily accumulate sentences until adding the next one would exceed
       *chunk_size*.
    3. When a chunk is full, start a new chunk with the last *overlap*
       characters from the previous chunk prepended (for context continuity).
    4. If a single sentence exceeds *chunk_size*, it is kept as its own chunk.

    Parameters
    ----------
    text:       Input text to split.
    chunk_size: Target maximum chunk length in characters.
    overlap:    Number of trailing characters from one chunk to prepend to the
                next, providing retrieval context continuity.

    Returns
    -------
    list[str]
        Non-empty text chunks.
    """
    if not text.strip():
        return []

    # Split on sentence boundaries while keeping the delimiters
    sentences = _SENTENCE_END.split(text.strip())
    sentences = [s.strip() for s in sentences if s.strip()]

    if not sentences:
        return []

    chunks: list[str] = []
    current: list[str] = []
    current_len = 0

    for sentence in sentences:
        sentence_len = len(sentence)

        if current_len + sentence_len + 1 > chunk_size and current:
            # Flush current chunk
            chunk_text_str = " ".join(current)
            chunks.append(chunk_text_str)

            # Carry-forward overlap: take trailing characters from last chunk
            carry = chunk_text_str[-overlap:] if overlap > 0 else ""
            current = [carry] if carry else []
            current_len = len(carry)

        current.append(sentence)
        current_len += sentence_len + 1  # +1 for space

    # Flush remaining
    if current:
        chunks.append(" ".join(current))

    return [c for c in chunks if c.strip()]


def chunks_from_page_record(record) -> list[Chunk]:
    """Create Chunk objects from a single PageRecord.

    Parameters
    ----------
    record: A PageRecord instance (imported to avoid circular imports).

    Returns
    -------
    list[Chunk]
        One Chunk per text sub-chunk extracted from the page.
    """
    sub_texts = chunk_text(record.text)
    chunks: list[Chunk] = []

    for idx, text in enumerate(sub_texts):
        chunks.append(Chunk(
            chunk_id=str(uuid.uuid4()),
            source_file=record.source_file,
            page_number=record.page_number,
            chunk_index=idx,
            text=text,
            format=record.format,
            ocr_confidence=record.ocr_confidence,
            page_image_path=record.page_image_path,
            section_title=getattr(record, "section_title", ""),
        ))

    return chunks


def chunk_all(records: list, source: str = "") -> list[Chunk]:
    """Chunk a list of PageRecords into a flat list of Chunks.

    Parameters
    ----------
    records: List of PageRecord instances.
    source:  Optional override for source_file (useful when known externally).

    Returns
    -------
    list[Chunk]
        All chunks from all records, in document order.
    """
    all_chunks: list[Chunk] = []

    for record in records:
        if source and not record.source_file:
            record.source_file = source

        page_chunks = chunks_from_page_record(record)
        all_chunks.extend(page_chunks)

    return all_chunks
