# DocVerify — Multi-Modal Document RAG

A document intelligence pipeline that extracts structured data from messy real-world PDFs — digital, scanned, and mixed-format — using OCR + LLM extraction, with a validation layer that flags low-confidence extractions for human review instead of silently trusting them.

## Features

- **Multi-format ingestion** — automatically classifies each PDF as digital, scanned, or mixed, and routes pages accordingly (only scanned/mixed pages go through OCR)
- **OCR with per-field confidence** — Tesseract-based extraction (PaddleOCR supported as a swap-in) with a confidence score attached to every extracted value
- **Structured table extraction** — table rows and columns are preserved, not flattened into linear text
- **LLM-based field extraction** — Groq (Llama / GPT-OSS models) extracts fields into strict JSON matching a Pydantic schema
- **Validation layer** — blends OCR/LLM confidence, format-rule checks, and cross-checks (e.g. line items vs. total) into one score per field
- **Human review queue** — a Streamlit UI surfaces only low-confidence fields, lowest confidence first, for a human to confirm or correct
- **Full audit trail** — every auto-extraction, confirmation, and correction is logged to SQLite with a timestamp

## Pipeline

```
PDF / image
   │
   ▼
ingestion.py          classify: digital / scanned / mixed / image, route per page
   │
   ▼
ocr_engine.py          (scanned/mixed pages) Tesseract OCR + per-word confidence
table_extraction.py    detect tables, keep rows/columns structured
   │
   ▼
llm_extraction.py      Groq → JSON matching a Pydantic schema
   │
   ▼
validation.py          blend OCR confidence + rule checks + cross-checks
                        → auto_accepted  or  pending_review
   ▼
storage.py              SQLite: documents, fields, full audit log
app/review_ui.py        Streamlit queue for pending_review fields
                        → human_confirmed / human_corrected, logged to audit_log
```

An optional `vector_store.py` layer indexes extracted text into ChromaDB for semantic search across processed documents (off by default — see Known issues below).

## Tech stack

| Layer | Tool |
|---|---|
| PDF parsing | PyMuPDF, pdfplumber |
| OCR | Tesseract (pytesseract), PaddleOCR (optional) |
| Table extraction | pdfplumber |
| LLM extraction | Groq API (Llama 3.x / GPT-OSS) |
| Schema validation | Pydantic |
| Vector store (optional) | ChromaDB |
| Review UI | Streamlit |
| Storage | SQLite |

## Project structure

```
docverify/
├── main.py                   CLI entry point / usage example
├── requirements.txt
├── .env.example
├── src/
│   ├── config.py              thresholds, model, feature flags
│   ├── schemas.py             Pydantic models used throughout
│   ├── ingestion.py           format classification + routing
│   ├── ocr_engine.py          OCR with per-word confidence
│   ├── table_extraction.py    structured table extraction
│   ├── llm_extraction.py      Groq call, JSON-schema enforced
│   ├── validation.py          confidence blending + review logic
│   ├── storage.py             SQLite persistence + audit trail
│   ├── vector_store.py        optional ChromaDB indexing layer
│   └── pipeline.py            orchestrates all of the above
├── app/
│   └── review_ui.py           Streamlit human review queue
└── tests/
    └── test_validation.py
```

## How to run

**1. Install dependencies**
```bash
pip install -r requirements.txt
```

**2. Install Tesseract** (system binary, not a Python package)
- macOS: `brew install tesseract`
- Ubuntu/Debian: `sudo apt install tesseract-ocr`
- Windows: [installer here](https://github.com/UB-Mannheim/tesseract/wiki) — add the install folder to PATH afterward

**3. Set up environment variables**
```bash
cp .env.example .env
```
Add your `GROQ_API_KEY` (from [console.groq.com](https://console.groq.com)). To see which models your key can access:
```bash
python -c "from groq import Groq; import os; from dotenv import load_dotenv; load_dotenv(); [print(m.id) for m in Groq(api_key=os.getenv('GROQ_API_KEY')).models.list().data]"
```

**4. Run the pipeline on a document**
```bash
python main.py path/to/document.pdf
```

**5. Work the human review queue**
```bash
streamlit run app/review_ui.py
```

**6. Run tests**
```bash
python -m pytest tests/
```

### Using a custom schema

```python
from pydantic import BaseModel
from src.pipeline import process_document

class ReceiptSchema(BaseModel):
    merchant_name: str | None = None
    date: str | None = None
    total: str | None = None

doc = process_document(
    file_path="receipt.pdf",
    file_name="receipt.pdf",
    schema=ReceiptSchema,
    field_types={"date": "date", "total": "number"},
)
```
---
