"""Utilities for loading configuration from YAML files."""
from __future__ import annotations

from pathlib import Path
from typing import Iterable, List

import yaml

from .models import Broker, DataSource, NewsSource


def _load_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def load_brokers_from_yaml(path: Path) -> List[Broker]:
    """Load broker definitions from the provided YAML file."""

    raw = _load_yaml(path)
    brokers: List[Broker] = []
    for entry in raw.get("brokers", []):
        data_sources = [
            DataSource(
                type=source.get("type", ""),
                description=source.get("description", ""),
                url=source.get("url"),
                allowed_to_scrape=source.get("allowed_to_scrape"),
                notes=source.get("notes"),
            )
            for source in entry.get("data_sources", [])
        ]

        news_sources = [
            NewsSource(
                url=source.get("url", ""),
                type=source.get("type", "webpage"),
                selector=source.get("selector"),
                allowed_to_scrape=source.get("allowed_to_scrape", False),
                description=source.get("description"),
                notes=source.get("notes"),
            )
            for source in entry.get("news_sources", [])
        ]

        brokers.append(
            Broker(
                name=entry.get("name", ""),
                website=entry.get("website", ""),
                country=entry.get("country", ""),
                instruments=list(entry.get("instruments", [])),
                data_sources=data_sources,
                news_sources=news_sources,
                notes=entry.get("notes"),
            )
        )
    return brokers


def load_brokers_from_directory(paths: Iterable[Path]) -> List[Broker]:
    """Aggregate broker definitions from multiple YAML files."""

    brokers: List[Broker] = []
    for path in paths:
        if path.exists() and path.suffix in {".yml", ".yaml"}:
            brokers.extend(load_brokers_from_yaml(path))
    return brokers
