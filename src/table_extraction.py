"""
Stage 3: table structure extraction.

Uses pdfplumber's table finder, which preserves row/column structure instead
of flattening a table into linear text. Confidence here is a simple structural
heuristic (row-length consistency + non-empty cell ratio) since pdfplumber
doesn't emit per-cell confidence the way OCR does. Swap in camelot or
table-transformer here if you need better detection on complex/borderless
tables - the rest of the pipeline only depends on the TableExtraction shape.
"""
from __future__ import annotations

import pdfplumber

from .schemas import TableExtraction


def _structural_confidence(rows: list[list[str]]) -> float:
    if not rows:
        return 0.0
    col_counts = [len(r) for r in rows]
    mode_len = max(set(col_counts), key=col_counts.count)
    consistent_rows = sum(1 for c in col_counts if c == mode_len)
    row_consistency = consistent_rows / len(rows)

    total_cells = sum(col_counts)
    filled_cells = sum(1 for r in rows for c in r if c and c.strip())
    fill_ratio = filled_cells / total_cells if total_cells else 0.0

    return round(0.6 * row_consistency + 0.4 * fill_ratio, 3)


def extract_tables(file_path: str, page_number: int) -> list[TableExtraction]:
    tables = []
    with pdfplumber.open(file_path) as pdf:
        page = pdf.pages[page_number]
        for table in page.find_tables():
            rows = table.extract()
            rows = [[cell or "" for cell in row] for row in rows]
            tables.append(
                TableExtraction(
                    page_number=page_number,
                    rows=rows,
                    confidence=_structural_confidence(rows),
                    bbox=list(table.bbox),
                )
            )
    return tables


def table_to_markdown(table: TableExtraction) -> str:
    """Used to hand a table to the LLM as structured context instead of a wall
    of flattened text - the model reads column relationships correctly."""
    if not table.rows:
        return ""
    header, *body = table.rows
    lines = ["| " + " | ".join(header) + " |", "| " + " | ".join(["---"] * len(header)) + " |"]
    for row in body:
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)