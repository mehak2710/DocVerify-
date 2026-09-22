"""
Stage 2: OCR with per-field confidence.

Default backend is pytesseract because it needs no model download and installs
cleanly with `apt install tesseract-ocr`. PaddleOCR is supported as a drop-in
alternative - swap OCR_ENGINE in config.py - since it tends to do better on
low-quality scans, at the cost of a heavier install.
"""
from __future__ import annotations

from dataclasses import dataclass

import fitz
from PIL import Image

from . import config


@dataclass
class OCRWord:
    text: str
    confidence: float  # 0-1
    bbox: list[float]  # [x0, y0, x1, y1] in page coordinates
    page_number: int


def render_page_to_image(file_path: str, page_number: int, zoom: float = 2.0) -> Image.Image:
    """Rasterize a PDF page at a higher DPI - OCR accuracy drops fast on
    low-resolution renders. Works for images too (zoom is ignored there)."""
    if str(file_path).lower().endswith((".png", ".jpg", ".jpeg", ".tif", ".tiff")):
        return Image.open(file_path).convert("RGB")

    doc = fitz.open(file_path)
    page = doc[page_number]
    mat = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=mat)
    doc.close()
    return Image.frombytes("RGB", (pix.width, pix.height), pix.samples)


def _ocr_tesseract(image: Image.Image, page_number: int) -> list[OCRWord]:
    import pytesseract
    from pytesseract import Output

    data = pytesseract.image_to_data(image, output_type=Output.DICT)
    words = []
    for i, text in enumerate(data["text"]):
        if not text.strip():
            continue
        conf = float(data["conf"][i])
        if conf < 0:  # tesseract uses -1 for non-text regions
            continue
        x, y, w, h = data["left"][i], data["top"][i], data["width"][i], data["height"][i]
        words.append(
            OCRWord(
                text=text,
                confidence=conf / 100.0,
                bbox=[x, y, x + w, y + h],
                page_number=page_number,
            )
        )
    return words


def _ocr_paddleocr(image: Image.Image, page_number: int) -> list[OCRWord]:
    from paddleocr import PaddleOCR
    import numpy as np

    ocr = PaddleOCR(use_angle_cls=True, lang="en", show_log=False)
    result = ocr.ocr(np.array(image), cls=True)
    words = []
    for line in result[0] or []:
        box, (text, conf) = line
        xs = [p[0] for p in box]
        ys = [p[1] for p in box]
        words.append(
            OCRWord(
                text=text,
                confidence=float(conf),
                bbox=[min(xs), min(ys), max(xs), max(ys)],
                page_number=page_number,
            )
        )
    return words


def ocr_page(file_path: str, page_number: int) -> list[OCRWord]:
    image = render_page_to_image(file_path, page_number)
    if config.OCR_ENGINE == "paddleocr":
        return _ocr_paddleocr(image, page_number)
    return _ocr_tesseract(image, page_number)


def page_text_and_confidence(file_path: str, page_number: int) -> tuple[str, float]:
    """Convenience for the pipeline: full page text plus a single mean
    confidence, used as the OCR-side signal that feeds the validation layer."""
    words = ocr_page(file_path, page_number)
    if not words:
        return "", 0.0
    text = " ".join(w.text for w in words)
    mean_conf = sum(w.confidence for w in words) / len(words)
    return text, mean_conf