"""Fetchers for broker sources with optional Playwright and caching.

Use `SimpleCache` to avoid re-fetching unchanged content within a TTL. Falls
back to `requests`/stdlib when Playwright is not available.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional, Tuple, Dict
import logging
import time
import random
import subprocess
import sys
import os

try:
    from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
except ImportError:
    sync_playwright = None
    PlaywrightTimeoutError = None

try:
    import requests
    from requests.exceptions import ReadTimeout, ConnectionError, HTTPError
except ImportError:
    requests = None
    ReadTimeout = None
    ConnectionError = None
    HTTPError = None

from .cache import SimpleCache

logger = logging.getLogger(__name__)


DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "DNT": "1",
}


class Fetcher:
    def __init__(
        self,
        cache_dir: Optional[Path] = None,
        ttl_seconds: int = 0,
        use_playwright: bool = False,
        headers: Optional[Dict[str, str]] = None,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        attempt_playwright_install: bool = True,
    ) -> None:
        self.cache = SimpleCache(cache_dir, ttl_seconds) if cache_dir else None
        # Only attempt Playwright if requested and the package is importable.
        # If launch fails (missing browser binaries), we mark Playwright as broken
        # and fall back to requests for subsequent fetches.
        # Respect environment variable BE_INVEST_PLAYWRIGHT_AUTOINSTALL (0/1 or false/true)
        env_val = os.getenv("BE_INVEST_PLAYWRIGHT_AUTOINSTALL")
        if env_val is not None:
            val = env_val.strip().lower()
            if val in ("0", "false", "no"):
                attempt_playwright_install = False
            elif val in ("1", "true", "yes"):
                attempt_playwright_install = True

        self.use_playwright = use_playwright and (sync_playwright is not None)
        self._playwright_broken = False
        self._playwright_warning_shown = False
        self._attempted_playwright_install = False
        self.attempt_playwright_install = attempt_playwright_install
        self.headers = headers or DEFAULT_HEADERS
        self.max_retries = max_retries
        self.retry_delay = retry_delay

        # Helpful startup log to aid troubleshooting: which python executable and whether Playwright is importable
        try:
            logger.info("Python executable: %s", sys.executable)
            logger.info("Playwright package available: %s", sync_playwright is not None)
            logger.info("Playwright auto-install allowed: %s (BE_INVEST_PLAYWRIGHT_AUTOINSTALL=%s)", self.attempt_playwright_install, env_val)
        except Exception:
            # Logging should not break initialization
            pass

    def _retry_with_backoff(self, func, *args, **kwargs):
        """Execute function with exponential backoff retry logic."""
        last_exception = None

        for attempt in range(self.max_retries):
            try:
                return func(*args, **kwargs)
            except (ReadTimeout, ConnectionError) as exc:
                last_exception = exc
                if attempt < self.max_retries - 1:
                    # Exponential backoff with jitter
                    delay = self.retry_delay * (2 ** attempt) + random.uniform(0, 1)
                    logger.info(f"Network timeout/error, retrying in {delay:.1f}s (attempt {attempt + 1}/{self.max_retries})")
                    time.sleep(delay)
                    continue
                else:
                    # Final attempt failed
                    raise last_exception
            except HTTPError as exc:
                # Don't retry HTTP errors like 403, 404, etc.
                raise exc
            except Exception as exc:
                # Don't retry other unexpected errors
                raise exc

        # Should not reach here, but just in case
        raise last_exception

    def _attempt_install_playwright_browsers(self) -> bool:
        """Try to install Playwright browser binaries using the current Python interpreter.

        Returns True on success, False otherwise. This is best-effort and will only
        be attempted once per Fetcher instance to avoid long blocking installs.
        """
        if self._attempted_playwright_install:
            return False
        self._attempted_playwright_install = True

        # Prefer running the playwright module under the same interpreter.
        cmd = [sys.executable, "-m", "playwright", "install", "chromium"]
        logger.info("Attempting to auto-install Playwright browsers by running: %s", " ".join(cmd))
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
            if proc.returncode == 0:
                logger.info("Playwright browsers installed successfully (chromium).")
                return True
            else:
                logger.warning("Playwright install exited with code %s. stdout: %s stderr: %s", proc.returncode, proc.stdout, proc.stderr)
                return False
        except FileNotFoundError:
            logger.warning("Could not run playwright install: 'playwright' module/entrypoint not found in this environment.")
            return False
        except subprocess.TimeoutExpired:
            logger.warning("Playwright install command timed out.")
            return False
        except Exception as exc:
            logger.error("Unexpected error while trying to auto-install Playwright browsers: %s", exc, exc_info=True)
            return False

    def fetch(self, url: str, timeout: float = 30.0, extract_text: bool = False) -> Tuple[Optional[bytes], Optional[str]]:
        """Fetch raw bytes from a URL. Uses Playwright if specified, otherwise falls back to requests.

        Args:
            url: URL to fetch
            timeout: Timeout in seconds
            extract_text: If True, extract visible text only (for LLM analysis).
                         If False, keep full HTML structure (for news scraping).
        """
        if self.cache:
            cached = self.cache.get(url)
            if cached is not None:
                logger.debug("Cache hit for %s", url)
                return cached, "from-cache"

        content: Optional[bytes] = None
        error_message: Optional[str] = None

        # Try Playwright only if enabled and not previously flagged as broken.
        if self.use_playwright and not getattr(self, "_playwright_broken", False):
            logger.info("🎭 Fetching with Playwright: %s", url)
            try:
                logger.debug("Launching Playwright chromium browser...")
                with sync_playwright() as p:
                    browser = p.chromium.launch(headless=True)
                    logger.debug("Browser launched, creating context...")

                    # Set Belgium-specific context for Revolut
                    context_options = {
                        "user_agent": self.headers["User-Agent"],
                    }

                    # For Revolut, set Belgium locale and geolocation
                    if "revolut.com" in url.lower():
                        context_options.update({
                            "locale": "en-BE",  # English (Belgium)
                            "timezone_id": "Europe/Brussels",
                            "geolocation": {"latitude": 50.8503, "longitude": 4.3517},  # Brussels coordinates
                            "permissions": ["geolocation"]
                        })
                        logger.debug("Using Belgium-specific context for Revolut")

                    context = browser.new_context(**context_options)
                    page = context.new_page()
                    logger.debug("Navigating to %s", url)

                    # Navigate to the page - wait for full load
                    response = page.goto(url, wait_until="load", timeout=int(timeout * 1000))
                    logger.debug("Page loaded, status: %s", response.status if response else "unknown")

                    # Wait for network to be idle (dynamic content loaded)
                    logger.debug("Waiting for network idle...")
                    try:
                        page.wait_for_load_state("networkidle", timeout=int(timeout * 1000))
                    except:
                        # If networkidle times out, still proceed (better than failing)
                        logger.debug("Network idle timeout, proceeding anyway...")

                    # Wait a bit more for JavaScript rendering
                    import time as time_module
                    time_module.sleep(2)

                    if response and response.ok:
                        # For data scraping (Revolut fees), extract visible text
                        # For news scraping, keep full HTML structure
                        if extract_text:
                            try:
                                # Extract clean text from body (for LLM analysis)
                                body_text = page.evaluate("""() => {
                                    // Remove scripts, styles, and hidden elements
                                    const clone = document.body.cloneNode(true);
                                    clone.querySelectorAll('script, style, [hidden], [aria-hidden="true"]').forEach(el => el.remove());
                                    return clone.innerText || clone.textContent;
                                }""")

                                if body_text and len(body_text.strip()) > 500:
                                    # Use cleaned text if substantial content found
                                    content = body_text.encode("utf-8")
                                    logger.debug("Extracted %d chars of visible text", len(body_text))
                                else:
                                    # Fall back to full HTML if text extraction didn't work well
                                    content = page.content().encode("utf-8")
                                    logger.debug("Using full HTML content (insufficient text)")
                            except:
                                # If JavaScript evaluation fails, use full HTML
                                content = page.content().encode("utf-8")
                                logger.debug("Text extraction failed, using full HTML")
                        else:
                            # Keep full HTML structure (for news scraping)
                            content = page.content().encode("utf-8")
                            logger.debug("Using full HTML content (extract_text=False)")
                        logger.info("✅ Playwright fetch successful: %s (%d bytes)", url, len(content))
                        logger.debug("Content preview: %s...", content[:200])
                    else:
                        status = response.status if response else "unknown"
                        error_message = f"Playwright navigation failed with status {status}"
                        logger.warning(error_message)

                    browser.close()
                    logger.debug("Browser closed")
            except PlaywrightTimeoutError:
                error_message = "Playwright timed out waiting for page to load."
                logger.warning(error_message)
            except Exception as exc:
                # Detect common Playwright-installation/browser-binary errors and avoid retry loops.
                msg = str(exc)
                error_message = f"Playwright fetch failed: {msg}"

                if "Executable doesn't exist" in msg or "playwright install" in msg or "Looks like Playwright was just installed" in msg:
                    # Mark broken so we don't repeatedly try Playwright on subsequent URLs.
                    self._playwright_broken = True

                    # Only show the installation warning once per Fetcher instance
                    if not self._playwright_warning_shown:
                        logger.warning(
                            "Playwright browser binaries are missing. "
                            "Attempting to auto-install when allowed; falling back to requests for now. "
                            "To manually install run: '%s -m playwright install chromium' and restart the process.",
                            sys.executable,
                        )
                        self._playwright_warning_shown = True

                    # Try auto-install if configured; if it succeeds, clear the broken flag and retry once.
                    if self.attempt_playwright_install and not self._attempted_playwright_install:
                        installed = self._attempt_install_playwright_browsers()
                        if installed:
                            # Reset flags and try Playwright once more on this call
                            self._playwright_broken = False
                            logger.info("Retrying Playwright fetch after successful installation...")
                            return self.fetch(url, timeout=timeout)
                        else:
                            logger.info("Auto-install did not succeed, will continue using requests fallback.")
                    else:
                        logger.debug("Auto-install disabled or already attempted; using requests fallback.")
                else:
                    # Other Playwright errors (not installation-related)
                    logger.error(error_message, exc_info=True)

        # Fallback to requests if Playwright is not used or fails
        if content is None and requests:
            # Use appropriate log level based on whether this is expected fallback
            if self._playwright_broken:
                logger.debug("Using requests fallback for: %s", url)
            else:
                logger.info("Falling back to requests for: %s", url)

            try:
                def _make_request():
                    resp = requests.get(url, timeout=timeout, headers=self.headers, allow_redirects=True)
                    resp.raise_for_status()
                    return resp

                resp = self._retry_with_backoff(_make_request)
                content = resp.content
                error_message = None # Clear error if requests succeeds
                logger.info("Successfully fetched with requests: %s", url)
            except (ReadTimeout, ConnectionError) as exc:
                error_message = f"Network timeout/connection error after {self.max_retries} retries: {exc}"
                logger.warning(error_message)
            except HTTPError as exc:
                error_message = f"HTTP error: {exc}"
                if exc.response.status_code == 403:
                    logger.warning(f"Access denied (403) for {url} - site may block automated requests")
                elif exc.response.status_code == 404:
                    logger.warning(f"Page not found (404): {url}")
                else:
                    logger.warning(error_message)
            except Exception as exc:
                error_message = f"Requests fetch failed: {exc}"
                logger.error(error_message, exc_info=True)

        if self.cache and content:
            self.cache.put(url, content)

        return content, error_message
