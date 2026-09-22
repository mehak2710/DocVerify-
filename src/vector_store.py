"""
Optional RAG layer: indexes each document's extracted text into ChromaDB so
content can be queried semantically across the whole document set - e.g.
"which invoices mention a late fee". This is separate from the extraction/
validation pipeline; a document only needs to be indexed here if you want
cross-document search on top of it.
"""
from __future__ import annotations

import chromadb

from . import config

_client = None


def _get_client():
    global _client
    if _client is None:
        _client = chromadb.PersistentClient(path=str(config.VECTOR_STORE_DIR))
    return _client


def get_collection():
    return _get_client().get_or_create_collection("docverify_documents")


def index_document(doc_id: str, file_name: str, text: str) -> None:
    if not text.strip():
        return
    collection = get_collection()
    # naive fixed-size chunking - fine for portfolio scope; swap for a
    # semantic chunker if documents get long
    chunk_size = 1000
    chunks = [text[i : i + chunk_size] for i in range(0, len(text), chunk_size)]
    collection.upsert(
        ids=[f"{doc_id}_{i}" for i in range(len(chunks))],
        documents=chunks,
        metadatas=[{"doc_id": doc_id, "file_name": file_name} for _ in chunks],
    )


def query(question: str, n_results: int = 5) -> list[dict]:
    collection = get_collection()
    results = collection.query(query_texts=[question], n_results=n_results)
    hits = []
    for doc, meta, dist in zip(
        results["documents"][0], results["metadatas"][0], results["distances"][0]
    ):
        hits.append({"text": doc, "file_name": meta["file_name"], "doc_id": meta["doc_id"], "distance": dist})
    return hits