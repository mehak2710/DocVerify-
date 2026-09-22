"""
Minimal CLI example. Real usage: define a Pydantic schema per document type
(invoice, receipt, ID card, purchase order, ...) and call process_document.

Example:
    python main.py sample_invoice.pdf
"""
import sys
import traceback

from pydantic import BaseModel

from src.pipeline import process_document


class InvoiceSchema(BaseModel):
    vendor_name: str | None = None
    invoice_number: str | None = None
    invoice_date: str | None = None
    total_amount: str | None = None


if __name__ == "__main__":
    print("main.py started", flush=True)

    if len(sys.argv) < 2:
        print("Usage: python main.py <path_to_pdf>", flush=True)
        sys.exit(1)

    file_path = sys.argv[1]
    print(f"Processing: {file_path}", flush=True)

    try:
        doc = process_document(
            file_path=file_path,
            file_name=file_path.split("/")[-1],
            schema=InvoiceSchema,
            field_types={"invoice_date": "date", "total_amount": "number"},
        )
    except Exception:
        print("Pipeline raised an exception:", flush=True)
        traceback.print_exc()
        sys.exit(1)

    print(f"\nDocument: {doc.file_name}  ({doc.document_format.value})", flush=True)
    print(f"Needs review: {doc.needs_review}\n", flush=True)

    if not doc.fields:
        print("No fields were extracted. Check that the LLM call is returning data.", flush=True)

    for f in doc.fields:
        flag = "REVIEW" if f.review_status.value == "pending_review" else "OK"
        try:
            print(f"  [{flag}]  {f.field_name}: {f.value!r}  (confidence {f.confidence:.2f})", flush=True)
        except UnicodeEncodeError:
            # Windows console sometimes can't print certain characters (e.g. £)
            safe_value = str(f.value).encode("ascii", errors="replace").decode("ascii")
            print(f"  [{flag}]  {f.field_name}: {safe_value!r}  (confidence {f.confidence:.2f})", flush=True)

    print("\nRun `streamlit run app/review_ui.py` to work the review queue.", flush=True)