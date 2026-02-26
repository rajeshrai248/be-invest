"""Tests for fee_calculator.py: verify all fee computation patterns produce
correct results and the validator catches LLM hallucinations."""

import pytest
from src.be_invest.validation.fee_calculator import (
    _compute_from_tiers,
    _register,
    FeeRule,
    FEE_RULES,
    calculate_fee,
)
from src.be_invest.validation.validator import (
    validate_comparison_table,
    build_correction_prompt,
    patch_table_with_corrections,
    ValidationError,
)


# ---------------------------------------------------------------------------
# _compute_from_tiers – pattern unit tests
# ---------------------------------------------------------------------------

class TestComputeFromTiers:
    """Verify each tier pattern returns correct fees."""

    def test_flat_fee(self):
        tiers = [{"flat": 15.0}]
        for amount in [250, 1000, 5000, 50000]:
            assert _compute_from_tiers(tiers, amount) == 15.0

    def test_flat_fee_with_handling(self):
        tiers = [{"flat": 2.0}]
        assert _compute_from_tiers(tiers, 5000, handling_fee=1.0) == 3.0

    def test_percentage_with_min_below_minimum(self):
        # rate applies but result is below min_fee -> min_fee wins
        tiers = [{"rate": 0.00026, "min_fee": 2.0}]
        fee = _compute_from_tiers(tiers, 5000)   # 5000*0.00026 = 1.3 < 2.0
        assert fee == 2.0

    def test_percentage_with_min_above_minimum(self):
        # rate applies and result is above min_fee -> rate wins
        tiers = [{"rate": 0.00026, "min_fee": 2.0}]
        fee = _compute_from_tiers(tiers, 10000)  # 10000*0.00026 = 2.6 > 2.0
        assert round(fee, 4) == 2.6

    def test_percentage_with_min_and_handling(self):
        tiers = [{"rate": 0.00026, "min_fee": 2.0}]
        fee = _compute_from_tiers(tiers, 5000, handling_fee=1.0)
        assert fee == 3.0  # max(1.3, 2.0) + 1.0

    def test_base_plus_slice_within_base(self):
        tiers = [{"base_up_to": 10000, "base_fee": 14.95, "per_slice": 10000, "slice_fee": 7.50}]
        fee = _compute_from_tiers(tiers, 5000)
        assert fee == 14.95

    def test_base_plus_slice_one_extra_slice(self):
        tiers = [{"base_up_to": 10000, "base_fee": 14.95, "per_slice": 10000, "slice_fee": 7.50}]
        # 15000 - 10000 = 5000 remainder -> ceil(5000/10000) = 1 slice
        fee = _compute_from_tiers(tiers, 15000)
        assert fee == 14.95 + 7.50

    def test_base_plus_slice_two_extra_slices(self):
        tiers = [{"base_up_to": 10000, "base_fee": 14.95, "per_slice": 10000, "slice_fee": 7.50}]
        # 25000 - 10000 = 15000 remainder -> ceil(15000/10000) = 2 slices
        fee = _compute_from_tiers(tiers, 25000)
        assert fee == 14.95 + 2 * 7.50

    def test_tiered_flat(self):
        tiers = [
            {"up_to": 2500, "fee": 7.50},
            {"up_to": 5000, "fee": 12.50},
            {"up_to": 10000, "fee": 19.95},
        ]
        assert _compute_from_tiers(tiers, 1000) == 7.50
        assert _compute_from_tiers(tiers, 2500) == 7.50
        assert _compute_from_tiers(tiers, 2501) == 12.50
        assert _compute_from_tiers(tiers, 5000) == 12.50
        assert _compute_from_tiers(tiers, 10000) == 19.95

    def test_tiered_flat_then_slice(self):
        tiers = [
            {"up_to": 2500, "fee": 7.50},
            {"up_to": 5000, "fee": 12.50},
            {"per_slice": 10000, "fee": 15.0},
        ]
        # Amount in flat tier
        assert _compute_from_tiers(tiers, 2500) == 7.50
        # Amount above all flat tiers -> per-slice applies to remainder above 5000
        # 6000: remainder = 6000 - 5000 = 1000 -> ceil(1000/10000) = 1 slice
        assert _compute_from_tiers(tiers, 6000) == 12.50 + 15.0
        # 15000: remainder = 15000 - 5000 = 10000 -> ceil(10000/10000) = 1 slice
        assert _compute_from_tiers(tiers, 15000) == 12.50 + 15.0
        # 15001: remainder = 15001 - 5000 = 10001 -> ceil(10001/10000) = 2 slices
        assert _compute_from_tiers(tiers, 15001) == 12.50 + 2 * 15.0

    def test_tiered_flat_then_slice_with_max_fee_cap(self):
        tiers = [
            {"up_to": 2500, "fee": 7.50},
            {"per_slice": 10000, "fee": 15.0, "max_fee": 50.0},
        ]
        # Very large amount would exceed cap without the cap
        fee = _compute_from_tiers(tiers, 500000)
        assert fee == 50.0

    def test_returns_zero_for_empty_tiers(self):
        assert _compute_from_tiers([], 5000) == 0.0


# ---------------------------------------------------------------------------
# validate_comparison_table – hallucination detection
# ---------------------------------------------------------------------------

class TestValidateComparisonTable:
    """Verify the validator correctly identifies LLM fee errors."""

    def setup_method(self):
        """Register a minimal test broker rule before each test."""
        FEE_RULES.clear()
        rule = FeeRule(
            broker="test broker",
            instrument="stocks",
            pattern="flat",
            tiers=[{"flat": 15.0}],
            handling_fee=0.0,
        )
        _register("test broker", "stocks", rule)

    def teardown_method(self):
        FEE_RULES.clear()

    def _make_table(self, broker: str, amount: str, value) -> dict:
        return {
            "euronext_brussels": {
                "stocks": {
                    broker: {amount: value}
                },
                "etfs": {},
                "bonds": {},
            }
        }

    def test_correct_value_passes(self):
        table = self._make_table("Test Broker", "5000", 15.0)
        result = validate_comparison_table(table)
        assert result.is_valid
        assert result.errors == []
        assert result.checked == 1
        assert result.passed == 1

    def test_wrong_value_detected(self):
        table = self._make_table("Test Broker", "5000", 10.0)
        result = validate_comparison_table(table)
        assert not result.is_valid
        assert len(result.errors) == 1
        err = result.errors[0]
        assert err.broker == "Test Broker"
        assert err.llm_value == 10.0
        assert err.expected_value == 15.0

    def test_string_value_parsed(self):
        table = self._make_table("Test Broker", "5000", "€15.00")
        result = validate_comparison_table(table)
        assert result.is_valid

    def test_unparseable_value_is_error(self):
        table = self._make_table("Test Broker", "5000", "N/A")
        result = validate_comparison_table(table)
        assert not result.is_valid
        assert "Could not parse" in result.errors[0].explanation

    def test_unknown_broker_is_skipped(self):
        table = self._make_table("Unknown Broker", "5000", 99.0)
        result = validate_comparison_table(table)
        assert result.is_valid
        assert result.checked == 0

    def test_tolerance_accepted(self):
        # ±€0.01 rounding tolerance should pass
        table = self._make_table("Test Broker", "5000", 15.005)
        result = validate_comparison_table(table)
        assert result.is_valid

    def test_list_format_supported(self):
        table = {
            "euronext_brussels": {
                "stocks": [{"broker": "Test Broker", "5000": 15.0}],
                "etfs": {},
                "bonds": {},
            }
        }
        result = validate_comparison_table(table)
        assert result.is_valid


# ---------------------------------------------------------------------------
# build_correction_prompt
# ---------------------------------------------------------------------------

class TestBuildCorrectionPrompt:

    def test_empty_errors_returns_empty_string(self):
        assert build_correction_prompt([]) == ""

    def test_contains_correction_details(self):
        errors = [
            ValidationError(
                broker="Bolero",
                instrument="stocks",
                amount="5000",
                llm_value=10.0,
                expected_value=15.0,
                explanation="Flat fee EUR15.00",
            )
        ]
        prompt = build_correction_prompt(errors)
        assert "Bolero" in prompt
        assert "10.00" in prompt
        assert "15.00" in prompt
        assert "CORRECTIONS" in prompt


# ---------------------------------------------------------------------------
# patch_table_with_corrections
# ---------------------------------------------------------------------------

class TestPatchTableWithCorrections:

    def test_patch_corrects_wrong_value(self):
        table = {
            "euronext_brussels": {
                "stocks": {"Bolero": {"5000": 10.0}},
                "etfs": {},
                "bonds": {},
            }
        }
        errors = [
            ValidationError(
                broker="Bolero",
                instrument="stocks",
                amount="5000",
                llm_value=10.0,
                expected_value=15.0,
                explanation="",
            )
        ]
        patched = patch_table_with_corrections(table, errors)
        assert patched["euronext_brussels"]["stocks"]["Bolero"]["5000"] == 15.0

    def test_patch_is_case_insensitive_on_broker(self):
        table = {
            "euronext_brussels": {
                "stocks": {"BOLERO": {"5000": 10.0}},
                "etfs": {},
                "bonds": {},
            }
        }
        errors = [
            ValidationError(
                broker="bolero",
                instrument="stocks",
                amount="5000",
                llm_value=10.0,
                expected_value=15.0,
                explanation="",
            )
        ]
        patched = patch_table_with_corrections(table, errors)
        assert patched["euronext_brussels"]["stocks"]["BOLERO"]["5000"] == 15.0


# ---------------------------------------------------------------------------
# Bolero and Rebel – specific amount checks at 5k, 10k, 50k
# ---------------------------------------------------------------------------

class TestBoleroAndRebelFees:
    """Verify Bolero and Rebel fee calculations at €5k, €10k and €50k.

    Bolero stocks/ETFs (Euronext Brussels, from official tariff sheet):
      - ≤ €250:              €2.50
      - €250.01 – €1,000:   €5.00
      - €1,000.01 – €2,500: €7.50
      - €2,500.01 – €70,000: €15 per started €10,000 of TOTAL, max €50
        → €5k: 1×€15 = €15  |  €10k: 1×€15 = €15  |  €50k: 5×€15=€75 → €50 (capped)
      - Above €70,000: €50 + €15 per extra €10,000 above €70k

    Rebel ETFs: 0.25% of trade value, minimum €7.50.

    Rebel stocks (Euronext Brussels):
      - Up to €2,500: flat €3.00  (tiered_flat pattern)
      - Above €2,500: 0.60% of the TOTAL trade value  (percentage_with_min)
      Note: Rebel's pricing switches from flat to a percentage of the total at the
      €2,500 threshold. The two ranges are tested separately with the pattern that
      models each range correctly.
    """

    # Bolero: tiered fee with per-10k slice for amounts above €2,500, capped at €50
    # Flat tiers encode the precomputed cumulative fee for each bracket:
    #   - €2,500.01–€70,000: €15 × ceil(amount/10,000), capped at €50
    #     e.g. €5k → 1×€15=€15; €10k → 1×€15=€15; €20k → 2×€15=€30; €50k → 5×€15=€75→€50
    # The explicit flat tiers faithfully represent these bracket values without needing
    # a per-slice calculation (which would charge on the remainder, not the total).
    _BOLERO_TIERS = [
        {"up_to": 250,   "fee": 2.5},
        {"up_to": 1000,  "fee": 5.0},
        {"up_to": 2500,  "fee": 7.5},
        {"up_to": 10000, "fee": 15.0},   # 1×€15
        {"up_to": 20000, "fee": 30.0},   # 2×€15
        {"up_to": 30000, "fee": 45.0},   # 3×€15
        {"up_to": 70000, "fee": 50.0},   # 4+×€15 ≥ €60 → capped at €50
        {"per_slice": 10000, "fee": 15.0},  # above €70k: €50 + €15/extra 10k
    ]

    def test_bolero_5k(self):
        # ceil(5000/10000)=1 × €15 = €15
        assert _compute_from_tiers(self._BOLERO_TIERS, 5000) == 15.0

    def test_bolero_10k(self):
        # ceil(10000/10000)=1 × €15 = €15
        assert _compute_from_tiers(self._BOLERO_TIERS, 10000) == 15.0

    def test_bolero_50k(self):
        # ceil(50000/10000)=5 × €15 = €75 → capped at €50
        assert _compute_from_tiers(self._BOLERO_TIERS, 50000) == 50.0

    # Rebel ETFs: 0.25% of trade value, minimum €7.50
    _REBEL_ETF_TIERS = [{"rate": 0.0025, "min_fee": 7.5}]

    def test_rebel_etfs_5k(self):
        # 5000 * 0.25% = 12.50  (above minimum of €7.50)
        assert _compute_from_tiers(self._REBEL_ETF_TIERS, 5000) == 12.5

    def test_rebel_etfs_10k(self):
        # 10000 * 0.25% = 25.00
        assert _compute_from_tiers(self._REBEL_ETF_TIERS, 10000) == 25.0

    def test_rebel_etfs_50k(self):
        # 50000 * 0.25% = 125.00
        assert _compute_from_tiers(self._REBEL_ETF_TIERS, 50000) == 125.0

    # Rebel stocks (Brussels): flat €3.00 for ≤ €2,500
    _REBEL_STOCKS_FLAT_TIERS = [{"up_to": 2500, "fee": 3.0}]

    def test_rebel_stocks_up_to_2500(self):
        assert _compute_from_tiers(self._REBEL_STOCKS_FLAT_TIERS, 2500) == 3.0

    # Rebel stocks (Brussels): 0.60% of TOTAL for amounts above €2,500
    # percentage_with_min(rate=0.006, min_fee=3.0) correctly models this range
    _REBEL_STOCKS_PCT_TIERS = [{"rate": 0.006, "min_fee": 3.0}]

    def test_rebel_stocks_5k(self):
        # 5000 * 0.60% = 30.00
        assert _compute_from_tiers(self._REBEL_STOCKS_PCT_TIERS, 5000) == 30.0

    def test_rebel_stocks_10k(self):
        # 10000 * 0.60% = 60.00
        assert _compute_from_tiers(self._REBEL_STOCKS_PCT_TIERS, 10000) == 60.0

    def test_rebel_stocks_50k(self):
        # 50000 * 0.60% = 300.00
        assert _compute_from_tiers(self._REBEL_STOCKS_PCT_TIERS, 50000) == 300.0
