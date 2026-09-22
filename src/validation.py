"""
Stage 5: validation layer.

This is the piece that stops the pipeline from silently trusting a pull.
For every field it blends three independent signals into one confidence
score, and anything under the threshold gets review_status = PENDING_REVIEW:

  1. extraction confidence  - OCR mean confidence, or the LLM's self-rating
  2. rule confidence        - does the value satisfy basic type/format checks
  3. cross-check confidence - does it agree with a related field (e.g. line
                               items sum to the stated total)
"""
from __future__ import annotations

import re

from . import config
from .schemas import DocumentExtraction, ExtractedField, ReviewStatus

_DATE_RE = re.compile(r"\d{1,4}[/-]\d{1,2}[/-]\d{1,4}")
_NUMBER_RE = re.compile(r"^-?\d+(\.\d+)?$")


def _rule_confidence(field: ExtractedField, expected_type: str | None) -> float:
    """Cheap sanity checks - not a replacement for real business rules, just a
    first line of defense. Add domain-specific rules here per document type."""
    value = field.value
    if value in (None, ""):
        return 0.0

    if expected_type == "date":
        return 1.0 if _DATE_RE.search(str(value)) else 0.2
    if expected_type == "number":
        return 1.0 if _NUMBER_RE.match(str(value).replace(",", "")) else 0.2
    return 0.9  # free text: no strong rule to apply, mild default confidence


def cross_check_total(fields: list[ExtractedField], line_item_names: list[str], total_name: str) -> float:
    """Example cross-check: do extracted line items sum to the extracted total?
    Returns a confidence score (1.0 = matches, 0.0 = way off) to fold into the
    total field's blended confidence."""
    by_name = {f.field_name: f for f in fields}
    total_field = by_name.get(total_name)
    if not total_field:
        return 0.5

    try:
        total_value = float(str(total_field.value).replace(",", ""))
        line_sum = sum(
            float(str(by_name[name].value).replace(",", ""))
            for name in line_item_names
            if name in by_name and by_name[name].value not in (None, "")
        )
    except (ValueError, TypeError):
        return 0.3

    if total_value == 0:
        return 0.5
    diff_ratio = abs(total_value - line_sum) / total_value
    return max(0.0, 1.0 - diff_ratio)


def score_field(
    field: ExtractedField,
    expected_type: str | None = None,
    cross_check_score: float | None = None,
) -> ExtractedField:
    """Blend extraction, rule, and (optional) cross-check confidence, then set
    review_status based on config.CONFIDENCE_THRESHOLD."""
    rule_conf = _rule_confidence(field, expected_type)

    weights = {"extraction": 0.5, "rule": 0.3, "cross_check": 0.2}
    if cross_check_score is None:
        total_w = weights["extraction"] + weights["rule"]
        blended = (field.confidence * weights["extraction"] + rule_conf * weights["rule"]) / total_w
    else:
        blended = (
            field.confidence * weights["extraction"]
            + rule_conf * weights["rule"]
            + cross_check_score * weights["cross_check"]
        )

    field.confidence = round(blended, 3)
    field.review_status = (
        ReviewStatus.AUTO_ACCEPTED
        if field.confidence >= config.CONFIDENCE_THRESHOLD
        else ReviewStatus.PENDING_REVIEW
    )
    return field


def validate_document(doc: DocumentExtraction) -> DocumentExtraction:
    doc.needs_review = any(f.review_status == ReviewStatus.PENDING_REVIEW for f in doc.fields)
    return doc