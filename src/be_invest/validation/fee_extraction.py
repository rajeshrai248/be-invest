"""Shared fee rule extraction logic: prompts, parsing, sanity checks, golden reference validation.

Used by both the /refresh-and-analyze server endpoint and scripts/refresh_fee_rules.py
to ensure consistent extraction quality and automatic correction of LLM errors.
"""

from __future__ import annotations

import json
import logging
import math
from typing import Any, Dict, List, Optional, Tuple

from .fee_calculator import (
    FeeRule,
    HiddenCosts,
    TRANSACTION_SIZES,
    _compute_from_tiers,
    _sanitize_tiers,
    _normalize_broker,
    _normalize_instrument,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Extraction prompt (single source of truth)
# ---------------------------------------------------------------------------

def build_extraction_prompt(broker_name: str, broker_data: Any) -> str:
    """Build the LLM prompt for extracting structured fee rules from broker data.

    This is the single source of truth for the extraction prompt, used by both
    the server endpoint and the standalone refresh script.
    """
    return f"""Extract ALL fee rules and hidden costs for {broker_name} on Euronext Brussels.

Extract:
1. TRADING RULES: The exact fee structure with pattern type and all tier thresholds
2. HIDDEN COSTS: Custody fees, connectivity fees, FX fees, dividend fees, subscription fees

Input data for {broker_name}:
{json.dumps(broker_data, indent=2)}

Return a JSON object with EXACTLY this structure:

{{
  "rules": [
    {{
      "broker": "{broker_name}",
      "instrument": "stocks",
      "pattern": "pattern_type",
      "tiers": [...],
      "handling_fee": 0.0,
      "exchange": "all",
      "conditions": [],
      "notes": "",
      "source": {{}}
    }}
  ],
  "hidden_costs": {{
    "{broker_name}": {{
      "custody_fee_monthly_pct": 0.0,
      "custody_fee_monthly_min": 0.0,
      "connectivity_fee_per_exchange_year": 0.0,
      "connectivity_fee_max_pct_account": 0.0,
      "subscription_fee_monthly": 0.0,
      "subscription_plan_name": "",
      "fx_fee_pct": 0.0,
      "handling_fee_per_trade": 0.0,
      "dividend_fee_pct": 0.0,
      "dividend_fee_min": 0.0,
      "dividend_fee_max": 0.0,
      "notes": "Brief description of hidden costs"
    }}
  }}
}}

PATTERN TYPES (use exactly these strings):
- "flat": Simple flat fee for all amounts (e.g., Degiro EUR2 + EUR1 handling)
- "tiered_flat": Multiple flat fee tiers by amount (only up_to tiers, no slice)
- "tiered_flat_then_slice": Flat tiers for small amounts, per-slice for larger amounts (Bolero, Keytrade, Rebel)
- "percentage_with_min": Percentage rate with minimum fee (ING, Revolut)
- "base_plus_slice": Single base fee threshold + per-slice for remainder

TIER TYPES:
- {{"flat": 2.00}} - simple flat fee
- {{"up_to": 2500, "fee": 7.50}} - flat fee for amounts up to threshold
- {{"per_slice": 10000, "fee": 15.00}} - per-started-slice (no up_to means it applies after all flat tiers)
- {{"per_slice": 10000, "fee": 15.00, "max_fee": 50.00}} - per-slice with fee cap
- {{"rate": 0.0035, "min_fee": 1.00}} - percentage rate with minimum

EXCHANGE FIELD:
- "all" (default) = applies to all exchanges
- Use specific exchange names when pricing differs: "euronext_brussels", "nyse", "nasdaq", "xetra", "lse", "euronext_amsterdam", "euronext_paris"
- Convention: lowercase, underscores, no spaces.
- If the data only shows one fee schedule (no exchange differentiation), use "all".

CONDITIONS FIELD (array of condition objects, empty [] for standard rates):
- Age-based: {{"type": "age", "min_age": 18, "max_age": 24}} — e.g., youth discount
- Plan-based: {{"type": "plan", "plan_name": "Plus", "plan_tier": "paid"}} — subscription tier pricing
- Order type: {{"type": "order_type", "order_type": "phone"}} — phone order surcharge
- Promotion: {{"type": "promotion", "promo_name": "Welcome", "valid_until": "2026-12-31"}}
- Only add conditions for NON-STANDARD rules. The standard fee schedule should have conditions=[].
- If a broker has both a standard rate AND a conditional rate, emit TWO separate rules.

NOTES FIELD:
- Brief free-text for edge cases or caveats not captured by conditions.
- Leave empty ("") for straightforward rules.

SOURCE FIELD:
- Provenance metadata: {{"pdf": "filename.pdf", "page": 3}}
- Leave empty ({{}}) if provenance is unknown.

CRITICAL — TWO DIFFERENT NUMERIC CONVENTIONS ARE USED IN THE SAME JSON:

1. TIER "rate" fields (inside the "tiers" array) use DECIMAL FRACTIONS:
   The calculator does: fee = amount * rate — so rate must be a decimal fraction.
   - rate: 0.0035 means 0.35% commission
   - rate: 0.0025 means 0.25% commission
   - rate: 0.005  means 0.50% commission
   - WRONG: rate=0.35 for a 0.35% fee. RIGHT: rate=0.0035 for a 0.35% fee.
   - WRONG: rate=0.25 for a 0.25% fee. RIGHT: rate=0.0025 for a 0.25% fee.

2. "_pct" fields in "hidden_costs" use PERCENTAGE NOTATION (NOT decimal fractions):
   - fx_fee_pct: 0.25 means 0.25%, NOT 25%. A value of 1.0 means 1%. A value of 1.40 means 1.40%.
   - custody_fee_monthly_pct: 0.0242 means 0.0242% per month. A value of 2.0 means 2% per month.
   - dividend_fee_pct: 2.42 means 2.42%. A value of 2.0 means 2%. Do NOT write 0.02 to mean 2%.
   - connectivity_fee_max_pct_account follows the same rule.
   - WRONG: dividend_fee_pct=0.02 for a 2% fee. RIGHT: dividend_fee_pct=2.0 for a 2% fee.
   - WRONG: fx_fee_pct=0.0025 for a 0.25% fee. RIGHT: fx_fee_pct=0.25 for a 0.25% fee.

IMPORTANT:
- Extract ALL tiers from the data. Many brokers have 4-5 tiers, not just 2.
- Include "max_fee" on the per_slice tier if the broker caps total commission.
- Include rules for stocks, etfs, AND bonds where the data is available.
- Use exact broker name: {broker_name}
- Extract the STANDARD fee schedule, not promotional or conditional rates.
  For example, Degiro has a "Core Selection" of ETFs with zero commission, but
  the standard ETF fee on Euronext Brussels is EUR2 + EUR1 handling (same as stocks).
  Always use the standard/default rate that applies to ALL instruments of that type.
- A rule where ALL fees are EUR 0.00 is almost certainly wrong. If fees appear
  to be zero, double-check whether a separate handling fee or commission applies.
- For brokers with SUBSCRIPTION-BASED pricing (e.g., monthly plans that include a number
  of free trades): set subscription_fee_monthly to the lowest PAID tier price (not the
  free/basic plan), and set subscription_plan_name to the name of that entry-level paid plan
  (e.g. "Plus", "Premium", "Pro"). Document ALL subscription tiers and what they include
  (free trades, FX limits, etc.) in the notes field.
  Example: subscription_fee_monthly=2.99, subscription_plan_name="Plus".

COMMON LLM EXTRACTION ERRORS TO AVOID:
- Keytrade Bank: stocks and ETFs/trackers have DIFFERENT fee tiers on Euronext Brussels.
  Stocks use higher fees (~EUR17/21/30) while trackers/ETFs use lower fees (~EUR2.45/5.95/14.95).
  Do NOT copy the tracker/ETF tiers into the stocks rule! They are separate instruments.
- Rebel: The standard stock fee on Euronext Brussels is EUR3 (up to EUR2500), then EUR10 per
  started EUR10000 slice. Do NOT confuse this with the youth (age 18-24) discount of EUR1 flat.
  Always extract the STANDARD rule (conditions=[]) separately from conditional rules.
- Bolero bonds: The bond fee is EUR25 per started EUR10000 slice (pattern=base_plus_slice),
  NOT a simple flat fee of EUR25. At EUR50000, it should be 5 slices × EUR25 = EUR125.
- Always emit separate stock and ETF rules when the broker charges different amounts for each.
  Check the source data for separate "aandelen"/"stocks" vs "trackers"/"etfs" sections.
"""


# ---------------------------------------------------------------------------
# LLM response parsing
# ---------------------------------------------------------------------------

def strip_markdown_fences(text: str) -> str:
    """Strip markdown code fences (```json ... ```) from LLM response."""
    stripped = text.strip()
    if stripped.startswith("```"):
        first_newline = stripped.index("\n")
        stripped = stripped[first_newline + 1:]
        if stripped.rstrip().endswith("```"):
            stripped = stripped.rstrip()[:-3].rstrip()
    return stripped


def parse_llm_extraction_response(
    response_text: str,
) -> Tuple[List[FeeRule], Dict[str, HiddenCosts]]:
    """Parse LLM JSON response into FeeRule and HiddenCosts objects.

    Returns (rules_list, hidden_costs_dict). Does NOT include all-zero QA check
    (callers handle that differently — server.py has Langfuse scoring).
    """
    stripped = strip_markdown_fences(response_text)
    data = json.loads(stripped)

    rules: List[FeeRule] = []
    for rule_dict in data.get("rules", []):
        broker = rule_dict.get("broker", "")
        instrument = rule_dict.get("instrument", "")
        if not broker or not instrument:
            continue
        rule = FeeRule(
            broker=broker,
            instrument=instrument,
            pattern=rule_dict.get("pattern", "unknown"),
            tiers=rule_dict.get("tiers", []),
            handling_fee=rule_dict.get("handling_fee", 0.0),
            min_fee=rule_dict.get("min_fee"),
            max_fee=rule_dict.get("max_fee"),
            min_order=rule_dict.get("min_order"),
            exchange=rule_dict.get("exchange", "all"),
            conditions=rule_dict.get("conditions", []),
            notes=rule_dict.get("notes", ""),
            source=rule_dict.get("source", {}),
        )
        rules.append(rule)

    hidden_costs: Dict[str, HiddenCosts] = {}
    for hc_name, costs_dict in data.get("hidden_costs", {}).items():
        if isinstance(costs_dict, dict):
            hidden_costs[hc_name] = HiddenCosts(
                custody_fee_monthly_pct=costs_dict.get("custody_fee_monthly_pct", 0.0),
                custody_fee_monthly_min=costs_dict.get("custody_fee_monthly_min", 0.0),
                connectivity_fee_per_exchange_year=costs_dict.get("connectivity_fee_per_exchange_year", 0.0),
                connectivity_fee_max_pct_account=costs_dict.get("connectivity_fee_max_pct_account", 0.0),
                subscription_fee_monthly=costs_dict.get("subscription_fee_monthly", 0.0),
                subscription_plan_name=costs_dict.get("subscription_plan_name", ""),
                fx_fee_pct=costs_dict.get("fx_fee_pct", 0.0),
                handling_fee_per_trade=costs_dict.get("handling_fee_per_trade", 0.0),
                dividend_fee_pct=costs_dict.get("dividend_fee_pct", 0.0),
                dividend_fee_min=costs_dict.get("dividend_fee_min", 0.0),
                dividend_fee_max=costs_dict.get("dividend_fee_max", 0.0),
                notes=costs_dict.get("notes", ""),
            )

    return rules, hidden_costs


# ---------------------------------------------------------------------------
# Programmatic sanity checks (run BEFORE golden reference validation)
# ---------------------------------------------------------------------------

def sanitize_extracted_rules(
    rules: Dict[tuple, FeeRule],
    hidden_costs: Optional[Dict[str, HiddenCosts]] = None,
) -> Tuple[Dict[tuple, FeeRule], List[str]]:
    """Run programmatic sanity checks on LLM-extracted rules and auto-fix common errors.

    Checks:
    1. Rate magnitude: rate > 0.05 is almost certainly percentage, not decimal fraction → auto-divide by 100
    2. Rate upper bound: rate > 1.0 is nonsensical → flag as error
    3. Handling fee double-count warning
    4. Pattern-tier consistency

    Returns (fixed_rules, warnings).
    """
    warnings: List[str] = []

    for key, rule in rules.items():
        broker = rule.broker
        instrument = rule.instrument

        # Check 1 & 2: Rate magnitude
        fixed_tiers = []
        tiers_modified = False
        for tier in rule.tiers:
            tier_copy = dict(tier)
            if "rate" in tier_copy:
                rate = tier_copy["rate"]
                if rate > 1.0:
                    warnings.append(
                        f"RATE ERROR: {broker} {instrument} has rate={rate} (>100%%) — "
                        f"this is nonsensical. Tier: {tier}. Manual review needed."
                    )
                elif rate > 0.05:
                    # Almost certainly percentage notation, not decimal fraction
                    # No real broker charges >5% commission
                    corrected = rate / 100.0
                    warnings.append(
                        f"RATE AUTO-FIX: {broker} {instrument} rate={rate} → {corrected} "
                        f"(was percentage notation, converted to decimal fraction)"
                    )
                    tier_copy["rate"] = corrected
                    tiers_modified = True
            fixed_tiers.append(tier_copy)

        if tiers_modified:
            rule.tiers = fixed_tiers

        # Check 3: Handling fee double-count warning
        if hidden_costs and rule.handling_fee > 0:
            hc = hidden_costs.get(broker)
            if hc and hc.handling_fee_per_trade > 0:
                warnings.append(
                    f"HANDLING FEE WARNING: {broker} {instrument} has handling_fee={rule.handling_fee} "
                    f"in the rule AND handling_fee_per_trade={hc.handling_fee_per_trade} in hidden_costs. "
                    f"Possible double-counting."
                )

        # Check 4: Pattern-tier consistency
        if rule.pattern == "percentage_with_min":
            rate_tiers = [t for t in rule.tiers if "rate" in t]
            if not rate_tiers:
                warnings.append(
                    f"PATTERN MISMATCH: {broker} {instrument} has pattern=percentage_with_min "
                    f"but no rate tier in tiers: {rule.tiers}"
                )
        elif rule.pattern == "flat":
            flat_tiers = [t for t in rule.tiers if "flat" in t]
            if not flat_tiers:
                warnings.append(
                    f"PATTERN MISMATCH: {broker} {instrument} has pattern=flat "
                    f"but no flat tier in tiers: {rule.tiers}"
                )

    return rules, warnings


# ---------------------------------------------------------------------------
# Golden reference data (authoritative, verified against PDFs)
# ---------------------------------------------------------------------------

# Known-correct Euronext Brussels fees for all brokers/instruments/tiers.
# If the LLM extraction disagrees, the extraction is wrong.
EURONEXT_BRUSSELS_REFERENCE: Dict[str, Dict[str, Dict[int, float]]] = {
    "stocks": {
        "Bolero": {50: 2.5, 100: 2.5, 250: 2.5, 500: 5.0, 1000: 5.0, 1500: 7.5, 2000: 7.5, 2500: 7.5, 5000: 15.0, 10000: 15.0, 50000: 50.0},
        "Keytrade Bank": {50: 17.45, 100: 17.45, 250: 17.45, 500: 20.95, 1000: 20.95, 1500: 20.95, 2000: 20.95, 2500: 20.95, 5000: 29.95, 10000: 29.95, 50000: 45.0},
        "Degiro Belgium": {50: 3.0, 100: 3.0, 250: 3.0, 500: 3.0, 1000: 3.0, 1500: 3.0, 2000: 3.0, 2500: 3.0, 5000: 3.0, 10000: 3.0, 50000: 3.0},
        "ING Self Invest": {50: 1.0, 100: 1.0, 250: 1.0, 500: 1.75, 1000: 3.5, 1500: 5.25, 2000: 7.0, 2500: 8.75, 5000: 17.5, 10000: 35.0, 50000: 175.0},
        "Rebel": {50: 3.0, 100: 3.0, 250: 3.0, 500: 3.0, 1000: 3.0, 1500: 3.0, 2000: 3.0, 2500: 3.0, 5000: 10.0, 10000: 10.0, 50000: 50.0},
        "Revolut": {50: 1.0, 100: 1.0, 250: 1.0, 500: 1.25, 1000: 2.5, 1500: 3.75, 2000: 5.0, 2500: 6.25, 5000: 12.5, 10000: 25.0, 50000: 125.0},
        "Trade Republic": {50: 1.0, 100: 1.0, 250: 1.0, 500: 1.0, 1000: 1.0, 1500: 1.0, 2000: 1.0, 2500: 1.0, 5000: 1.0, 10000: 1.0, 50000: 1.0},
    },
    "etfs": {
        "Bolero": {50: 2.5, 100: 2.5, 250: 2.5, 500: 5.0, 1000: 5.0, 1500: 7.5, 2000: 7.5, 2500: 7.5, 5000: 15.0, 10000: 15.0, 50000: 50.0},
        "Keytrade Bank": {50: 2.45, 100: 2.45, 250: 2.45, 500: 5.95, 1000: 5.95, 1500: 5.95, 2000: 5.95, 2500: 5.95, 5000: 14.95, 10000: 14.95, 50000: 44.95},
        "Degiro Belgium": {50: 3.0, 100: 3.0, 250: 3.0, 500: 3.0, 1000: 3.0, 1500: 3.0, 2000: 3.0, 2500: 3.0, 5000: 3.0, 10000: 3.0, 50000: 3.0},
        "ING Self Invest": {50: 1.0, 100: 1.0, 250: 1.0, 500: 1.75, 1000: 3.5, 1500: 5.25, 2000: 7.0, 2500: 8.75, 5000: 17.5, 10000: 35.0, 50000: 175.0},
        "Rebel": {50: 1.0, 100: 1.0, 250: 1.0, 500: 2.0, 1000: 2.0, 1500: 3.0, 2000: 3.0, 2500: 3.0, 5000: 10.0, 10000: 10.0, 50000: 50.0},
        "Revolut": {50: 1.0, 100: 1.0, 250: 1.0, 500: 1.25, 1000: 2.5, 1500: 3.75, 2000: 5.0, 2500: 6.25, 5000: 12.5, 10000: 25.0, 50000: 125.0},
        "Trade Republic": {50: 1.0, 100: 1.0, 250: 1.0, 500: 1.0, 1000: 1.0, 1500: 1.0, 2000: 1.0, 2500: 1.0, 5000: 1.0, 10000: 1.0, 50000: 1.0},
    },
    "bonds": {
        "Bolero": {50: 25.0, 100: 25.0, 250: 25.0, 500: 25.0, 1000: 25.0, 1500: 25.0, 2000: 25.0, 2500: 25.0, 5000: 25.0, 10000: 25.0, 50000: 125.0},
        "Keytrade Bank": {50: 29.95, 100: 29.95, 250: 29.95, 500: 29.95, 1000: 29.95, 1500: 29.95, 2000: 29.95, 2500: 29.95, 5000: 29.95, 10000: 29.95, 50000: 100.0},
        "Degiro Belgium": {50: 3.0, 100: 3.0, 250: 3.0, 500: 3.0, 1000: 3.0, 1500: 3.0, 2000: 3.0, 2500: 3.0, 5000: 3.0, 10000: 3.0, 50000: 3.0},
        "ING Self Invest": {50: 50.0, 100: 50.0, 250: 50.0, 500: 50.0, 1000: 50.0, 1500: 50.0, 2000: 50.0, 2500: 50.0, 5000: 50.0, 10000: 50.0, 50000: 250.0},
        "Trade Republic": {50: 1.0, 100: 1.0, 250: 1.0, 500: 1.0, 1000: 1.0, 1500: 1.0, 2000: 1.0, 2500: 1.0, 5000: 1.0, 10000: 1.0, 50000: 1.0},
    },
}

# Known-correct fee rules for Euronext Brussels — used to auto-correct LLM errors.
EURONEXT_BRUSSELS_CORRECT_RULES: Dict[tuple, dict] = {
    ("Keytrade Bank", "stocks", "euronext_brussels"): {
        "pattern": "tiered_flat_then_slice",
        "tiers": [
            {"up_to": 250, "fee": 17.45},
            {"up_to": 2500, "fee": 20.95},
            {"up_to": 10000, "fee": 29.95},
            {"per_slice": 10000, "fee": 7.5},
            {"rate": 0.0009},
        ],
        "handling_fee": 0.0,
        "notes": "Online orders on Euronext Brussels. Stocks have different tiers than ETFs/trackers. Above EUR10K: 0.09% x order amount.",
    },
    ("Keytrade Bank", "etfs", "euronext_brussels"): {
        "pattern": "tiered_flat_then_base_plus_slice",
        "tiers": [
            {"up_to": 250, "fee": 2.45},
            {"up_to": 2500, "fee": 5.95},
            {"base_up_to": 10000, "base_fee": 14.95, "per_slice": 10000, "slice_fee": 7.50},
        ],
        "handling_fee": 0.0,
        "notes": "ETF/tracker fees on Euronext Brussels. Flat tiers up to EUR10000, then EUR14.95 base + EUR7.50 per additional started EUR10000 slice.",
    },
    ("Rebel", "stocks", "euronext_brussels"): {
        "pattern": "tiered_flat_then_slice",
        "tiers": [
            {"up_to": 2500, "fee": 3.0},
            {"per_slice": 10000, "fee": 10.0},
        ],
        "handling_fee": 0.0,
        "notes": "Standard stock fees on Euronext Brussels. EUR3 up to EUR2500, then EUR10 per started EUR10K slice.",
    },
    ("Bolero", "bonds", "all"): {
        "pattern": "base_plus_slice",
        "tiers": [
            {"base_up_to": 10000, "base_fee": 25.0, "per_slice": 10000, "slice_fee": 25.0},
        ],
        "handling_fee": 0.0,
        "notes": "EUR25 per started EUR10,000 slice. Non-listed bonds secondary market.",
    },
    ("ING Self Invest", "stocks", "euronext_brussels"): {
        "pattern": "percentage_with_min",
        "tiers": [{"rate": 0.0035, "min_fee": 1.0}],
        "handling_fee": 0.0,
        "notes": "0.35% x order amount (min EUR1) — web/app rate for Euronext Brussels. ING Self Invest stocks.",
    },
    ("ING Self Invest", "stocks", "all"): {
        "pattern": "percentage_with_min",
        "tiers": [{"rate": 0.005, "min_fee": 1.0}],
        "handling_fee": 0.0,
        "notes": "0.50% x order amount (min EUR1) — web/app rate for other exchanges. ING Self Invest stocks.",
    },
    ("ING Self Invest", "etfs", "euronext_brussels"): {
        "pattern": "percentage_with_min",
        "tiers": [{"rate": 0.0035, "min_fee": 1.0}],
        "handling_fee": 0.0,
        "notes": "0.35% x order amount (min EUR1) — web/app rate for Euronext Brussels. ING Self Invest ETFs.",
    },
    ("ING Self Invest", "etfs", "all"): {
        "pattern": "percentage_with_min",
        "tiers": [{"rate": 0.005, "min_fee": 1.0}],
        "handling_fee": 0.0,
        "notes": "0.50% x order amount (min EUR1) — web/app rate for other exchanges. ING Self Invest ETFs.",
    },
    ("ING Self Invest", "bonds", "all"): {
        "pattern": "percentage_with_min",
        "tiers": [{"rate": 0.005, "min_fee": 50.0}],
        "handling_fee": 0.0,
        "notes": "0.50% x order amount (min EUR50). ING Self Invest bonds.",
    },
    ("Rebel", "etfs", "euronext_brussels"): {
        "pattern": "tiered_flat_then_slice",
        "tiers": [
            {"up_to": 250, "fee": 1.0},
            {"up_to": 1000, "fee": 2.0},
            {"up_to": 2500, "fee": 3.0},
            {"per_slice": 10000, "fee": 10.0},
        ],
        "handling_fee": 0.0,
        "notes": "Rebel ETF/tracker fees on Euronext Brussels. EUR1/EUR2/EUR3 tiered, then EUR10 per started EUR10K slice.",
    },
    ("Trade Republic", "bonds", "all"): {
        "pattern": "flat",
        "tiers": [{"flat": 1.0}],
        "handling_fee": 0.0,
        "notes": "EUR1 flat fee per trade. Trade Republic bonds.",
    },
    ("Revolut", "stocks", "all"): {
        "pattern": "percentage_with_min",
        "tiers": [{"rate": 0.0025, "min_fee": 1.0}],
        "handling_fee": 0.0,
        "notes": "Standard plan (free): 0.25% min EUR1 per trade after 1 free trade/month. Revolut stocks.",
    },
    ("Revolut", "etfs", "all"): {
        "pattern": "percentage_with_min",
        "tiers": [{"rate": 0.0025, "min_fee": 1.0}],
        "handling_fee": 0.0,
        "notes": "Standard plan (free): 0.25% min EUR1 per trade after 1 free trade/month. Revolut ETFs.",
    },
}


# ---------------------------------------------------------------------------
# Golden reference validation
# ---------------------------------------------------------------------------

def validate_and_fix_extracted_rules(
    rules: Dict[tuple, FeeRule],
) -> Tuple[Dict[tuple, FeeRule], int, List[str]]:
    """Validate LLM-extracted rules against known-good reference values.

    For each broker/instrument/amount in the reference, compute the fee
    from the extracted rule and compare. If ANY fee mismatches, replace
    the rule with the known-correct version from EURONEXT_BRUSSELS_CORRECT_RULES.

    Returns (fixed_rules, fix_count, warnings).
    """
    warnings: List[str] = []
    fix_count = 0

    for instrument, broker_ref in EURONEXT_BRUSSELS_REFERENCE.items():
        for broker_display, expected_fees in broker_ref.items():
            norm_broker = _normalize_broker(broker_display)
            norm_instr = _normalize_instrument(instrument)

            # Try euronext_brussels first, then 'all'
            key_exch = (norm_broker, norm_instr, "euronext_brussels")
            key_all = (norm_broker, norm_instr, "all")
            rule = rules.get(key_exch) or rules.get(key_all)
            matched_key = key_exch if key_exch in rules else key_all if key_all in rules else None

            if rule is None:
                # No rule exists — inject correct one
                msg = f"No rule for {broker_display} {instrument} on euronext_brussels — injecting correct rule"
                warnings.append(msg)
                logger.warning(f"  VALIDATION: {msg}")

                correct = EURONEXT_BRUSSELS_CORRECT_RULES.get((broker_display, instrument, "euronext_brussels"))
                if correct is None:
                    correct = EURONEXT_BRUSSELS_CORRECT_RULES.get((broker_display, instrument, "all"))
                if correct:
                    exch = "euronext_brussels" if (broker_display, instrument, "euronext_brussels") in EURONEXT_BRUSSELS_CORRECT_RULES else "all"
                    inject_key = (norm_broker, norm_instr, exch)
                    rules[inject_key] = FeeRule(
                        broker=broker_display,
                        instrument=instrument,
                        exchange=exch,
                        **correct,
                    )
                    fix_count += 1
                    logger.info(f"  VALIDATION: Injected correct rule for {broker_display} {instrument}")
                else:
                    warnings.append(f"No correct rule available for {broker_display} {instrument}")
                    logger.error(f"  VALIDATION: No correct rule available for {broker_display} {instrument}")
                continue

            # Compute fees from extracted rule and compare
            tiers = _sanitize_tiers(rule.tiers)
            mismatches = []
            for amount, expected_fee in expected_fees.items():
                actual_fee = _compute_from_tiers(tiers, float(amount), rule.handling_fee, rule.max_fee)
                actual_fee = round(actual_fee, 2)
                if abs(actual_fee - expected_fee) > 0.01:
                    mismatches.append((amount, expected_fee, actual_fee))

            if mismatches:
                mismatch_summary = "; ".join(
                    f"EUR{amt}: expected={exp}, got={act}" for amt, exp, act in mismatches[:5]
                )
                msg = f"{broker_display} {instrument} has {len(mismatches)} fee mismatches: {mismatch_summary}"
                warnings.append(msg)
                logger.warning(f"  VALIDATION: {msg}")

                # Look up the correct rule
                correct = EURONEXT_BRUSSELS_CORRECT_RULES.get((broker_display, instrument, rule.exchange))
                if correct is None:
                    for ck, cv in EURONEXT_BRUSSELS_CORRECT_RULES.items():
                        if ck[0] == broker_display and ck[1] == instrument:
                            correct = cv
                            break

                if correct:
                    fixed_rule = FeeRule(
                        broker=rule.broker,
                        instrument=rule.instrument,
                        exchange=rule.exchange,
                        conditions=rule.conditions if rule.conditions else [],
                        source=rule.source,
                        **correct,
                    )
                    rules[matched_key] = fixed_rule
                    fix_count += 1
                    logger.info(
                        f"  VALIDATION: Auto-corrected {broker_display} {instrument} "
                        f"({len(mismatches)} fee errors fixed)"
                    )
                else:
                    warnings.append(
                        f"{broker_display} {instrument} has errors but no correct reference rule — manual fix needed"
                    )
                    logger.error(
                        f"  VALIDATION: {broker_display} {instrument} has errors but no "
                        f"correct reference rule available — manual fix needed"
                    )

    return rules, fix_count, warnings


# ---------------------------------------------------------------------------
# High-level orchestrator
# ---------------------------------------------------------------------------

def validate_and_fix_extraction(
    rules: Dict[tuple, FeeRule],
    hidden_costs: Optional[Dict[str, HiddenCosts]] = None,
) -> Tuple[Dict[tuple, FeeRule], int, List[str]]:
    """Run full validation pipeline on extracted rules.

    1. Programmatic sanity checks (rate magnitude, pattern consistency)
    2. Golden reference validation (auto-correct against known-good values)

    Returns (fixed_rules, total_fix_count, all_warnings).
    """
    all_warnings: List[str] = []

    # Step 1: Programmatic sanity checks
    rules, sanity_warnings = sanitize_extracted_rules(rules, hidden_costs)
    all_warnings.extend(sanity_warnings)

    # Step 2: Golden reference validation
    rules, fix_count, ref_warnings = validate_and_fix_extracted_rules(rules)
    all_warnings.extend(ref_warnings)

    if all_warnings:
        logger.warning(f"Extraction validation: {len(all_warnings)} warnings, {fix_count} auto-corrections")
    else:
        logger.info("Extraction validation: all rules match reference values")

    return rules, fix_count, all_warnings
