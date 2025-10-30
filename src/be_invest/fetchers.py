"""Fetchers for broker sources with optional Playwright and caching.

Use `SimpleCache` to avoid re-fetching unchanged content within a TTL. Falls
back to `requests`/stdlib when Playwright is not available.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional, Tuple, Dict
import logging

try:
    from playwright.sync_api import sync_playwright  # type: ignore
except Exception:
    sync_playwright = None  # type: ignore

try:
    import requests  # type: ignore
except Exception:
    requests = None  # type: ignore

from .cache import SimpleCache

logger = logging.getLogger(__name__)


DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,application/pdf;q=0.8,*/*;q=0.7",
    "Accept-Language": "en-US,en;q=0.9",
}


class Fetcher:
    def __init__(
        self,
        cache_dir: Optional[Path] = None,
        ttl_seconds: int = 0,
        use_playwright: bool = False,
        headers: Optional[Dict[str, str]] = None,
    ) -> None:
        self.cache = SimpleCache(cache_dir, ttl_seconds) if cache_dir else None
        self.use_playwright = use_playwright and (sync_playwright is not None)
        self.headers = headers or DEFAULT_HEADERS

    def fetch(self, url: str, timeout: float = 15.0) -> Tuple[Optional[bytes], Optional[str]]:
        # Cache hit
        if self.cache:
            cached = self.cache.get(url)
            if cached is not None:
                logger.debug("Cache hit for %s (%d bytes)", url, len(cached))
                return cached, None

        # Remote fetch via requests
        content: Optional[bytes] = None
        content_type: Optional[str] = None
        if requests is not None:
            try:
                resp = requests.get(url, timeout=timeout, headers=self.headers, allow_redirects=True)
                content = resp.content
                content_type = resp.headers.get("Content-Type")
                resp.raise_for_status()
            except Exception as exc:
                logger.debug("requests fetch failed for %s: %s", url, exc)

        # Playwright fallback for dynamic pages or blocked requests
        if (content is None or not content) and self.use_playwright:
            if sync_playwright is None:
                logger.debug("Playwright not available; cannot fetch %s", url)
            else:
                try:
                    with sync_playwright() as p:
                        browser = p.chromium.launch(headless=True)
                        page = browser.new_page()
                        resp = page.goto(url, wait_until="networkidle", timeout=int(timeout * 1000))
                        # If it's a PDF, try to get the response body
                        if resp and resp.ok:
                            # Playwright python does not expose body() on Response; use JS fetch fallback
                            body = page.evaluate("() => document.contentType || ''")
                            content_type = str(body) if body else content_type
                        # Fallback to page content
                        content = page.content().encode("utf-8")
                        browser.close()
                except Exception as exc:
                    logger.debug("Playwright fetch failed for %s: %s", url, exc)

        # Local files as last resort
        if content is None or not content:
            p = Path(url.replace("file://", ""))
            if p.exists():
                try:
                    content = p.read_bytes()
                except Exception:
                    content = None

        # Cache store
        if self.cache and content is not None:
            self.cache.put(url, content, metadata={"content_type": content_type})

        return content, content_type

