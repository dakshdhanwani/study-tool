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
        mat = fitz.Matrix(2, 2)   # 2x scale
        pix = page.get_pixmap(matrix=mat, alpha=False)
        pix.save(str(img_path))
    except Exception as exc:
        print(f"[WARN] Could not render page image {img_path.name}: {exc}", file=sys.stderr)
        return ""
    return str(img_path)

def _batch_ocr_pages(records: list[PageRecord]):
    """Batch OCR sparse pages to save API quota."""
    pages_needing_ocr = [rec for rec in records if rec.ocr_confidence == 0.5 and rec.page_image_path]
    if not pages_needing_ocr:
        return

    try:
        import google.generativeai as genai
        from src.config import GEMINI_VISION_MODEL
        import PIL.Image
        import os
        import re

        key = os.environ.get("GEMINI_API_KEY", "")
        if not key: return
        genai.configure(api_key=key)
        model = genai.GenerativeModel(GEMINI_VISION_MODEL)

        batch_size = 15
        for i in range(0, len(pages_needing_ocr), batch_size):
            batch = pages_needing_ocr[i:i+batch_size]
            prompt = "Transcribe the text in each of the following images. Separate the transcription of each image EXACTLY with the line '===PAGE_N===' where N is the image's order in this prompt (1, 2, 3, etc.). Do not miss any image."
            contents = [prompt]
            for rec in batch:
                contents.append(PIL.Image.open(rec.page_image_path))

            print(f"[INFO] Batch OCR-ing {len(batch)} pages...", file=sys.stderr)
            response = model.generate_content(contents)

            parts = re.split(r'===PAGE_\d+===', response.text)
            if len(parts) > 1 and "===" not in parts[0]:
                parts = parts[1:]

            parts = [p.strip() for p in parts]
            for j, rec in enumerate(batch):
                if j < len(parts) and parts[j]:
                    rec.text += "\\n" + parts[j]
                    rec.ocr_confidence = 0.85
    except Exception as exc:
        print(f"[WARN] Batch OCR failed: {exc}", file=sys.stderr)

def extract_pdf_pages(pdf_path: Path, output_image_dir: Optional[Path] = None) -> list[PageRecord]:
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
        text = page.get_text("text").strip()

        confidence = 1.0
        if len(text) < 20:
            confidence = 0.5  # Likely image-only page

        img_path = _render_page_image(page, output_image_dir, stem, page_num + 1)

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
    _batch_ocr_pages(records)
    return records


def extract_slide_pages(pdf_path: Path, output_image_dir: Optional[Path] = None) -> list[PageRecord]:
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

        notes_parts: list[str] = []
        for annot in page.annots():
            if annot.info.get("content"):
                notes_parts.append(annot.info["content"].strip())

        full_text = slide_text
        if notes_parts:
            full_text += "\n\n[Speaker Notes]\n" + "\n".join(notes_parts)

        confidence = 1.0 if len(slide_text) >= 20 else 0.5
        img_path = _render_page_image(page, output_image_dir, stem, page_num + 1)

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
    _batch_ocr_pages(records)
    return records
