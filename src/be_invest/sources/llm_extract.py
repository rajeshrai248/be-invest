"""LLM-backed extraction of broker fee records from text (PDF/HTML).

Uses OpenAI GPT-4o to convert extracted text into normalized FeeRecord rows
with evidence snippets, under strict JSON constraints. Results are cached by
content hash and model to avoid re-billing for identical inputs.
"""
from __future__ import annotations

import os
import json
import hashlib
from typing import Iterable, List, Optional, Dict, Any
from dataclasses import asdict
import logging

try:
    from openai import OpenAI  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    OpenAI = None  # type: ignore

from ..models import FeeRecord
from ..cache import SimpleCache

logger = logging.getLogger(__name__)


PROMPT_SYSTEM = (
    "You are a careful analyst extracting brokerage fee data into strict JSON. "
    "Do not guess; omit fields if not present. Include short evidence snippets and page numbers when possible."
)


def _make_prompt(broker: str, source_url: str, text: str) -> List[Dict[str, str]]:
    user = f"""
Extract broker fee records from the text below for broker: {broker}.
Source: {source_url}

Return ONLY a compact JSON array with objects like:
[
  {{
    "broker": "{broker}",
    "instrument_type": "Equities|ETFs|Options|Bonds|Funds",
    "order_channel": "Online Platform|Phone|Branch|Other",
    "base_fee": 0.0,           // number or null
    "variable_fee": "0.35%",  // string like "0.35%" or null
    "currency": "EUR|USD|...",
    "source": "{source_url}",
    "notes": null,
    "page": 1,                 // integer page number if known, else null
    "evidence": "verbatim short snippet supporting the numbers"
  }}
]

Rules:
- Do not invent values; leave fields null if not present.
- Keep evidence under 160 characters, verbatim from the text.
- Prefer EUR for Belgian brokers unless text states another currency.
- Map instrument types to the provided set when possible.

TEXT START
{text}
TEXT END
"""
    return [{"role": "system", "content": PROMPT_SYSTEM}, {"role": "user", "content": user}]


def _coerce_record(obj: Dict[str, Any]) -> Optional[FeeRecord]:
    try:
        broker = str(obj.get("broker") or "").strip()
        instrument_type = str(obj.get("instrument_type") or "").strip()
        order_channel = str(obj.get("order_channel") or "").strip() or "Online Platform"
        base_fee_val = obj.get("base_fee")
        base_fee = float(base_fee_val) if base_fee_val not in (None, "") else None
        variable_fee = str(obj.get("variable_fee")).strip() if obj.get("variable_fee") not in (None, "") else None
        currency = str(obj.get("currency") or "").strip() or "EUR"
        source = str(obj.get("source") or "").strip()
        notes = obj.get("notes")
        if isinstance(notes, str) and not notes.strip():
            notes = None
        # Evidence and page are ignored for FeeRecord but kept in notes if present
        page = obj.get("page")
        evidence = obj.get("evidence")
        if evidence:
            ev = str(evidence)[:200]
            notes = (f"evidence: {ev}; page: {page}" if page else f"evidence: {ev}") if not notes else f"{notes}; evidence: {ev}"

        if not broker or not instrument_type:
            return None

        return FeeRecord(
            broker=broker,
            instrument_type=instrument_type,
            order_channel=order_channel,
            base_fee=base_fee,
            variable_fee=variable_fee,
            currency=currency,
            source=source,
            notes=notes if isinstance(notes, (str, type(None))) else None,
        )
    except Exception:
        return None


def _hash_key(text: str, model: str, broker: str) -> str:
    return hashlib.sha256((model + "\n" + broker + "\n" + text).encode("utf-8")).hexdigest()


def extract_fee_records_via_openai(
    text: str,
    broker: str,
    source_url: str,
    *,
    model: str = "gpt-4o",
    api_key_env: str = "OPENAI_API_KEY",
    llm_cache_dir: Optional[os.PathLike] = None,
    max_output_tokens: int = 1500,
    temperature: float = 0.0,
) -> List[FeeRecord]:
    """Call OpenAI to extract fee records, with optional on-disk caching."""

    if not text.strip():
        return []

    api_key = os.getenv(api_key_env)
    if not api_key or OpenAI is None:
        logger.info("OpenAI not configured or SDK missing; skipping LLM extraction.")
        return []

    cache = SimpleCache(Path(llm_cache_dir), ttl_seconds=0) if llm_cache_dir else None
    cache_key = f"llm:{model}:{broker}:{_hash_key(text, model, broker)}"

    if cache:
        cached = cache.get(cache_key)
        if cached:
            try:
                raw = json.loads(cached.decode("utf-8"))
                return [r for r in (_coerce_record(o) for o in raw if isinstance(o, dict)) if r is not None]
            except Exception:
                pass

    client = OpenAI(api_key=api_key)
    messages = _make_prompt(broker, source_url, text[:120000])  # keep prompt size manageable

    try:
        resp = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_output_tokens,
            response_format={"type": "json_object"} if model.startswith("gpt-4o-" ) else None,
        )
        content = resp.choices[0].message.content if resp and resp.choices else ""
        # Some models return plain JSON array; others may return wrapped JSON
        parsed: Any
        try:
            parsed = json.loads(content)
        except Exception:
            # try to locate JSON array within content
            start = content.find("[")
            end = content.rfind("]")
            parsed = json.loads(content[start : end + 1]) if start != -1 and end != -1 else []
        if isinstance(parsed, dict) and "results" in parsed:
            parsed = parsed.get("results")
        if not isinstance(parsed, list):
            parsed = []
        records = [r for r in (_coerce_record(o) for o in parsed if isinstance(o, dict)) if r is not None]
        if cache:
            try:
                cache.put(cache_key, json.dumps(parsed).encode("utf-8"))
            except Exception:
                pass
        return records
    except Exception as exc:  # pragma: no cover - external call
        logger.info("OpenAI extraction failed: %s", exc)
        return []

