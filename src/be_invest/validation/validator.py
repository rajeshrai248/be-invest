"""Validates LLM-generated cost comparison tables against deterministic fee calculations.

Provides:
- validate_comparison_table(): checks each broker fee cell against calculate_fee()
- build_correction_prompt(): builds retry prompt with specific error corrections
- patch_table_with_corrections(): overwrites wrong values as last resort
"""

import logging
from dataclasses import dataclass, field
from typing import List, Optional

from .fee_calculator import calculate_fee, generate_explanation

logger = logging.getLogger(__name__)

TRANSACTION_SIZES = ["250", "500", "1000", "1500", "2000", "2500", "5000", "10000", "50000"]
ASSET_TYPES = ["stocks", "etfs", "bonds"]
TOLERANCE = 0.01  # Allow ±€0.01 rounding tolerance


@dataclass
class ValidationError:
    """A single fee cell that doesn't match the deterministic calculation."""
    broker: str
    instrument: str
    amount: str
    llm_value: float
    expected_value: float
    explanation: str


@dataclass
class ValidationResult:
    """Result of validating a full cost comparison table."""
    is_valid: bool
    errors: List[ValidationError] = field(default_factory=list)
    checked: int = 0
    passed: int = 0


def _extract_numeric(value) -> Optional[float]:
    """Extract a numeric fee from an LLM response cell value.

    Handles: 3.0, "3.00", "€3.00", "$3.00", "3,00"
    """
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        # Strip currency symbols and whitespace
        cleaned = value.strip().replace("€", "").replace("$", "").replace(",", ".").strip()
        try:
            return float(cleaned)
        except ValueError:
            return None
    return None


def _explain_fee(broker: str, instrument: str, amount: float, expected: float) -> str:
    """Generate a human-readable explanation of how the expected fee was calculated."""
    return generate_explanation(broker, instrument, amount)


def validate_comparison_table(table_data: dict) -> ValidationResult:
    """Validate an LLM-generated cost comparison table against deterministic fee calculations.

    Walks the response structure (euronext_brussels.stocks/etfs/bonds arrays)
    and checks each broker's fee at each amount against calculate_fee().

    Args:
        table_data: The parsed JSON response from the LLM.

    Returns:
        ValidationResult with is_valid=True if all checkable cells match.
    """
    errors: List[ValidationError] = []
    checked = 0
    passed = 0

    # Find the exchange data (usually "euronext_brussels")
    for exchange_key, exchange_data in table_data.items():
        if not isinstance(exchange_data, dict):
            continue
        # Skip metadata keys
        if exchange_key.startswith("_"):
            continue

        for asset_type in ASSET_TYPES:
            if asset_type not in exchange_data:
                continue
            asset_data = exchange_data[asset_type]

            # Support both array format [{"broker": "X", "250": ...}]
            # and dict format {"X": {"250": ...}}
            if isinstance(asset_data, list):
                rows = []
                for row in asset_data:
                    if isinstance(row, dict) and "broker" in row:
                        rows.append((row["broker"], row))
            elif isinstance(asset_data, dict):
                rows = []
                for broker_name, fee_dict in asset_data.items():
                    if isinstance(fee_dict, dict):
                        rows.append((broker_name, fee_dict))
            else:
                continue

            for broker, row in rows:
                for size_str in TRANSACTION_SIZES:
                    if size_str not in row:
                        continue

                    expected = calculate_fee(broker, asset_type, float(size_str))
                    if expected is None:
                        # No rule for this broker/instrument combo -- skip
                        continue

                    checked += 1
                    llm_raw = row[size_str]
                    llm_value = _extract_numeric(llm_raw)

                    if llm_value is None:
                        errors.append(ValidationError(
                            broker=broker,
                            instrument=asset_type,
                            amount=size_str,
                            llm_value=0.0,
                            expected_value=expected,
                            explanation=f"Could not parse LLM value: {llm_raw!r}",
                        ))
                        continue

                    if abs(llm_value - expected) <= TOLERANCE:
                        passed += 1
                    else:
                        explanation = _explain_fee(broker, asset_type, float(size_str), expected)
                        errors.append(ValidationError(
                            broker=broker,
                            instrument=asset_type,
                            amount=size_str,
                            llm_value=llm_value,
                            expected_value=expected,
                            explanation=explanation,
                        ))

    return ValidationResult(
        is_valid=len(errors) == 0,
        errors=errors,
        checked=checked,
        passed=passed,
    )


def build_correction_prompt(errors: List[ValidationError]) -> str:
    """Build a string to append to the LLM prompt on retry with specific corrections.

    Produces a numbered list of errors with the correct value and explanation.
    """
    if not errors:
        return ""

    lines = [
        "",
        "CORRECTIONS FROM PREVIOUS ATTEMPT (YOU MUST FIX THESE):",
        "",
    ]
    for i, err in enumerate(errors, 1):
        lines.append(
            f"{i}. {err.broker} {err.instrument} €{err.amount}: "
            f"you said €{err.llm_value:.2f}, correct answer is €{err.expected_value:.2f}"
        )
        lines.append(f"   Reason: {err.explanation}")

    lines.append("")
    lines.append("Fix ALL of the above values. Do not change any other values that were correct.")
    return "\n".join(lines)


def patch_table_with_corrections(table_data: dict, errors: List[ValidationError]) -> dict:
    """Directly overwrite wrong values in the LLM response with deterministic values.

    Used as last resort after max retries. Modifies table_data in place and returns it.
    """
    # Build a lookup: (broker_lower, instrument, amount_str) -> expected_value
    corrections = {}
    for err in errors:
        key = (err.broker.lower(), err.instrument.lower(), err.amount)
        corrections[key] = err.expected_value

    for exchange_key, exchange_data in table_data.items():
        if not isinstance(exchange_data, dict) or exchange_key.startswith("_"):
            continue

        for asset_type in ASSET_TYPES:
            if asset_type not in exchange_data:
                continue
            asset_data = exchange_data[asset_type]

            # Support both array format and dict format
            if isinstance(asset_data, list):
                items = []
                for row in asset_data:
                    if isinstance(row, dict) and "broker" in row:
                        items.append((row["broker"], row))
            elif isinstance(asset_data, dict):
                items = [(broker_name, fee_dict) for broker_name, fee_dict in asset_data.items()
                         if isinstance(fee_dict, dict)]
            else:
                continue

            for broker_name, row in items:
                broker_lower = broker_name.lower()
                for size_str in TRANSACTION_SIZES:
                    if size_str not in row:
                        continue
                    key = (broker_lower, asset_type.lower(), size_str)
                    if key in corrections:
                        old_val = row[size_str]
                        row[size_str] = corrections[key]
                        logger.info(
                            f"Patched {broker_name} {asset_type} EUR{size_str}: "
                            f"{old_val} -> {corrections[key]}"
                        )

    return table_data
