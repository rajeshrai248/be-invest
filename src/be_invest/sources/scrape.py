"""Web scraping scaffolding for broker fee data.

This module provides an optional mechanism to fetch fee data directly from
broker-published sources when you have permission to automate (according to
their terms and robots.txt). It intentionally ships with minimal, generic
helpers and does not include site-specific parsers.
"""
from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from html.parser import HTMLParser
from typing import List, Optional, Callable, Dict
import logging
import time

try:  # Prefer requests when available, but keep stdlib fallback
    import requests  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    requests = None  # type: ignore

from ..models import Broker, FeeRecord
from ..fetchers import Fetcher
from .llm_extract import extract_fee_records_via_openai

logger = logging.getLogger(__name__)


_DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,application/pdf;q=0.8,*/*;q=0.7",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "DNT": "1",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}


def _get_session() -> Optional["requests.Session"]:
    if requests is None:
        return None
    try:
        from requests.adapters import HTTPAdapter  # type: ignore
        from urllib3.util.retry import Retry  # type: ignore

        retry = Retry(
            total=3,
            read=3,
            connect=3,
            backoff_factor=0.8,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=("GET", "HEAD"),
            raise_on_status=False,
        )
        sess = requests.Session()
        adapter = HTTPAdapter(max_retries=retry)
        sess.mount("http://", adapter)
        sess.mount("https://", adapter)

        # Add session-level headers that persist
        sess.headers.update(_DEFAULT_HEADERS)

        return sess
    except Exception:  # pragma: no cover - optional dependency
        return requests.Session() if requests is not None else None


def _fetch_url(url: str, timeout: float = 10.0, fetcher: Optional[Fetcher] = None) -> Optional[bytes]:
    """Fetch raw bytes from a URL using requests if installed, else urllib."""

    if not url:
        return None
    # Local file support (absolute path or file:// URI)
    try:
        if url.startswith("file://"):
            p = Path(url.replace("file://", "", 1))
            if p.exists():
                logger.debug("Reading local file via file:// %s", p)
                data = p.read_bytes()
                logger.debug("Read %d bytes from local file %s", len(data), p)
                return data
        p = Path(url)
        if p.exists():
            logger.debug("Reading local file %s", p)
            data = p.read_bytes()
            logger.debug("Read %d bytes from local file %s", len(data), p)
            return data

        # Try shared fetcher first (may include cache/Playwright)
        if fetcher is not None:
            data, _ = fetcher.fetch(url, timeout=timeout)
            if data:
                return data

        # Remote URLs
        if requests is not None:
            sess = _get_session()
            assert sess is not None
            logger.debug("Fetching URL %s with requests session", url)

            # Special handling for Degiro - establish session first
            if "degiro.nl" in url.lower():
                logger.info("🔐 Degiro detected - establishing legitimate session...")
                try:
                    # Visit main site first to get cookies and establish legitimate session
                    logger.info("⏱️ Step 1: Visiting Degiro main page...")
                    time.sleep(1)
                    main_resp = sess.get(
                        "https://www.degiro.nl/",
                        timeout=timeout,
                        headers=_DEFAULT_HEADERS,
                        allow_redirects=True,
                        verify=True
                    )
                    logger.info(f"✓ Main page visited (status: {main_resp.status_code})")
                    time.sleep(2)  # Wait before PDF request

                    # Now try to get the PDF
                    logger.info("⏱️ Step 2: Downloading PDF with established session...")
                    headers = _DEFAULT_HEADERS.copy()
                    headers["Referer"] = "https://www.degiro.nl/"

                    resp = sess.get(
                        url,
                        timeout=timeout,
                        headers=headers,
                        allow_redirects=False,
                        verify=True
                    )
                    logger.debug("Fetched %s -> %s, %d bytes", url, resp.status_code, len(resp.content or b""))

                    if resp.status_code == 503 and "myracloud" in resp.text.lower():
                        logger.warning("⚠️ Degiro WAF still blocked (503 myracloud)")
                        logger.info("💡 Recommendation: Download manually from browser and save locally")
                        return None

                    resp.raise_for_status()
                    logger.info(f"✅ Successfully downloaded Degiro PDF ({len(resp.content)} bytes)")
                    return resp.content

                except Exception as e:
                    logger.warning(f"⚠️ Degiro PDF download failed: {e}")
                    logger.info("💡 Try downloading manually from: https://www.degiro.nl/data/pdf/Tarievenoverzicht.pdf")
                    return None

            # Standard URL fetching for other brokers
            headers = _DEFAULT_HEADERS.copy()
            try:
                resp = sess.get(
                    url,
                    timeout=timeout,
                    headers=headers,
                    allow_redirects=True,
                    verify=True
                )
                logger.debug("Fetched %s -> %s, %d bytes", url, resp.status_code, len(resp.content or b""))
                resp.raise_for_status()
                return resp.content
            except Exception as e:
                logger.warning("Request failed for %s: %s. Retrying with verify=False...", url, e)
                try:
                    resp = sess.get(
                        url,
                        timeout=timeout,
                        headers=headers,
                        allow_redirects=True,
                        verify=False
                    )
                    logger.debug("Fetched %s (verify=False) -> %s, %d bytes", url, resp.status_code, len(resp.content or b""))
                    resp.raise_for_status()
                    return resp.content
                except Exception as e2:
                    logger.warning("Retry also failed: %s", e2)
                    return None
        # Fallback to urllib to avoid hard dependency
        from urllib.request import urlopen
        req_headers = _DEFAULT_HEADERS
        try:
            from urllib.request import Request  # type: ignore
            req = Request(url, headers=req_headers)
        except Exception:
            req = url  # type: ignore
        with urlopen(req, timeout=timeout) as resp:  # type: ignore[attr-defined]
            data = resp.read()
            logger.debug("Fetched via urllib %s, %d bytes", url, len(data))
            return data
    except Exception as exc:  # pragma: no cover - network dependent
        logger.warning("Failed to fetch %s: %s", url, exc)
        return None


class _NaiveTableParser(HTMLParser):
    """Very naive HTML table parser for simple, well-formed tables.

    This is only a convenience for cases where brokers expose basic HTML tables
    with headers, and should be replaced with site-specific logic for
    production use.
    """

    def __init__(self) -> None:
        super().__init__()
        self.in_th = False
        self.in_td = False
        self.in_tr = False
        self.headers: List[str] = []
        self.current_row: List[str] = []
        self.rows: List[List[str]] = []

    def handle_starttag(self, tag, attrs):  # type: ignore[override]
        if tag == "tr":
            self.in_tr = True
            self.current_row = []
        elif tag == "th":
            self.in_th = True
        elif tag == "td":
            self.in_td = True

    def handle_endtag(self, tag):  # type: ignore[override]
        if tag == "tr" and self.in_tr:
            self.in_tr = False
            if self.current_row:
                if not self.headers:
                    self.headers = [c.strip() for c in self.current_row]
                else:
                    self.rows.append([c.strip() for c in self.current_row])
        elif tag == "th":
            self.in_th = False
        elif tag == "td":
            self.in_td = False

    def handle_data(self, data):  # type: ignore[override]
        if self.in_th or self.in_td:
            self.current_row.append(data)


def _try_parse_simple_table(html_bytes: bytes, broker_name: str, source_url: str) -> List[FeeRecord]:
    """Best-effort parse of a simple HTML table into fee records.

    This attempts to map columns with names resembling our FeeRecord fields.
    It will return an empty list if a mapping can't be reasonably inferred.
    """

    try:
        text = html_bytes.decode("utf-8", errors="ignore")
    except Exception:
        return []

    parser = _NaiveTableParser()
    parser.feed(text)
    headers = [h.lower() for h in parser.headers]
    if not headers or not parser.rows:
        return []

    # Heuristic column mapping
    def col(*names: str) -> Optional[int]:
        for n in names:
            if n in headers:
                return headers.index(n)
        return None

    idx_instrument = col("instrument", "instrument_type", "product")
    idx_channel = col("channel", "order_channel", "execution")
    idx_base = col("base_fee", "fixed", "base")
    idx_var = col("variable_fee", "variable", "%", "commission")
    idx_curr = col("currency", "curr", "ccy")

    if idx_instrument is None or (idx_base is None and idx_var is None):
        return []

    records: List[FeeRecord] = []
    for r in parser.rows:
        try:
            base_val = None
            if idx_base is not None:
                raw = r[idx_base] if idx_base < len(r) else ""
                base_val = float(raw.replace(",", ".").strip()) if raw else None
        except Exception:
            base_val = None

        records.append(
            FeeRecord(
                broker=broker_name,
                instrument_type=(r[idx_instrument] if idx_instrument is not None and idx_instrument < len(r) else "").strip(),
                order_channel=(r[idx_channel] if idx_channel is not None and idx_channel < len(r) else "").strip(),
                base_fee=base_val,
                variable_fee=(r[idx_var] if idx_var is not None and idx_var < len(r) else "").strip() or None,
                currency=(r[idx_curr] if idx_curr is not None and idx_curr < len(r) else "").strip() or "",
                source=source_url,
                notes=None,
            )
        )
    return records


def _safe_name(s: str) -> str:
    return "".join(ch if ch.isalnum() else "_" for ch in s)[:120]


def _parse_pdf_text_generic(broker_name: str, source_url: str, text: str) -> List[FeeRecord]:
    """Heuristic PDF text parser to extract fee-like records.

    Looks for instrument keywords and nearby numeric values that resemble base
    fees (EUR/€ amounts) and variable fees (percentages).
    """
    instruments: Dict[str, List[str]] = {
        "Equities": ["equities", "shares", "aandelen"],
        "ETFs": ["etf", "etfs"],
        "Options": ["options", "opties"],
        "Bonds": ["bonds", "obligaties"],
        "Funds": ["funds", "fondsen", "fund"],
    }

    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    lower = [ln.lower() for ln in lines]

    import re
    eur_re = re.compile(r"(\d+[.,]?\d*)\s*(?:eur|€)", re.I)
    pct_re = re.compile(r"(\d+[.,]?\d*)\s*%")
    channel_re = re.compile(r"(online|platform|web|phone|telefoon|branch|agency)", re.I)

    records: List[FeeRecord] = []
    for idx, l in enumerate(lower):
        match_instrument: Optional[str] = None
        for name, keys in instruments.items():
            if any(k in l for k in keys):
                match_instrument = name
                break
        if not match_instrument:
            continue

        window = " ".join(lower[idx: idx + 3])  # current + next 2 lines
        window_orig = " ".join(lines[idx: idx + 3])

        base_fee_val: Optional[float] = None
        m_eur = eur_re.search(window)
        if m_eur:
            try:
                base_fee_val = float(m_eur.group(1).replace(",", "."))
            except Exception:
                base_fee_val = None

        variable_fee: Optional[str] = None
        m_pct = pct_re.search(window)
        if m_pct:
            variable_fee = m_pct.group(1) + "%"

        m_channel = channel_re.search(window)
        order_channel = m_channel.group(1).title() if m_channel else "Online Platform"

        if base_fee_val is None and not variable_fee:
            continue

        records.append(
            FeeRecord(
                broker=broker_name,
                instrument_type=match_instrument,
                order_channel=order_channel,
                base_fee=base_fee_val,
                variable_fee=variable_fee,
                currency="EUR",
                source=source_url,
                notes=None,
            )
        )
    return records


def _parse_pdf_text_degiro(broker_name: str, source_url: str, text: str) -> List[FeeRecord]:
    """Degiro-specific PDF heuristic parsing.

    Looks for Dutch terms common in Degiro's tariff documents and extracts
    base and variable components per instrument type where possible.
    """
    import re
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    lower = [ln.lower() for ln in lines]

    patterns = [
        ("Equities", ["aandelen", "equities", "aandelen europa", "aandelen vs"]) ,
        ("ETFs", ["etf", "etfs"]) ,
        ("Options", ["opties", "options"]) ,
        ("Bonds", ["obligaties", "bonds"]) ,
    ]

    eur_re = re.compile(r"(€|eur)\s*(\d+[.,]?\d*)", re.I)
    pct_re = re.compile(r"(\d+[.,]?\d*)\s*%")

    records: List[FeeRecord] = []
    for i, l in enumerate(lower):
        for instr, keys in patterns:
            if any(k in l for k in keys):
                window = " ".join(lower[i:i+4])
                window_orig = " ".join(lines[i:i+4])
                base: Optional[float] = None
                var: Optional[str] = None
                m_eur = eur_re.search(window_orig)
                if m_eur:
                    try:
                        base = float(m_eur.group(2).replace(",", "."))
                    except Exception:
                        base = None
                m_pct = pct_re.search(window)
                if m_pct:
                    var = m_pct.group(1) + "%"
                if base is None and not var:
                    continue
                records.append(
                    FeeRecord(
                        broker=broker_name,
                        instrument_type=instr,
                        order_channel="Online Platform",
                        base_fee=base,
                        variable_fee=var,
                        currency="EUR",
                        source=source_url,
                        notes=None,
                    )
                )
                break
    return records


_SPECIALIZED_SCRAPERS: Dict[str, Callable[[Broker], List[FeeRecord]]] = {}
_PDF_TEXT_PARSERS: Dict[str, Callable[[str, str, str], List[FeeRecord]]] = {
    "Bolero": _parse_pdf_text_generic,
    "Keytrade Bank": _parse_pdf_text_generic,
    "Degiro Belgium": _parse_pdf_text_degiro,
    "ING Self Invest": _parse_pdf_text_generic,
}


def scrape_fee_records(
    brokers: List[Broker], *, force: bool = False, timeout: float = 10.0, pdf_text_dump_dir: Optional[Path] = None,
    cache_dir: Optional[Path] = None, cache_ttl_seconds: int = 0, use_playwright: bool = False, strict_parse: bool = False,
    use_llm: bool = False, llm_model: str = "gpt-4o", llm_api_key_env: str = "OPENAI_API_KEY", llm_cache_dir: Optional[Path] = None,
    llm_max_tokens: int = 1500, llm_temperature: float = 0.0
) -> List[FeeRecord]:
    """Attempt to scrape fee records for brokers with permitted sources.

    - Respects each data source's `allowed_to_scrape` flag unless `force=True`.
    - Performs a minimal best-effort parse for simple HTML tables.
    - Returns an empty list when a site requires a custom parser (most cases).
    """

    logger.debug("Starting scrape over %d brokers", len(brokers))
    all_records: List[FeeRecord] = []
    fetcher = Fetcher(cache_dir=cache_dir, ttl_seconds=cache_ttl_seconds, use_playwright=use_playwright)
    for broker in brokers:
        logger.debug("Broker: %s (sources: %d)", broker.name, len(getattr(broker, 'data_sources', []) or []))
        # Allow a specialized scraper for known brokers
        special = _SPECIALIZED_SCRAPERS.get(broker.name)
        if callable(special):
            try:
                all_records.extend(special(broker))  # type: ignore[misc]
                continue
            except Exception as exc:
                logger.warning("Specialized scraper failed for %s: %s", broker.name, exc)

        for ds in broker.data_sources:
            logger.debug("Source: type=%s url=%s allowed=%s", getattr(ds, 'type', None), ds.url, ds.allowed_to_scrape)
            if not ds.url:
                logger.debug("Skipping source with empty URL for broker %s", broker.name)
                continue
            if ds.allowed_to_scrape is False and not force:
                logger.info("Skipping %s (scraping not permitted): %s", broker.name, ds.url)
                continue
            logger.debug("Fetching %s -> %s", broker.name, ds.url)
            raw = _fetch_url(ds.url, timeout=timeout, fetcher=fetcher)
            if not raw:
                logger.debug("No data fetched for %s -> %s", broker.name, ds.url)
                continue
            # Minimal HTML table handling; PDFs and complex pages require custom logic
            if raw.startswith(b"<"):
                logger.debug("Guessed content type: HTML (%d bytes)", len(raw))
                parsed = _try_parse_simple_table(raw, broker.name, ds.url)
                if parsed:
                    logger.debug("Parsed %d rows from simple HTML table for %s", len(parsed), broker.name)
                    all_records.extend(parsed)
                else:
                    logger.info("No simple table parse for %s; source likely needs a custom scraper", broker.name)
            else:
                # Likely a PDF or binary; attempt best-effort PDF text extraction
                if raw[:4] == b"%PDF":
                    logger.debug("Guessed content type: PDF (%d bytes)", len(raw))
                    try:
                        from pdfminer.high_level import extract_text  # type: ignore
                        # pdfminer expects a file-like or path; write to memory requires BytesIO
                        from io import BytesIO
                        text = extract_text(BytesIO(raw)) or ""
                        if pdf_text_dump_dir is not None:
                            try:
                                pdf_text_dump_dir.mkdir(parents=True, exist_ok=True)
                                out = pdf_text_dump_dir / f"{_safe_name(broker.name)}__{_safe_name(Path(ds.url).name)}.txt"
                                out.write_text(text, encoding="utf-8")
                                logger.debug("Wrote extracted PDF text to %s", out)
                            except Exception as dump_exc:
                                logger.debug("Failed to write PDF text dump: %s", dump_exc)
                        logger.debug("Extracted PDF text length: %d chars for %s", len(text), broker.name)
                        if not text.strip():
                            logger.info("PDF text empty for %s; check source.", broker.name)
                        else:
                            parser = _PDF_TEXT_PARSERS.get(broker.name, _parse_pdf_text_generic)
                            parsed_pdf = parser(broker.name, ds.url, text)
                            if strict_parse:
                                parsed_pdf = [r for r in parsed_pdf if (r.base_fee is not None and (r.variable_fee is not None and r.variable_fee != ""))]
                            if parsed_pdf:
                                logger.debug("Parsed %d rows from PDF text for %s", len(parsed_pdf), broker.name)
                                all_records.extend(parsed_pdf)
                            else:
                                logger.info("No heuristic rows for %s; considering LLM extraction...", broker.name)
                                if use_llm:
                                    llm_rows = extract_fee_records_via_openai(
                                        text,
                                        broker=broker.name,
                                        source_url=ds.url,
                                        model=llm_model,
                                        api_key_env=llm_api_key_env,
                                        llm_cache_dir=llm_cache_dir,
                                        max_output_tokens=llm_max_tokens,
                                        temperature=llm_temperature,
                                        strict_mode=strict_parse,
                                        focus_fee_lines=True,
                                    )
                                    if strict_parse:
                                        llm_rows = [r for r in llm_rows if (r.base_fee is not None and (r.variable_fee is not None and r.variable_fee != ""))]
                                    if llm_rows:
                                        logger.debug("LLM parsed %d rows for %s", len(llm_rows), broker.name)
                                        all_records.extend(llm_rows)
                                    else:
                                        logger.info("LLM extraction returned no rows for %s", broker.name)
                    except Exception as exc:  # pragma: no cover - optional dependency
                        logger.info("PDF parsing not available or failed for %s: %s", broker.name, exc)
                else:
                    logger.debug("Guessed content type: binary/other (%d bytes)", len(raw))
                    logger.info("Non-HTML content for %s (%s); implement a binary parser.", broker.name, ds.url)

    # De-duplicate identical records (best-effort)
    unique: List[FeeRecord] = []
    seen = set()
    for r in all_records:
        key = tuple(asdict(r).items())
        if key not in seen:
            seen.add(key)
            unique.append(r)
    logger.debug("Scrape finished. %d records before de-dupe, %d after.", len(all_records), len(unique))
    return unique
