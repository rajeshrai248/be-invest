"""Pipeline utilities for managing broker fee data."""
from __future__ import annotations

from pathlib import Path
from typing import Iterable, List

from .config_loader import load_brokers_from_directory, load_brokers_from_yaml
from .models import Broker, FeeRecord
from .sources.manual import load_manual_fee_records


def load_brokers(config_paths: Iterable[Path]) -> List[Broker]:
    """Load broker definitions from YAML configuration files."""

    return load_brokers_from_directory(config_paths)


def load_fee_records(manual_fee_paths: Iterable[Path]) -> List[FeeRecord]:
    """Load fee records from manual data sources (CSV/TSV)."""

    records: List[FeeRecord] = []
    for path in manual_fee_paths:
        if path.exists():
            records.extend(load_manual_fee_records(path))
    return records


def generate_report(fee_records: List[FeeRecord]) -> List[dict]:
    """Convert fee records into dictionaries ready for CSV/JSON export."""

    report_rows: List[dict] = []
    for record in fee_records:
        report_rows.append(
            {
                "broker": record.broker,
                "instrument_type": record.instrument_type,
                "order_channel": record.order_channel,
                "base_fee": record.base_fee,
                "variable_fee": record.variable_fee,
                "currency": record.currency,
                "notes": record.notes,
                "source": record.source,
            }
        )
    return report_rows
