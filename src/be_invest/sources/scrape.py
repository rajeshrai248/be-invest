"""Web scraping scaffolding for broker fee data.

This module provides an optional mechanism to fetch fee data directly from
broker-published sources when you have permission to automate (according to
their terms and robots.txt). It intentionally ships with minimal, generic
helpers and does not include site-specific parsers.
"""
from __future__ import annotations

from pathlib import Path
from typing import List, Optional, Tuple
import logging
import re
import hashlib
from urllib.parse import urljoin

try:  # Prefer requests when available, but keep stdlib fallback
    import requests  # type: ignore
    from requests.exceptions import HTTPError, RequestException
except Exception:  # pragma: no cover - optional dependency
    requests = None  # type: ignore
    HTTPError = RequestException = Exception # type: ignore

from ..models import Broker, FeeRecord
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


def _fetch_url(url: str, timeout: float = 10.0, use_playwright_fallback: bool = True) -> Tuple[Optional[bytes], Optional[str]]:
    """Fetch raw bytes from a URL using requests library, with Playwright fallback for 403 errors."""
    if not url:
        return None, "URL is empty"
    try:
        if url.startswith("file://"):
            p = Path(url.replace("file://", "", 1))
            return (p.read_bytes(), None) if p.exists() else (None, "File not found")
        p = Path(url)
        if p.exists():
            return p.read_bytes(), None

        # Try requests first
        if requests is not None:
            try:
                sess = _get_session()
                assert sess is not None
                resp = sess.get(url, timeout=timeout, headers=_DEFAULT_HEADERS, allow_redirects=True, verify=True)
                resp.raise_for_status()
                return resp.content, None
            except HTTPError as e:
                # If 403 Forbidden, fall back to Playwright
                if e.response.status_code == 403 and use_playwright_fallback:
                    logger.warning(f"Requests got 403 for {url}, falling back to Playwright...")
                    return _fetch_url_with_playwright(url, timeout)
                raise
        else:
            from urllib.request import urlopen, Request
            req = Request(url, headers=_DEFAULT_HEADERS)
            with urlopen(req, timeout=timeout) as response:
                return response.read(), None
    except Exception as exc:
        error_msg = f"Failed to fetch {url}: {exc}"
        logger.error(error_msg, exc_info=True)
        return None, error_msg


def _fetch_url_with_playwright(url: str, timeout: float = 10.0) -> Tuple[Optional[bytes], Optional[str]]:
    """Fetch URL content using Playwright to bypass bot detection.
    Uses text extraction for better LLM analysis."""
    try:
        from ..fetchers import Fetcher
        logger.info(f"Using Playwright to fetch {url}...")
        fetcher = Fetcher(use_playwright=True)
        # Extract visible text for data scraping (better for LLM)
        html_bytes, error = fetcher.fetch(url, timeout=timeout, extract_text=True)

        if error:
            return None, f"Playwright fetch failed: {error}"
        if not html_bytes:
            return None, "Playwright returned empty content"

        logger.info(f"Successfully fetched {len(html_bytes)} bytes with Playwright")
        return html_bytes, None
    except Exception as exc:
        error_msg = f"Playwright fetch failed for {url}: {exc}"
        logger.error(error_msg, exc_info=True)
        return None, error_msg


def _extract_pdf_links_from_html(html: str, base_url: Optional[str] = None) -> List[str]:
    """Find PDF links in HTML and return resolved absolute URLs.

    Looks for <a>, <iframe>, <embed> and simple href/src occurrences that reference .pdf.
    """
    links: List[str] = []
    try:
        # Simple regex to find href/src values ending/containing .pdf
        # This is intentionally permissive to catch common patterns.
        for match in re.findall(r"(?:href|src)=[\"']([^\"']+\.pdf[^\"']*)[\"']", html, flags=re.IGNORECASE):
            resolved = urljoin(base_url or "", match)
            links.append(resolved)

        # Fallback: look for bare URLs ending with .pdf
        for match in re.findall(r"https?://[^\s'\"<>]+\.pdf(?:\?[^\s'\"<>]*)?", html, flags=re.IGNORECASE):
            if match not in links:
                links.append(match)
    except Exception:
        pass
    return links


def scrape_fee_records(
    brokers: List[Broker], *, force: bool = False, timeout: float = 10.0, pdf_text_dump_dir: Optional[Path] = None,
    use_llm: bool = False, llm_model: str = "gpt-4o", llm_cache_dir: Optional[Path] = None,
    llm_max_tokens: int = 1500, llm_temperature: float = 0.0, strict_parse: bool = False
) -> List[FeeRecord]:
    """
    Attempts to scrape fee records for all brokers from PDF sources.
    Non-PDF sources are ignored.
    """
    logger.info("Starting scrape process for %d brokers...", len(brokers))
    all_records: List[FeeRecord] = []

    for broker in brokers:
        logger.debug("Processing broker: %s", broker.name)

        for ds in broker.data_sources:
            if not ds.url or (ds.allowed_to_scrape is False and not force):
                continue

            is_pdf = bool(getattr(ds, "type", "").lower() == "pdf") or getattr(ds, "url", "").lower().endswith('.pdf')
            is_webpage = ds.type == "webpage" or (not is_pdf and ds.url.startswith('http'))

            # Skip non-PDF, non-webpage sources
            if not is_pdf and not is_webpage:
                logger.info("Skipping unknown source type for %s: %s", broker.name, ds.url)
                continue

            logger.debug("Fetching %s for %s: %s", 'PDF' if is_pdf else 'webpage', broker.name, ds.url)

            # Always use Playwright for Revolut (bypasses bot detection)
            if broker.name == "Revolut":
                logger.info(f"Using Playwright for Revolut (bypasses bot detection)...")
                raw_bytes, fetch_error = _fetch_url_with_playwright(ds.url, timeout)
            else:
                raw_bytes, fetch_error = _fetch_url(ds.url, timeout=timeout)

            if not raw_bytes:
                logger.warning("No data fetched for %s from %s. Error: %s", broker.name, ds.url, fetch_error)
                continue

            # Handle PDF
            if is_pdf and raw_bytes.startswith(b"%PDF"):
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
                    elif ds.use_llm and text.strip():
                        # Check individual data source use_llm flag
                        logger.info("Using LLM for data source with use_llm=True: %s", broker.name)
                        llm_rows = extract_fee_records_via_llm(
                            text, broker=broker.name, source_url=ds.url, model=llm_model,
                            llm_cache_dir=llm_cache_dir, max_output_tokens=llm_max_tokens,
                            temperature=llm_temperature, strict_mode=strict_parse
                        )
                        all_records.extend(llm_rows)
                        logger.info("LLM extracted %d records for %s via data source flag.", len(llm_rows), broker.name)

                except Exception as exc:
                    logger.error("PDF processing failed for %s", broker.name, exc_info=True)

            # Handle Webpage (HTML) sources
            elif is_webpage:
                logger.debug("Processing webpage for %s", broker.name)
                try:
                    # Decode HTML and extract text
                    try:
                        html_str = raw_bytes.decode('utf-8', errors='ignore')
                    except Exception:
                        html_str = raw_bytes.decode('latin-1', errors='ignore')

                    # Normalized safe names (always define these so linked-PDF handling can use them)
                    safe_broker_name = re.sub(r'[\s/]+', '_', broker.name)
                    safe_desc = re.sub(r'[\s/]+', '_', ds.description or 'document')

                    # Save HTML content to text file (same as PDF)
                    if pdf_text_dump_dir and html_str.strip():
                        pdf_text_dump_dir.mkdir(parents=True, exist_ok=True)
                        url_hash = hashlib.md5(ds.url.encode()).hexdigest()[:8]
                        text_filename = f"{safe_broker_name}_{safe_desc}_{url_hash}.txt"
                        out_path = pdf_text_dump_dir / text_filename
                        out_path.write_text(html_str, encoding="utf-8")
                        logger.info("Saved extracted webpage text to %s", out_path)

                    # If the page contains links to PDFs, fetch and process those PDFs as well
                    pdf_links = _extract_pdf_links_from_html(html_str, base_url=ds.url)
                    if pdf_links:
                        logger.info("Found %d PDF link(s) on page for %s; attempting to fetch them...", len(pdf_links), broker.name)
                        for pl in pdf_links:
                            try:
                                pdf_bytes, pdf_err = _fetch_url(pl, timeout=timeout)
                                if not pdf_bytes:
                                    logger.warning("Failed to fetch linked PDF %s for %s: %s", pl, broker.name, pdf_err)
                                    continue

                                if pdf_bytes.startswith(b"%PDF"):
                                    logger.info("Processing linked PDF %s for %s (%d bytes)", pl, broker.name, len(pdf_bytes))
                                    try:
                                        from pdfminer.high_level import extract_text
                                        from io import BytesIO
                                        linked_text = extract_text(BytesIO(pdf_bytes)) or ""

                                        if pdf_text_dump_dir and linked_text.strip():
                                            url_hash2 = hashlib.md5(pl.encode()).hexdigest()[:8]
                                            linked_filename = f"{safe_broker_name}_{safe_desc}_{url_hash2}.txt"
                                            linked_out = pdf_text_dump_dir / linked_filename
                                            linked_out.write_text(linked_text, encoding="utf-8")
                                            logger.info("Saved extracted linked PDF text to %s", linked_out)

                                        # Extract fee records from linked PDF using LLM if requested
                                        if use_llm and linked_text.strip():
                                            llm_rows = extract_fee_records_via_llm(
                                                linked_text, broker=broker.name, source_url=pl, model=llm_model,
                                                llm_cache_dir=llm_cache_dir, max_output_tokens=llm_max_tokens,
                                                temperature=llm_temperature, strict_mode=strict_parse
                                            )
                                            all_records.extend(llm_rows)
                                            logger.info("LLM extracted %d records from linked PDF for %s.", len(llm_rows), broker.name)
                                        elif ds.use_llm and linked_text.strip():
                                            llm_rows = extract_fee_records_via_llm(
                                                linked_text, broker=broker.name, source_url=pl, model=llm_model,
                                                llm_cache_dir=llm_cache_dir, max_output_tokens=llm_max_tokens,
                                                temperature=llm_temperature, strict_mode=strict_parse
                                            )
                                            all_records.extend(llm_rows)
                                            logger.info("LLM extracted %d records from linked PDF for %s via ds.use_llm.", len(llm_rows), broker.name)

                                    except Exception as exc:
                                        logger.error("Linked PDF processing failed for %s (%s)", broker.name, pl, exc_info=True)
                                else:
                                    logger.warning("Linked resource is not a PDF (or invalid PDF header): %s", pl)
                            except Exception as e:
                                logger.exception("Error fetching/processing linked PDF %s for %s", pl, broker.name)

                    # Use LLM to extract fee records from HTML content
                    if use_llm and html_str.strip():
                        logger.info("Using LLM to extract fees from webpage for %s", broker.name)
                        llm_rows = extract_fee_records_via_llm(
                            html_str, broker=broker.name, source_url=ds.url, model=llm_model,
                            llm_cache_dir=llm_cache_dir, max_output_tokens=llm_max_tokens,
                            temperature=llm_temperature, strict_mode=strict_parse
                        )
                        all_records.extend(llm_rows)
                        logger.info("LLM extracted %d records for %s from webpage.", len(llm_rows), broker.name)
                    elif ds.use_llm and html_str.strip():
                        # Check individual data source use_llm flag
                        logger.info("Using LLM for webpage with use_llm=True: %s", broker.name)
                        llm_rows = extract_fee_records_via_llm(
                            html_str, broker=broker.name, source_url=ds.url, model=llm_model,
                            llm_cache_dir=llm_cache_dir, max_output_tokens=llm_max_tokens,
                            temperature=llm_temperature, strict_mode=strict_parse
                        )
                        all_records.extend(llm_rows)
                        logger.info("LLM extracted %d records for %s from webpage via data source flag.", len(llm_rows), broker.name)
                    else:
                        logger.warning("Webpage source requires use_llm=True for %s", broker.name)

                except Exception as exc:
                    logger.error("Webpage processing failed for %s", broker.name, exc_info=True)
            else:
                logger.warning("Skipping non-PDF/non-webpage content for %s from %s.", broker.name, ds.url)

    logger.info("Scrape finished. Found %d total records.", len(all_records))
    unique_records = list(dict.fromkeys(all_records))
    logger.info("Returning %d unique records.", len(unique_records))
    return unique_records

