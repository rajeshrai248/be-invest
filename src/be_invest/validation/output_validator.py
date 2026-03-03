"""Output validator for API responses to ensure calculation accuracy.

This module validates that all fees, rankings, and comparative statements
in API responses match the deterministic calculations from fee_calculator.py.

Use this before sending data to the frontend to catch LLM hallucinations
or calculation errors.
"""

import logging
from typing import Dict, Any, List, Optional, Tuple
from decimal import Decimal

from .fee_calculator import calculate_fee, _get_display_name, _ensure_rules_loaded

logger = logging.getLogger(__name__)


class ValidationError:
    """A single validation error found in the output."""
    
    def __init__(self, field: str, expected: Any, actual: Any, description: str):
        self.field = field
        self.expected = expected
        self.actual = actual
        self.description = description
    
    def __repr__(self):
        return f"ValidationError({self.field}: expected={self.expected}, actual={self.actual}, desc='{self.description}')"


class ValidationResult:
    """Result of output validation."""
    
    def __init__(self):
        self.errors: List[ValidationError] = []
        self.warnings: List[str] = []
        self.validated_fields: int = 0
    
    def add_error(self, field: str, expected: Any, actual: Any, description: str):
        """Add a validation error."""
        self.errors.append(ValidationError(field, expected, actual, description))
    
    def add_warning(self, message: str):
        """Add a validation warning."""
        self.warnings.append(message)
    
    def is_valid(self) -> bool:
        """Check if validation passed (no errors)."""
        return len(self.errors) == 0
    
    def get_summary(self) -> Dict[str, Any]:
        """Get validation summary."""
        return {
            "valid": self.is_valid(),
            "errors": len(self.errors),
            "warnings": len(self.warnings),
            "validated_fields": self.validated_fields,
            "error_details": [
                {
                    "field": e.field,
                    "expected": e.expected,
                    "actual": e.actual,
                    "description": e.description
                }
                for e in self.errors
            ],
            "warning_messages": self.warnings
        }


def _fees_match(calculated: float, stated: float, tolerance: float = 0.01) -> bool:
    """Check if two fees match within tolerance."""
    return abs(calculated - stated) <= tolerance


def validate_fee_table(
    broker_name: str,
    instrument: str,
    fee_table: Dict[str, float],
    result: ValidationResult
) -> None:
    """Validate a broker's fee table for an instrument against deterministic calculations.
    
    Args:
        broker_name: Broker name
        instrument: Instrument type (stocks, etfs, bonds)
        fee_table: Dict mapping amount strings to fee values
        result: ValidationResult to accumulate errors
    """
    _ensure_rules_loaded()
    
    for amount_str, stated_fee in fee_table.items():
        if stated_fee is None:
            continue
            
        try:
            amount = float(amount_str)
        except (ValueError, TypeError):
            result.add_warning(f"Invalid amount format: {amount_str}")
            continue
        
        calculated_fee = calculate_fee(broker_name, instrument, amount)
        
        if calculated_fee is None:
            result.add_warning(
                f"No fee rule for {broker_name} {instrument} - cannot validate {amount_str}"
            )
            continue
        
        result.validated_fields += 1
        
        if not _fees_match(calculated_fee, stated_fee):
            result.add_error(
                field=f"{broker_name}.{instrument}.{amount_str}",
                expected=calculated_fee,
                actual=stated_fee,
                description=f"Fee mismatch for {broker_name} {instrument} €{amount}: expected €{calculated_fee:.2f}, got €{stated_fee:.2f}"
            )


def validate_comparison_tables(data: Dict[str, Any]) -> ValidationResult:
    """Validate cost comparison tables output.
    
    Args:
        data: The response data from /cost-comparison-tables endpoint
        
    Returns:
        ValidationResult with any errors found
    """
    result = ValidationResult()
    _ensure_rules_loaded()
    
    # Get the euronext_brussels data
    exchange_data = data.get("euronext_brussels", {})
    if not exchange_data:
        result.add_warning("No euronext_brussels data found")
        return result
    
    # Validate each instrument type
    for instrument in ["stocks", "etfs", "bonds"]:
        instrument_data = exchange_data.get(instrument, {})
        
        for broker_name, fee_table in instrument_data.items():
            if not isinstance(fee_table, dict):
                continue
            
            validate_fee_table(broker_name, instrument, fee_table, result)
    
    # Validate investor persona rankings if present
    personas = exchange_data.get("investor_personas", {})
    if personas:
        validate_persona_rankings(personas, result)
    
    return result


def validate_persona_rankings(personas: Dict[str, Any], result: ValidationResult) -> None:
    """Validate that persona cost rankings are correct.
    
    Args:
        personas: investor_personas dict
        result: ValidationResult to accumulate errors
    """
    for persona_key, persona_data in personas.items():
        rankings = persona_data.get("rankings", [])
        
        if len(rankings) < 2:
            continue
        
        # Check that costs are in ascending order (rank 1 should be cheapest)
        for i in range(len(rankings) - 1):
            current = rankings[i]
            next_item = rankings[i + 1]
            
            current_cost = current.get("cost", 0)
            next_cost = next_item.get("cost", 0)
            current_rank = current.get("rank", 0)
            next_rank = next_item.get("rank", 0)
            
            # Rank should increase
            if current_rank >= next_rank:
                result.add_error(
                    field=f"personas.{persona_key}.rankings[{i}].rank",
                    expected=f"< {next_rank}",
                    actual=current_rank,
                    description=f"Rank order violation: {current['broker']} rank {current_rank} should be < {next_item['broker']} rank {next_rank}"
                )
            
            # Cost should increase with rank
            if current_cost > next_cost:
                result.add_error(
                    field=f"personas.{persona_key}.rankings[{i}].cost",
                    expected=f"<= {next_cost}",
                    actual=current_cost,
                    description=f"Cost order violation: {current['broker']} (€{current_cost:.2f}) should be <= {next_item['broker']} (€{next_cost:.2f})"
                )
            
            result.validated_fields += 1


def validate_cheapest_claims(data: Dict[str, Any], result: ValidationResult) -> None:
    """Validate 'cheapest' claims against actual fee data.
    
    Args:
        data: Response data containing cheapestPerTier or similar fields
        result: ValidationResult to accumulate errors
    """
    cheapest_per_tier = data.get("cheapestPerTier", {})
    
    if not cheapest_per_tier:
        return
    
    _ensure_rules_loaded()
    
    for instrument, tiers in cheapest_per_tier.items():
        if not isinstance(tiers, dict):
            continue
            
        for amount_str, claim in tiers.items():
            try:
                amount = float(amount_str)
            except (ValueError, TypeError):
                continue
            
            # Parse claim (format: "Broker Name (€XX.XX)")
            if not isinstance(claim, str) or "(" not in claim:
                result.add_warning(f"Invalid cheapest claim format: {claim}")
                continue
            
            claimed_broker = claim.split("(")[0].strip()
            claimed_cost_str = claim.split("(")[1].rstrip(")").replace("€", "").strip()
            
            try:
                claimed_cost = float(claimed_cost_str)
            except ValueError:
                result.add_warning(f"Invalid cost format in claim: {claim}")
                continue
            
            # Verify this is actually the cheapest
            actual_cheapest_broker, actual_cheapest_cost = find_cheapest_broker(
                instrument, amount
            )
            
            if actual_cheapest_broker is None:
                result.add_warning(f"Could not determine cheapest for {instrument} €{amount}")
                continue
            
            result.validated_fields += 1
            
            # Check if claimed broker matches actual cheapest
            if claimed_broker.lower() != actual_cheapest_broker.lower():
                result.add_error(
                    field=f"cheapestPerTier.{instrument}.{amount_str}",
                    expected=f"{actual_cheapest_broker} (€{actual_cheapest_cost:.2f})",
                    actual=claim,
                    description=f"Wrong cheapest broker for {instrument} €{amount}: claimed {claimed_broker}, but {actual_cheapest_broker} is cheaper (€{actual_cheapest_cost:.2f} vs €{claimed_cost:.2f})"
                )
            elif not _fees_match(claimed_cost, actual_cheapest_cost):
                result.add_error(
                    field=f"cheapestPerTier.{instrument}.{amount_str}.cost",
                    expected=actual_cheapest_cost,
                    actual=claimed_cost,
                    description=f"Wrong cost for {claimed_broker}: claimed €{claimed_cost:.2f}, actual €{actual_cheapest_cost:.2f}"
                )


def find_cheapest_broker(instrument: str, amount: float) -> Tuple[Optional[str], Optional[float]]:
    """Find the cheapest broker for an instrument/amount combination.
    
    Returns:
        Tuple of (broker_name, cost) or (None, None) if no data available
    """
    _ensure_rules_loaded()
    
    from .fee_calculator import FEE_RULES
    
    cheapest_broker = None
    cheapest_cost = float('inf')
    
    for (broker_key, instr_key, exch_key), rule in FEE_RULES.items():
        if instr_key != instrument.lower():
            continue
        
        cost = calculate_fee(rule.broker, instrument, amount)
        if cost is not None and cost < cheapest_cost:
            cheapest_cost = cost
            cheapest_broker = _get_display_name(rule.broker)
    
    if cheapest_broker is None:
        return None, None
    
    return cheapest_broker, cheapest_cost


def compute_cheapest_per_tier(broker_names: Optional[List[str]] = None) -> Dict[str, Dict[str, str]]:
    """Deterministically compute the cheapest broker for each tier/amount.
    
    Args:
        broker_names: Optional list of broker names to consider. If None, uses all brokers with rules.
        
    Returns:
        Dict with structure:
        {
            "stocks": {"250": "Broker (€X.XX)", "2500": "Broker (€X.XX)", ...},
            "etfs": {"500": "Broker (€X.XX)", ...}
        }
    """
    _ensure_rules_loaded()
    
    result = {"stocks": {}, "etfs": {}, "bonds": {}}
    tiers = {
        "stocks": [250, 2500, 10000, 50000],
        "etfs": [500, 5000],
        "bonds": [10000]
    }
    
    for instrument, amounts in tiers.items():
        for amount in amounts:
            cheapest_broker, cheapest_cost = find_cheapest_broker(instrument, amount)
            
            if cheapest_broker is not None:
                result[instrument][str(amount)] = f"{cheapest_broker} (€{cheapest_cost:.2f})"
    
    return result


def find_cheapest_broker(instrument: str, amount: float) -> Tuple[Optional[str], Optional[float]]:
    """Find the cheapest broker for an instrument/amount combination.
    
    Returns:
        Tuple of (broker_name, cost) or (None, None) if no data available
    """
    _ensure_rules_loaded()
    
    from .fee_calculator import FEE_RULES
    
    cheapest_broker = None
    cheapest_cost = float('inf')
    
    for (broker_key, instr_key, exch_key), rule in FEE_RULES.items():
        if instr_key != instrument.lower():
            continue
        
        cost = calculate_fee(rule.broker, instrument, amount)
        if cost is not None and cost < cheapest_cost:
            cheapest_cost = cost
            cheapest_broker = _get_display_name(rule.broker)
    
    if cheapest_broker is None:
        return None, None
    
    return cheapest_broker, cheapest_cost


def validate_financial_analysis(data: Dict[str, Any]) -> ValidationResult:
    """Validate financial analysis output.
    
    Args:
        data: The response data from /financial-analysis endpoint
        
    Returns:
        ValidationResult with any errors found
    """
    result = ValidationResult()
    
    # Validate cheapest per tier claims
    validate_cheapest_claims(data, result)
    
    # Validate cost comparison rankings
    cost_comparison = data.get("costComparison", {})
    for persona_key, rankings in cost_comparison.items():
        if not isinstance(rankings, list):
            continue
        
        # Verify rankings are in cost order
        for i in range(len(rankings) - 1):
            current = rankings[i]
            next_item = rankings[i + 1]
            
            if not isinstance(current, dict) or not isinstance(next_item, dict):
                continue
            
            current_cost = current.get("annualCost", 0)
            next_cost = next_item.get("annualCost", 0)
            current_rank = current.get("rank", 0)
            next_rank = next_item.get("rank", 0)
            
            result.validated_fields += 1
            
            if current_cost > next_cost and current_rank < next_rank:
                result.add_error(
                    field=f"costComparison.{persona_key}[{i}]",
                    expected=f"cost <= {next_cost} for rank {current_rank}",
                    actual=current_cost,
                    description=f"{current['broker']} (rank {current_rank}, €{current_cost}) has higher cost than {next_item['broker']} (rank {next_rank}, €{next_cost})"
                )
    
    return result


def auto_fix_rankings(data: Dict[str, Any]) -> Dict[str, Any]:
    """Auto-fix ranking errors by recomputing ranks from costs.
    
    Args:
        data: Response data with potentially wrong rankings
        
    Returns:
        Fixed data with correct rankings
    """
    # Fix investor persona rankings
    exchange_data = data.get("euronext_brussels", {})
    personas = exchange_data.get("investor_personas", {})
    
    for persona_key, persona_data in personas.items():
        rankings = persona_data.get("rankings", [])
        
        if len(rankings) < 2:
            continue
        
        # Sort by cost and reassign ranks
        sorted_rankings = sorted(rankings, key=lambda x: x.get("cost", float('inf')))
        for i, item in enumerate(sorted_rankings):
            item["rank"] = i + 1
        
        persona_data["rankings"] = sorted_rankings
    
    # Fix costComparison rankings in financial-analysis
    cost_comparison = data.get("costComparison", {})
    for persona_key, rankings in cost_comparison.items():
        if not isinstance(rankings, list) or len(rankings) < 2:
            continue
        
        # Sort by annual cost and reassign ranks
        sorted_rankings = sorted(rankings, key=lambda x: x.get("annualCost", float('inf')))
        for i, item in enumerate(sorted_rankings):
            item["rank"] = i + 1
        
        cost_comparison[persona_key] = sorted_rankings
    
    return data


def validate_and_fix(data: Dict[str, Any], endpoint: str) -> Tuple[Dict[str, Any], ValidationResult]:
    """Validate API response and auto-fix if possible.
    
    Args:
        data: API response data
        endpoint: Endpoint name (cost-comparison-tables, financial-analysis)
        
    Returns:
        Tuple of (fixed_data, validation_result)
    """
    # Validate first
    if endpoint == "cost-comparison-tables":
        result = validate_comparison_tables(data)
    elif endpoint == "financial-analysis":
        result = validate_financial_analysis(data)
    else:
        result = ValidationResult()
        result.add_warning(f"Unknown endpoint: {endpoint}")
        return data, result
    
    # If there are errors, try to auto-fix
    if not result.is_valid():
        logger.warning(f"Validation failed for {endpoint}: {len(result.errors)} errors found")
        fixed_data = auto_fix_rankings(data)
        
        # Validate again after fixing
        if endpoint == "cost-comparison-tables":
            revalidation = validate_comparison_tables(fixed_data)
        else:
            revalidation = validate_financial_analysis(fixed_data)
        
        if revalidation.is_valid():
            logger.info(f"Auto-fix successful: corrected {len(result.errors)} errors")
            return fixed_data, revalidation
        else:
            logger.warning(f"Auto-fix incomplete: {len(revalidation.errors)} errors remain")
            return fixed_data, revalidation
    
    return data, result
