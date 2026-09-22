"""
Smoke tests for the validation layer - the one piece of the pipeline that
needs no external services (no OCR binary, no Groq key) to test, so it's a
good place to start when checking the project actually runs.

Run with: python -m pytest tests/
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.schemas import ExtractedField, ReviewStatus
from src.validation import score_field, cross_check_total


def test_high_confidence_number_is_auto_accepted():
    field = ExtractedField(
        field_name="total_amount", value="1250.00", confidence=0.95, source="llm", page_number=0
    )
    scored = score_field(field, expected_type="number")
    assert scored.review_status == ReviewStatus.AUTO_ACCEPTED


def test_malformed_date_drops_to_review():
    field = ExtractedField(
        field_name="invoice_date", value="not a date", confidence=0.9, source="ocr", page_number=0
    )
    scored = score_field(field, expected_type="date")
    assert scored.review_status == ReviewStatus.PENDING_REVIEW


def test_low_ocr_confidence_drops_to_review():
    field = ExtractedField(
        field_name="vendor_name", value="Acme Corp", confidence=0.4, source="ocr", page_number=0
    )
    scored = score_field(field)
    assert scored.review_status == ReviewStatus.PENDING_REVIEW


def test_cross_check_total_flags_mismatch():
    fields = [
        ExtractedField(field_name="item_1", value="50", confidence=0.9, source="llm", page_number=0),
        ExtractedField(field_name="item_2", value="50", confidence=0.9, source="llm", page_number=0),
        ExtractedField(field_name="total", value="500", confidence=0.9, source="llm", page_number=0),
    ]
    score = cross_check_total(fields, line_item_names=["item_1", "item_2"], total_name="total")
    assert score < 0.5  # 100 vs 500 is a big mismatch


if __name__ == "__main__":
    test_high_confidence_number_is_auto_accepted()
    test_malformed_date_drops_to_review()
    test_low_ocr_confidence_drops_to_review()
    test_cross_check_total_flags_mismatch()
    print("All smoke tests passed.")
