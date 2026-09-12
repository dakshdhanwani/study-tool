"""
Markdown and plain-text file loader for the study workspace ingestion pipeline.

Splits documents into section-level records, preserving heading structure
as metadata so citations can reference named sections.
"""
from __future__ import annotations

import re
from pathlib import Path

from src.ingestion.pdf_parser import PageRecord

# ── Section-split patterns ────────────────────────────────────────────────────
_MD_HEADING = re.compile(r"^(#{1,3})\s+(.+)$", re.MULTILINE)
_LINES_PER_PAGE = 40   # approximate "page" size for plain-text files


def load_markdown_file(md_path: Path) -> list[PageRecord]:
    """Load a Markdown file and split it into section-level PageRecords.

    Each ATX heading (``#``, ``##``, ``###``) starts a new section. Content
    before the first heading is captured as section 0 ("Preamble").

    Parameters
    ----------
    md_path:
        Path to the ``.md`` file.

    Returns
    -------
    list[PageRecord]
        One record per section. ``page_number`` is set to ``section_index + 1``
        to provide a stable, human-readable citation target.
    """
    md_path = Path(md_path)
    raw = md_path.read_text(encoding="utf-8", errors="replace")

    # Find all headings with their byte offsets
    heading_matches = list(_MD_HEADING.finditer(raw))

    if not heading_matches:
        # No headings — treat whole file as one section
        return [PageRecord(
            source_file=md_path.name,
            page_number=1,
            text=raw.strip(),
            format="markdown",
            ocr_confidence=1.0,
            section_title="(full document)",
            section_index=0,
        )]

    records: list[PageRecord] = []
    section_idx = 0

    # Text before first heading
    preamble = raw[: heading_matches[0].start()].strip()
    if preamble:
        records.append(PageRecord(
            source_file=md_path.name,
            page_number=1,
            text=preamble,
            format="markdown",
            ocr_confidence=1.0,
            section_title="Preamble",
            section_index=0,
        ))
        section_idx = 1

    for i, match in enumerate(heading_matches):
        title = match.group(2).strip()
        content_start = match.end()
        content_end = heading_matches[i + 1].start() if i + 1 < len(heading_matches) else len(raw)
        body = raw[content_start:content_end].strip()
        full_text = f"{title}\n\n{body}" if body else title

        records.append(PageRecord(
            source_file=md_path.name,
            page_number=section_idx + 1,
            text=full_text,
            format="markdown",
            ocr_confidence=1.0,
            section_title=title,
            section_index=section_idx,
        ))
        section_idx += 1

    return records


def load_text_file(txt_path: Path) -> list[PageRecord]:
    """Load a plain-text file and split it into approximate page chunks.

    Every ``_LINES_PER_PAGE`` lines constitute one "page" for citation
    purposes.

    Parameters
    ----------
    txt_path:
        Path to the ``.txt`` file.

    Returns
    -------
    list[PageRecord]
    """
    txt_path = Path(txt_path)
    lines = txt_path.read_text(encoding="utf-8", errors="replace").splitlines()

    records: list[PageRecord] = []
    page_num = 1

    for start in range(0, max(len(lines), 1), _LINES_PER_PAGE):
        chunk_lines = lines[start: start + _LINES_PER_PAGE]
        text = "\n".join(chunk_lines).strip()
        if not text:
            continue

        records.append(PageRecord(
            source_file=txt_path.name,
            page_number=page_num,
            text=text,
            format="text",
            ocr_confidence=1.0,
            section_title=f"Page {page_num}",
            section_index=page_num - 1,
        ))
        page_num += 1

    return records
