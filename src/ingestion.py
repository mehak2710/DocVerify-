"""
Stage 1: ingestion + routing.

Looks at a PDF (or image) and decides which extraction path it needs:
- digital PDF with a real text layer -> skip OCR, go straight to LLM extraction
- scanned pages (image only) -> OCR first
- mixed -> route page-by-page
"""
from __future__ import annotations

from pathlib import Path

import fitz  # PyMuPDF

from .schemas import DocumentFormat


def classify_document(file_path: str, min_chars_per_page: int = 20) -> DocumentFormat:
    """
    Heuristic: a page with a real text layer will yield a meaningful amount of
    extractable text via PyMuPDF. A scanned page yields ~nothing because the
    "text" is actually pixels.
    """
    path = Path(file_path)
    if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".tif", ".tiff"}:
        return DocumentFormat.IMAGE

    doc = fitz.open(file_path)
    page_has_text = []
    for page in doc:
        text = page.get_text("text")
        page_has_text.append(len(text.strip()) >= min_chars_per_page)
    doc.close()

    if all(page_has_text):
        return DocumentFormat.DIGITAL_PDF
    if not any(page_has_text):
        return DocumentFormat.SCANNED_PDF
    return DocumentFormat.MIXED_PDF


def page_needs_ocr(file_path: str, page_number: int, min_chars: int = 20) -> bool:
    """Per-page check, used by the pipeline when a document is MIXED_PDF."""
    doc = fitz.open(file_path)
    text = doc[page_number].get_text("text")
    doc.close()
    return len(text.strip()) < min_chars


def extract_digital_text(file_path: str, page_number: int) -> str:
    doc = fitz.open(file_path)
    text = doc[page_number].get_text("text")
    doc.close()
    return text


def page_count(file_path: str) -> int:
    doc = fitz.open(file_path)
    n = doc.page_count
    doc.close()
    return n