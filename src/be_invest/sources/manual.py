"""Manual data ingestion helpers."""
from __future__ import annotations

import csv
from pathlib import Path
from typing import Iterable, List

from ..models import FeeRecord


REQUIRED_COLUMNS = {
    "broker",
    "instrument_type",
    "order_channel",
    "base_fee",
    "variable_fee",
    "currency",
    "source",
    "notes",
}


def _normalize_row(row: dict) -> FeeRecord:
    base_fee_value = row.get("base_fee")
    base_fee = float(base_fee_value) if base_fee_value not in {None, ""} else None

    notes = row.get("notes") or None
    variable_fee = row.get("variable_fee") or None

    return FeeRecord(
        broker=row.get("broker", "").strip(),
        instrument_type=row.get("instrument_type", "").strip(),
        order_channel=row.get("order_channel", "").strip(),
        base_fee=base_fee,
        variable_fee=variable_fee,
        currency=row.get("currency", "").strip(),
        source=row.get("source", "").strip(),
        notes=notes.strip() if isinstance(notes, str) else notes,
    )


def load_manual_fee_records(path: Path) -> List[FeeRecord]:
    """Load manually curated fee records from a CSV file."""

    records: List[FeeRecord] = []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        missing = REQUIRED_COLUMNS.difference(reader.fieldnames or [])
        if missing:
            missing_list = ", ".join(sorted(missing))
            raise ValueError(f"Missing required columns in {path}: {missing_list}")
        for row in reader:
            records.append(_normalize_row(row))
    return records


def export_fee_records_to_csv(records: Iterable[FeeRecord], path: Path) -> None:
    """Write fee records to a CSV file."""

    fieldnames = [
        "broker",
        "instrument_type",
        "order_channel",
        "base_fee",
        "variable_fee",
        "currency",
        "source",
        "notes",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for record in records:
            writer.writerow(
                {
                    "broker": record.broker,
                    "instrument_type": record.instrument_type,
                    "order_channel": record.order_channel,
                    "base_fee": record.base_fee if record.base_fee is not None else "",
                    "variable_fee": record.variable_fee or "",
                    "currency": record.currency,
                    "source": record.source,
                    "notes": record.notes or "",
                }
            )
