"""Test data quality validation for broker fees based on Rudolf's feedback.

This module contains expected fee data for validation of LLM extraction results
to ensure accuracy against known broker pricing information.
"""
from __future__ import annotations

from typing import Dict, List, Optional
from dataclasses import dataclass

try:
    import pytest
    HAS_PYTEST = True
except ImportError:
    HAS_PYTEST = False

from be_invest.models import FeeRecord


@dataclass
class ExpectedFee:
    """Expected fee data for validation."""
    broker: str
    instrument_type: str
    order_channel: str = "Online Platform"
    base_fee: Optional[float] = None
    variable_fee: Optional[str] = None
    currency: str = "EUR"
    notes: Optional[str] = None
    # Test-specific fields
    trade_size_eur: Optional[float] = None  # For validation
    expected_total_cost_eur: Optional[float] = None  # For validation


# Rudolf's feedback corrections - Expected data quality standards
EXPECTED_BROKER_FEES = {
    "ETF": [
        # ING: correct (as per Rudolf)
        ExpectedFee(
            broker="ING Self Invest",
            instrument_type="ETFs",
            base_fee=7.5,
            variable_fee=None,
            trade_size_eur=5000,
            expected_total_cost_eur=7.5,
            notes="Flat fee structure"
        ),

        # Rebel: correct (as per Rudolf) - formerly Belfius
        ExpectedFee(
            broker="Rebel",  # Renamed from Belfius per Rudolf's request
            instrument_type="ETFs",
            base_fee=0.0,
            variable_fee="0.25%",
            trade_size_eur=5000,
            expected_total_cost_eur=12.5,  # 5000 * 0.0025
            notes="Percentage-based fee structure"
        ),

        # Bolero: CORRECTED - 5k trade cost 15€ not 10€
        ExpectedFee(
            broker="Bolero",
            instrument_type="ETFs",
            base_fee=15.0,  # FIXED: was incorrectly showing 10€
            variable_fee=None,
            trade_size_eur=5000,
            expected_total_cost_eur=15.0,
            notes="Flat fee structure - corrected from 10€ to 15€"
        ),

        # Degiro: CORRECTED - missing 1€ handling fee
        ExpectedFee(
            broker="Degiro Belgium",
            instrument_type="ETFs",
            base_fee=1.0,  # FIXED: was missing 1€ handling fee
            variable_fee=None,
            trade_size_eur=5000,
            expected_total_cost_eur=1.0,
            notes="1€ handling fee was missing from previous extraction"
        ),

        # Keytrade: correct (as per Rudolf)
        ExpectedFee(
            broker="Keytrade Bank",
            instrument_type="ETFs",
            base_fee=0.0,
            variable_fee="0.19%",
            trade_size_eur=5000,
            expected_total_cost_eur=9.5,  # 5000 * 0.0019
            notes="Percentage-based fee structure"
        ),
    ],

    "Stocks": [
        # ING: correct (as per Rudolf)
        ExpectedFee(
            broker="ING Self Invest",
            instrument_type="Equities",
            base_fee=7.5,
            variable_fee=None,
            trade_size_eur=5000,
            expected_total_cost_eur=7.5,
            notes="Flat fee structure"
        ),

        # Rebel: CORRECTED - was using Paris/Amsterdam data instead of Brussels
        ExpectedFee(
            broker="Rebel",  # Renamed from Belfius per Rudolf's request
            instrument_type="Equities",
            base_fee=3.0,  # FIXED: Euronext Brussels data, not Paris/Amsterdam
            variable_fee=None,
            trade_size_eur=2500,  # Up to 2.5k cost 3€
            expected_total_cost_eur=3.0,
            notes="Euronext Brussels pricing, not Paris/Amsterdam - up to 2.5k cost 3€"
        ),

        # Bolero: CORRECTED - 5k trade costs 15€ not 10€
        ExpectedFee(
            broker="Bolero",
            instrument_type="Equities",
            base_fee=15.0,  # FIXED: was incorrectly showing 10€
            variable_fee=None,
            trade_size_eur=5000,
            expected_total_cost_eur=15.0,
            notes="Flat fee structure - corrected from 10€ to 15€"
        ),

        # Degiro: CORRECTED - missing 1€ handling fee
        ExpectedFee(
            broker="Degiro Belgium",
            instrument_type="Equities",
            base_fee=1.0,  # FIXED: was missing 1€ handling fee
            variable_fee="€2 + 0.026%",
            trade_size_eur=5000,
            expected_total_cost_eur=3.3,  # 1€ + 2€ + (5000 * 0.00026)
            notes="1€ handling fee + €2 base + 0.026% variable fee"
        ),
    ]
}

# Fee structure types for analysis
FEE_STRUCTURE_TYPES = {
    "tiered": "Fee varies by trade size bands",
    "flat": "Fixed fee regardless of trade size",
    "percentage": "Percentage of trade value",
    "composite": "Combination of flat + percentage"
}

# Custody fee expectations
EXPECTED_CUSTODY_FEES = {
    "ING Self Invest": {"has_custody_fee": True, "amount": "0.24% annually", "notes": "Annual custody fee"},
    "Rebel": {"has_custody_fee": False, "amount": None, "notes": "No custody fee"},
    "Bolero": {"has_custody_fee": True, "amount": "0.15% annually", "notes": "Annual custody fee"},
    "Degiro Belgium": {"has_custody_fee": False, "amount": None, "notes": "No custody fee"},
    "Keytrade Bank": {"has_custody_fee": False, "amount": None, "notes": "No custody fee"},
}

# Investor scenario parameters
INVESTOR_SCENARIOS = {
    "A": {
        "lump_sum": 0.0,
        "monthly_investment": 169.0,
        "duration_years": 5,
        "description": "Monthly investor starting from zero"
    },
    "B": {
        "lump_sum": 10000.0,
        "monthly_investment": 500.0,
        "duration_years": 5,
        "description": "High-value investor with lump sum + monthly"
    }
}


def validate_fee_structure_type(fee_record: FeeRecord) -> str:
    """Determine fee structure type from a FeeRecord."""
    if fee_record.base_fee is not None and fee_record.variable_fee is not None:
        return "composite"
    elif fee_record.variable_fee is not None and "%" in str(fee_record.variable_fee):
        return "percentage"
    elif fee_record.base_fee is not None:
        return "flat"
    else:
        return "unknown"


def calculate_total_cost(fee_record: FeeRecord, trade_value_eur: float) -> float:
    """Calculate total trading cost for a given trade value."""
    total = 0.0

    if fee_record.base_fee is not None:
        total += fee_record.base_fee

    if fee_record.variable_fee is not None:
        variable_str = str(fee_record.variable_fee)

        # Handle percentage fees
        if "%" in variable_str:
            # Extract percentage value
            import re
            pct_match = re.search(r'(\d+\.?\d*)%', variable_str)
            if pct_match:
                percentage = float(pct_match.group(1)) / 100
                total += trade_value_eur * percentage

        # Handle composite fees like "€2 + 0.026%"
        composite_match = re.search(r'€(\d+\.?\d*)\s*\+\s*(\d+\.?\d*)%', variable_str)
        if composite_match:
            base_amount = float(composite_match.group(1))
            percentage = float(composite_match.group(2)) / 100
            total += base_amount + (trade_value_eur * percentage)

    return round(total, 2)


def calculate_investor_scenario_cost(
    fee_record: FeeRecord,
    scenario: Dict,
    custody_fee_info: Dict
) -> Dict:
    """Calculate total cost for an investor scenario over 5 years."""
    lump_sum = scenario["lump_sum"]
    monthly = scenario["monthly_investment"]
    years = scenario["duration_years"]

    # Transaction costs
    transaction_cost = 0.0

    # Lump sum transaction cost
    if lump_sum > 0:
        transaction_cost += calculate_total_cost(fee_record, lump_sum)

    # Monthly transaction costs
    monthly_transactions = years * 12
    monthly_cost = calculate_total_cost(fee_record, monthly)
    transaction_cost += monthly_cost * monthly_transactions

    # Custody fee calculation (if applicable)
    custody_cost = 0.0
    if custody_fee_info.get("has_custody_fee", False):
        # Simplified calculation - assumes average portfolio value
        total_invested = lump_sum + (monthly * monthly_transactions)
        avg_portfolio = total_invested / 2  # Simple average over time

        # Extract custody fee percentage
        custody_amount = custody_fee_info.get("amount", "")
        if "%" in custody_amount:
            import re
            pct_match = re.search(r'(\d+\.?\d*)%', custody_amount)
            if pct_match:
                annual_rate = float(pct_match.group(1)) / 100
                custody_cost = avg_portfolio * annual_rate * years

    return {
        "transaction_cost": round(transaction_cost, 2),
        "custody_cost": round(custody_cost, 2),
        "total_cost": round(transaction_cost + custody_cost, 2),
        "total_invested": lump_sum + (monthly * monthly_transactions)
    }


class TestDataQualityValidation:
    """Test suite for data quality validation."""

    def test_expected_etf_fees(self):
        """Validate that extracted ETF fees match Rudolf's expectations."""
        expected_fees = EXPECTED_BROKER_FEES["ETF"]

        for expected in expected_fees:
            # This would test against actual LLM extraction results
            # For now, we define the expected structure
            assert expected.broker is not None
            assert expected.instrument_type == "ETFs"

            if expected.trade_size_eur and expected.expected_total_cost_eur:
                # Create a temporary FeeRecord for cost calculation
                test_record = FeeRecord(
                    broker=expected.broker,
                    instrument_type=expected.instrument_type,
                    order_channel=expected.order_channel,
                    base_fee=expected.base_fee,
                    variable_fee=expected.variable_fee,
                    currency=expected.currency,
                    source="test_validation",
                    notes=expected.notes
                )

                calculated_cost = calculate_total_cost(test_record, expected.trade_size_eur)
                assert calculated_cost == expected.expected_total_cost_eur, \
                    f"{expected.broker} ETF cost mismatch: expected {expected.expected_total_cost_eur}, got {calculated_cost}"

    def test_expected_stock_fees(self):
        """Validate that extracted stock fees match Rudolf's expectations."""
        expected_fees = EXPECTED_BROKER_FEES["Stocks"]

        for expected in expected_fees:
            assert expected.broker is not None
            assert expected.instrument_type == "Equities"

            if expected.trade_size_eur and expected.expected_total_cost_eur:
                test_record = FeeRecord(
                    broker=expected.broker,
                    instrument_type=expected.instrument_type,
                    order_channel=expected.order_channel,
                    base_fee=expected.base_fee,
                    variable_fee=expected.variable_fee,
                    currency=expected.currency,
                    source="test_validation",
                    notes=expected.notes
                )

                calculated_cost = calculate_total_cost(test_record, expected.trade_size_eur)
                assert calculated_cost == expected.expected_total_cost_eur, \
                    f"{expected.broker} Stock cost mismatch: expected {expected.expected_total_cost_eur}, got {calculated_cost}"

    def test_fee_structure_identification(self):
        """Test fee structure type identification."""
        # Test flat fee
        flat_fee = FeeRecord("Test", "ETFs", "Online Platform", 15.0, None, "EUR", "test")
        assert validate_fee_structure_type(flat_fee) == "flat"

        # Test percentage fee
        pct_fee = FeeRecord("Test", "ETFs", "Online Platform", 0.0, "0.25%", "EUR", "test")
        assert validate_fee_structure_type(pct_fee) == "percentage"

        # Test composite fee
        comp_fee = FeeRecord("Test", "ETFs", "Online Platform", 2.0, "0.026%", "EUR", "test")
        assert validate_fee_structure_type(comp_fee) == "composite"

    def test_investor_scenarios(self):
        """Test investor scenario calculations."""
        # Test with a sample fee structure
        test_fee = FeeRecord("Test Broker", "ETFs", "Online Platform", 0.0, "0.25%", "EUR", "test")
        test_custody = {"has_custody_fee": True, "amount": "0.24%"}

        scenario_a = INVESTOR_SCENARIOS["A"]
        result_a = calculate_investor_scenario_cost(test_fee, scenario_a, test_custody)

        # Scenario A: 60 monthly trades of €169 each
        expected_transactions_a = 60 * (169 * 0.0025)  # 60 trades * €169 * 0.25%

        assert result_a["transaction_cost"] == round(expected_transactions_a, 2)
        assert result_a["total_invested"] == 169 * 60  # €10,140

        scenario_b = INVESTOR_SCENARIOS["B"]
        result_b = calculate_investor_scenario_cost(test_fee, scenario_b, test_custody)

        # Scenario B: 1 lump sum + 60 monthly trades
        expected_transactions_b = (10000 * 0.0025) + (60 * (500 * 0.0025))

        assert result_b["transaction_cost"] == round(expected_transactions_b, 2)
        assert result_b["total_invested"] == 10000 + (500 * 60)  # €40,000


if __name__ == "__main__":
    # Run some basic validation
    print("Running data quality validation tests...")

    test_suite = TestDataQualityValidation()
    try:
        test_suite.test_expected_etf_fees()
        print("✓ ETF fee validation passed")

        test_suite.test_expected_stock_fees()
        print("✓ Stock fee validation passed")

        test_suite.test_fee_structure_identification()
        print("✓ Fee structure identification passed")

        test_suite.test_investor_scenarios()
        print("✓ Investor scenario calculations passed")

        print("\nAll data quality validation tests passed!")

    except AssertionError as e:
        print(f"❌ Test failed: {e}")
    except Exception as e:
        print(f"❌ Error running tests: {e}")
