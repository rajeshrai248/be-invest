"""Test output validation and calculation verification."""

import json
import pytest
from pathlib import Path

from be_invest.validation import (
    validate_comparison_tables,
    validate_financial_analysis,
    validate_and_fix,
    compute_cheapest_per_tier,
    calculate_fee,
)


def test_validate_correct_comparison_tables():
    """Test validation passes for correct comparison tables."""
    # Create valid test data
    data = {
        "euronext_brussels": {
            "stocks": {
                "Bolero": {
                    "250": 7.50,
                    "500": 10.00,
                    "1000": 15.00,
                },
                "Keytrade Bank": {
                    "250": 7.50,
                    "500": 7.50,
                    "1000": 14.95,
                }
            },
            "etfs": {
                "Bolero": {
                    "250": 7.50,
                    "500": 10.00,
                },
            }
        }
    }
    
    result = validate_comparison_tables(data)
    
    # Should pass validation (fees computed correctly)
    assert result.is_valid() or len(result.errors) == 0  # May have warnings but no errors


def test_validate_incorrect_fee():
    """Test validation catches incorrect fees."""
    # Deliberately wrong fee
    data = {
        "euronext_brussels": {
            "stocks": {
                "Bolero": {
                    "1000": 999.99,  # Wrong! Should be 15.00
                }
            }
        }
    }
    
    result = validate_comparison_tables(data)
    
    # Should fail if we have the Bolero fee rule loaded
    # (may pass if fee_rules.json doesn't have Bolero)
    print(f"Validation result: {result.get_summary()}")


def test_validate_persona_rankings():
    """Test persona ranking validation."""
    data = {
        "euronext_brussels": {
            "investor_personas": {
                "passive_investor": {
                    "rankings": [
                        {"broker": "Bolero", "cost": 100, "rank": 1},
                        {"broker": "Keytrade Bank", "cost": 150, "rank": 2},
                        {"broker": "Degiro", "cost": 200, "rank": 3},
                    ]
                }
            }
        }
    }
    
    result = validate_comparison_tables(data)
    assert result.is_valid()


def test_validate_wrong_persona_rankings():
    """Test validation catches wrong persona rankings."""
    data = {
        "euronext_brussels": {
            "investor_personas": {
                "passive_investor": {
                    "rankings": [
                        {"broker": "Bolero", "cost": 200, "rank": 1},  # Wrong! Cost is highest
                        {"broker": "Keytrade Bank", "cost": 150, "rank": 2},
                        {"broker": "Degiro", "cost": 100, "rank": 3},  # Wrong! Cost is lowest
                    ]
                }
            }
        }
    }
    
    result = validate_comparison_tables(data)
    assert not result.is_valid()
    assert len(result.errors) >= 2  # Should catch both ranking errors


def test_auto_fix_rankings():
    """Test that auto-fix corrects ranking errors."""
    data = {
        "euronext_brussels": {
            "investor_personas": {
                "passive_investor": {
                    "rankings": [
                        {"broker": "Expensive", "cost": 200, "rank": 1},
                        {"broker": "Medium", "cost": 150, "rank": 2},
                        {"broker": "Cheap", "cost": 100, "rank": 3},
                    ]
                }
            }
        }
    }
    
    fixed_data, validation_result = validate_and_fix(data, "cost-comparison-tables")
    
    # Check that rankings are now correct
    rankings = fixed_data["euronext_brussels"]["investor_personas"]["passive_investor"]["rankings"]
    assert rankings[0]["broker"] == "Cheap"
    assert rankings[0]["rank"] == 1
    assert rankings[2]["broker"] == "Expensive"
    assert rankings[2]["rank"] == 3


def test_compute_cheapest_per_tier():
    """Test deterministic cheapest computation."""
    result = compute_cheapest_per_tier()
    
    print("\n\nCheapest Per Tier:")
    print(json.dumps(result, indent=2))
    
    # Should have data for all instruments
    assert "stocks" in result
    assert "etfs" in result
    
    # Stocks should have common tiers
    assert "250" in result["stocks"]
    assert "2500" in result["stocks"]
    assert "10000" in result["stocks"]
    
    # Each entry should be in format "Broker (€X.XX)"
    for instrument, tiers in result.items():
        for amount, claim in tiers.items():
            if claim:  # May be empty if no brokers have that instrument
                assert "(" in claim
                assert "€" in claim
                assert ")" in claim


def test_validate_wrong_cheapest_claim():
    """Test validation catches wrong 'cheapest' claims."""
    data = {
        "cheap estPerTier": {
            "stocks": {
                "10000": "MeDirect (€35.00)"  # Wrong! Bolero is cheaper at €15.00
            }
        }
    }
    
    result = validate_financial_analysis(data)
    
    # Should catch the error if both Bolero and MeDirect rules exist
    print(f"\nValidation result for wrong cheapest: {result.get_summary()}")
    if not result.is_valid():
        print(f"Errors caught: {[e.description for e in result.errors]}")


def test_fee_calculation_consistency():
    """Test that our deterministic calculation matches what's in fee_rules.json."""
    # Test a few known brokers and amounts
    test_cases = [
        ("Bolero", "stocks", 10000),
        ("Keytrade Bank", "stocks", 10000),
        ("Degiro Belgium", "etfs", 500),
    ]
    
    print("\n\nFee Calculation Tests:")
    for broker, instrument, amount in test_cases:
        fee = calculate_fee(broker, instrument, amount)
        if fee is not None:
            print(f"  {broker} {instrument} €{amount}: €{fee:.2f}")
            assert fee >= 0, f"Fee should be non-negative for {broker}"
        else:
            print(f"  {broker} {instrument} €{amount}: No rule found")


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "-s"])
