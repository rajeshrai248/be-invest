"""Data models for broker fee aggregation."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass(frozen=True)
class DataSource:
    """Configuration for a broker data source."""

    type: str
    description: str
    url: Optional[str] = None
    allowed_to_scrape: Optional[bool] = None
    notes: Optional[str] = None


@dataclass(frozen=True)
class NewsSource:
    """Configuration for a broker news source."""

    url: str
    type: str  # "rss", "webpage", "json_api"
    selector: Optional[str] = None  # CSS selector for webpage scraping
    allowed_to_scrape: bool = False
    description: Optional[str] = None
    notes: Optional[str] = None


@dataclass(frozen=True)
class Broker:
    """Basic information about an investment broker."""

    name: str
    website: str
    country: str
    instruments: List[str]
    data_sources: List[DataSource] = field(default_factory=list)
    news_sources: List[NewsSource] = field(default_factory=list)
    notes: Optional[str] = None


@dataclass(frozen=True)
class FeeRecord:
    """Normalized representation of a single fee entry."""

    broker: str
    instrument_type: str
    order_channel: str
    base_fee: Optional[float]
    variable_fee: Optional[str]
    currency: str
    source: str
    notes: Optional[str] = None
