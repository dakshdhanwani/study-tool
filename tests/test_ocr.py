"""Tests for OCR pipeline."""
import sys
from pathlib import Path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def test_ocr_result_structure():
    from src.ingestion.ocr_pipeline import OCRResult
    r = OCRResult(text="hello", confidence=0.9, raw_text="hello", method="test", image_path="x.png")
    assert r.text == "hello"
    assert 0 <= r.confidence <= 1.0


def test_image_to_base64():
    """Test base64 encoding of a small test image."""
    import base64
    from PIL import Image
    import io
    from src.ingestion.ocr_pipeline import image_to_base64

    # Create a tiny in-memory PNG
    img = Image.new("RGB", (10, 10), color=(255, 0, 0))
    tmp_path = Path("tests") / "_test_img.png"
    tmp_path.parent.mkdir(exist_ok=True)
    img.save(str(tmp_path))

    try:
        b64 = image_to_base64(tmp_path)
        decoded = base64.b64decode(b64)
        assert len(decoded) > 0
    finally:
        if tmp_path.exists():
            tmp_path.unlink()


def test_ocr_no_api_key():
    """OCR should return failure gracefully with no API key."""
    import os
    from pathlib import Path
    from PIL import Image
    from src.ingestion.ocr_pipeline import ocr_with_gemini_vision

    # Create tiny test image
    img = Image.new("RGB", (100, 100), color=(200, 200, 200))
    tmp = Path("tests/_ocr_test.png")
    tmp.parent.mkdir(exist_ok=True)
    img.save(str(tmp))

    original = os.environ.pop("GEMINI_API_KEY", None)
    try:
        result = ocr_with_gemini_vision(tmp, api_key="")
        assert result.confidence == 0.0
        assert "FAILED" in result.text or "OCR" in result.text
    finally:
        if original:
            os.environ["GEMINI_API_KEY"] = original
        if tmp.exists():
            tmp.unlink()
