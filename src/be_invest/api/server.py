from __future__ import annotations

from dotenv import load_dotenv
load_dotenv()

import hashlib
import ipaddress
import json
import logging
import os
import re
import shutil
import time
from datetime import datetime
from functools import wraps
from pathlib import Path
from typing import List, Optional, Dict, Any, Callable

from fastapi import FastAPI, HTTPException, Query, Body, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, HttpUrl

from langfuse.decorators import observe, langfuse_context

from ..config_loader import load_brokers_from_yaml
from ..models import Broker
from ..sources.scrape import scrape_fee_records
from ..sources.news_scrape import scrape_broker_news
from ..news import NewsFlash, save_news_flash, load_news, get_news_by_broker, delete_news_flash, get_recent_news, get_news_statistics
from ..utils.cache import FileCache
from ..validation.validator import validate_comparison_table, build_correction_prompt, patch_table_with_corrections
from ..validation.fee_calculator import (
    build_comparison_tables, BROKER_NOTES, load_fee_rules, save_fee_rules,
    get_rules_diff, FEE_RULES, FeeRule, HiddenCosts, HIDDEN_COSTS,
    _get_display_name, _build_broker_notes,
    calculate_fee, generate_explanation, BROKER_ALIASES, _ensure_rules_loaded,
)
from ..validation.persona_calculator import build_persona_comparison

# ========================================================================================
# PYDANTIC MODELS
# ========================================================================================

class NewsFlashRequest(BaseModel):
    """Request model for creating news flashes."""
    broker: str
    title: str
    summary: str
    url: Optional[HttpUrl] = None
    date: Optional[str] = None
    source: Optional[str] = None
    notes: Optional[str] = None


class NewsFlashResponse(BaseModel):
    """Response model for news flashes."""
    broker: str
    title: str
    summary: str
    url: Optional[str] = None
    date: Optional[str] = None
    source: Optional[str] = None
    notes: Optional[str] = None
    created_at: Optional[str] = None


class NewsDeleteRequest(BaseModel):
    """Request model for deleting news flashes."""
    broker: str
    title: str


class ChatMessage(BaseModel):
    """A single message in conversation history."""
    role: str
    content: str


class ChatRequest(BaseModel):
    """Request model for the chatbot endpoint."""
    question: str
    history: Optional[List[ChatMessage]] = None
    model: Optional[str] = None
    lang: Optional[str] = "en"


# ========================================================================================
# LANGUAGE SUPPORT
# ========================================================================================

LANGUAGE_MAP = {
    "en": "English",
    "fr-be": "French (Belgian)",
    "nl-be": "Dutch (Belgian)",
}


def _get_language_name(lang: str) -> str:
    """Map a language code to a full language name for LLM prompts."""
    return LANGUAGE_MAP.get(lang, "English")


# Static translations for persona definitions
_PERSONA_TRANSLATIONS: Dict[str, Dict[str, Dict[str, str]]] = {
    "fr-be": {
        "passive_investor": {
            "name": "Investisseur Passif",
            "description": "Achats mensuels d'ETF de 500 EUR. Stratégie d'achat et de conservation à long terme.",
        },
        "moderate_investor": {
            "name": "Investisseur Modéré",
            "description": "Combinaison d'achats d'ETF et d'actions. Gestion de portefeuille semi-active.",
        },
        "active_trader": {
            "name": "Trader Actif",
            "description": "Transactions fréquentes d'actions, y compris de grandes positions. Gestion active du portefeuille.",
        },
    },
    "nl-be": {
        "passive_investor": {
            "name": "Passieve Belegger",
            "description": "Maandelijkse ETF-aankopen van 500 EUR. Langetermijn buy-and-hold strategie.",
        },
        "moderate_investor": {
            "name": "Gematigde Belegger",
            "description": "Mix van ETF- en aandelenaankopen. Semi-actief portefeuillebeheer.",
        },
        "active_trader": {
            "name": "Actieve Handelaar",
            "description": "Frequente aandelentransacties inclusief grote posities. Actief portefeuillebeheer.",
        },
    },
}

# Static translation fragments for broker hidden cost notes
_NOTE_LABELS: Dict[str, Dict[str, str]] = {
    "en": {
        "custody": "Custody",
        "month": "month",
        "min": "min",
        "connectivity": "Connectivity",
        "exchange_year": "exchange/year",
        "subscription": "Subscription",
        "fx": "FX",
        "dividend_fee": "Dividend fee",
        "no_hidden": "No significant hidden costs",
    },
    "fr-be": {
        "custody": "Frais de garde",
        "month": "mois",
        "min": "min",
        "connectivity": "Connectivité",
        "exchange_year": "bourse/an",
        "subscription": "Abonnement",
        "fx": "Frais de change",
        "dividend_fee": "Frais de dividende",
        "no_hidden": "Pas de frais cachés significatifs",
    },
    "nl-be": {
        "custody": "Bewaarloon",
        "month": "maand",
        "min": "min",
        "connectivity": "Connectiviteit",
        "exchange_year": "beurs/jaar",
        "subscription": "Abonnement",
        "fx": "Wisselkoerskosten",
        "dividend_fee": "Dividendkosten",
        "no_hidden": "Geen significante verborgen kosten",
    },
}


def _build_localized_broker_notes(lang: str) -> Dict[str, str]:
    """Build broker notes from structured hidden costs using localized labels.

    Uses static translation labels instead of LLM. Falls back to English for
    unknown languages.
    """
    from ..validation.fee_calculator import HIDDEN_COSTS, _build_broker_notes
    if not HIDDEN_COSTS:
        return _build_broker_notes()

    labels = _NOTE_LABELS.get(lang, _NOTE_LABELS["en"])
    notes = {}

    for broker_name, costs in HIDDEN_COSTS.items():
        # If there's a raw notes string and lang is English, use it directly
        if lang == "en" and costs.notes:
            notes[broker_name] = costs.notes
            continue

        parts = []
        if costs.custody_fee_monthly_pct > 0:
            parts.append(f"{labels['custody']}: {costs.custody_fee_monthly_pct}%/{labels['month']} ({labels['min']} EUR{costs.custody_fee_monthly_min:.2f}/{labels['month']})")
        if costs.connectivity_fee_per_exchange_year > 0:
            parts.append(f"{labels['connectivity']}: EUR{costs.connectivity_fee_per_exchange_year:.2f}/{labels['exchange_year']}")
        if costs.subscription_fee_monthly > 0:
            parts.append(f"{labels['subscription']}: EUR{costs.subscription_fee_monthly:.2f}/{labels['month']}")
        if costs.fx_fee_pct > 0:
            parts.append(f"{labels['fx']}: {costs.fx_fee_pct}%")
        if costs.dividend_fee_pct > 0:
            parts.append(f"{labels['dividend_fee']}: {costs.dividend_fee_pct}%")
        if not parts:
            parts.append(labels["no_hidden"])

        notes[broker_name] = ". ".join(parts) + "."

    # Fallback statics for brokers with no hidden cost data
    from ..validation.fee_calculator import _build_broker_notes as _build_en_notes
    en_notes = _build_en_notes()
    for name, note in en_notes.items():
        if name not in notes:
            notes[name] = note

    return notes


# ========================================================================================
# FASTAPI APPLICATION
# ========================================================================================

app = FastAPI(title="be-invest PDF Text API", version="0.1.0")
logger = logging.getLogger(__name__)

# CORS: use CORS_ORIGINS env var for production (comma-separated), defaults to * for dev
_cors_origins = [o.strip() for o in os.getenv("CORS_ORIGINS", "*").split(",")]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=False,  # MUST be False with wildcard origins
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)

# Initialize caches
llm_cache = FileCache(Path("data/cache/llm"), default_ttl=7 * 24 * 3600)  # 7 days

# ========================================================================================
# RATE LIMITING & SECURITY
# ========================================================================================
# Track requests per IP to prevent reconnaissance and abuse
_ip_request_counts: Dict[str, List[float]] = {}
_RATE_LIMIT_WINDOW = 60  # seconds
_RATE_LIMIT_REQUESTS = 100  # max requests per window per IP
_RATE_LIMIT_SCANS = 10  # max suspicious requests (404s, invalid paths) per window per IP

_blocked_ips: Dict[str, float] = {}   # IP -> block-expiry timestamp
_BLOCK_DURATION = 600                  # 10 min ban
_ip_scan_counts: Dict[str, List[float]] = {}  # IP -> list of suspicious request timestamps

_VALID_PATH_PREFIXES = frozenset({
    "/health", "/cost-analysis", "/cost-comparison-tables",
    "/financial-analysis", "/brokers", "/summary",
    "/refresh-pdfs", "/refresh-and-analyze",
    "/news", "/chat", "/docs", "/openapi.json", "/redoc",
})


def _get_client_ip(request: Request) -> str:
    """Respect X-Forwarded-For for reverse proxy setups."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _is_private_ip(ip_str: str) -> bool:
    """Check if IP is localhost or RFC-1918 private."""
    try:
        return ipaddress.ip_address(ip_str).is_loopback or ipaddress.ip_address(ip_str).is_private
    except ValueError:
        return False


# ========================================================================================
# TIMING UTILITIES
# ========================================================================================

def time_api_call(func: Callable) -> Callable:
    """Decorator to log API call execution time."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        endpoint_name = func.__name__

        try:
            result = func(*args, **kwargs)
            duration = time.time() - start_time
            logger.info(f"[ENDPOINT] {endpoint_name} completed in {duration:.3f}s")
            return result
        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"[ENDPOINT_ERROR] {endpoint_name} failed after {duration:.3f}s: {str(e)}")
            raise

    return wrapper


@app.middleware("http")
async def rate_limit_and_log(request: Request, call_next):
    """Middleware to rate limit requests and log all HTTP requests."""
    start_time = time.time()
    method = request.method
    path = request.url.path
    query_string = request.url.query or ""
    client_ip = _get_client_ip(request)

    # Build URL string
    url_str = path
    if query_string:
        url_str += f"?{query_string}"

    # ====== BLOCKED IP CHECK ======
    if client_ip in _blocked_ips:
        if time.time() < _blocked_ips[client_ip]:
            return JSONResponse(status_code=403, content={"detail": "Forbidden"})
        else:
            del _blocked_ips[client_ip]

    # ====== RATE LIMITING ======
    current_time = time.time()

    # Initialize IP tracking if needed
    if client_ip not in _ip_request_counts:
        _ip_request_counts[client_ip] = []

    # Clean old entries outside the rate limit window
    _ip_request_counts[client_ip] = [
        req_time for req_time in _ip_request_counts[client_ip]
        if current_time - req_time < _RATE_LIMIT_WINDOW
    ]

    # Check if IP is scanning (making lots of 404s or probing invalid paths)
    path_lower = path.lower()
    query_lower = query_string.lower()
    is_suspicious_path = (
        path.startswith("/api/") or          # Probing for /api endpoints
        "cmd=" in query_string or            # Command injection attempt
        ".env" in path or                    # Trying to access config files
        "config" in path_lower or            # Trying to access config
        "admin" in path_lower or             # Trying to access admin endpoints
        "shell" in path_lower or             # Trying to access shell
        "exec" in path_lower or              # Trying to execute code
        "passwd" in path_lower or            # Password file probing
        "wp-" in path_lower or               # WordPress probing
        "phpmy" in path_lower or             # phpMyAdmin probing
        ".git" in path_lower or              # Git repo probing
        "base64" in query_lower or           # Encoded payload attempts
        "../" in path or                     # Path traversal
        "%2e%2e" in path_lower or            # URL-encoded path traversal
        not any(path.startswith(p) for p in _VALID_PATH_PREFIXES)  # Unknown path
    )

    # Count requests
    request_count = len(_ip_request_counts[client_ip])

    # Check if rate limit exceeded
    if request_count >= _RATE_LIMIT_REQUESTS:
        logger.warning(f"Rate limit exceeded for IP {client_ip}: {request_count} requests in {_RATE_LIMIT_WINDOW}s")
        return JSONResponse(
            status_code=429,
            content={"detail": "Too many requests. Please try again later."}
        )

    # Track and auto-block IPs with repeated suspicious requests
    if is_suspicious_path:
        logger.warning(f"SUSPICIOUS REQUEST from {client_ip}: {method} {url_str}")

        if client_ip not in _ip_scan_counts:
            _ip_scan_counts[client_ip] = []
        _ip_scan_counts[client_ip] = [
            t for t in _ip_scan_counts[client_ip]
            if current_time - t < _RATE_LIMIT_WINDOW
        ]
        _ip_scan_counts[client_ip].append(current_time)

        if len(_ip_scan_counts[client_ip]) >= _RATE_LIMIT_SCANS:
            _blocked_ips[client_ip] = current_time + _BLOCK_DURATION
            logger.warning(f"BLOCKED IP {client_ip} for {_BLOCK_DURATION}s after {len(_ip_scan_counts[client_ip])} suspicious requests")
            return JSONResponse(status_code=403, content={"detail": "Forbidden"})

    _ip_request_counts[client_ip].append(current_time)

    # ====== CALL ENDPOINT ======
    try:
        response = await call_next(request)
        duration = time.time() - start_time
        status_code = response.status_code

        # Log detailed request information
        log_msg = (
            f"API Request | Time: {duration*1000:.2f}ms | "
            f"{method} {url_str} | Status: {status_code} | "
            f"Client: {client_ip}"
        )

        if is_suspicious_path:
            logger.warning(log_msg)
        else:
            logger.info(log_msg)

        return response
    except Exception as e:
        duration = time.time() - start_time
        logger.error(
            f"API Error | Time: {duration*1000:.2f}ms | "
            f"{method} {url_str} | Error: {str(e)} | "
            f"Client: {client_ip}",
            exc_info=True
        )
        raise


news_cache = FileCache(Path("data/cache/news"), default_ttl=24 * 3600)  # 24 hours


def _default_output_dir() -> Path:
    """Resolve the output directory path."""
    cwd_path = Path("data") / "output"
    if cwd_path.exists():
        return cwd_path
    repo_root = Path(__file__).resolve().parents[3]
    fallback = repo_root / "data" / "output"
    return fallback


def _default_brokers_yaml() -> Path:
    """Resolve the brokers.yaml file path."""
    cwd_path = Path("data") / "brokers.yaml"
    if cwd_path.exists():
        return cwd_path
    repo_root = Path(__file__).resolve().parents[3]
    fallback = repo_root / "data" / "brokers.yaml"
    return fallback


@observe(as_type="generation")
def _call_llm(model: str, system_prompt: str, user_prompt: str, response_format: str = "json",
              temperature: Optional[float] = None, messages: Optional[List[dict]] = None) -> str:
    """
    Unified LLM caller supporting both OpenAI (gpt-*) and Anthropic (claude-*) models.

    Args:
        model: Model name (e.g., "gpt-4o", "claude-sonnet-4-20250514")
        system_prompt: System message content
        user_prompt: User message content
        response_format: "json" for JSON mode, "text" for regular text
        temperature: Optional temperature override (defaults to 0.0)
        messages: Optional list of message dicts; if provided, used instead of single user_prompt

    Returns:
        String response from the LLM
    """
    effective_temperature = temperature if temperature is not None else 0.0

    # Determine provider for metadata
    if model.startswith("gemini"):
        provider = "google"
    elif model.startswith("groq/"):
        provider = "groq"
    elif model.startswith("claude"):
        provider = "anthropic"
    else:
        provider = "openai"

    langfuse_context.update_current_observation(
        model=model,
        input={"system": system_prompt, "user": user_prompt},
        metadata={"provider": provider, "temperature": effective_temperature, "response_format": response_format},
    )
    if model.startswith("gemini"):
        # Use Google Generative AI SDK
        try:
            from google import genai as google_genai
            from google.genai import types as genai_types
        except ImportError:
            raise HTTPException(
                status_code=500,
                detail="Google GenAI SDK not installed. Run: pip install google-genai"
            )

        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise HTTPException(status_code=500, detail="GOOGLE_API_KEY not set.")

        client = google_genai.Client(api_key=api_key)

        logger.info(f"Calling Gemini model: {model}")

        try:
            config_kwargs = {"temperature": effective_temperature}
            if response_format == "json":
                config_kwargs["response_mime_type"] = "application/json"
            if system_prompt:
                config_kwargs["system_instruction"] = system_prompt

            # Build contents for Gemini
            if messages is not None:
                contents = []
                for msg in messages:
                    role = "model" if msg["role"] == "assistant" else msg["role"]
                    contents.append(genai_types.Content(role=role, parts=[genai_types.Part(text=msg["content"])]))
            else:
                contents = user_prompt

            response = client.models.generate_content(
                model=model,
                contents=contents,
                config=genai_types.GenerateContentConfig(**config_kwargs),
            )

            # Report token usage to Langfuse
            usage_meta = getattr(response, "usage_metadata", None)
            if usage_meta:
                langfuse_context.update_current_observation(
                    output=response.text,
                    usage={
                        "input": getattr(usage_meta, "prompt_token_count", 0),
                        "output": getattr(usage_meta, "candidates_token_count", 0),
                    },
                )
            else:
                langfuse_context.update_current_observation(output=response.text)

            return response.text

        except Exception as e:
            logger.error(f"Gemini API call failed: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Gemini API call failed: {str(e)}")

    elif model.startswith("groq/"):
        # Use Groq API (OpenAI-compatible)
        try:
            from openai import OpenAI
        except ImportError:
            raise HTTPException(
                status_code=500,
                detail="OpenAI SDK not installed. Run: pip install openai"
            )

        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise HTTPException(status_code=500, detail="GROQ_API_KEY not set.")

        client = OpenAI(api_key=api_key, base_url="https://api.groq.com/openai/v1")
        groq_model = model.removeprefix("groq/")

        logger.info(f"Calling Groq model: {groq_model}")

        try:
            if messages is not None:
                api_messages = [{"role": "system", "content": system_prompt}] + messages
            else:
                api_messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ]

            params = {
                "model": groq_model,
                "messages": api_messages,
                "temperature": effective_temperature,
            }

            if response_format == "json":
                params["response_format"] = {"type": "json_object"}

            response = client.chat.completions.create(**params)
            result_text = response.choices[0].message.content

            # Report token usage to Langfuse
            if response.usage:
                langfuse_context.update_current_observation(
                    output=result_text,
                    usage={
                        "input": response.usage.prompt_tokens,
                        "output": response.usage.completion_tokens,
                    },
                )
            else:
                langfuse_context.update_current_observation(output=result_text)

            return result_text

        except Exception as e:
            logger.error(f"Groq API call failed: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Groq API call failed: {str(e)}")

    elif model.startswith("claude"):
        # Use Anthropic API
        try:
            import anthropic
            import time
        except ImportError:
            raise HTTPException(
                status_code=500,
                detail="Anthropic SDK not installed. Run: pip install anthropic"
            )

        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise HTTPException(status_code=500, detail="ANTHROPIC_API_KEY not set.")

        client = anthropic.Anthropic(api_key=api_key)

        logger.info(f"🔄 Calling Anthropic model: {model}")

        # Retry logic with exponential backoff for rate limits
        max_retries = 3
        base_delay = 2.0

        for attempt in range(max_retries):
            try:
                # Claude doesn't have native JSON mode, so we add it to the prompt
                enhanced_user_prompt = user_prompt
                if response_format == "json":
                    enhanced_user_prompt += "\n\nIMPORTANT: Return ONLY valid JSON. No markdown, no explanations, no code blocks."

                # Use provided messages or build from user_prompt
                if messages is not None:
                    api_messages = messages
                else:
                    api_messages = [{"role": "user", "content": enhanced_user_prompt}]

                response = client.messages.create(
                    model=model,
                    max_tokens=4096,
                    temperature=effective_temperature,
                    system=system_prompt,
                    messages=api_messages,
                )

                response_text = response.content[0].text

                # Clean up any markdown formatting and common JSON issues Claude might add
                if response_format == "json":
                    # Remove markdown code blocks
                    if response_text.strip().startswith("```"):
                        lines = response_text.strip().split("\n")
                        if lines[0].startswith("```"):
                            lines = lines[1:]
                        if lines and lines[-1].strip().startswith("```"):
                            lines = lines[:-1]
                        response_text = "\n".join(lines).strip()

                    # Clean up common Claude JSON issues
                    response_text = response_text.strip()

                    # Remove any text before the first {
                    first_brace = response_text.find('{')
                    if first_brace > 0:
                        response_text = response_text[first_brace:]

                    # Remove any text after the last }
                    last_brace = response_text.rfind('}')
                    if last_brace > 0 and last_brace < len(response_text) - 1:
                        response_text = response_text[:last_brace + 1]

                    # Try to validate JSON and fix common issues
                    try:
                        json.loads(response_text)
                    except json.JSONDecodeError as json_error:
                        logger.warning(f"⚠️ Claude returned invalid JSON, attempting to fix: {json_error}")
                        # Try to fix common issues like unescaped quotes or trailing commas
                        # This is a basic attempt - if it fails, we'll let the calling function handle it
                        pass

                # Report token usage to Langfuse
                langfuse_context.update_current_observation(
                    output=response_text,
                    usage={
                        "input": response.usage.input_tokens,
                        "output": response.usage.output_tokens,
                    },
                )

                return response_text

            except anthropic.APIStatusError as e:
                if e.status_code not in (429, 529):
                    raise
                error_type = "Rate limit" if e.status_code == 429 else "Overloaded (529)"
                if attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt)  # Exponential backoff
                    logger.warning(f"⚠️ {error_type} hit (attempt {attempt + 1}/{max_retries}). Retrying in {delay}s...")
                    time.sleep(delay)
                    continue
                else:
                    logger.error(f"❌ {error_type} after {max_retries} attempts")
                    # Fallback to GPT-4o if rate limited/overloaded
                    logger.info("🔄 Falling back to GPT-4o due to API issues...")
                    langfuse_context.score_current_trace(name="required_fallback", value=1)
                    return _call_llm("gpt-4o", system_prompt, user_prompt, response_format,
                                     temperature=temperature, messages=messages)

            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"❌ Anthropic API call failed: {e}", exc_info=True)
                raise HTTPException(status_code=500, detail=f"Anthropic API call failed: {str(e)}")

    else:
        # Use OpenAI API (default for gpt-* models)
        try:
            from openai import OpenAI
        except ImportError:
            raise HTTPException(
                status_code=500,
                detail="OpenAI SDK not installed. Run: pip install openai"
            )

        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise HTTPException(status_code=500, detail="OPENAI_API_KEY not set.")

        client = OpenAI(api_key=api_key)

        logger.info(f"🔄 Calling OpenAI model: {model}")

        try:
            # Use provided messages or build from user_prompt
            if messages is not None:
                api_messages = [{"role": "system", "content": system_prompt}] + messages
            else:
                api_messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ]

            # OpenAI-specific parameters
            params = {
                "model": model,
                "messages": api_messages,
                "temperature": effective_temperature,
            }

            if response_format == "json":
                params["response_format"] = {"type": "json_object"}

            response = client.chat.completions.create(**params)
            result_text = response.choices[0].message.content

            # Report token usage to Langfuse
            if response.usage:
                langfuse_context.update_current_observation(
                    output=result_text,
                    usage={
                        "input": response.usage.prompt_tokens,
                        "output": response.usage.completion_tokens,
                    },
                )
            else:
                langfuse_context.update_current_observation(output=result_text)

            return result_text

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"❌ OpenAI API call failed: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"OpenAI API call failed: {str(e)}")


def _get_cost_analysis_data() -> Dict[str, Any]:
    """Helper to load the main cost analysis JSON."""
    output_dir = _default_output_dir()
    analysis_file = output_dir / "broker_cost_analyses.json"
    if not analysis_file.exists():
        raise HTTPException(
            status_code=404,
            detail="Cost analysis file not found. Run generate_exhaustive_summary.py first."
        )
    try:
        with open(analysis_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to load analysis file: {exc}")

def _get_cost_comparison_data() -> Dict[str, Any]:
    """Helper to load the cost comparison analysis JSON."""
    output_dir = _default_output_dir()
    analysis_file = output_dir / "cost_comparison_tables.json"
    if not analysis_file.exists():
        raise HTTPException(
            status_code=404,
            detail="Cost analysis file not found. Run generate_exhaustive_summary.py first."
        )
    try:
        with open(analysis_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to load analysis file: {exc}")


def _submit_groundedness_evaluation(
    endpoint: str,
    user_input: str,
    retrieved_context: str,
    generated_output: str,
) -> None:
    """
    Submit an async evaluation task for groundedness scoring.
    Logs results back to Langfuse trace AND creates evaluation record in Langfuse table.
    Does not block the response.
    """
    try:
        import threading
        from ..evaluation import evaluate_groundedness_sync, create_langfuse_evaluation

        # Get current trace ID from Langfuse context (must capture before thread starts)
        trace_id = None
        try:
            trace_id = langfuse_context.get_current_trace_id()
        except Exception:
            pass

        if not trace_id:
            logger.warning(f"⚠️ No Langfuse trace_id captured for {endpoint} — judge score won't appear on trace")

        def evaluate_and_score():
            """Inner function to run in background thread."""
            try:
                result = evaluate_groundedness_sync(
                    endpoint=endpoint,
                    user_input=user_input,
                    retrieved_context=retrieved_context,
                    generated_output=generated_output,
                )

                if result:
                    score = result.get("score", 0.0)
                    hallucinations = result.get("hallucinations", [])
                    grounded_facts = result.get("grounded_facts", [])
                    reasoning = result.get("reasoning", "")

                    # Create evaluation record in Langfuse via direct client
                    # (langfuse_context is not available in background threads)
                    eval_id = create_langfuse_evaluation(
                        endpoint=endpoint,
                        evaluation_result=result,
                        trace_id=trace_id,
                    )

                    logger.info(f"✅ Groundedness evaluation complete: score={score}, trace_id={trace_id}")

                    # Log detailed feedback for low scores
                    if score < 1.0:
                        logger.warning(
                            f"⚠️ [{endpoint}] Groundedness score={score} | "
                            f"Hallucinations ({len(hallucinations)}): {hallucinations} | "
                            f"Grounded facts ({len(grounded_facts)}): {grounded_facts}"
                        )
                        if reasoning:
                            logger.info(f"📝 [{endpoint}] Judge reasoning: {reasoning[:1000]}")
                else:
                    logger.warning(f"⚠️ Groundedness evaluation failed (no result)")
            except Exception as e:
                logger.warning(f"⚠️ Groundedness evaluation error: {e}")

        # Run in background thread to not block response
        thread = threading.Thread(target=evaluate_and_score, daemon=True)
        thread.start()

    except Exception as e:
        logger.warning(f"⚠️ Failed to submit groundedness evaluation: {e}")


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.options("/health")
@app.options("/cost-analysis")
@app.options("/cost-analysis/{broker_name}")
@app.options("/cost-comparison-tables")
@app.options("/financial-analysis")
@app.options("/brokers")
@app.options("/summary")
@app.options("/refresh-pdfs")
@app.options("/refresh-and-analyze")
@app.options("/news")
@app.options("/news/broker/{broker_name}")
@app.options("/news/recent")
@app.options("/news/statistics")
@app.options("/news/scrape")
@app.options("/chat")
async def options_handler():
    """Handle OPTIONS (preflight) requests for CORS."""
    return JSONResponse(
        content={"message": "OK"},
        headers={
            "Access-Control-Allow-Origin": ",".join(_cors_origins),
            "Access-Control-Allow-Methods": "GET, POST, DELETE, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, Authorization",
            "Access-Control-Max-Age": "3600",
        }
    )


@app.get("/cost-analysis", response_class=JSONResponse)
@time_api_call
def get_cost_analysis() -> Dict[str, Any]:
    """Get the comprehensive cost and charges analysis for all brokers."""
    return _get_cost_analysis_data()


@app.get("/cost-comparison-tables", response_class=JSONResponse)
@time_api_call
@observe(name="cost-comparison-tables")
def get_cost_comparison_tables(
        request: Request,
        model: str = Query("claude-sonnet-4-20250514", description="LLM to use for notes generation"),
        force: bool = Query(False, description="Force fresh generation, ignore cache"),
        lang: str = Query("en", description="Response language: en, fr-be, nl-be")
) -> Dict[str, Any]:
    """
    Generates three cost comparison tables for ETFs, Stocks, and Bonds.

    Fees are computed deterministically from fee rules (no LLM math).
    Notes and text labels are localized to the requested language.
    Set force=True to re-extract fee rules from broker_cost_analyses.json
    via LLM before building tables.
    """
    if force and not _is_private_ip(_get_client_ip(request)):
        logger.info(f"force=True ignored for public IP {_get_client_ip(request)}")
        force = False

    # Check cache first (unless force=True)
    cache_key = FileCache.make_key("cost_comparison", model, lang)
    if not force:
        cached = llm_cache.get(cache_key)
        if cached:
            logger.info(f"Returning cached cost comparison tables (lang={lang})")
            langfuse_context.update_current_observation(metadata={"model": model, "lang": lang, "force": force, "cache_hit": True})
            return cached

    langfuse_context.update_current_observation(metadata={"model": model, "lang": lang, "force": force, "cache_hit": False})
    cost_data = _get_cost_analysis_data()

    # Extract broker names
    broker_names = [name for name in cost_data.keys() if "error" not in cost_data.get(name, {})]

    if not broker_names:
        raise HTTPException(
            status_code=404,
            detail="No valid broker data found. Run /refresh-and-analyze first."
        )

    # When force=True, re-extract fee rules + hidden costs from broker_cost_analyses.json
    if force:
        logger.info(f"force=True: Re-extracting fee rules from broker_cost_analyses.json using {model}")
        try:
            old_rules = dict(FEE_RULES)
            new_rules = _extract_fee_rules_from_cost_data(cost_data, model)
            if new_rules:
                fee_rules_diff = get_rules_diff(old_rules, new_rules)
                if fee_rules_diff:
                    logger.info(f"Fee rules changed: {fee_rules_diff}")
                # Merge new rules into existing (don't clear — preserves rules
                # for any broker where extraction might have failed)
                FEE_RULES.update(new_rules)
                save_fee_rules(source="llm_extracted")
                logger.info(f"Re-extracted {len(new_rules)} fee rules and hidden costs for {len(HIDDEN_COSTS)} brokers")
            else:
                logger.warning("Fee rule extraction returned no rules, using existing rules")
        except Exception as e:
            logger.warning(f"Fee rule re-extraction failed (using existing rules): {e}")

    logger.info(f"Building deterministic fee tables for {len(broker_names)} brokers (lang={lang}): {', '.join(broker_names)}")

    # Build fee tables deterministically (no LLM needed)
    result = build_comparison_tables(broker_names)

    # Generate notes with localized labels (no LLM needed)
    hidden_cost_notes = _build_localized_broker_notes(lang)
    notes = {_get_display_name(name): hidden_cost_notes.get(_get_display_name(name), "") for name in broker_names}
    result["euronext_brussels"]["notes"] = notes

    # Add investor persona comparison
    persona_success = False
    try:
        persona_data = build_persona_comparison(broker_names)
        result["euronext_brussels"]["investor_personas"] = persona_data["investor_personas"]
        result["euronext_brussels"]["persona_definitions"] = persona_data["persona_definitions"]
        persona_success = True

        # Localize persona definitions for non-English
        if lang != "en":
            result["euronext_brussels"]["persona_definitions"] = _localize_persona_definitions(
                model, result["euronext_brussels"]["persona_definitions"], lang
            )
    except Exception as e:
        logger.warning(f"Persona calculation failed (non-fatal): {e}")

    # Count computed cells and analyze data quality
    cells_computed = 0
    cells_with_data = 0
    pricing_tiers_found = set()

    for asset_type in ["stocks", "etfs", "bonds"]:
        asset_data = result["euronext_brussels"].get(asset_type, {})
        for broker_name, broker_fees in asset_data.items():
            cells_computed += len(broker_fees)
            for tier_key, fee_value in broker_fees.items():
                if fee_value is not None and fee_value != 0:
                    cells_with_data += 1
                pricing_tiers_found.add(tier_key)

    # Calculate data completeness score
    data_completeness = (cells_with_data / cells_computed * 100) if cells_computed > 0 else 0

    # Determine source from loaded fee_rules.json
    source = "llm_re_extracted" if force else ("llm_extracted" if HIDDEN_COSTS else "default")

    # Pricing coverage analysis
    pricing_coverage = {
        "total_tiers": len(pricing_tiers_found),
        "brokers_covered": len(broker_names),
        "asset_types": ["stocks", "etfs", "bonds"]
    }

    result["_validation"] = {
        "method": "deterministic",
        "source": source,
        "cells_computed": cells_computed,
        "cells_with_data": cells_with_data,
        "data_completeness_pct": round(data_completeness, 2),
        "fee_rules_count": len(FEE_RULES),
        "hidden_costs_brokers": len(HIDDEN_COSTS),
        "lang": lang,
        "pricing_coverage": pricing_coverage,
        "persona_calculation_success": persona_success,
    }

    # Log metrics
    logger.info(f"Deterministic computation complete: {cells_computed} cells computed, {cells_with_data} with data (lang={lang})")
    logger.info(f"Data completeness: {data_completeness:.1f}% | Fee rules: {len(FEE_RULES)} | Hidden costs: {len(HIDDEN_COSTS)}")
    logger.info(f"Pricing coverage: {len(pricing_tiers_found)} tiers across {len(broker_names)} brokers")

    # Add trace metadata for Langfuse
    langfuse_context.update_current_observation(
        metadata={
            "model": model,
            "lang": lang,
            "force": force,
            "cache_hit": False,
            "cells_computed": cells_computed,
            "cells_with_data": cells_with_data,
            "data_completeness_pct": round(data_completeness, 2),
            "fee_rules_count": len(FEE_RULES),
            "hidden_costs_brokers": len(HIDDEN_COSTS),
            "pricing_tiers": len(pricing_tiers_found),
            "brokers_covered": len(broker_names),
            "source": source,
            "persona_success": persona_success,
        }
    )

    # Add scores for data quality evaluation
    langfuse_context.score_current_trace(name="data_completeness", value=data_completeness / 100)
    langfuse_context.score_current_trace(name="broker_coverage", value=len(broker_names) / 6)  # Assuming 6 is max brokers
    langfuse_context.score_current_trace(name="pricing_coverage", value=len(pricing_tiers_found) / 20)  # Assuming ~20 tiers is complete
    langfuse_context.score_current_trace(name="persona_calculation", value=1.0 if persona_success else 0.0)

    # Save the JSON response to output directory
    output_dir = _default_output_dir()
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "cost_comparison_tables.json"

    try:
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        logger.info(f"Saved cost comparison tables to: {output_path}")
    except Exception as save_error:
        logger.warning(f"Failed to save JSON response to file: {save_error}")

    # Cache the result
    llm_cache.set(cache_key, result)
    logger.info(f"Cached cost comparison tables (lang={lang})")

    # Submit async groundedness evaluation (doesn't block response)
    try:
        _submit_groundedness_evaluation(
            endpoint="cost-comparison-tables",
            user_input=f"Generate cost comparison tables for {len(broker_names)} brokers (lang={lang})",
            retrieved_context=json.dumps(cost_data, indent=2)[:50000],
            generated_output=json.dumps(result["euronext_brussels"], indent=2)[:50000],
        )
    except Exception as e:
        logger.warning(f"Failed to submit evaluation: {e}")

    return result


def _generate_broker_notes(model: str, cost_data: Dict[str, Any], broker_names: List[str], lang: str = "en") -> Dict[str, str]:
    """Generate broker notes (hidden costs narrative) via LLM.

    Falls back to BROKER_NOTES on any failure.
    """
    language_name = _get_language_name(lang)
    system_prompt = f"You are a financial analyst specializing in Belgian broker fees. Return ONLY valid JSON. Write all text in {language_name}."

    broker_list = ", ".join(broker_names)
    user_prompt = f"""Summarize hidden costs for each of these Belgian brokers: {broker_list}

For each broker, write a 1-2 sentence note in {language_name} about hidden costs NOT reflected in transaction fees:
- Custody/account fees
- Connectivity fees (per exchange/year)
- Currency exchange (FX) fees/margins
- Platform/subscription fees
- Dividend handling fees

Input data:
{json.dumps(cost_data, indent=2)[:8000]}

Return a JSON object mapping broker name to note string:
{{"Broker Name": "Note about hidden costs...", ...}}
"""

    try:
        response_text = _call_llm(model, system_prompt, user_prompt, response_format="json")
        notes = json.loads(response_text)
        if isinstance(notes, dict):
            # Ensure all broker names are present
            for name in broker_names:
                display = _get_display_name(name)
                if display not in notes:
                    notes[display] = BROKER_NOTES.get(display, "")
            return notes
    except Exception as e:
        logger.warning(f"LLM notes parsing failed: {e}")

    # Fallback
    return {_get_display_name(name): BROKER_NOTES.get(_get_display_name(name), "") for name in broker_names}


def _localize_persona_definitions(model: str, persona_defs: Dict[str, Any], lang: str) -> Dict[str, Any]:
    """Translate persona name and description fields using static translations.

    Keeps all numeric/structural fields unchanged. Falls back to English for unknown languages.
    """
    import copy
    localized = copy.deepcopy(persona_defs)

    for persona_key, persona_data in localized.items():
        trans = _PERSONA_TRANSLATIONS.get(lang, {}).get(persona_key)
        if trans:
            persona_data["name"] = trans["name"]
            persona_data["description"] = trans["description"]

    return localized


@app.get("/financial-analysis")
@time_api_call
@observe(name="financial-analysis")
def generate_financial_analysis(
        request: Request,
        model: str = Query("claude-sonnet-4-20250514", description="LLM to use: claude-sonnet-4-20250514 (default), gpt-4o"),
        force: bool = Query(False, description="Force fresh generation, ignore cache"),
        lang: str = Query("en", description="Response language: en, fr-be, nl-be")
) -> Dict[str, Any]:
    """
    Generate a comprehensive financial analysis comparing Belgian investment brokers.

    Returns structured JSON with:
    - Title and metadata
    - Executive summary
    - Detailed cost analysis by product type (ETFs, Stocks, Bonds)
    - Broker comparisons and recommendations
    - Market insights and trends
    - Investment scenarios

    Perfect for React/Vue/Angular apps to render with custom styling.
    """
    if force and not _is_private_ip(_get_client_ip(request)):
        logger.info(f"force=True ignored for public IP {_get_client_ip(request)}")
        force = False

    # Check cache first (unless force=True)
    cache_key = FileCache.make_key("financial_analysis", model, lang)
    if not force:
        cached = llm_cache.get(cache_key)
        if cached:
            logger.info(f"📦 Returning cached financial analysis for model: {model}, lang: {lang}")
            langfuse_context.update_current_observation(metadata={"model": model, "lang": lang, "force": force, "cache_hit": True})
            return cached

    langfuse_context.update_current_observation(metadata={"model": model, "lang": lang, "force": force, "cache_hit": False})
    language_name = _get_language_name(lang)

    # ... (existing logic continues)
    cost_data = _get_cost_comparison_data()

    # Extract broker names
    broker_names = [name for name in cost_data.keys() if "error" not in cost_data.get(name, {})]

    if not broker_names:
        raise HTTPException(
            status_code=404,
            detail="No valid broker data found. Run generate_exhaustive_summary.py first."
        )

    # Prepare comprehensive prompt for financial analysis
    system_prompt = f"""
    Act as a Senior Financial Analyst and Investment Journalist specializing in the Euronext Brussels market. I need a structured, evidence-based investment memo on [INSERT TICKER/COMPANY NAME HERE] designed for a modern financial application (mobile-first, scannable).

Your analysis must include:

The 'Lede': A 2-sentence executive summary of the current investment thesis.

Quantitative Evidence: Use LaTeX for financial formulas. Focus on Free Cash Flow (FCF), EBITDA margins, Net Debt/EBITDA, and P/E ratios relative to historical averages and peers.

The Belgian Context: Analyze specific local factors (e.g., Belgian withholding tax, index weighting in the BEL20, exposure to the Belgian economy/bonds).

Bull vs. Bear: Three distinct, data-backed points for both the upside and downside.

Valuation & Verdict: A clear rating (Buy/Hold/Sell) based on a specific valuation method (DCF or Peer Multiples).

Tone: Professional, skeptical, and objective. Avoid generic fluff; prioritize hard data.

IMPORTANT LANGUAGE INSTRUCTION: Generate ALL human-readable text content (titles, summaries, pros, cons, bestFor, cost evidence descriptions) in {language_name}. Keep broker names, currency symbols (EUR/€), JSON keys, and numerical values unchanged.
    """

    # Create explicit list of all brokers
    broker_list = ", ".join(broker_names)

    # Get current date for the analysis
    from datetime import datetime
    current_date = datetime.now().strftime('%B %d, %Y')

    user_prompt = f"""Generate a comprehensive financial analysis comparing ALL Belgian investment brokers.

    CRITICAL: You MUST include ALL {len(broker_names)} brokers in your analysis:
    {broker_list}

    BROKER DATA:
    {json.dumps(cost_data, indent=2)}

    ### CALCULATION RULES (STRICT):
    1. **Total Cost of Ownership (TCO)**: You MUST add ALL hidden fees to the transaction cost:
       - **Handling Fees**: e.g., Degiro's €1.00 per trade.
       - **Connectivity Fees**: e.g., Degiro's €2.50/year (amortize or add to annual totals).
       - **Custody Fees**: e.g., ING's % fee per month.
       - **Service Fees**: Any fixed monthly platform fees (e.g., Keytrade Pro if applicable, though usually free).
    2. **Profiles for Annual Cost**:
       - **Passive Investor (monthly500ETF)**: Buys €500 of ETFs once per month (12 trades/year). *Assumption: Core Selection if available, otherwise standard.*
       - **Active Trader**: Buys €2,500 of Stocks 10 times/month + €10,000 of Stocks 2 times/month (144 trades/year).

    ### OUTPUT STRUCTURE
    Return a SIMPLE JSON object. Keep all text strings short (max 150 chars).

    {{
      "metadata": {{
        "title": "Short catchy title (max 80 chars)",
        "subtitle": "Key insight (max 100 chars)",
        "publishDate": "{current_date}",
        "readingTimeMinutes": 12
      }},
      "executiveSummary": [
        "Finding 1 (max 150 chars)",
        "Finding 2 (max 150 chars)",
        "Finding 3 (max 150 chars)"
      ],
      "brokerComparisons": [
        {{
          "broker": "Name",
          "overallRating": 5,
          "etfRating": 5,
          "stockRating": 5,
          "pros": ["Pro 1", "Pro 2"],
          "cons": ["Con 1", "Con 2"],
          "bestFor": ["Buy & Hold", "Day Trading"]
        }}
        // ... Repeat for ALL brokers
      ],
      "cheapestPerTier": {{
        "stocks": {{
          "250": "Broker Name (€Cost)",
          "2500": "Broker Name (€Cost)",
          "10000": "Broker Name (€Cost)",
          "50000": "Broker Name (€Cost)"
        }},
        "etfs": {{
          "500": "Broker Name (€Cost)",
          "5000": "Broker Name (€Cost)"
        }}
      }},
      "costComparison": {{
        "passiveInvestor": [
          {{"broker": "Name", "annualCost": 0, "rank": 1}},
          // ... All brokers sorted by cost
        ],
        "activeTrader": [
          {{"broker": "Name", "annualCost": 100, "rank": 1}},
          // ... All brokers sorted by cost
        ]
      }},
      "costEvidence": {{
        "passiveInvestor": {{
          "Broker Name": "12 x (€0 fee + €1 handling) + €0 custody = €12/yr",
          "Another Broker": "12 x €5 fee = €60/yr"
        }},
        "activeTrader": {{
          "Broker Name": "120x(€3) + 24x(€10) + €2.50 conn = €602.50/yr"
        }}
      }}
    }}

    CRITICAL OUTPUT RULES:
    1. **Valid JSON Only**: No markdown formatting.
    2. **All Brokers**: Every list must contain exactly {len(broker_names)} entries.
    3. **Math Check**: Verify your "Active Trader" sums. (e.g. if fee is €3/trade, annual is ~€432, not €50).
    4. **Language**: All human-readable text values MUST be in {language_name}. JSON keys must remain in English.
    """

    try:
        logger.info(f"📊 Generating structured financial analysis using {model}...")

        # Call the unified LLM helper
        response_text = _call_llm(model, system_prompt, user_prompt, response_format="json")

        if not response_text or not response_text.strip():
            raise HTTPException(status_code=500, detail="LLM returned an empty response.")

        # Parse JSON response with retry on failure
        try:
            result = json.loads(response_text)
            langfuse_context.score_current_trace(name="json_valid", value=1)
        except json.JSONDecodeError as e:
            langfuse_context.score_current_trace(name="json_valid", value=0)
            logger.error(f"❌ JSON parsing failed: {e}")
            logger.error(f"Response preview: {response_text[:500]}")

            # If Claude failed, try with GPT-4o as fallback
            if model.startswith("claude"):
                logger.info("🔄 Retrying with GPT-4o due to JSON parsing failure...")
                langfuse_context.score_current_trace(name="required_fallback", value=1)
                try:
                    response_text = _call_llm("gpt-4o", system_prompt, user_prompt, response_format="json")
                    result = json.loads(response_text)
                    logger.info("✅ Successfully generated with GPT-4o fallback")
                except Exception as fallback_error:
                    logger.error(f"❌ Fallback to GPT-4o also failed: {fallback_error}")
                    raise HTTPException(status_code=500, detail=f"Failed to parse LLM response as JSON: {e}")
            else:
                raise HTTPException(status_code=500, detail=f"Failed to parse LLM response as JSON: {e}")

        # Validation - The response should be grouped by exchanges
        logger.info(f"🔍 Validating response structure...")

        if not isinstance(result, dict):
            raise ValueError("Response must be a JSON object")

        # Expected exchanges - at least one should be present
        found_exchanges = []
        total_broker_entries = 0
        pricing_data_completeness = 0
        all_tier_counts = {}
        fallback_used = False

        for exchange_key, exchange_data in result.items():
            if isinstance(exchange_data, dict):
                found_exchanges.append(exchange_key)

                # Check if this exchange has the expected structure
                if "stocks" in exchange_data or "etfs" in exchange_data:
                    logger.info(f"✅ Found valid exchange data for: {exchange_key}")

                    # Count and validate broker entries
                    tier_counts = {}
                    for asset_type in ["stocks", "etfs"]:
                        if asset_type in exchange_data and isinstance(exchange_data[asset_type], list):
                            total_broker_entries += len(exchange_data[asset_type])

                            # Validate each row has broker field
                            for row in exchange_data[asset_type]:
                                if not isinstance(row, dict) or "broker" not in row:
                                    logger.warning(f"Invalid row structure in {exchange_key}.{asset_type}")
                                    continue

                                # Check for transaction sizes (optional validation)
                                transaction_sizes = ["250", "500", "1000", "1500", "2000", "2500", "5000", "10000", "50000"]
                                missing_sizes = [size for size in transaction_sizes if size not in row]
                                if missing_sizes:
                                    logger.warning(f"Row for {row.get('broker', 'unknown')} in '{exchange_key}.{asset_type}' missing sizes: {missing_sizes}")
                                else:
                                    tier_counts[row.get('broker', 'unknown')] = len(transaction_sizes)

                    if tier_counts:
                        all_tier_counts[asset_type] = tier_counts
                        pricing_data_completeness = (len(tier_counts) / max(1, len(transaction_sizes))) * 100

        if not found_exchanges:
            raise ValueError("No valid exchange data found in response")

        logger.info(f"✅ Successfully generated comparison tables for {len(found_exchanges)} exchanges with {total_broker_entries} broker entries")

        # Save the JSON response to output directory
        output_dir = _default_output_dir()
        output_dir.mkdir(parents=True, exist_ok=True)

        # Create filename with timestamp and model name
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_model_name = re.sub(r'[^\w\-.]', '_', model)
        output_filename = f"financial_analysis_{safe_model_name}_{timestamp}.json"
        output_path = output_dir / output_filename

        try:
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(result, f, indent=2, ensure_ascii=False)
            logger.info(f"💾 Saved financial analysis to: {output_path}")
        except Exception as save_error:
            logger.warning(f"⚠️  Failed to save JSON response to file: {save_error}")

        # Cache the result
        llm_cache.set(cache_key, result)
        logger.info(f"💾 Cached financial analysis for model: {model}")

        # Add detailed tracing metadata
        langfuse_context.update_current_observation(
            output={
                "exchanges_found": len(found_exchanges),
                "broker_entries": total_broker_entries,
                "pricing_completeness_pct": round(pricing_data_completeness, 2),
            },
            metadata={
                "model": model,
                "lang": lang,
                "force": force,
                "cache_hit": False,
                "exchanges": found_exchanges,
                "total_broker_entries": total_broker_entries,
                "pricing_completeness": round(pricing_data_completeness, 2),
                "fallback_used": fallback_used,
                "output_file": output_filename,
            }
        )

        # Add quality scores
        langfuse_context.score_current_trace(name="response_validity", value=1.0)
        langfuse_context.score_current_trace(name="data_completeness", value=pricing_data_completeness / 100)
        langfuse_context.score_current_trace(name="broker_coverage", value=min(total_broker_entries / 50, 1.0))  # Normalized to 50 entries
        langfuse_context.score_current_trace(name="fallback_required", value=0.0 if not fallback_used else 1.0)

        # Submit async groundedness evaluation (doesn't block response)
        try:
            _submit_groundedness_evaluation(
                endpoint="financial-analysis",
                user_input=f"Generate financial analysis for {len(found_exchanges)} exchanges with {total_broker_entries} broker entries (lang={lang})",
                retrieved_context=json.dumps(cost_data, indent=2)[:50000],
                generated_output=json.dumps(result, indent=2)[:50000],
            )
        except Exception as e:
            logger.warning(f"Failed to submit evaluation: {e}")

        return result

    except json.JSONDecodeError as e:
        logger.error(f"❌ JSON parsing failed: {e}")
        logger.error(f"Response was: {response_text[:500]}")
        # Log fallback score
        langfuse_context.score_current_trace(name="response_validity", value=0.0)
        raise HTTPException(status_code=500, detail=f"Failed to parse LLM response as JSON: {e}")
    except Exception as e:
        logger.error(f"❌ Failed to generate financial analysis: {e}", exc_info=True)
        langfuse_context.score_current_trace(name="response_validity", value=0.0)
        raise HTTPException(status_code=500, detail=f"Failed to generate financial analysis: {e}")



@app.get("/brokers")
@time_api_call
def list_brokers() -> List[Dict[str, Any]]:
    path = _default_brokers_yaml()
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Brokers file not found: {path}")
    brokers: List[Broker] = load_brokers_from_yaml(path)
    return [b.dict() for b in brokers]


@app.post("/refresh-pdfs")
@time_api_call
def refresh_pdfs(
        request: Request,
        brokers_to_refresh: Optional[List[str]] = Query(None,
                                                        description="Specific brokers to refresh (if None, refreshes all)"),
        force: bool = Query(False, description="Ignore allowed_to_scrape flag if true"),
        save_dir: Optional[str] = Query(None,
                                        description="Directory to save extracted text (default: data/output/pdf_text)"),
) -> Dict[str, Any]:
    if force and not _is_private_ip(_get_client_ip(request)):
        logger.info(f"force=True ignored for public IP {_get_client_ip(request)}")
        force = False

    brokers_yaml = _default_brokers_yaml()
    if not brokers_yaml.exists():
        raise HTTPException(status_code=404, detail=f"Brokers file not found: {brokers_yaml}")

    all_brokers: List[Broker] = load_brokers_from_yaml(brokers_yaml)
    brokers_to_process = all_brokers

    if brokers_to_refresh:
        brokers_to_process = [
            b for b in all_brokers
            if b.name.lower() in [br.lower() for br in brokers_to_refresh]
        ]
        if not brokers_to_process:
            raise HTTPException(
                status_code=404,
                detail=f"No matching brokers found. Requested: {brokers_to_refresh}"
            )

    output_dir = Path(save_dir) if save_dir else _default_pdf_text_dir()
    output_dir.mkdir(parents=True, exist_ok=True)

    cleaned_files_count = 0
    for txt_file in output_dir.glob("*.txt"):
        try:
            txt_file.unlink()
            cleaned_files_count += 1
        except OSError as e:
            logger.warning("Error deleting old text file %s: %s", txt_file, e)
    if cleaned_files_count > 0:
        logger.info("Cleaned up %d old text files from %s", cleaned_files_count, output_dir)

    try:
        scraped_records = scrape_fee_records(
            brokers=brokers_to_process,
            force=force,
            pdf_text_dump_dir=output_dir,
            use_playwright=True
        )

        broker_summary = {}
        for record in scraped_records:
            broker_summary.setdefault(record.broker, 0)
            broker_summary[record.broker] += 1

        return {
            "status": "completed",
            "message": "Scraping process finished.",
            "records_found_by_broker": broker_summary,
            "total_records_found": len(scraped_records)
        }

    except Exception as e:
        logger.error("An error occurred during the scraping process.", exc_info=True)
        raise HTTPException(status_code=500, detail=f"An internal error occurred: {e}")


def _default_pdf_text_dir() -> Path:
    """Resolve the PDF text directory path."""
    cwd_path = Path("data") / "output" / "pdf_text"
    if cwd_path.exists():
        return cwd_path
    repo_root = Path(__file__).resolve().parents[3]
    fallback = repo_root / "data" / "output" / "pdf_text"
    return fallback


def _clear_pdf_text_dir(directory: Path, keep: Optional[List[str]] = None) -> None:
    """
    Remove all files and subdirectories in the PDF text directory.
    Optionally keep files named in `keep` (e.g. ['.gitkeep']).
    """
    if not directory.exists():
        return

    keep_set = set(keep or [])
    removed_count = 0

    try:
        for child in directory.iterdir():
            try:
                if child.name in keep_set:
                    continue

                if child.is_dir():
                    shutil.rmtree(child)
                    logger.info(f"🗑️  Removed directory: {child.name}")
                else:
                    child.unlink()
                    logger.info(f"🗑️  Removed file: {child.name}")
                removed_count += 1

            except Exception as exc:
                logger.warning(f"⚠️  Failed to remove {child}: {exc}")

        if removed_count > 0:
            logger.info(f"✅ Cleared {removed_count} old items from PDF text directory")
        else:
            logger.info("📂 PDF text directory was already empty")

    except Exception as exc:
        logger.error(f"❌ Error clearing PDF text directory: {exc}")


@app.get("/cost-analysis/{broker_name}")
@time_api_call
def get_broker_cost_analysis(broker_name: str) -> Dict[str, Any]:
    output_dir = _default_output_dir()
    analysis_file = output_dir / "broker_cost_analyses.json"

    if not analysis_file.exists():
        raise HTTPException(
            status_code=404,
            detail="Cost analysis not found. Run generate_exhaustive_summary.py first."
        )

    try:
        with open(analysis_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        if broker_name not in data:
            raise HTTPException(
                status_code=404,
                detail=f"Broker not found: {broker_name}. Available: {', '.join(data.keys())}"
            )

        return {
            "broker": broker_name,
            "analysis": data[broker_name]
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to load analysis: {str(exc)}")


@app.get("/summary")

@time_api_call
def get_summary() -> str:
    output_dir = _default_output_dir()
    summary_file = output_dir / "exhaustive_cost_charges_summary.md"

    if not summary_file.exists():
        raise HTTPException(
            status_code=404,
            detail="Summary not found. Run generate_exhaustive_summary.py first."
        )

    try:
        with open(summary_file, "r", encoding="utf-8") as f:
            content = f.read()
        return content
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to load summary: {str(exc)}")


@app.post("/refresh-and-analyze")
@time_api_call
@observe(name="refresh-and-analyze")
def refresh_and_analyze(
        request: Request,
        brokers_to_process: Optional[List[str]] = Query(None,
                                                        description="Specific brokers to analyze (if None, analyzes all)"),
        force: bool = Query(False, description="Ignore allowed_to_scrape flag if true"),
        model: str = Query("claude-sonnet-4-20250514", description="LLM model: claude-sonnet-4-20250514 (default), gpt-4o, etc."),
) -> Dict[str, Any]:
    """
    Refresh PDFs, extract text, and generate comprehensive cost analysis.
    This endpoint combines /refresh-pdfs with LLM-based analysis generation.

    Supports both OpenAI (gpt-*) and Anthropic (claude-*) models.
    """
    import time

    if force and not _is_private_ip(_get_client_ip(request)):
        logger.info(f"force=True ignored for public IP {_get_client_ip(request)}")
        force = False

    langfuse_context.update_current_observation(metadata={"model": model, "force": force})

    logger.info("=" * 80)
    logger.info("🚀 REFRESH AND ANALYZE REQUEST")
    logger.info("=" * 80)

    # Step 1: Load brokers
    brokers_yaml = _default_brokers_yaml()
    if not brokers_yaml.exists():
        raise HTTPException(status_code=404, detail=f"Brokers file not found: {brokers_yaml}")

    all_brokers: List[Broker] = load_brokers_from_yaml(brokers_yaml)
    brokers_list = all_brokers

    if brokers_to_process:
        brokers_list = [
            b for b in all_brokers
            if b.name.lower() in [br.lower() for br in brokers_to_process]
        ]
        if not brokers_list:
            raise HTTPException(
                status_code=404,
                detail=f"No matching brokers found. Requested: {brokers_to_process}"
            )

    logger.info(f"📋 Processing {len(brokers_list)} broker(s): {', '.join(b.name for b in brokers_list)}")

    # Step 2: Clear old PDF text files and prepare output directory
    output_dir = _default_pdf_text_dir()

    logger.info("🧹 Clearing old PDF text files...")
    _clear_pdf_text_dir(output_dir, keep=[".gitkeep"])

    output_dir.mkdir(parents=True, exist_ok=True)

    logger.info(f"📥 Downloading PDFs and extracting text to: {output_dir}")

    refresh_start = time.time()
    try:
        scraped_records = scrape_fee_records(
            brokers=brokers_list,
            force=force,
            pdf_text_dump_dir=output_dir,
            use_llm=True,
            llm_model=model,
        )

        refresh_duration = time.time() - refresh_start

        broker_summary = {}
        for record in scraped_records:
            broker_summary.setdefault(record.broker, 0)
            broker_summary[record.broker] += 1

        refresh_results = {
            "status": "completed",
            "duration_seconds": round(refresh_duration, 2),
            "records_found_by_broker": broker_summary,
            "total_records_found": len(scraped_records)
        }

        logger.info(f"✅ PDF refresh completed in {refresh_duration:.2f}s")

    except Exception as e:
        logger.error(f"❌ PDF refresh failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"PDF refresh failed: {e}")

    # Step 3: Load extracted texts
    logger.info("📂 Loading extracted PDF texts...")

    def get_text_filename_for_broker_source(broker_name: str, ds_description: str, url: str) -> str:
        """Recreate the exact filename generated by the scraper."""
        safe_broker_name = re.sub(r'[\s/]+', '_', broker_name)
        safe_desc = re.sub(r'[\s/]+', '_', ds_description or 'document')
        url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
        return f"{safe_broker_name}_{safe_desc}_{url_hash}.txt"

    pdf_texts = {}
    for broker in brokers_list:
        if not broker.data_sources:
            continue

        broker_texts = []
        for ds in broker.data_sources:
            if not ds.url:
                continue

            expected_filename = get_text_filename_for_broker_source(broker.name, ds.description, ds.url)
            text_file_path = output_dir / expected_filename

            if text_file_path.exists():
                try:
                    content = text_file_path.read_text(encoding="utf-8")
                    if content.strip():
                        broker_texts.append({
                            "filename": text_file_path.name,
                            "content": content,
                            "size": len(content)
                        })
                        logger.info(f"  📄 {broker.name}: {text_file_path.name} ({len(content):,} chars)")
                except Exception as e:
                    logger.error(f"  ❌ Failed to read {text_file_path.name}: {e}")

        if broker_texts:
            pdf_texts[broker.name] = broker_texts

    logger.info(f"✅ Loaded texts for {len(pdf_texts)} broker(s)")

    if not pdf_texts:
        raise HTTPException(
            status_code=500,
            detail="No PDF texts extracted. Check broker data sources and allowed_to_scrape flags."
        )

    # Step 4: Run LLM analysis
    logger.info(f"🤖 Running LLM analysis using {model}...")

    all_analyses = {}
    analysis_start = time.time()

    for broker_name, texts in pdf_texts.items():
        combined_text = "\n\n".join(t["content"] for t in texts)
        logger.info(f"  🔍 Analyzing {broker_name} ({len(combined_text):,} chars)...")

        analysis_prompt = f"""Extract ALL broker fees from the following tariffs for {broker_name}.
Return ONLY a valid JSON object with structured fee data.

{combined_text[:15000]}
"""

        system_prompt = "You are a financial analyst. Return ONLY valid JSON, no explanations."

        try:
            # Use unified LLM caller (supports both OpenAI and Claude)
            response_text = _call_llm(model, system_prompt, analysis_prompt, response_format="json")

            if not response_text or not response_text.strip().startswith('{'):
                logger.error(f"  ❌ Invalid response for {broker_name}")
                langfuse_context.score_current_trace(name="json_valid", value=0)
                all_analyses[broker_name] = {"error": "Invalid LLM response"}
            else:
                try:
                    analysis = json.loads(response_text)
                    langfuse_context.score_current_trace(name="json_valid", value=1)
                    all_analyses[broker_name] = analysis
                    logger.info(f"  ✅ {broker_name} analysis complete")
                except json.JSONDecodeError:
                    langfuse_context.score_current_trace(name="json_valid", value=0)
                    all_analyses[broker_name] = {"error": "Invalid JSON from LLM"}

        except Exception as e:
            logger.error(f"  ❌ Analysis failed for {broker_name}: {e}")
            all_analyses[broker_name] = {"error": str(e)}

    analysis_duration = time.time() - analysis_start
    logger.info(f"✅ LLM analysis completed in {analysis_duration:.2f}s")

    # Step 5: Save results
    json_output_path = _default_output_dir() / "broker_cost_analyses.json"
    logger.info(f"💾 Saving analysis to: {json_output_path}")

    try:
        with open(json_output_path, "w", encoding="utf-8") as f:
            json.dump(all_analyses, f, indent=2, ensure_ascii=False)
        logger.info("✅ Analysis saved successfully")
    except Exception as e:
        logger.error(f"❌ Failed to save analysis: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to save analysis: {e}")

    # Step 6: Extract fee rules from freshly scraped data (per-broker)
    fee_rules_diff = []
    try:
        old_rules = dict(FEE_RULES)
        new_rules = _extract_fee_rules_from_cost_data(all_analyses, model)
        if new_rules:
            fee_rules_diff = get_rules_diff(old_rules, new_rules)
            if fee_rules_diff:
                logger.info(f"Fee rules changed: {fee_rules_diff}")
            # Merge new rules into existing (preserves rules for brokers that weren't scraped)
            FEE_RULES.update(new_rules)
            save_fee_rules(source="llm_extracted")
            logger.info(f"Saved {len(FEE_RULES)} fee rules and {len(HIDDEN_COSTS)} hidden cost entries")
    except Exception as e:
        logger.warning(f"Fee rule extraction failed (non-fatal): {e}")

    # Return comprehensive results
    logger.info("=" * 80)
    logger.info("REFRESH AND ANALYZE COMPLETE")
    logger.info("=" * 80)

    response_data = {
        "status": "completed",
        "refresh_results": refresh_results,
        "analysis_results": {
            "brokers_analyzed": len(all_analyses),
            "duration_seconds": round(analysis_duration, 2),
            "model_used": model,
            "analyses": all_analyses
        },
        "output_file": str(json_output_path),
    }

    if fee_rules_diff:
        response_data["fee_rules_changes"] = fee_rules_diff

    # Submit async groundedness evaluation (doesn't block response)
    try:
        _submit_groundedness_evaluation(
            endpoint="refresh-and-analyze",
            user_input=f"Refresh and analyze fee rules for {len(brokers_succeeded)} brokers",
            retrieved_context=json.dumps({"refresh_results": refresh_results}, indent=2)[:50000],
            generated_output=json.dumps({"analyses": all_analyses}, indent=2)[:50000],
        )
    except Exception as e:
        logger.warning(f"Failed to submit evaluation: {e}")

    return response_data


def _extract_fee_rules_from_cost_data(cost_data: Dict[str, Any], model: str) -> Optional[Dict[tuple, FeeRule]]:
    """Extract structured fee rules + hidden costs from broker cost analysis data via LLM.

    Processes each broker individually to avoid truncation issues.
    Returns a dict of FeeRule objects, or None if extraction fails for all brokers.
    Also populates HIDDEN_COSTS global registry.
    """
    system_prompt = "You are a financial data extractor specializing in Belgian broker fee structures. Return ONLY valid JSON."

    all_rules: Dict[tuple, FeeRule] = {}
    brokers_succeeded = []
    brokers_failed = []

    for broker_name, broker_data in cost_data.items():
        if not isinstance(broker_data, dict) or "error" in broker_data:
            logger.warning(f"Skipping {broker_name}: invalid or error data")
            continue

        logger.info(f"Extracting fee rules for {broker_name}...")

        user_prompt = f"""Extract ALL fee rules and hidden costs for {broker_name} on Euronext Brussels.

Extract:
1. TRADING RULES: The exact fee structure with pattern type and all tier thresholds
2. HIDDEN COSTS: Custody fees, connectivity fees, FX fees, dividend fees, subscription fees

Input data for {broker_name}:
{json.dumps(broker_data, indent=2)}

Return a JSON object with EXACTLY this structure:

{{
  "rules": [
    {{
      "broker": "{broker_name}",
      "instrument": "stocks",
      "pattern": "pattern_type",
      "tiers": [...],
      "handling_fee": 0.0
    }}
  ],
  "hidden_costs": {{
    "{broker_name}": {{
      "custody_fee_monthly_pct": 0.0,
      "custody_fee_monthly_min": 0.0,
      "connectivity_fee_per_exchange_year": 0.0,
      "connectivity_fee_max_pct_account": 0.0,
      "subscription_fee_monthly": 0.0,
      "fx_fee_pct": 0.0,
      "handling_fee_per_trade": 0.0,
      "dividend_fee_pct": 0.0,
      "dividend_fee_min": 0.0,
      "dividend_fee_max": 0.0,
      "notes": "Brief description of hidden costs"
    }}
  }}
}}

PATTERN TYPES (use exactly these strings):
- "flat": Simple flat fee for all amounts (e.g., Degiro EUR2 + EUR1 handling)
- "tiered_flat": Multiple flat fee tiers by amount (only up_to tiers, no slice)
- "tiered_flat_then_slice": Flat tiers for small amounts, per-slice for larger amounts (Bolero, Keytrade, Rebel)
- "percentage_with_min": Percentage rate with minimum fee (ING, Revolut)
- "base_plus_slice": Single base fee threshold + per-slice for remainder

TIER TYPES:
- {{"flat": 2.00}} - simple flat fee
- {{"up_to": 2500, "fee": 7.50}} - flat fee for amounts up to threshold
- {{"per_slice": 10000, "fee": 15.00}} - per-started-slice (no up_to means it applies after all flat tiers)
- {{"per_slice": 10000, "fee": 15.00, "max_fee": 50.00}} - per-slice with fee cap
- {{"rate": 0.0035, "min_fee": 1.00}} - percentage rate with minimum

IMPORTANT:
- Extract ALL tiers from the data. Many brokers have 4-5 tiers, not just 2.
- Include "max_fee" on the per_slice tier if the broker caps total commission.
- Include rules for stocks, etfs, AND bonds where the data is available.
- Use exact broker name: {broker_name}
- Extract the STANDARD fee schedule, not promotional or conditional rates.
  For example, Degiro has a "Core Selection" of ETFs with zero commission, but
  the standard ETF fee on Euronext Brussels is EUR2 + EUR1 handling (same as stocks).
  Always use the standard/default rate that applies to ALL instruments of that type.
- A rule where ALL fees are EUR 0.00 is almost certainly wrong. If fees appear
  to be zero, double-check whether a separate handling fee or commission applies.
"""

        try:
            response_text = _call_llm(model, system_prompt, user_prompt, response_format="json")
            data = json.loads(response_text)
            rules_list = data.get("rules", [])

            broker_rule_count = 0
            for rule_dict in rules_list:
                broker = rule_dict.get("broker", "")
                instrument = rule_dict.get("instrument", "")
                if not broker or not instrument:
                    continue
                rule = FeeRule(
                    broker=broker,
                    instrument=instrument,
                    pattern=rule_dict.get("pattern", "unknown"),
                    tiers=rule_dict.get("tiers", []),
                    handling_fee=rule_dict.get("handling_fee", 0.0),
                    min_fee=rule_dict.get("min_fee"),
                    max_fee=rule_dict.get("max_fee"),
                )
                all_rules[(broker.lower(), instrument.lower())] = rule
                broker_rule_count += 1

            # Load hidden costs for this broker
            hidden_costs_data = data.get("hidden_costs", {})
            for hc_name, costs_dict in hidden_costs_data.items():
                if isinstance(costs_dict, dict):
                    HIDDEN_COSTS[hc_name] = HiddenCosts(
                        custody_fee_monthly_pct=costs_dict.get("custody_fee_monthly_pct", 0.0),
                        custody_fee_monthly_min=costs_dict.get("custody_fee_monthly_min", 0.0),
                        connectivity_fee_per_exchange_year=costs_dict.get("connectivity_fee_per_exchange_year", 0.0),
                        connectivity_fee_max_pct_account=costs_dict.get("connectivity_fee_max_pct_account", 0.0),
                        subscription_fee_monthly=costs_dict.get("subscription_fee_monthly", 0.0),
                        fx_fee_pct=costs_dict.get("fx_fee_pct", 0.0),
                        handling_fee_per_trade=costs_dict.get("handling_fee_per_trade", 0.0),
                        dividend_fee_pct=costs_dict.get("dividend_fee_pct", 0.0),
                        dividend_fee_min=costs_dict.get("dividend_fee_min", 0.0),
                        dividend_fee_max=costs_dict.get("dividend_fee_max", 0.0),
                        notes=costs_dict.get("notes", ""),
                    )

            # QA check: warn if any extracted rule produces 0 for all sizes
            from ..validation.fee_calculator import _compute_from_tiers, TRANSACTION_SIZES as TS
            for (bk, ik), rule in list(all_rules.items()):
                if bk == broker_name.lower():
                    all_zero = all(
                        _compute_from_tiers(rule.tiers, amt, rule.handling_fee, rule.max_fee) == 0.0
                        for amt in TS
                    )
                    if all_zero:
                        langfuse_context.score_current_trace(name="all_zero_fees", value=1)
                        logger.warning(
                            f"  QA WARNING: {rule.broker} {rule.instrument} extracted with all-zero fees. "
                            f"Tiers: {rule.tiers}. This rule will be skipped."
                        )
                        del all_rules[(bk, ik)]
                        broker_rule_count -= 1

            brokers_succeeded.append(broker_name)
            logger.info(f"  {broker_name}: extracted {broker_rule_count} rules")

        except Exception as e:
            brokers_failed.append(broker_name)
            logger.warning(f"  {broker_name}: extraction failed: {e}")

    logger.info(
        f"Fee rule extraction complete: {len(all_rules)} rules from "
        f"{len(brokers_succeeded)} brokers. Failed: {brokers_failed or 'none'}"
    )

    if all_rules:
        return all_rules

    return None


# ========================================================================================
# NEWS FLASH ENDPOINTS
# ========================================================================================

@app.post("/news/scrape")
@time_api_call
@observe(name="news-scrape")
def scrape_news_endpoint(
    request: Request,
    brokers_to_scrape: Optional[List[str]] = Query(None, description="Specific brokers to scrape (if None, scrapes all with news_sources)"),
    force: bool = Query(False, description="Force fresh scrape, ignore cache"),
) -> Dict[str, Any]:
    """
    Automatically scrape news from broker websites, RSS feeds, and APIs.

    Set force=True to bypass cache and perform fresh scrape.
    """
    import time

    if force and not _is_private_ip(_get_client_ip(request)):
        logger.info(f"force=True ignored for public IP {_get_client_ip(request)}")
        force = False

    start_time = time.time()

    try:
        # Check cache first (unless force=True)
        cache_key = FileCache.make_key("news_scrape", ",".join(brokers_to_scrape) if brokers_to_scrape else "all")
        if not force:
            cached = news_cache.get(cache_key)
            if cached:
                logger.info(f"📦 Returning cached news scrape results")
                cached["duration_seconds"] = round(time.time() - start_time, 2)
                cached["from_cache"] = True

                # Add tracing for cache hit
                langfuse_context.update_current_observation(
                    metadata={
                        "force": force,
                        "cache_hit": True,
                        "brokers_requested": brokers_to_scrape,
                        "cached_items": cached.get("total_scraped", 0),
                    }
                )
                langfuse_context.score_current_trace(name="cache_efficiency", value=1.0)

                return cached

        # Load brokers configuration
        brokers_yaml = _default_brokers_yaml()
        if not brokers_yaml.exists():
            raise HTTPException(status_code=404, detail=f"Brokers file not found: {brokers_yaml}")

        all_brokers = load_brokers_from_yaml(brokers_yaml)

        # Filter brokers if specified
        if brokers_to_scrape:
            brokers_to_process = [
                b for b in all_brokers
                if b.name.lower() in [name.lower() for name in brokers_to_scrape]
            ]
            if not brokers_to_process:
                raise HTTPException(
                    status_code=404,
                    detail=f"No brokers found matching: {brokers_to_scrape}"
                )
        else:
            # Only process brokers that have news_sources configured
            brokers_to_process = [b for b in all_brokers if b.news_sources]

        if not brokers_to_process:
            response = {
                "status": "no_news_sources",
                "message": "No brokers have news_sources configured",
                "brokers_checked": len(all_brokers),
                "duration_seconds": round(time.time() - start_time, 2)
            }
            return response

        logger.info("=" * 80)
        logger.info("📰 AUTOMATED NEWS SCRAPING STARTED")
        logger.info("=" * 80)
        logger.info(f"🎯 Brokers to process: {[b.name for b in brokers_to_process]} (force={force})")

        # Perform the scraping
        scraped_news = scrape_broker_news(brokers_to_process, force=force)

        # Group results by broker for summary
        broker_summary = {}
        error_summary = {}

        for broker in brokers_to_process:
            broker_news_count = len([n for n in scraped_news if n.broker == broker.name])
            if broker_news_count > 0:
                broker_summary[broker.name] = broker_news_count

            # Check for any news sources that might have failed
            if broker.news_sources:
                sources_attempted = len([s for s in broker.news_sources if s.allowed_to_scrape or force])
                if sources_attempted > 0 and broker_news_count == 0:
                    error_summary[broker.name] = f"No news found from {sources_attempted} source(s)"

        duration = round(time.time() - start_time, 2)

        logger.info("=" * 80)
        logger.info("✅ AUTOMATED NEWS SCRAPING COMPLETED")
        logger.info("=" * 80)
        logger.info(f"📊 Total news items: {len(scraped_news)}")
        logger.info(f"⏱️ Duration: {duration}s")

        # Convert news items to response format
        news_items_response = [
            {
                "broker": news.broker,
                "title": news.title,
                "summary": news.summary[:150] + "..." if len(news.summary) > 150 else news.summary,
                "url": news.url,
                "date": news.date,
                "source": news.source
            }
            for news in scraped_news
        ]

        # Calculate metrics for tracing
        scrape_success_rate = (len(broker_summary) / len(brokers_to_process) * 100) if brokers_to_process else 0
        news_items_per_broker = len(scraped_news) / max(len(broker_summary), 1) if broker_summary else 0
        error_count = len(error_summary)

        response = {
            "status": "success",
            "message": f"Successfully scraped {len(scraped_news)} news items from {len(broker_summary)} brokers",
            "news_by_broker": broker_summary,
            "news_items": news_items_response,  # Add actual news items with URLs
            "total_scraped": len(scraped_news),
            "brokers_with_news": len(broker_summary),
            "brokers_processed": len(brokers_to_process),
            "duration_seconds": duration,
            "from_cache": False
        }

        if error_summary:
            response["warnings"] = error_summary

        # Cache the result
        news_cache.set(cache_key, response)

        # Add tracing metadata
        langfuse_context.update_current_observation(
            output={
                "total_news_items": len(scraped_news),
                "brokers_with_news": len(broker_summary),
                "scrape_success_rate": round(scrape_success_rate, 1),
                "avg_items_per_broker": round(news_items_per_broker, 2),
            },
            metadata={
                "force": force,
                "brokers_requested": brokers_to_scrape,
                "brokers_processed": len(brokers_to_process),
                "brokers_with_news": len(broker_summary),
                "total_news_items": len(scraped_news),
                "errors": error_count,
                "duration_seconds": duration,
                "cache_hit": False,
                "scrape_success_rate_pct": round(scrape_success_rate, 1),
            }
        )

        # Add quality scores
        langfuse_context.score_current_trace(name="scrape_coverage", value=scrape_success_rate / 100)
        langfuse_context.score_current_trace(name="news_volume", value=min(len(scraped_news) / 20, 1.0))  # Normalize to 20 items
        langfuse_context.score_current_trace(name="error_rate", value=1.0 - (error_count / max(len(brokers_to_process), 1)))

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ News scraping failed: {e}", exc_info=True)
        langfuse_context.score_current_trace(name="scrape_coverage", value=0.0)
        raise HTTPException(status_code=500, detail=f"News scraping failed: {str(e)}")


@app.post("/news", status_code=201)
@time_api_call
def add_news_flash(news: NewsFlashRequest) -> Dict[str, str]:
    """
    Add a new news flash for a broker.
    """
    try:
        # Convert Pydantic model to NewsFlash dataclass
        news_flash = NewsFlash(
            broker=news.broker,
            title=news.title,
            summary=news.summary,
            url=str(news.url) if news.url else None,
            date=news.date,
            source=news.source,
            notes=news.notes
        )

        save_news_flash(news_flash)

        return {
            "status": "success",
            "message": f"News flash added for {news.broker}",
            "broker": news.broker,
            "title": news.title
        }
    except Exception as e:
        logger.error(f"❌ Failed to save news flash: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to save news flash: {str(e)}")


@app.get("/news", response_model=List[NewsFlashResponse])
@time_api_call
def get_all_news() -> List[NewsFlashResponse]:
    """
    Get all news flashes, sorted by creation date (newest first).
    """
    try:
        news_list = load_news()
        return [
            NewsFlashResponse(
                broker=news.broker,
                title=news.title,
                summary=news.summary,
                url=news.url,
                date=news.date,
                source=news.source,
                notes=news.notes,
                created_at=news.created_at
            )
            for news in news_list
        ]
    except Exception as e:
        logger.error(f"❌ Failed to load news: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to load news: {str(e)}")


@app.get("/news/broker/{broker_name}", response_model=List[NewsFlashResponse])
@time_api_call
def get_news_for_broker(broker_name: str) -> List[NewsFlashResponse]:
    """
    Get all news flashes for a specific broker.
    """
    try:
        news_list = get_news_by_broker(broker_name)
        return [
            NewsFlashResponse(
                broker=news.broker,
                title=news.title,
                summary=news.summary,
                url=news.url,
                date=news.date,
                source=news.source,
                notes=news.notes,
                created_at=news.created_at
            )
            for news in news_list
        ]
    except Exception as e:
        logger.error(f"❌ Failed to load news for {broker_name}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to load news for broker: {str(e)}")


@app.get("/news/recent", response_model=List[NewsFlashResponse])
@time_api_call
def get_recent_news_endpoint(limit: int = Query(10, description="Maximum number of news items to return")) -> List[NewsFlashResponse]:
    """
    Get the most recent news flashes across all brokers.
    """
    try:
        news_list = get_recent_news(limit)
        return [
            NewsFlashResponse(
                broker=news.broker,
                title=news.title,
                summary=news.summary,
                url=news.url,
                date=news.date,
                source=news.source,
                notes=news.notes,
                created_at=news.created_at
            )
            for news in news_list
        ]
    except Exception as e:
        logger.error(f"❌ Failed to load recent news: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to load recent news: {str(e)}")


@app.get("/news/statistics")
@time_api_call
def get_news_stats() -> Dict[str, Any]:
    """
    Get statistics about the news data.
    """
    try:
        return get_news_statistics()
    except Exception as e:
        logger.error(f"❌ Failed to get news statistics: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get news statistics: {str(e)}")


@app.delete("/news")
def delete_news_endpoint(request: NewsDeleteRequest) -> Dict[str, str]:
    """
    Delete a specific news flash by broker and title.
    """
    try:
        deleted = delete_news_flash(request.broker, request.title)

        if deleted:
            return {
                "status": "success",
                "message": f"News flash deleted for {request.broker}: {request.title}"
            }
        else:
            raise HTTPException(
                status_code=404,
                detail=f"News flash not found for {request.broker}: {request.title}"
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to delete news flash: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete news flash: {str(e)}")


# ========================================================================================
# CHATBOT ENDPOINT
# ========================================================================================

_chat_context_cache: Dict[str, Any] = {"text": None, "expires_at": 0.0}


def _build_chat_context() -> str:
    """Build a compact text summary of all broker data for LLM context."""
    _ensure_rules_loaded()

    lines: List[str] = []

    # Fee rules per broker/instrument
    lines.append("## Fee Rules")
    grouped: Dict[str, List[str]] = {}
    for (broker_key, instr_key), rule in sorted(FEE_RULES.items()):
        display = _get_display_name(broker_key)
        desc = f"  {instr_key}: pattern={rule.pattern}, tiers={rule.tiers}"
        if rule.handling_fee > 0:
            desc += f", handling=EUR{rule.handling_fee:.2f}"
        if rule.max_fee is not None:
            desc += f", max_fee=EUR{rule.max_fee:.2f}"
        grouped.setdefault(display, []).append(desc)

    for broker_display, descs in sorted(grouped.items()):
        lines.append(f"\n{broker_display}:")
        lines.extend(descs)

    # Comparison table matrices
    lines.append("\n## Comparison Tables (transaction fee in EUR)")
    try:
        broker_names = list(set(rule.broker for rule in FEE_RULES.values()))
        tables = build_comparison_tables(broker_names)
        eb = tables.get("euronext_brussels", {})
        for asset_type in ["stocks", "etfs", "bonds"]:
            asset_data = eb.get(asset_type, {})
            if asset_data:
                lines.append(f"\n### {asset_type.upper()}")
                for broker_display, fees in sorted(asset_data.items()):
                    fee_str = ", ".join(f"EUR{k}={v}" for k, v in sorted(fees.items(), key=lambda x: int(x[0])))
                    lines.append(f"  {broker_display}: {fee_str}")
    except Exception as e:
        lines.append(f"  (table build failed: {e})")

    # Hidden costs
    lines.append("\n## Hidden Costs")
    for broker_name, costs in sorted(HIDDEN_COSTS.items()):
        parts = []
        if costs.custody_fee_monthly_pct > 0:
            parts.append(f"custody={costs.custody_fee_monthly_pct}%/mo")
        if costs.connectivity_fee_per_exchange_year > 0:
            parts.append(f"connectivity=EUR{costs.connectivity_fee_per_exchange_year:.2f}/exch/yr")
        if costs.subscription_fee_monthly > 0:
            parts.append(f"subscription=EUR{costs.subscription_fee_monthly:.2f}/mo")
        if costs.fx_fee_pct > 0:
            parts.append(f"FX={costs.fx_fee_pct}%")
        if costs.handling_fee_per_trade > 0:
            parts.append(f"handling=EUR{costs.handling_fee_per_trade:.2f}/trade")
        if costs.dividend_fee_pct > 0:
            parts.append(f"dividend={costs.dividend_fee_pct}%")
        if not parts:
            parts.append("none significant")
        lines.append(f"  {broker_name}: {', '.join(parts)}")

    # Persona TCO rankings
    lines.append("\n## Investor Persona TCO Rankings")
    try:
        from ..validation.persona_calculator import PERSONAS, compute_persona_costs
        broker_names_for_persona = list(set(rule.broker for rule in FEE_RULES.values()))
        for persona_key, persona_def in PERSONAS.items():
            results = []
            for broker in broker_names_for_persona:
                result = compute_persona_costs(broker, persona_key)
                if result is not None:
                    results.append(result)
            results.sort(key=lambda r: r.total_annual_tco)
            lines.append(f"\n### {persona_def.name} ({persona_def.description})")
            for i, r in enumerate(results, 1):
                lines.append(f"  {i}. {r.broker}: EUR{r.total_annual_tco:.2f}/yr")
    except Exception as e:
        lines.append(f"  (persona calculation failed: {e})")

    return "\n".join(lines)


def _get_chat_context() -> str:
    """Caching wrapper for _build_chat_context with 5-minute TTL."""
    now = time.time()
    if _chat_context_cache["text"] is not None and now < _chat_context_cache["expires_at"]:
        return _chat_context_cache["text"]

    text = _build_chat_context()
    _chat_context_cache["text"] = text
    _chat_context_cache["expires_at"] = now + 300  # 5 minutes
    return text


def _precompute_fee_calculations(question: str) -> Optional[Dict[str, Any]]:
    """Extract broker names, instruments, and EUR amounts from the question.

    Runs calculate_fee() + generate_explanation() for matches and returns
    pre-computed results to inject into the system prompt.
    """
    _ensure_rules_loaded()

    # Extract EUR amounts (e.g., EUR5000, EUR 5000, 5000 euro, €5000)
    amount_pattern = r'(?:EUR\s?|€)\s?([\d,]+(?:\.\d+)?)|(\d[\d,]+(?:\.\d+)?)\s*(?:euro|EUR|€)'
    amount_matches = re.findall(amount_pattern, question, re.IGNORECASE)
    amounts = []
    for m in amount_matches:
        raw = m[0] or m[1]
        raw = raw.replace(",", "")
        try:
            amounts.append(float(raw))
        except ValueError:
            pass

    if not amounts:
        return None

    # Extract broker names
    question_lower = question.lower()
    found_brokers = []
    for alias, canonical in sorted(BROKER_ALIASES.items(), key=lambda x: -len(x[0])):
        if alias in question_lower and canonical not in found_brokers:
            found_brokers.append(canonical)

    if not found_brokers:
        # Use all brokers if none specifically mentioned
        found_brokers = list(set(rule.broker.lower() for rule in FEE_RULES.values()))

    # Detect instruments mentioned
    instruments = []
    for keyword, instrument in [("stock", "stocks"), ("etf", "etfs"), ("bond", "bonds"),
                                 ("aandeel", "stocks"), ("tracker", "etfs"), ("obligatie", "bonds")]:
        if keyword in question_lower:
            instruments.append(instrument)
    if not instruments:
        instruments = ["stocks", "etfs"]  # default

    # Compute fees
    results: Dict[str, Any] = {}
    for broker in found_brokers:
        display = _get_display_name(broker)
        broker_results = {}
        for instrument in instruments:
            for amount in amounts:
                fee = calculate_fee(broker, instrument, amount)
                if fee is not None:
                    explanation = generate_explanation(broker, instrument, amount)
                    key = f"{instrument}_EUR{int(amount)}"
                    broker_results[key] = {
                        "fee": fee,
                        "explanation": explanation,
                    }
        if broker_results:
            results[display] = broker_results

    return results if results else None


CHAT_SYSTEM_PROMPT_TEMPLATE = """You are a helpful assistant specializing in Belgian broker fees and investment costs.
You help users compare brokers on Euronext Brussels: Degiro Belgium, Bolero, Keytrade Bank, ING Self Invest, Rebel, and Revolut.

## Data Context
{context}

## Pre-Computed Fee Calculations
{pre_computed}

## Instructions
- When pre-computed calculations are provided above, use those EXACT EUR amounts. Do NOT re-calculate or approximate.
- Be precise with EUR amounts — always show 2 decimal places (e.g., EUR7.50, not "about EUR8").
- Consider BOTH transaction fees AND hidden costs (custody, connectivity, FX, dividends) when comparing total cost.
- When asked "which is cheapest", check the comparison tables or pre-computed results rather than guessing.
- Answer concisely but completely. Use bullet points for comparisons.
- If you don't have data for a specific scenario, say so rather than guessing.
- You MUST respond in {language}. All explanations, comparisons, and advice must be in {language}. Keep broker names, EUR amounts, and technical terms unchanged.
"""


@app.post("/chat")
@time_api_call
@observe(name="chat")
def chat_endpoint(request: ChatRequest) -> Dict[str, Any]:
    """
    Chatbot endpoint for natural language questions about Belgian broker fees.

    Accepts a question, optional conversation history, and optional model.
    Pre-computes specific fee calculations when amounts are mentioned.
    """
    model = request.model or "groq/llama-3.3-70b-versatile"
    fallback_model = "gemini-2.0-flash"
    language_name = _get_language_name(request.lang or "en")
    langfuse_context.update_current_observation(metadata={"model": model, "lang": request.lang or "en"})

    # Build context
    context = _get_chat_context()

    # Pre-compute specific fee calculations from the question
    pre_computed = _precompute_fee_calculations(request.question)
    pre_computed_text = "None (general question)" if pre_computed is None else json.dumps(pre_computed, indent=2)

    # Build system prompt
    system_prompt = CHAT_SYSTEM_PROMPT_TEMPLATE.format(
        context=context,
        pre_computed=pre_computed_text,
        language=language_name,
    )

    # Build conversation messages
    conv_messages: List[dict] = []
    if request.history:
        for msg in request.history:
            conv_messages.append({"role": msg.role, "content": msg.content})
    conv_messages.append({"role": "user", "content": request.question})

    llm_kwargs = dict(
        system_prompt=system_prompt,
        user_prompt=request.question,
        response_format="text",
        temperature=0.3,
        messages=conv_messages,
    )

    # Track pre-computed metrics
    has_pre_computed = pre_computed is not None
    num_pre_computed_items = len(pre_computed) if has_pre_computed else 0
    has_conversation_history = request.history is not None and len(request.history) > 0

    try:
        answer = _call_llm(model=model, **llm_kwargs)
        used_model = model
        fallback_required = False
    except Exception as e:
        fallback_required = True
        if model != fallback_model:
            logger.warning(f"Primary model {model} failed, falling back to {fallback_model}: {e}")
            try:
                answer = _call_llm(model=fallback_model, **llm_kwargs)
                used_model = fallback_model
            except Exception as fallback_err:
                logger.error(f"Fallback model {fallback_model} also failed: {fallback_err}", exc_info=True)
                langfuse_context.update_current_observation(
                    metadata={
                        "model": model,
                        "lang": request.lang or "en",
                        "fallback_required": True,
                        "fallback_failed": True,
                        "error": str(fallback_err),
                    }
                )
                langfuse_context.score_current_trace(name="answer_quality", value=0.0)
                raise HTTPException(status_code=500, detail=f"All models failed. Primary: {e} | Fallback: {fallback_err}")
        else:
            logger.error(f"Chat endpoint failed: {e}", exc_info=True)
            langfuse_context.update_current_observation(
                metadata={
                    "model": model,
                    "lang": request.lang or "en",
                    "fallback_required": True,
                    "error": str(e),
                }
            )
            langfuse_context.score_current_trace(name="answer_quality", value=0.0)
            raise HTTPException(status_code=500, detail=f"Chat failed: {str(e)}")

    # Calculate answer quality metrics
    answer_length = len(answer) if answer else 0
    has_specific_amounts = any(c.isdigit() or '€' in answer or 'EUR' in answer for c in answer)

    # Update tracing with final metadata
    langfuse_context.update_current_observation(
        output=answer,
        metadata={
            "model": model,
            "lang": request.lang or "en",
            "used_model": used_model,
            "fallback_required": fallback_required,
            "has_pre_computed": has_pre_computed,
            "num_pre_computed_items": num_pre_computed_items,
            "has_history": has_conversation_history,
            "answer_length": answer_length,
            "has_specific_amounts": has_specific_amounts,
            "conversation_turns": len(conv_messages),
        }
    )

    # Add quality scores
    answer_quality = min(answer_length / 500, 1.0)  # Longer answers tend to be more detailed
    langfuse_context.score_current_trace(name="answer_quality", value=answer_quality)
    langfuse_context.score_current_trace(name="answer_specificity", value=1.0 if has_specific_amounts else 0.5)
    langfuse_context.score_current_trace(name="pre_computed_usage", value=1.0 if has_pre_computed else 0.0)
    langfuse_context.score_current_trace(name="fallback_required", value=1.0 if fallback_required else 0.0)

    # Submit async groundedness evaluation (doesn't block response)
    try:
        _submit_groundedness_evaluation(
            endpoint="chat",
            user_input=request.question,
            retrieved_context=context[:50000],
            generated_output=answer,
        )
    except Exception as e:
        logger.warning(f"Failed to submit evaluation: {e}")

    return {
        "answer": answer,
        "model_used": used_model,
        "pre_computed": pre_computed,
    }


# ========================================================================================
# LANGFUSE SHUTDOWN
# ========================================================================================

@app.on_event("shutdown")
def _flush_langfuse():
    """Ensure all Langfuse traces are sent before the process exits."""
    langfuse_context.flush()
