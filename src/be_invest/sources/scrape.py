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
from typing import List, Optional, Callable, Dict, Tuple
import logging
import time
import re
import hashlib

try:  # Prefer requests when available, but keep stdlib fallback
    import requests  # type: ignore
    from requests.exceptions import HTTPError, RequestException
except Exception:  # pragma: no cover - optional dependency
    requests = None  # type: ignore
    HTTPError = RequestException = Exception # type: ignore

from ..models import Broker, FeeRecord
from ..fetchers import Fetcher
from .llm_extract import extract_fee_records_via_llm

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
        sess.headers.update(_DEFAULT_HEADERS)
        return sess
    except Exception:
        return requests.Session() if requests is not None else None


def _fetch_url(url: str, timeout: float = 10.0) -> Tuple[Optional[bytes], Optional[str]]:
    """Fetch raw bytes from a URL using the requests library."""
    if not url:
        return None, "URL is empty"
    try:
        if url.startswith("file://"):
            p = Path(url.replace("file://", "", 1))
            return (p.read_bytes(), None) if p.exists() else (None, "File not found")
        p = Path(url)
        if p.exists():
            return p.read_bytes(), None

        if requests is not None:
            sess = _get_session()
            assert sess is not None
            resp = sess.get(url, timeout=timeout, headers=_DEFAULT_HEADERS, allow_redirects=True, verify=True)
            resp.raise_for_status()
            return resp.content, None
        else:
            from urllib.request import urlopen, Request
            req = Request(url, headers=_DEFAULT_HEADERS)
            with urlopen(req, timeout=timeout) as response:
                return response.read(), None
    except Exception as exc:
        error_msg = f"Failed to fetch {url}: {exc}"
        logger.error(error_msg, exc_info=True)
        return None, error_msg


def scrape_fee_records(
    brokers: List[Broker], *, force: bool = False, timeout: float = 10.0, pdf_text_dump_dir: Optional[Path] = None,
    use_llm: bool = False, llm_model: str = "gpt-4o", llm_cache_dir: Optional[Path] = None,
    llm_max_tokens: int = 1500, llm_temperature: float = 0.0, strict_parse: bool = False
) -> List[FeeRecord]:
    """
    Attempts to scrape fee records for all brokers from PDF sources.
    Non-PDF sources are ignored.
    """
    logger.info("Starting PDF scrape process for %d brokers...", len(brokers))
    all_records: List[FeeRecord] = []

    for broker in brokers:
        logger.debug("Processing broker: %s", broker.name)

        for ds in broker.data_sources:
            if not ds.url or (ds.allowed_to_scrape is False and not force):
                continue
            
            # This simplified version only processes URLs that look like PDFs
            if not ds.url.lower().endswith('.pdf'):
                logger.info("Skipping non-PDF data source for %s: %s", broker.name, ds.url)
                continue

            logger.debug("Fetching PDF URL for %s: %s", broker.name, ds.url)
            raw_bytes, fetch_error = _fetch_url(ds.url, timeout=timeout)

            if not raw_bytes:
                logger.warning("No data fetched for %s from %s. Error: %s", broker.name, ds.url, fetch_error)
                continue

            if raw_bytes.startswith(b"%PDF"):
                logger.debug("Processing PDF for %s (%d bytes)", broker.name, len(raw_bytes))
                try:
                    from pdfminer.high_level import extract_text
                    from io import BytesIO
                    text = extract_text(BytesIO(raw_bytes)) or ""

                    if pdf_text_dump_dir and text.strip():
                        pdf_text_dump_dir.mkdir(parents=True, exist_ok=True)
                        safe_broker_name = re.sub(r'[\s/]+', '_', broker.name)
                        safe_desc = re.sub(r'[\s/]+', '_', ds.description or 'document')
                        url_hash = hashlib.md5(ds.url.encode()).hexdigest()[:8]
                        text_filename = f"{safe_broker_name}_{safe_desc}_{url_hash}.txt"
                        out_path = pdf_text_dump_dir / text_filename
                        out_path.write_text(text, encoding="utf-8")
                        logger.info("Saved extracted PDF text to %s", out_path)
                    
                    if use_llm and text.strip():
                        llm_rows = extract_fee_records_via_llm(
                            text, broker=broker.name, source_url=ds.url, model=llm_model,
                            llm_cache_dir=llm_cache_dir, max_output_tokens=llm_max_tokens,
                            temperature=llm_temperature, strict_mode=strict_parse
                        )
                        all_records.extend(llm_rows)
                        logger.info("LLM extracted %d records for %s.", len(llm_rows), broker.name)

                except Exception as exc:
                    logger.error("PDF processing failed for %s", broker.name, exc_info=True)
            else:
                logger.warning("Skipping non-PDF content for %s from %s.", broker.name, ds.url)

    logger.info("Scrape finished. Found %d total records.", len(all_records))
    unique_records = list(dict.fromkeys(all_records))
    logger.info("Returning %d unique records.", len(unique_records))
    return unique_records
