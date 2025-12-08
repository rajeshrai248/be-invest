"""
News flash functionality for broker updates and announcements.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
import json
import logging
from typing import Optional, List, Union, Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class NewsFlash:
    """Data structure for broker news flashes."""
    broker: str
    title: str
    summary: str
    url: Optional[str] = None
    date: Optional[str] = None   # ISO date string recommended
    source: Optional[str] = None
    notes: Optional[str] = None
    created_at: Optional[str] = None  # Auto-filled timestamp

    def __post_init__(self):
        """Set created_at timestamp if not provided."""
        if self.created_at is None:
            self.created_at = datetime.now().isoformat()


def _default_news_file() -> Path:
    """Get the default news file path."""
    # Try current working directory first
    cwd_path = Path("data") / "output" / "news.jsonl"
    if cwd_path.parent.exists():
        return cwd_path

    # Fall back to repo structure
    repo_root = Path(__file__).resolve().parents[2]
    fallback = repo_root / "data" / "output" / "news.jsonl"
    fallback.parent.mkdir(parents=True, exist_ok=True)
    return fallback


def save_news_flash(news: NewsFlash, path: Optional[Union[str, Path]] = None) -> None:
    """
    Save a news flash to the JSON Lines file.

    Args:
        news: NewsFlash instance to save
        path: Optional custom path (defaults to data/output/news.jsonl)
    """
    if path is None:
        path = _default_news_file()

    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)

    with p.open("a", encoding="utf-8") as fh:
        json.dump(asdict(news), fh, ensure_ascii=False)
        fh.write("\n")

    logger.info(f"📰 Saved news flash for {news.broker}: {news.title}")


def load_news(path: Optional[Union[str, Path]] = None) -> List[NewsFlash]:
    """
    Load all news flashes from the JSON Lines file.

    Args:
        path: Optional custom path (defaults to data/output/news.jsonl)

    Returns:
        List of NewsFlash objects, sorted by created_at (newest first)
    """
    if path is None:
        path = _default_news_file()

    p = Path(path)
    if not p.exists():
        logger.info(f"📰 News file not found: {p}, returning empty list")
        return []

    items: List[NewsFlash] = []

    with p.open("r", encoding="utf-8") as fh:
        line_num = 0
        for line in fh:
            line_num += 1
            line = line.strip()
            if not line:
                continue

            try:
                obj = json.loads(line)
                items.append(NewsFlash(**obj))
            except json.JSONDecodeError as e:
                logger.warning(f"⚠️ Failed to parse JSON on line {line_num}: {e}")
                logger.debug(f"   Line content: {line[:100]}...")
            except TypeError as e:
                logger.warning(f"⚠️ Invalid NewsFlash data on line {line_num}: {e}")
                logger.debug(f"   Data: {obj}")

    # Sort by created_at, newest first
    items.sort(key=lambda x: x.created_at or "", reverse=True)

    logger.info(f"📰 Loaded {len(items)} news flashes from {p}")
    return items


def get_news_by_broker(broker_name: str, path: Optional[Union[str, Path]] = None) -> List[NewsFlash]:
    """
    Get news flashes for a specific broker.

    Args:
        broker_name: Name of the broker to filter by
        path: Optional custom path (defaults to data/output/news.jsonl)

    Returns:
        List of NewsFlash objects for the broker, sorted by created_at (newest first)
    """
    all_news = load_news(path)
    broker_news = [n for n in all_news if n.broker.lower() == broker_name.lower()]

    logger.info(f"📰 Found {len(broker_news)} news items for {broker_name}")
    return broker_news


def delete_news_flash(broker: str, title: str, path: Optional[Union[str, Path]] = None) -> bool:
    """
    Delete a specific news flash by broker and title.

    Args:
        broker: Broker name
        title: News title
        path: Optional custom path (defaults to data/output/news.jsonl)

    Returns:
        True if deleted, False if not found
    """
    if path is None:
        path = _default_news_file()

    p = Path(path)
    if not p.exists():
        logger.warning(f"📰 News file not found: {p}")
        return False

    # Load all news
    all_news = load_news(path)

    # Filter out the one to delete
    original_count = len(all_news)
    filtered_news = [
        n for n in all_news
        if not (n.broker.lower() == broker.lower() and n.title == title)
    ]

    if len(filtered_news) == original_count:
        logger.warning(f"📰 News item not found: {broker} - {title}")
        return False

    # Rewrite the entire file
    p.unlink()  # Delete old file

    for news in filtered_news:
        save_news_flash(news, path)

    logger.info(f"📰 Deleted news item: {broker} - {title}")
    return True


def get_recent_news(limit: int = 10, path: Optional[Union[str, Path]] = None) -> List[NewsFlash]:
    """
    Get the most recent news flashes across all brokers.

    Args:
        limit: Maximum number of news items to return
        path: Optional custom path (defaults to data/output/news.jsonl)

    Returns:
        List of NewsFlash objects, limited and sorted by created_at (newest first)
    """
    all_news = load_news(path)
    return all_news[:limit]


def get_news_statistics(path: Optional[Union[str, Path]] = None) -> Dict[str, Any]:
    """
    Get statistics about the news data.

    Args:
        path: Optional custom path (defaults to data/output/news.jsonl)

    Returns:
        Dictionary with statistics
    """
    all_news = load_news(path)

    # Count by broker
    broker_counts = {}
    for news in all_news:
        broker = news.broker
        broker_counts[broker] = broker_counts.get(broker, 0) + 1

    # Get date range
    dates = [n.created_at for n in all_news if n.created_at]
    oldest_date = min(dates) if dates else None
    newest_date = max(dates) if dates else None

    return {
        "total_news": len(all_news),
        "brokers_with_news": len(broker_counts),
        "news_per_broker": broker_counts,
        "oldest_news": oldest_date,
        "newest_news": newest_date
    }
