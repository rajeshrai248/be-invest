"""LLM-backed extraction of broker fee records from text (PDF/HTML).

Uses OpenAI GPT-4o to convert extracted text into normalized FeeRecord rows
with evidence snippets, under strict JSON constraints. Results are cached by
content hash and model to avoid re-billing for identical inputs.
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
    from openai import OpenAI  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    OpenAI = None  # type: ignore

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
    # Optional keys we will default if missing
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
        f"- base_fee: number or null (strip currency symbols).\n"
        f"- variable_fee: verbatim string or null (keep percentage/tier text).\n"
        f"- currency: detected (default EUR if genuinely absent).\n"
        f"- evidence: <=160 chars verbatim (no paraphrase).\n"
        f"- page: integer if discernible else null.\n"
        f"- notes: null unless footnotes or multi-part fee need consolidation.\n"
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


def _split_semantic_chunks(text: str, max_len: int, max_chunks: int) -> List[str]:
    """Split text by semantic headers (fee-related keywords) while respecting size limits.

    Falls back to fixed slicing if no headers detected.
    """
    cleaned = text.replace("\r", "")
    lines = cleaned.split("\n")
    header_indices: List[int] = []
    for i, line in enumerate(lines):
        low = line.lower()
        if any(k in low for k in HEADER_KEYWORDS) and 0 < len(line) < 160:
            header_indices.append(i)
    if not header_indices:
        # fallback fixed-size slicing
        return [text[i : i + max_len] for i in range(0, min(len(text), max_len * max_chunks), max_len)]

    # Build chunks from header to next header
    chunks: List[str] = []
    for idx, start in enumerate(header_indices):
        end = header_indices[idx + 1] if idx + 1 < len(header_indices) else len(lines)
        segment = "\n".join(lines[start:end])
        # If segment too large, further slice
        if len(segment) > max_len:
            for i in range(0, min(len(segment), max_len * max_chunks), max_len):
                chunks.append(segment[i : i + max_len])
        else:
            chunks.append(segment)
        if len(chunks) >= max_chunks:
            break
    return chunks


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
    chunk_chars: int = 18000,
    max_chunks: int = 8,
    strict_mode: bool = False,
    focus_fee_lines: bool = True,
    max_focus_lines: int = 450,
) -> List[FeeRecord]:
    """Call OpenAI to extract fee records using the latest model (gpt-4o by default).

    Improvements over previous version:
    - Fixed missing Path import (cache instantiation).
    - Removed commented / invalid JSON example causing parse instability.
    - Added optional naive chunking to reduce truncation risk for large PDFs.
    - Stricter instructions: single instrument_type choice, composite fee handling.
    - Evidence retained succinctly in notes for downstream audit (until model extended).
    - Uses latest gpt-4o model for enhanced accuracy and reasoning.
    - Optimized for detailed fee extraction with better handling of complex fee structures.
    """

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
    # Chunk very large text to avoid losing tail sections; process sequentially and merge.
    raw_text = text.strip()
    if not raw_text:
        return []
    if len(raw_text) > chunk_chars:
        chunks = _split_semantic_chunks(raw_text, chunk_chars, max_chunks)
    else:
        chunks = [raw_text]

    all_records: List[FeeRecord] = []
    for idx, chunk in enumerate(chunks):
        # Optionally reduce chunk to only lines likely containing fees (currency/percent patterns)
        if focus_fee_lines:
            fee_lines: List[str] = []
            for ln in chunk.splitlines():
                low = ln.lower()
                if any(sym in low for sym in ["%", "eur", "€", "usd"]):
                    fee_lines.append(ln.strip())
                elif any(k in low for k in ["commission", "tarif", "fee", "kosten", "pricing"]):
                    fee_lines.append(ln.strip())
            # Deduplicate and cap
            unique_fee = []
            seen_line = set()
            for fl in fee_lines:
                if fl and fl not in seen_line:
                    seen_line.add(fl)
                    unique_fee.append(fl)
                if len(unique_fee) >= max_focus_lines:
                    break
            focused_text = "\n".join(unique_fee) if unique_fee else chunk
        else:
            focused_text = chunk
        messages = _make_prompt(broker, source_url, focused_text)
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_output_tokens,
                response_format={"type": "json_object"} if model.startswith("gpt-4o-") else None,
            )
            content = resp.choices[0].message.content if resp and resp.choices else ""
        except Exception as exc:  # pragma: no cover
            logger.info("OpenAI extraction failed (chunk %d): %s", idx, exc)
            continue

        parsed: Any
        try:
            parsed = json.loads(content)
        except Exception:
            start = content.find("[")
            end = content.rfind("]")
            parsed = json.loads(content[start : end + 1]) if start != -1 and end != -1 else []
        if isinstance(parsed, dict) and "results" in parsed:
            parsed = parsed.get("results")
        if not isinstance(parsed, list):
            parsed = []

        # Schema validation + composite fee post-process
        validated: List[Dict[str, Any]] = []
        for obj in parsed:
            if not isinstance(obj, dict):
                continue
            # Supply defaults for optional keys if absent
            for k in JSON_SCHEMA["optional"]:
                obj.setdefault(k, None)
            # Required keys present (allow null base/variable) & minimal broker/instrument non-empty
            if any(k not in obj for k in JSON_SCHEMA["required"]):
                continue
            broker_raw = str(obj.get("broker") or "").strip()
            if not broker_raw:
                continue
            itype = str(obj.get("instrument_type") or "").strip()
            if itype not in JSON_SCHEMA["instrument_type"]:
                continue
            # Order channel normalization
            och = str(obj.get("order_channel") or "Online Platform").strip()
            if och not in JSON_SCHEMA["order_channel"]:
                och = "Online Platform"
            obj["order_channel"] = och
            # Composite fee splitting pattern
            vf = obj.get("variable_fee")
            bf = obj.get("base_fee")
            if (bf in (None, "") or (isinstance(bf, str) and not bf.strip())) and isinstance(vf, str):
                m = re.match(r"^[€$]?([0-9]+(?:\.[0-9]+)?)\s*\+\s*([0-9]+(?:\.[0-9]+)?%)$", vf.strip())
                if m:
                    obj["base_fee"] = float(m.group(1))
                    obj["variable_fee"] = m.group(2)
            validated.append(obj)

        if strict_mode:
            filtered_objs: List[Dict[str, Any]] = []
            for o in validated:
                bf = o.get("base_fee")
                vf = o.get("variable_fee")
                keep = (bf not in (None, "")) or (isinstance(vf, str) and vf.strip())
                if keep:
                    filtered_objs.append(o)
            validated = filtered_objs

        chunk_records = [r for r in (_coerce_record(o) for o in validated) if r is not None]
        all_records.extend(chunk_records)

    # Deduplicate simple identical rows (without deep fuzzy matching)
    seen: set[str] = set()
    deduped: List[FeeRecord] = []
    for r in all_records:
        key = f"{r.broker}|{r.instrument_type}|{r.order_channel}|{r.base_fee}|{r.variable_fee}|{r.currency}"
        if key not in seen:
            seen.add(key)
            deduped.append(r)

    if cache:
        try:
            cache.put(cache_key, json.dumps([asdict(x) for x in deduped]).encode("utf-8"))
        except Exception:
            pass
    return deduped

