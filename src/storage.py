"""
Storage: persistence for documents, fields, and the audit trail
(auto-extracted vs human-confirmed vs human-corrected).

Plain sqlite3 rather than an ORM - the schema is small and stable, and this
keeps the project dependency-light. Swap DB_PATH for a DuckDB file in
config.py if you'd rather do analytical queries over extraction accuracy.
"""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime

from . import config
from .schemas import DocumentExtraction, ExtractedField

SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
    doc_id TEXT PRIMARY KEY,
    file_name TEXT,
    document_format TEXT,
    raw_text TEXT,
    needs_review INTEGER,
    created_at TEXT
);

CREATE TABLE IF NOT EXISTS fields (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    doc_id TEXT,
    field_name TEXT,
    value TEXT,
    confidence REAL,
    source TEXT,
    page_number INTEGER,
    bbox TEXT,
    review_status TEXT,
    original_value TEXT,
    FOREIGN KEY(doc_id) REFERENCES documents(doc_id)
);

CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    doc_id TEXT,
    field_name TEXT,
    event_type TEXT,
    old_value TEXT,
    new_value TEXT,
    confidence REAL,
    reviewer TEXT,
    timestamp TEXT
);
"""


@contextmanager
def get_conn():
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with get_conn() as conn:
        conn.executescript(SCHEMA)


def save_document(doc: DocumentExtraction) -> None:
    with get_conn() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO documents VALUES (?, ?, ?, ?, ?, ?)",
            (
                doc.doc_id,
                doc.file_name,
                doc.document_format.value,
                doc.raw_text,
                int(doc.needs_review),
                doc.created_at.isoformat(),
            ),
        )
        conn.execute("DELETE FROM fields WHERE doc_id = ?", (doc.doc_id,))
        for f in doc.fields:
            conn.execute(
                "INSERT INTO fields (doc_id, field_name, value, confidence, source, "
                "page_number, bbox, review_status, original_value) VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    doc.doc_id,
                    f.field_name,
                    json.dumps(f.value),
                    f.confidence,
                    f.source,
                    f.page_number,
                    json.dumps(f.bbox) if f.bbox else None,
                    f.review_status.value,
                    json.dumps(f.original_value) if f.original_value is not None else None,
                ),
            )


def get_pending_review_fields() -> list[sqlite3.Row]:
    with get_conn() as conn:
        cur = conn.execute(
            "SELECT f.*, d.file_name FROM fields f JOIN documents d ON f.doc_id = d.doc_id "
            "WHERE f.review_status = 'pending_review' ORDER BY f.confidence ASC"
        )
        return cur.fetchall()


def update_field_value(field_id: int, new_value, reviewer: str, corrected: bool) -> None:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM fields WHERE id = ?", (field_id,)).fetchone()
        old_value = json.loads(row["value"]) if row["value"] else None
        status = "human_corrected" if corrected else "human_confirmed"

        conn.execute(
            "UPDATE fields SET value = ?, review_status = ?, original_value = ? WHERE id = ?",
            (json.dumps(new_value), status, row["value"], field_id),
        )
        conn.execute(
            "INSERT INTO audit_log (doc_id, field_name, event_type, old_value, new_value, "
            "confidence, reviewer, timestamp) VALUES (?,?,?,?,?,?,?,?)",
            (
                row["doc_id"],
                row["field_name"],
                status,
                json.dumps(old_value),
                json.dumps(new_value),
                row["confidence"],
                reviewer,
                datetime.utcnow().isoformat(),
            ),
        )


def log_auto_extraction(doc_id: str, field: ExtractedField) -> None:
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO audit_log (doc_id, field_name, event_type, old_value, new_value, "
            "confidence, reviewer, timestamp) VALUES (?,?,?,?,?,?,?,?)",
            (
                doc_id,
                field.field_name,
                "auto_extracted",
                None,
                json.dumps(field.value),
                field.confidence,
                None,
                datetime.utcnow().isoformat(),
            ),
        )


def get_audit_trail(doc_id: str) -> list[sqlite3.Row]:
    with get_conn() as conn:
        cur = conn.execute(
            "SELECT * FROM audit_log WHERE doc_id = ? ORDER BY timestamp ASC", (doc_id,)
        )
        return cur.fetchall()