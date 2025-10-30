"""Data models for broker fee aggregation."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class DataSource:
    """Configuration for a broker data source."""

    type: str
    description: str
    url: Optional[str] = None
    allowed_to_scrape: Optional[bool] = None
    notes: Optional[str] = None


@dataclass
class Broker:
    """Basic information about an investment broker."""

    name: str
    website: str
    country: str
    instruments: List[str]
    data_sources: List[DataSource] = field(default_factory=list)
    notes: Optional[str] = None


@dataclass
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
