"""LLM-backed extraction of broker fee records from text (PDF/HTML).

Uses OpenAI GPT-4o or Anthropic Claude 3 Opus to convert extracted text into
normalized FeeRecord rows with evidence snippets, under strict JSON constraints.
Results are cached by content hash and model to avoid re-billing for identical inputs.
"""
from __future__ import annotations

import os
import json
import hashlib
import re
from dataclasses import asdict
from pathlib import Path
from typing import List, Optional, Dict, Any
import logging

try:
    from openai import OpenAI
except ImportError:  # pragma: no cover
    OpenAI = None  # type: ignore

try:
    from anthropic import Anthropic
except ImportError:  # pragma: no cover
    Anthropic = None  # type: ignore

from ..models import FeeRecord
from ..cache import SimpleCache

logger = logging.getLogger(__name__)


PROMPT_SYSTEM = (
    "You are a meticulous extraction engine. Return ONLY a JSON array of fee objects. "
    "Never include commentary. Never invent numbers. If a value is absent, use null. Choose ONE instrument_type from the allowed set."
)


ALLOWED_INSTRUMENTS = ["Equities", "ETFs", "Options", "Bonds", "Funds", "Futures"]

JSON_SCHEMA = {
    "required": [
        "broker",
        "instrument_type",
        "order_channel",
        "base_fee",
        "variable_fee",
        "currency",
        "source",
    ],
    "optional": ["notes", "page", "evidence"],
    "instrument_type": set(ALLOWED_INSTRUMENTS),
    "order_channel": {"Online Platform", "Phone", "Branch", "Other"},
}

HEADER_KEYWORDS = [
    "tarif", "tariff", "fee", "commission", "kosten", "charges", "pricing", "courtage"
]


def _make_prompt(broker: str, source_url: str, text: str) -> List[Dict[str, str]]:
    example = {
        "broker": broker,
        "instrument_type": "Equities",
        "order_channel": "Online Platform",
        "base_fee": 0.0,
        "variable_fee": "0.35%",
        "currency": "EUR",
        "source": source_url,
        "notes": None,
        "page": None,
        "evidence": "Short verbatim snippet"
    }
    instruction = (
        f"Extract brokerage fee records for broker '{broker}'. Source: {source_url}.\n"
        f"Return ONLY a JSON array (no wrapper object, no comments). Each element must have at least: broker, instrument_type, order_channel, base_fee, variable_fee, currency, source. Optional: notes, page, evidence.\n"
        f"Constraints:\n"
        f"- instrument_type: one of {ALLOWED_INSTRUMENTS}.\n"
        f"- order_channel: choose from ['Online Platform','Phone','Branch','Other'] or infer closest; default 'Online Platform'.\n"
        f"- base_fee: number or null (strip currency symbols). Use 0.0 for percentage-only fees or free trades.\n"
        f"- variable_fee: verbatim string or null (keep percentage/tier text). Examples: '0.25%', '0.35%', '1% Min. €40'.\n"
        f"- currency: detected (default EUR if genuinely absent).\n"
        f"- evidence: <=160 chars verbatim (no paraphrase).\n"
        f"- page: integer if discernible else null.\n"
        f"- notes: Use this field for:\n"
        f"  * Free trade allowances (e.g., 'Standard: 1 free order/month, Plus: 3 free orders/month')\n"
        f"  * Special conditions or footnotes\n"
        f"  * Multi-part fee explanations\n"
        f"  * Plan-specific variations\n"
        f"IMPORTANT for percentage-based fees:\n"
        f"- If commission is percentage-based (e.g., 0.25%), set base_fee=0.0 and variable_fee='0.25%'\n"
        f"- If there are free trades followed by percentage fees, include free trade info in notes\n"
        f"- Example: base_fee=0.0, variable_fee='0.25%', notes='1 free order/month for Standard plan'\n"
        f"If a composite fee like '€1 + 0.35%' appears, set base_fee to fixed numeric portion (1) and variable_fee to remainder ('0.35%').\n"
        f"Example single element (not exhaustive):\n{json.dumps(example, ensure_ascii=False)}\n"
        f"PDF TEXT BEGIN\n{text}\nPDF TEXT END"
    )
    return [
        {"role": "system", "content": PROMPT_SYSTEM},
        {"role": "user", "content": instruction},
    ]


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


def _split_semantic_chunks(text: str, max_len: int, max_chunks: int) -> List[str]:
    cleaned = text.replace("\r", "")
    lines = cleaned.split("\n")
    header_indices: List[int] = []
    for i, line in enumerate(lines):
        low = line.lower()
        if any(k in low for k in HEADER_KEYWORDS) and 0 < len(line) < 160:
            header_indices.append(i)
    if not header_indices:
        return [text[i : i + max_len] for i in range(0, min(len(text), max_len * max_chunks), max_len)]

    chunks: List[str] = []
    for idx, start in enumerate(header_indices):
        end = header_indices[idx + 1] if idx + 1 < len(header_indices) else len(lines)
        segment = "\n".join(lines[start:end])
        if len(segment) > max_len:
            for i in range(0, min(len(segment), max_len * max_chunks), max_len):
                chunks.append(segment[i : i + max_len])
        else:
            chunks.append(segment)
        if len(chunks) >= max_chunks:
            break
    return chunks


def extract_fee_records_via_llm(
    text: str,
    broker: str,
    source_url: str,
    *,
    model: str = "gpt-4o",
    llm_cache_dir: Optional[os.PathLike] = None,
    max_output_tokens: int = 2000,
    temperature: float = 0.0,
    chunk_chars: int = 18000,
    max_chunks: int = 8,
    strict_mode: bool = False,
    focus_fee_lines: bool = True,
    max_focus_lines: int = 450,
) -> List[FeeRecord]:
    """Call a large language model to extract fee records.

    Supports OpenAI (gpt-*) and Anthropic (claude-*) models.
    """
    if not text.strip():
        return []

    provider = "anthropic" if model.startswith("claude") else "openai"
    api_key_env = "ANTHROPIC_API_KEY" if provider == "anthropic" else "OPENAI_API_KEY"
    api_key = os.getenv(api_key_env)

    if not api_key or (provider == "openai" and OpenAI is None) or (provider == "anthropic" and Anthropic is None):
        logger.info("%s not configured or SDK missing; skipping LLM extraction.", provider.title())
        return []

    cache = SimpleCache(Path(llm_cache_dir), ttl_seconds=0) if llm_cache_dir else None
    cache_key = f"llm:{model}:{broker}:{_hash_key(text, model, broker)}"

    if cache and cache.get(cache_key):
        try:
            cached_data = json.loads(cache.get(cache_key).decode("utf-8"))
            return [r for r in (_coerce_record(o) for o in cached_data) if r]
        except Exception:
            pass  # Cache miss

    client: Any = Anthropic(api_key=api_key) if provider == "anthropic" else OpenAI(api_key=api_key)
    raw_text = text.strip()
    chunks = _split_semantic_chunks(raw_text, chunk_chars, max_chunks) if len(raw_text) > chunk_chars else [raw_text]

    all_records: List[FeeRecord] = []
    for idx, chunk in enumerate(chunks):
        if focus_fee_lines:
            fee_lines = [
                ln.strip() for ln in chunk.splitlines()
                if any(sym in ln.lower() for sym in ["%", "eur", "€", "usd"]) or
                   any(k in ln.lower() for k in ["commission", "tarif", "fee", "kosten", "pricing"])
            ]
            unique_fee = list(dict.fromkeys(fee_lines))[:max_focus_lines]
            focused_text = "\n".join(unique_fee) if unique_fee else chunk
        else:
            focused_text = chunk

        messages = _make_prompt(broker, source_url, focused_text)
        system_prompt = next((m["content"] for m in messages if m["role"] == "system"), "")
        user_prompt = next((m["content"] for m in messages if m["role"] == "user"), "")

        content = ""
        try:
            if provider == "anthropic":
                resp = client.messages.create(
                    model=model,
                    system=system_prompt,
                    messages=[{"role": "user", "content": user_prompt}],
                    temperature=temperature,
                    max_tokens=max_output_tokens,
                )
                content = resp.content[0].text if resp.content else ""
            else:  # openai
                resp = client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_output_tokens,
                    response_format={"type": "json_object"} if "json" in model else None,
                )
                content = resp.choices[0].message.content if resp.choices else ""
        except Exception as exc:
            logger.info("%s extraction failed (chunk %d): %s", provider.title(), idx, exc)
            continue

        # Post-process and validate JSON
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError:
            start, end = content.find("["), content.rfind("]")
            if start != -1 and end != -1:
                try:
                    parsed = json.loads(content[start : end + 1])
                except json.JSONDecodeError:
                    parsed = []
            else:
                parsed = []

        if isinstance(parsed, dict) and "results" in parsed:
            parsed = parsed.get("results", [])
        if not isinstance(parsed, list):
            continue

        validated: List[Dict[str, Any]] = []
        for obj in parsed:
            if not isinstance(obj, dict):
                continue
            for k in JSON_SCHEMA["optional"]:
                obj.setdefault(k, None)
            if any(k not in obj for k in JSON_SCHEMA["required"]) or not obj.get("broker") or not obj.get("instrument_type"):
                continue
            if obj.get("instrument_type") not in JSON_SCHEMA["instrument_type"]:
                continue
            obj["order_channel"] = obj.get("order_channel") or "Online Platform"
            if obj["order_channel"] not in JSON_SCHEMA["order_channel"]:
                obj["order_channel"] = "Online Platform"

            vf, bf = obj.get("variable_fee"), obj.get("base_fee")
            if (bf is None or bf == "") and isinstance(vf, str):
                m = re.match(r"^[€$]?([0-9]+(?:\.[0-9]+)?)\s*\+\s*([0-9]+(?:\.[0-9]+)?%)$", vf.strip())
                if m:
                    obj["base_fee"], obj["variable_fee"] = float(m.group(1)), m.group(2)
            validated.append(obj)

        if strict_mode:
            validated = [o for o in validated if o.get("base_fee") is not None or (isinstance(o.get("variable_fee"), str) and o.get("variable_fee").strip())]

        all_records.extend(r for r in (_coerce_record(o) for o in validated) if r)

    deduped = list(dict.fromkeys(all_records))

    if cache:
        try:
            cache.put(cache_key, json.dumps([asdict(x) for x in deduped]).encode("utf-8"))
        except Exception:
            pass
    return deduped
