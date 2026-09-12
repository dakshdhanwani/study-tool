"""
PDF and Slide page extraction for the study workspace ingestion pipeline.

Extracts text and page images from PDF documents using PyMuPDF.
Each page becomes a PageRecord with source metadata and image path.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

try:
    import fitz  # PyMuPDF
    FITZ_AVAILABLE = True
except ImportError:
    FITZ_AVAILABLE = False


@dataclass
class PageRecord:
    """A single page extracted from any source document.

    Attributes
    ----------
    source_file:    Filename of the originating document (basename only).
    page_number:    1-based page index within the document.
    text:           Extracted text content (may be OCR'd).
    page_image_path: Absolute path to the rendered PNG of this page.
    format:         One of 'pdf', 'slide', 'handwritten', 'markdown', 'text'.
    ocr_confidence: Float 0.0–1.0. 1.0 for native-text PDFs, lower for OCR.
    raw_ocr_text:   Unprocessed OCR text before cleanup (empty for native PDFs).
    section_title:  Optional section heading (populated by markdown loader).
    section_index:  Used by markdown/text loaders for page approximation.
    """
    source_file: str
    page_number: int
    text: str
    page_image_path: str = ""
    format: str = "pdf"
    ocr_confidence: float = 1.0
    raw_ocr_text: str = ""
    section_title: str = ""
    section_index: int = 0


def _render_page_image(page, output_image_dir: Path, stem: str, page_num: int) -> str:
    """Render a fitz Page to a PNG file and return its path string."""
    output_image_dir.mkdir(parents=True, exist_ok=True)
    img_path = output_image_dir / f"{stem}_p{page_num:04d}.png"
    if img_path.exists():
        return str(img_path)
    try:
        mat = fitz.Matrix(2, 2)   # 2x scale → ~144 dpi
        pix = page.get_pixmap(matrix=mat, alpha=False)
        pix.save(str(img_path))
    except Exception as exc:
        print(f"[WARN] Could not render page image {img_path.name}: {exc}", file=sys.stderr)
        return ""
    return str(img_path)


def extract_pdf_pages(pdf_path: Path, output_image_dir: Optional[Path] = None) -> list[PageRecord]:
    """Extract text and page images from a lecture PDF.

    Parameters
    ----------
    pdf_path:
        Path to the PDF file.
    output_image_dir:
        Directory to save rendered page images. Defaults to
        ``{pdf_path.parent}/page_images/``.

    Returns
    -------
    list[PageRecord]
        One record per page. Pages with fewer than 20 characters of extracted
        text are still included but marked with ``ocr_confidence=0.5`` to
        indicate they may need OCR.
    """
    if not FITZ_AVAILABLE:
        raise ImportError("PyMuPDF (fitz) is required. Install with: pip install PyMuPDF")

    pdf_path = Path(pdf_path)
    if output_image_dir is None:
        output_image_dir = pdf_path.parent / "page_images"

    records: list[PageRecord] = []
    stem = pdf_path.stem

    try:
        doc = fitz.open(str(pdf_path))
    except Exception as exc:
        print(f"[ERROR] Cannot open {pdf_path.name}: {exc}", file=sys.stderr)
        return []

    for page_num in range(len(doc)):
        page = doc[page_num]
        text = page.get_text("text").strip()

        confidence = 1.0
        if len(text) < 20:
            confidence = 0.5  # Likely image-only page or very sparse

        img_path = _render_page_image(page, output_image_dir, stem, page_num + 1)

        # Fallback to OCR if the page seems to be an image/scan
        if confidence == 0.5 and img_path:
            try:
                from src.ingestion.ocr_pipeline import ocr_with_gemini_vision
                ocr_res = ocr_with_gemini_vision(Path(img_path))
                if ocr_res.text and "[OCR FAILED" not in ocr_res.text:
                    text = ocr_res.text
                    confidence = ocr_res.confidence
            except Exception as exc:
                print(f"[WARN] OCR fallback failed for {img_path}: {exc}", file=sys.stderr)

        records.append(PageRecord(
            source_file=pdf_path.name,
            page_number=page_num + 1,
            text=text,
            page_image_path=img_path,
            format="pdf",
            ocr_confidence=confidence,
            raw_ocr_text="",
        ))

    doc.close()
    return records


def extract_slide_pages(pdf_path: Path, output_image_dir: Optional[Path] = None) -> list[PageRecord]:
    """Extract text and page images from a slide-deck PDF.

    Identical to :func:`extract_pdf_pages` but sets ``format='slide'`` and
    also attempts to extract any speaker-note text embedded in the PDF.

    Parameters
    ----------
    pdf_path:
        Path to the slide PDF.
    output_image_dir:
        Directory for rendered slide images.

    Returns
    -------
    list[PageRecord]
    """
    if not FITZ_AVAILABLE:
        raise ImportError("PyMuPDF (fitz) is required.")

    pdf_path = Path(pdf_path)
    if output_image_dir is None:
        output_image_dir = pdf_path.parent / "page_images"

    records: list[PageRecord] = []
    stem = pdf_path.stem

    try:
        doc = fitz.open(str(pdf_path))
    except Exception as exc:
        print(f"[ERROR] Cannot open {pdf_path.name}: {exc}", file=sys.stderr)
        return []

    for page_num in range(len(doc)):
        page = doc[page_num]
        slide_text = page.get_text("text").strip()

        # Speaker notes are sometimes embedded as annotation text
        notes_parts: list[str] = []
        for annot in page.annots():
            if annot.info.get("content"):
                notes_parts.append(annot.info["content"].strip())

        full_text = slide_text
        if notes_parts:
            full_text += "\n\n[Speaker Notes]\n" + "\n".join(notes_parts)

        confidence = 1.0 if len(slide_text) >= 20 else 0.5
        img_path = _render_page_image(page, output_image_dir, stem, page_num + 1)

        # Fallback to OCR if the page seems to be an image/scan
        if confidence == 0.5 and img_path:
            try:
                from src.ingestion.ocr_pipeline import ocr_with_gemini_vision
                ocr_res = ocr_with_gemini_vision(Path(img_path))
                if ocr_res.text and '[OCR FAILED' not in ocr_res.text:
                    full_text += '\n' + ocr_res.text
                    confidence = ocr_res.confidence
            except Exception as exc:
                import sys
                print(f'[WARN] OCR fallback failed: {exc}', file=sys.stderr)

        records.append(PageRecord(
            source_file=pdf_path.name,
            page_number=page_num + 1,
            text=full_text,
            page_image_path=img_path,
            format="slide",
            ocr_confidence=confidence,
            raw_ocr_text="",
        ))

    doc.close()
    return records
