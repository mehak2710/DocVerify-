"""
Pydantic schemas for DocVerify.

These define the structured shapes that flow through the pipeline:
- a single extracted field (value + confidence + source)
- a full document extraction result
- the audit record produced once a field has been auto-extracted or reviewed
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class DocumentFormat(str, Enum):
    DIGITAL_PDF = "digital_pdf"       # has a real text layer
    SCANNED_PDF = "scanned_pdf"       # image-only pages, needs OCR
    MIXED_PDF = "mixed_pdf"           # some digital pages, some scanned
    IMAGE = "image"                   # a bare scanned image (png/jpg/tiff)


class ReviewStatus(str, Enum):
    AUTO_ACCEPTED = "auto_accepted"       # confidence high enough, no human needed
    PENDING_REVIEW = "pending_review"     # below threshold, sitting in the queue
    HUMAN_CONFIRMED = "human_confirmed"   # reviewer looked at it and agreed
    HUMAN_CORRECTED = "human_corrected"   # reviewer looked at it and changed it


class ExtractedField(BaseModel):
    """One field pulled out of a document, with everything needed to judge it."""

    field_name: str
    value: Any
    confidence: float = Field(ge=0.0, le=1.0)
    source: str = Field(description="'ocr', 'llm', or 'table'")
    page_number: int
    bbox: Optional[list[float]] = Field(
        default=None, description="[x0, y0, x1, y1] on the page, for source highlighting"
    )
    review_status: ReviewStatus = ReviewStatus.AUTO_ACCEPTED
    original_value: Optional[Any] = Field(
        default=None, description="value before any human correction, kept for the audit trail"
    )


class TableExtraction(BaseModel):
    page_number: int
    rows: list[list[str]]
    confidence: float = Field(ge=0.0, le=1.0)
    bbox: Optional[list[float]] = None


class DocumentExtraction(BaseModel):
    """Full result of running one document through the pipeline."""

    doc_id: str
    file_name: str
    document_format: DocumentFormat
    fields: list[ExtractedField] = Field(default_factory=list)
    tables: list[TableExtraction] = Field(default_factory=list)
    raw_text: str = ""
    needs_review: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)


class AuditEvent(BaseModel):
    doc_id: str
    field_name: str
    event_type: str  # "auto_extracted", "human_confirmed", "human_corrected"
    old_value: Optional[Any] = None
    new_value: Optional[Any] = None
    confidence: Optional[float] = None
    reviewer: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)