"""
Human review queue. Run with: streamlit run app/review_ui.py

Shows every field currently sitting at review_status = pending_review, lowest
confidence first, so a reviewer works the riskiest pulls first instead of
scrolling through everything.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st

from src import storage

st.set_page_config(page_title="DocVerify Review Queue", layout="wide")
storage.init_db()

st.title("DocVerify — Human Review Queue")
st.caption("Low-confidence extractions only. Everything above the threshold was auto-accepted.")

rows = storage.get_pending_review_fields()

if not rows:
    st.success("Queue is empty — nothing below the confidence threshold right now.")
    st.stop()

st.write(f"{len(rows)} field(s) awaiting review, ordered by lowest confidence first.")

for row in rows:
    with st.container(border=True):
        col_source, col_form = st.columns([1, 1])

        with col_source:
            st.caption(f"{row['file_name']}  ·  page {row['page_number'] + 1}")
            st.write(f"**Field:** `{row['field_name']}`")
            st.caption(f"Source: {row['source']}")
            # In a full deployment, store the source file path per document and
            # crop the bbox region here with ocr_engine.render_page_to_image so
            # the reviewer sees the exact pixels the value came from.

        with col_form:
            current_value = json.loads(row["value"])
            st.metric("Confidence", f"{row['confidence']:.0%}")
            corrected_value = st.text_input(
                "Value", value=str(current_value), key=f"val_{row['id']}"
            )

            c1, c2 = st.columns(2)
            if c1.button("Confirm as-is", key=f"confirm_{row['id']}"):
                storage.update_field_value(row["id"], current_value, reviewer="reviewer", corrected=False)
                st.rerun()
            if c2.button("Save correction", key=f"save_{row['id']}"):
                storage.update_field_value(row["id"], corrected_value, reviewer="reviewer", corrected=True)
                st.rerun()

st.divider()
with st.expander("Audit trail for a document"):
    doc_id = st.text_input("Document ID")
    if doc_id:
        for event in storage.get_audit_trail(doc_id):
            st.write(
                f"`{event['timestamp']}` — **{event['field_name']}** "
                f"[{event['event_type']}]: {event['old_value']} → {event['new_value']}"
            )