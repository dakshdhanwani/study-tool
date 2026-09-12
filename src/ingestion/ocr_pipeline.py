"""
OCR pipeline using Gemini Vision for handwritten and scanned images.

Since Tesseract is not installed, we use Gemini 1.5 Pro's vision capability
exclusively. OCR results include a confidence estimate and the original image
path for user verification.
"""
from __future__ import annotations

import base64
import os
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

# Lazy import to avoid errors at module load if key not set yet
_genai = None


def _get_genai():
    global _genai
    if _genai is None:
        try:
            import google.generativeai as genai
            _genai = genai
        except ImportError:
            raise ImportError(
                "google-generativeai is required for OCR. "
                "Install with: pip install google-generativeai"
            )
    return _genai


@dataclass
class OCRResult:
    """Result of OCR processing on a single image.

    Attributes
    ----------
    text:        Transcribed text content.
    confidence:  Estimated confidence 0.0–1.0.
    raw_text:    Unprocessed output from the vision model.
    method:      How OCR was performed (e.g. 'gemini_vision').
    image_path:  Path to the source image file.
    """
    text: str
    confidence: float
    raw_text: str
    method: str
    image_path: str


def image_to_base64(image_path: Path) -> str:
    """Read an image file and return its base64-encoded string.

    Parameters
    ----------
    image_path: Path to the image file.

    Returns
    -------
    str  Base64-encoded image bytes.
    """
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def ocr_with_gemini_vision(
    image_path: Path,
    model_name: str = "gemini-1.5-pro",
    api_key: Optional[str] = None,
) -> OCRResult:
    """Transcribe handwritten or scanned image text using Gemini Vision.

    Parameters
    ----------
    image_path:   Path to the image to transcribe.
    model_name:   Gemini model to use (must support vision).
    api_key:      Optional API key override; falls back to env var.

    Returns
    -------
    OCRResult
        On success: method='gemini_vision', confidence=0.85.
        On failure: text='[OCR FAILED]', confidence=0.0.
    """
    genai = _get_genai()

    key = api_key or os.environ.get("GEMINI_API_KEY", "")
    if not key:
        return OCRResult(
            text="[OCR FAILED: No GEMINI_API_KEY set]",
            confidence=0.0,
            raw_text="",
            method="gemini_vision",
            image_path=str(image_path),
        )

    genai.configure(api_key=key)

    prompt = (
        "You are an expert at reading handwritten and scanned notes. "
        "Please transcribe ALL text visible in this image exactly as written, "
        "preserving any mathematical notation, diagrams labels, arrows, bullet points, "
        "and structural layout. Include every word even if uncertain — mark uncertain "
        "words with [?] immediately after them. "
        "If a region is completely illegible, write [ILLEGIBLE]. "
        "Format: output ONLY the transcribed text, nothing else. "
        "Do not add commentary, headers, or explanations."
    )

    try:
        # Read image and determine MIME type
        image_path = Path(image_path)
        ext = image_path.suffix.lower()
        mime_map = {".jpg": "image/jpeg", ".jpeg": "image/jpeg",
                    ".png": "image/png", ".webp": "image/webp"}
        mime_type = mime_map.get(ext, "image/png")

        image_bytes = image_path.read_bytes()

        model = genai.GenerativeModel(model_name)
        response = model.generate_content([
            prompt,
            {"mime_type": mime_type, "data": image_bytes},
        ])

        raw_text = response.text.strip()

        # Heuristic confidence: lower if many [?] markers
        uncertain_count = raw_text.count("[?]") + raw_text.count("[ILLEGIBLE]")
        word_count = max(len(raw_text.split()), 1)
        confidence = max(0.3, 0.85 - (uncertain_count / word_count) * 0.5)

        return OCRResult(
            text=raw_text,
            confidence=confidence,
            raw_text=raw_text,
            method="gemini_vision",
            image_path=str(image_path),
        )

    except Exception as exc:
        error_msg = f"[OCR FAILED: {type(exc).__name__}: {exc}]"
        print(f"[ERROR] OCR failed for {image_path.name}: {exc}", file=sys.stderr)
        return OCRResult(
            text=error_msg,
            confidence=0.0,
            raw_text="",
            method="gemini_vision",
            image_path=str(image_path),
        )


def process_handwritten_image(
    image_path: Path,
    output_image_dir: Optional[Path] = None,
    api_key: Optional[str] = None,
) -> list:
    """Process a handwritten image: OCR it and return a list of PageRecords.

    The original image is copied to output_image_dir for citation preview.

    Parameters
    ----------
    image_path:       Path to the handwritten image file.
    output_image_dir: Where to copy the image for persistent reference.
                      Defaults to ``{image_path.parent}/page_images/``.
    api_key:          Optional Gemini API key override.

    Returns
    -------
    list[PageRecord]
        A single-element list containing the OCR result as a PageRecord.
    """
    # Import here to avoid circular import at module load
    from src.ingestion.pdf_parser import PageRecord

    image_path = Path(image_path)

    if output_image_dir is None:
        output_image_dir = image_path.parent / "page_images"
    output_image_dir = Path(output_image_dir)
    output_image_dir.mkdir(parents=True, exist_ok=True)

    # Copy image to output dir for stable reference
    dest_image = output_image_dir / image_path.name
    if not dest_image.exists():
        shutil.copy2(str(image_path), str(dest_image))

    # Run OCR
    ocr_result = ocr_with_gemini_vision(image_path, api_key=api_key)

    record = PageRecord(
        source_file=image_path.name,
        page_number=1,
        text=ocr_result.text,
        page_image_path=str(dest_image),
        format="handwritten",
        ocr_confidence=ocr_result.confidence,
        raw_ocr_text=ocr_result.raw_text,
        section_title="Handwritten Notes",
        section_index=0,
    )

    return [record]
