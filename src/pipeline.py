"""
Pipeline orchestrator: ingestion -> OCR/table extraction -> LLM extraction ->
validation -> storage. This is the main entry point a caller uses.
"""
from __future__ import annotations

import uuid

from pydantic import BaseModel

from . import config, ingestion, llm_extraction, ocr_engine, storage, table_extraction
from .schemas import DocumentExtraction, DocumentFormat, ExtractedField
from .validation import score_field, validate_document


def process_document(
    file_path: str,
    file_name: str,
    schema: type[BaseModel],
    field_types: dict[str, str] | None = None,
) -> DocumentExtraction:
    """
    field_types: optional {"invoice_date": "date", "total_amount": "number"}
    used by the validation layer's rule checks. Free-text fields can be omitted.
    """
    field_types = field_types or {}
    doc_id = str(uuid.uuid4())
    doc_format = ingestion.classify_document(file_path)

    all_text_parts: list[str] = []
    fields: list[ExtractedField] = []

    n_pages = ingestion.page_count(file_path) if doc_format != DocumentFormat.IMAGE else 1

    for page_num in range(n_pages):
        needs_ocr = doc_format in (DocumentFormat.SCANNED_PDF, DocumentFormat.IMAGE) or (
            doc_format == DocumentFormat.MIXED_PDF and ingestion.page_needs_ocr(file_path, page_num)
        )

        if needs_ocr:
            page_text, ocr_confidence = ocr_engine.page_text_and_confidence(file_path, page_num)
        else:
            page_text = ingestion.extract_digital_text(file_path, page_num)
            ocr_confidence = 1.0  # digital text layer, no OCR uncertainty

        all_text_parts.append(page_text)

        tables = table_extraction.extract_tables(file_path, page_num) if doc_format != DocumentFormat.IMAGE else []
        page_tables_md = "\n\n".join(table_extraction.table_to_markdown(t) for t in tables)

        parsed, llm_confidence = llm_extraction.extract_fields(page_text, schema, page_tables_md)
        if parsed is None:
            continue

        extraction_confidence = min(ocr_confidence, llm_confidence) if needs_ocr else llm_confidence
        for name, value in parsed.model_dump().items():
            field = ExtractedField(
                field_name=name,
                value=value,
                confidence=extraction_confidence,
                source="ocr" if needs_ocr else "llm",
                page_number=page_num,
            )
            fields.append(score_field(field, expected_type=field_types.get(name)))

    doc = DocumentExtraction(
        doc_id=doc_id,
        file_name=file_name,
        document_format=doc_format,
        fields=fields,
        raw_text="\n".join(all_text_parts),
    )
    doc = validate_document(doc)

    storage.init_db()
    storage.save_document(doc)
    for f in doc.fields:
        storage.log_auto_extraction(doc_id, f)

    if config.ENABLE_VECTOR_INDEX:
        # imported lazily so a broken chromadb/onnxruntime install on the
        # machine can't take down the core extraction pipeline (see config.py)
        from . import vector_store

        vector_store.index_document(doc_id, file_name, doc.raw_text)

    return doc