"""Validation module for cost comparison table fee verification."""

from .fee_calculator import calculate_fee, calculate_all_fees, HiddenCosts, HIDDEN_COSTS
from .validator import validate_comparison_table
from .persona_calculator import compute_persona_costs, build_persona_comparison, PERSONAS
from .output_validator import (
    validate_comparison_tables,
    validate_financial_analysis,
    validate_and_fix,
    ValidationResult,
    ValidationError,
    compute_cheapest_per_tier,
)

__all__ = [
    "calculate_fee",
    "calculate_all_fees",
    "validate_comparison_table",
    "HiddenCosts",
    "HIDDEN_COSTS",
    "compute_persona_costs",
    "build_persona_comparison",
    "PERSONAS",
    "validate_comparison_tables",
    "validate_financial_analysis",
    "validate_and_fix",
    "ValidationResult",
    "ValidationError",
    "compute_cheapest_per_tier",
]
