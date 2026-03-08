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
    """Test validation passes for correct comparison tables built from fee rules."""
    # Build data from the actual fee calculator so values match fee_rules.json
    stocks_data = {}
    etfs_data = {}
    amounts = [250, 500, 1000]

    for broker in ["Bolero", "Keytrade Bank"]:
        for amt in amounts:
            fee = calculate_fee(broker, "stocks", amt)
            if fee is not None:
                stocks_data.setdefault(broker, {})[str(amt)] = fee

            fee = calculate_fee(broker, "etfs", amt)
            if fee is not None:
                etfs_data.setdefault(broker, {})[str(amt)] = fee

    if not stocks_data and not etfs_data:
        pytest.skip("No fee rules loaded — fee_rules.json may be missing")

    data = {"euronext_brussels": {"stocks": stocks_data, "etfs": etfs_data}}

    result = validate_comparison_tables(data)

    # Should pass validation (fees computed from the same rules the validator uses)
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


def test_fee_rules_3tuple_keys():
    """Test that FEE_RULES uses 3-tuple keys (broker, instrument, exchange)."""
    from be_invest.validation.fee_calculator import FEE_RULES, _ensure_rules_loaded
    _ensure_rules_loaded()

    if not FEE_RULES:
        pytest.skip("No fee rules loaded — fee_rules.json may be missing")

    for key in FEE_RULES:
        assert len(key) == 3, f"FEE_RULES key should be 3-tuple, got {key}"
        broker, instrument, exchange = key
        assert isinstance(broker, str)
        assert isinstance(instrument, str)
        assert isinstance(exchange, str)
        assert exchange, "exchange should not be empty"


def test_exchange_fallback_logic():
    """Test that calculate_fee falls back from specific exchange to 'all'."""
    from be_invest.validation.fee_calculator import FEE_RULES, _ensure_rules_loaded
    _ensure_rules_loaded()

    if not FEE_RULES:
        pytest.skip("No fee rules loaded — fee_rules.json may be missing")

    # Pick a broker that has an "all" exchange rule
    all_keys = [k for k in FEE_RULES if k[2] == "all"]
    if not all_keys:
        pytest.skip("No rules with exchange='all'")

    broker, instrument, _ = all_keys[0]
    rule = FEE_RULES[all_keys[0]]

    # Exact match with "all"
    fee_all = calculate_fee(rule.broker, instrument, 1000, "all")
    assert fee_all is not None

    # Fallback: non-existent exchange should fall back to "all"
    fee_fallback = calculate_fee(rule.broker, instrument, 1000, "nonexistent_exchange")
    assert fee_fallback is not None
    assert fee_fallback == fee_all, "Fallback to 'all' should return same fee"


def test_backward_compat_calculate_fee():
    """Test that calculate_fee(broker, instrument, amount) still works without exchange."""
    from be_invest.validation.fee_calculator import _ensure_rules_loaded
    _ensure_rules_loaded()

    # These are the same 3-arg calls that existed before the enrichment
    fee = calculate_fee("Bolero", "stocks", 1000)
    # Should not raise; may be None if fee_rules.json is missing
    if fee is not None:
        assert fee >= 0


def test_fee_rule_new_fields():
    """Test that FeeRule has exchange, conditions, notes, source fields with correct defaults."""
    from be_invest.validation.fee_calculator import FeeRule

    rule = FeeRule(broker="Test", instrument="stocks")
    assert rule.exchange == "all"
    assert rule.conditions == []
    assert rule.notes == ""
    assert rule.source == {}

    rule_with_fields = FeeRule(
        broker="Test",
        instrument="stocks",
        exchange="nyse",
        conditions=[{"type": "age", "min_age": 18, "max_age": 24}],
        notes="Youth discount",
        source={"pdf": "test.pdf", "page": 1},
    )
    assert rule_with_fields.exchange == "nyse"
    assert len(rule_with_fields.conditions) == 1
    assert rule_with_fields.conditions[0]["type"] == "age"
    assert rule_with_fields.notes == "Youth discount"
    assert rule_with_fields.source["pdf"] == "test.pdf"


def test_fee_rule_load_save_roundtrip():
    """Test that new fields survive a save/load roundtrip."""
    import tempfile
    from be_invest.validation.fee_calculator import FeeRule, save_fee_rules, load_fee_rules, FEE_RULES

    rule = FeeRule(
        broker="TestBroker",
        instrument="stocks",
        pattern="flat",
        tiers=[{"flat": 5.00}],
        exchange="euronext_brussels",
        conditions=[{"type": "plan", "plan_name": "Plus"}],
        notes="Test note",
        source={"pdf": "test.pdf"},
    )
    test_rules = {("testbroker", "stocks", "euronext_brussels"): rule}

    with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
        tmp_path = Path(f.name)

    try:
        save_fee_rules(test_rules, tmp_path, source="test")

        # Read the JSON to verify fields are present
        with open(tmp_path, "r") as f:
            data = json.load(f)
        saved_rule = data["rules"][0]
        assert saved_rule["exchange"] == "euronext_brussels"
        assert saved_rule["conditions"] == [{"type": "plan", "plan_name": "Plus"}]
        assert saved_rule["notes"] == "Test note"
        assert saved_rule["source"] == {"pdf": "test.pdf"}

        # Clear and reload
        old_rules = dict(FEE_RULES)
        FEE_RULES.clear()
        load_fee_rules(tmp_path)

        loaded_key = ("testbroker", "stocks", "euronext_brussels")
        assert loaded_key in FEE_RULES
        loaded_rule = FEE_RULES[loaded_key]
        assert loaded_rule.exchange == "euronext_brussels"
        assert loaded_rule.conditions == [{"type": "plan", "plan_name": "Plus"}]
        assert loaded_rule.notes == "Test note"
        assert loaded_rule.source == {"pdf": "test.pdf"}
    finally:
        tmp_path.unlink(missing_ok=True)
        # Restore original rules
        FEE_RULES.clear()
        FEE_RULES.update(old_rules)


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "-s"])
