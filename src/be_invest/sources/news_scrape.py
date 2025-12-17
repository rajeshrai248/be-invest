"""
Automated news scraping for Belgian investment brokers.
"""
from __future__ import annotations

import logging
import re
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Dict, Set
from urllib.parse import urljoin, urlparse
import time

try:
    import requests
    import feedparser
    from bs4 import BeautifulSoup
except ImportError as e:
    raise ImportError(f"Required packages missing: {e}. Install with: pip install requests feedparser beautifulsoup4 python-dateutil") from e

from ..models import Broker, NewsSource
from ..news import NewsFlash, save_news_flash, load_news
from ..fetchers import Fetcher

logger = logging.getLogger(__name__)


class NewsScraper:
    """Automated news scraper for broker websites."""

    def __init__(self, output_dir: Optional[Path] = None, cache_hours: int = 24):
        """
        Initialize news scraper.
        """
        self.cache_hours = cache_hours
        self._scraped_hashes: Set[str] = set()
        self._load_scraped_cache()
        self.fetcher = Fetcher(use_playwright=True) # Always use Playwright for robustness

        logger.info("🔧 NewsScraper initialized")
        logger.info(f"   Playwright enabled: {self.fetcher.use_playwright}")
        logger.info(f"   Cache duration: {cache_hours} hours")

        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36',
        }

    def scrape_all_broker_news(self, brokers: List[Broker], force: bool = False) -> Dict[str, List[NewsFlash]]:
        """
        Scrape news from all brokers with configured news sources.
        """
        results = {}
        total_success = 0
        total_attempts = 0

        for broker in brokers:
            if not broker.news_sources:
                logger.info(f"📰 No news sources configured for {broker.name}")
                continue

            broker_news = []
            broker_attempts = 0

            logger.info(f"🎯 Processing {broker.name}...")

            for news_source in broker.news_sources:
                broker_attempts += 1
                total_attempts += 1

                # ALWAYS respect allowed_to_scrape=false (even with force=true)
                if not news_source.allowed_to_scrape:
                    logger.info(f"📰 Skipping {broker.name} news source (not allowed): {news_source.url}")
                    continue

                try:
                    scraped_news = self._scrape_news_source(broker, news_source, force=force)  # Pass force here
                    if scraped_news:
                        broker_news.extend(scraped_news)
                        total_success += 1
                        logger.info(f"✅ {broker.name}: {len(scraped_news)} items from {news_source.description}")
                    else:
                        logger.info(f"ℹ️ {broker.name}: No new items from {news_source.description}")

                    time.sleep(1.5)

                except Exception as e:
                    logger.warning(f"⚠️ {broker.name} source failed: {str(e)[:80]}")
                    continue

            if broker_news:
                results[broker.name] = broker_news
                logger.info(f"🎯 {broker.name} total: {len(broker_news)} news items")
            else:
                logger.info(f"📭 {broker.name}: No news found from {broker_attempts} source(s)")

        logger.info(f"📊 SCRAPING SUMMARY: {len(results)} brokers with news, {total_success}/{total_attempts} sources successful")
        return results

    def _scrape_news_source(self, broker: Broker, source: NewsSource, force: bool = False) -> List[NewsFlash]:
        """Scrape a single news source."""
        if source.type == "rss":
            return self._scrape_rss_feed(broker.name, source, force=force)
        elif source.type == "webpage":
            return self._scrape_webpage(broker.name, source, force=force)
        else:
            logger.warning(f"⚠️ Unknown news source type: {source.type}")
            return []

    def _scrape_rss_feed(self, broker_name: str, source: NewsSource, force: bool = False) -> List[NewsFlash]:
        """Scrape RSS feed for news."""
        try:
            logger.info(f"📡 Fetching RSS feed: {source.url}")
            response = requests.get(source.url, headers=self.headers, timeout=15)
            response.raise_for_status()
            feed = feedparser.parse(response.content)

            if feed.bozo:
                logger.warning(f"⚠️ RSS feed may be malformed: {source.url} (bozo: {feed.bozo_exception})")

            news_items = []
            for entry in feed.entries[:20]:
                try:
                    title = self._clean_text(entry.get('title', 'Untitled'))
                    summary = self._clean_html(entry.get('summary', entry.get('description', '')))
                    if not title or not summary: continue

                    content_hash = self._create_content_hash(broker_name, title, summary)
                    if content_hash in self._scraped_hashes: continue

                    news_flash = NewsFlash(
                        broker=broker_name,
                        title=title[:200],
                        summary=summary[:1000],
                        url=entry.get('link'),
                        date=self._parse_date(entry.get('published')),
                        source=f"RSS: {source.description or urlparse(source.url).netloc}",
                        notes=f"RSS feed from {source.url}"
                    )
                    news_items.append(news_flash)
                    self._scraped_hashes.add(content_hash)
                except Exception as e:
                    logger.debug(f"⚠️ Failed to process RSS entry: {e}")
                    continue
            return news_items
        except Exception as e:
            logger.warning(f"⚠️ RSS feed parsing failed for {source.url}: {e}")
            return []

    def _scrape_webpage(self, broker_name: str, source: NewsSource, force: bool = False) -> List[NewsFlash]:
        """Scrape webpage using Playwright and BeautifulSoup."""
        try:
            logger.info(f"🌐 Fetching webpage with Playwright: {source.url}")
            # Keep HTML structure for news scraping (extract_text=False)
            html_bytes, error = self.fetcher.fetch(source.url, extract_text=False)

            if error or not html_bytes:
                logger.error(f"❌ Playwright failed to fetch {source.url}: {error}")
                return []

            logger.debug(f"Received {len(html_bytes)} bytes from {source.url}")

            # Try to decode HTML bytes with proper encoding handling
            try:
                # Try UTF-8 first (most common)
                html_str = html_bytes.decode('utf-8', errors='ignore')
                logger.debug("Decoded with UTF-8")
            except Exception:
                # Fall back to latin-1 (very permissive)
                try:
                    html_str = html_bytes.decode('latin-1', errors='ignore')
                    logger.debug("Decoded with latin-1")
                except Exception:
                    # Last resort: ignore all errors
                    html_str = html_bytes.decode('utf-8', errors='ignore')
                    logger.debug("Decoded with UTF-8 (ignoring errors)")

            # Try lxml parser first (fastest), fall back to html.parser
            try:
                soup = BeautifulSoup(html_str, 'lxml')
                logger.debug("Using lxml parser")
            except (ImportError, Exception) as e:
                # lxml not available or BeautifulSoup can't use it - use html.parser
                logger.debug(f"lxml failed ({e}), using html.parser")
                soup = BeautifulSoup(html_str, 'html.parser')
                logger.debug("Using html.parser")

            news_items = []

            if source.selector:
                logger.debug(f"Using CSS selector: {source.selector}")
                articles = soup.select(source.selector)

                # If selector is "div", filter for divs with actual news content
                if source.selector == "div" and articles:
                    logger.debug(f"Filtering {len(articles)} divs to find news-like content")
                    filtered = []
                    for div in articles[:100]:  # Only check first 100 divs
                        # Look for heading + text pattern
                        heading = div.find(['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'a'])
                        summary = div.find(['p', 'span', 'div'])

                        if heading and summary:
                            heading_text = self._clean_text(heading.get_text())
                            summary_text = self._clean_text(summary.get_text())

                            # Ensure meaningful content
                            if heading_text and len(heading_text) > 10 and summary_text and len(summary_text) > 20:
                                filtered.append(div)

                    articles = filtered
                    logger.debug(f"Filtered to {len(articles)} news-like divs")

                # If selector found nothing, fall back to auto-detection
                if not articles:
                    logger.debug("Selector returned no results, falling back to auto-detection")
                    articles = self._find_news_articles(soup)
            else:
                logger.debug("No selector provided, using auto-detection")
                articles = self._find_news_articles(soup)

            logger.info(f"🎯 Found {len(articles)} potential articles on {source.url}")

            if len(articles) == 0:
                logger.warning(f"⚠️ No articles found. Page title: {soup.title.string if soup.title else 'N/A'}")
                logger.debug(f"HTML preview (first 500 chars): {str(soup)[:500]}")

            for article in articles[:20]:
                try:
                    logger.debug(f"Processing article element: {article.name if hasattr(article, 'name') else 'unknown'}")
                    title = self._extract_title(article)
                    logger.debug(f"  Title: {title[:50] if title else 'NONE'}")

                    summary = self._extract_summary(article)
                    logger.debug(f"  Summary: {summary[:50] if summary else 'NONE'}...")

                    url = self._extract_url(article, source.url)
                    logger.debug(f"  URL: {url}")

                    date = self._extract_date(article)
                    logger.debug(f"  Date: {date}")

                    if not title or not summary:
                        logger.debug(f"  ❌ Skipping: missing title or summary")
                        continue

                    content_hash = self._create_content_hash(broker_name, title, summary)

                    # Skip deduplication check if force=True
                    if not force and content_hash in self._scraped_hashes:
                        logger.debug(f"  ℹ️ Skipping: duplicate (hash: {content_hash[:8]})")
                        continue

                    news_flash = NewsFlash(
                        broker=broker_name,
                        title=title[:200],
                        summary=summary[:1000],
                        url=url,
                        date=date,
                        source=f"Website: {source.description or urlparse(source.url).netloc}",
                        notes=f"Scraped from {source.url}"
                    )
                    news_items.append(news_flash)
                    self._scraped_hashes.add(content_hash)
                except Exception as e:
                    logger.debug(f"⚠️ Failed to process article: {e}")
                    continue
            return news_items
        except Exception as e:
            logger.error(f"❌ Unexpected error scraping {source.url}: {e}", exc_info=True)
            return []

    def _find_news_articles(self, soup: BeautifulSoup) -> List:
        """Intelligently find news articles on a webpage with multiple strategies."""
        # Strategy 1: Try common semantic HTML selectors
        common_selectors = ['article', '.news-item', '.press-release', '.post', '.entry', '.article']
        for selector in common_selectors:
            articles = soup.select(selector)
            if articles:
                logger.debug(f"Found articles with selector: {selector}")
                return articles

        # Strategy 2: Try attribute-based selectors for modern frameworks
        attribute_selectors = [
            "[class*='post']",
            "[class*='article']",
            "[class*='news']",
            "[class*='press']",
            "[role='article']",
            "[data-type='news']",
            "[data-type='article']"
        ]
        for selector in attribute_selectors:
            articles = soup.select(selector)
            if articles and len(articles) > 0:
                logger.debug(f"Found articles with selector: {selector}")
                return articles

        # Strategy 3: Look for common container patterns
        container_selectors = [
            ".news-container",
            ".articles-list",
            ".press-releases",
            ".blog-posts",
            "[class*='container']"
        ]
        for selector in container_selectors:
            container = soup.select_one(selector)
            if container:
                # Look for article-like divs within the container
                articles = container.find_all(['div', 'li', 'article'], class_=True, limit=20)
                if articles:
                    logger.debug(f"Found articles in container: {selector}")
                    return articles

        # Strategy 4: Look for content that has heading + summary pattern
        # This is a fallback that looks for any div with h2/h3 + p combination
        potential_articles = soup.find_all('div', limit=100)
        structured_articles = []
        for div in potential_articles:
            heading = div.find(['h1', 'h2', 'h3', 'h4'])
            summary = div.find(['p', 'span'])
            if heading and summary:
                structured_articles.append(div)

        if structured_articles:
            logger.debug(f"Found {len(structured_articles)} articles using pattern matching")
            return structured_articles[:20]

        logger.debug("No articles found using any strategy")
        return []

    def _extract_title(self, article) -> Optional[str]:
        # Try headers first
        for selector in ['h1', 'h2', 'h3', 'h4', '.title', '.headline']:
            elem = article.select_one(selector)
            if elem:
                text = self._clean_text(elem.get_text())
                if text and len(text) > 5:  # Ensure meaningful title
                    return text

        # Try link text (many sites use this for article titles)
        link = article.select_one('a[href]')
        if link:
            text = self._clean_text(link.get_text())
            if text and len(text) > 10:  # Links should have decent length
                return text

        return None

    def _extract_summary(self, article) -> Optional[str]:
        # Try specific summary selectors first
        for selector in ['.summary', '.excerpt', '.description', '.intro']:
            elem = article.select_one(selector)
            if elem:
                text = self._clean_html(elem.get_text())
                if text and len(text) > 20:
                    return text

        # Try all paragraphs and pick the first meaningful one
        paras = article.find_all('p')
        for p in paras:
            text = self._clean_html(p.get_text())
            if text and len(text) > 15:  # Ensure substantial content
                return text

        # Fallback: use article's full text content (excluding title)
        full_text = self._clean_html(article.get_text(separator=' ', strip=True))
        if full_text and len(full_text) > 30:
            # Limit to first 200 chars as summary
            return full_text[:200]

        return None

    def _extract_url(self, article, base_url: str) -> Optional[str]:
        # Check if article itself is a link
        if article.name == 'a' and article.get('href'):
            href = article.get('href')
        else:
            # Otherwise look for link inside article
            link = article.select_one('a[href]')
            if not link or not link.get('href'):
                return None
            href = link.get('href')

        # Handle relative URLs properly to avoid duplication
        if href.startswith(('http://', 'https://')):
            # Already absolute URL
            return href
        elif href.startswith('/'):
            # Root-relative URL
            from urllib.parse import urlparse
            parsed_base = urlparse(base_url)
            return f"{parsed_base.scheme}://{parsed_base.netloc}{href}"
        else:
            # Relative URL - need to be careful about duplication
            # If the relative URL starts with the same path segment as base_url ends with,
            # we might have duplication
            from urllib.parse import urlparse
            parsed_base = urlparse(base_url)
            base_path = parsed_base.path.rstrip('/')

            # Check for path segment duplication (e.g., base ends with /blog/ and href starts with blog/)
            if base_path and href.startswith(base_path.split('/')[-1] + '/'):
                # Remove the duplicate segment
                href = href[len(base_path.split('/')[-1]) + 1:]

            return urljoin(base_url, href)

    def _extract_date(self, article) -> Optional[str]:
        for selector in ['time', '.date', '[datetime]']:
            elem = article.select_one(selector)
            if elem: return self._parse_date(elem.get('datetime') or elem.get_text())
        return None

    def _parse_date(self, date_str: Optional[str]) -> Optional[str]:
        if not date_str: return None
        try:
            from dateutil import parser
            return parser.parse(date_str, fuzzy=True).strftime('%Y-%m-%d')
        except:
            return None

    def _clean_text(self, text: str) -> str:
        return ' '.join(text.split()).strip() if text else ""

    def _clean_html(self, text: str) -> str:
        return self._clean_text(re.sub(r'<[^>]+>', ' ', text)) if text else ""

    def _create_content_hash(self, broker: str, title: str, summary: str) -> str:
        return hashlib.md5(f"{broker}:{title}:{summary}".lower().encode('utf-8')).hexdigest()

    def _load_scraped_cache(self):
        try:
            for news in load_news():
                self._scraped_hashes.add(self._create_content_hash(news.broker, news.title, news.summary))
            logger.info(f"📝 Loaded {len(self._scraped_hashes)} existing news hashes for deduplication")
        except Exception as e:
            logger.debug(f"Could not load existing news for deduplication: {e}")


def scrape_broker_news(brokers: List[Broker], force: bool = False) -> List[NewsFlash]:
    """Main function to scrape news from all brokers."""
    scraper = NewsScraper()
    results = scraper.scrape_all_broker_news(brokers, force=force)
    
    all_news = []
    for broker_name, broker_news in results.items():
        for news in broker_news:
            try:
                save_news_flash(news)
                all_news.append(news)
            except Exception as e:
                logger.error(f"❌ Failed to save news for {broker_name}: {e}")

    logger.info(f"🎉 Total news scraped and saved: {len(all_news)}")
    return all_news
