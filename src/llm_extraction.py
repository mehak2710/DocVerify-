"""
Stage 4: LLM-based field extraction.

Sends page text (+ table markdown, if any) to Groq's Llama 3.x with a strict
JSON-schema prompt. The response is validated against a caller-supplied
Pydantic model - if it fails validation, we retry once with the error message
appended, then give up and let the validation layer flag the whole page for
review instead of guessing.
"""
from __future__ import annotations

import json

from groq import Groq
from pydantic import BaseModel, ValidationError

from . import config

_client: Groq | None = None


def _client_singleton() -> Groq:
    global _client
    if _client is None:
        _client = Groq(api_key=config.GROQ_API_KEY)
    return _client


def extract_fields(
    text: str,
    schema: type[BaseModel],
    tables_markdown: str = "",
    max_retries: int = 1,
) -> tuple[BaseModel | None, float]:
    """
    Returns (parsed_result, self_reported_confidence).

    self_reported_confidence comes from asking the model to rate its own
    extraction (0-1). It's a soft signal - always blended with OCR confidence
    and rule checks downstream in validation.py, never trusted alone.
    """
    if not text.strip() and not tables_markdown.strip():
        return None, 0.0

    schema_json = json.dumps(schema.model_json_schema(), indent=2)
    system_prompt = (
        "You extract structured data from document text into JSON that matches "
        "the given schema exactly. Only use information present in the text - "
        "never invent values. If a field isn't present, use null. "
        "Also include a top-level `_confidence` field (0-1) reflecting how sure "
        "you are that every value is correct and unambiguous.\n\n"
        f"Schema:\n{schema_json}"
    )
    user_prompt = f"Document text:\n{text}\n\n"
    if tables_markdown:
        user_prompt += f"Tables:\n{tables_markdown}\n\n"
    user_prompt += "Return only the JSON object, nothing else."

    client = _client_singleton()
    last_error = ""
    for attempt in range(max_retries + 1):
        prompt = user_prompt if attempt == 0 else f"{user_prompt}\n\nPrevious attempt failed validation: {last_error}"
        response = client.chat.completions.create(
            model=config.GROQ_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0,
        )
        raw = response.choices[0].message.content
        try:
            data = json.loads(raw)
            confidence = float(data.pop("_confidence", 0.5))
            parsed = schema.model_validate(data)
            return parsed, confidence
        except (json.JSONDecodeError, ValidationError) as e:
            last_error = str(e)
            continue

    return None, 0.0