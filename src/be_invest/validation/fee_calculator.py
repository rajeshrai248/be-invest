"""Deterministic fee calculator for Belgian broker cost comparison tables.

Computes exact fees for (broker, instrument, trade_amount) tuples using known
calculation rules. Rules are loaded from data/output/fee_rules.json, which is
populated by LLM extraction from scraped broker PDFs.

Python defines HOW to compute (pattern types). The LLM extracts WHAT the
numbers are (from PDFs). Hidden costs are structured data, not just text.
"""

import json
import logging
import math
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List

logger = logging.getLogger(__name__)

TRANSACTION_SIZES = [250, 500, 1000, 1500, 2000, 2500, 5000, 10000, 50000]
ASSET_TYPES = ["stocks", "etfs", "bonds"]


@dataclass
class FeeRule:
    """A single fee rule for a broker/instrument combination."""
    broker: str
    instrument: str  # "stocks", "etfs", "bonds"
    pattern: str = "unknown"
    # Pattern types:
    #   "flat"                    -- simple flat fee for all amounts
    #   "tiered_flat"             -- flat fees by tier (up_to thresholds)
    #   "tiered_flat_then_slice"  -- flat tiers + per-slice for amounts above all tiers
    #   "percentage_with_min"     -- percentage rate with minimum fee
    #   "base_plus_slice"         -- base fee up to threshold + per-slice for remainder
    tiers: List[dict] = field(default_factory=list)
    # Tiers can contain:
    #   {"up_to": 2500, "fee": 7.50}          -- flat fee for amounts <= up_to
    #   {"per_slice": 10000, "fee": 15.0}      -- per-started-slice fee for amounts above tiers
    #   {"per_slice": 10000, "fee": 15.0, "max_fee": 50.0} -- per-slice with cap
    #   {"base_up_to": 10000, "base_fee": 14.95, "per_slice": 10000, "slice_fee": 7.50}
    #                                           -- base fee + per-slice for remainder
    #   {"rate": 0.0035, "min_fee": 1.00}      -- percentage rate with minimum
    #   {"flat": 3.00}                          -- simple flat fee for all amounts
    handling_fee: float = 0.0
    min_fee: Optional[float] = None
    max_fee: Optional[float] = None


@dataclass
class HiddenCosts:
    """Structured hidden costs for a broker (beyond per-trade fees)."""
    custody_fee_monthly_pct: float = 0.0
    custody_fee_monthly_min: float = 0.0
    connectivity_fee_per_exchange_year: float = 0.0
    connectivity_fee_max_pct_account: float = 0.0
    subscription_fee_monthly: float = 0.0
    fx_fee_pct: float = 0.0
    handling_fee_per_trade: float = 0.0
    dividend_fee_pct: float = 0.0
    dividend_fee_min: float = 0.0
    dividend_fee_max: float = 0.0
    notes: str = ""


# Registry of known fee rules
FEE_RULES: Dict[tuple, FeeRule] = {}

# Registry of hidden costs per broker (keyed by display name)
HIDDEN_COSTS: Dict[str, HiddenCosts] = {}

# Track whether rules have been loaded from JSON
_rules_loaded_from_json = False


def _register(broker: str, instrument: str, rule: FeeRule) -> None:
    """Register a fee rule in the global registry."""
    FEE_RULES[(broker.lower(), instrument.lower())] = rule


def _compute_from_tiers(tiers: List[dict], amount: float, handling_fee: float = 0.0,
                        max_fee: Optional[float] = None) -> float:
    """Compute fee from a tier list for a given amount.

    Supports: flat, percentage_with_min, base_plus_slice, tiered_flat,
    tiered_flat_then_slice (with max_fee cap).
    """
    # Check for simple flat fee
    if len(tiers) == 1 and "flat" in tiers[0]:
        return tiers[0]["flat"] + handling_fee

    # Check for percentage rate
    if len(tiers) == 1 and "rate" in tiers[0]:
        fee = amount * tiers[0]["rate"]
        min_f = tiers[0].get("min_fee", 0.0)
        return max(fee, min_f) + handling_fee

    # Check for base + slice model (Keytrade-style single tier)
    if len(tiers) == 1 and "base_up_to" in tiers[0]:
        tier = tiers[0]
        if amount <= tier["base_up_to"]:
            return tier["base_fee"] + handling_fee
        remainder = amount - tier["base_up_to"]
        slices = math.ceil(remainder / tier["per_slice"])
        return tier["base_fee"] + (slices * tier["slice_fee"]) + handling_fee

    # Tiered flat fees + optional per-slice tier at the end
    # Separate flat tiers (with up_to) from slice tiers (with per_slice, no up_to)
    flat_tiers = [t for t in tiers if "up_to" in t]
    slice_tiers = [t for t in tiers if "per_slice" in t and "up_to" not in t]

    # Find the applicable flat tier
    for tier in flat_tiers:
        if amount <= tier["up_to"]:
            return tier["fee"] + handling_fee

    # Amount exceeds all flat tiers -> use per_slice tier
    if slice_tiers:
        slice_tier = slice_tiers[0]
        # Find the highest flat tier threshold to use as the base boundary
        highest_flat_threshold = max(t["up_to"] for t in flat_tiers) if flat_tiers else 0
        highest_flat_fee = 0.0
        if flat_tiers:
            # Get fee of the highest flat tier
            highest_flat_fee = max(
                (t for t in flat_tiers),
                key=lambda t: t["up_to"]
            )["fee"]

        # Compute slices for the remainder above the highest flat tier
        remainder = amount - highest_flat_threshold
        slices = math.ceil(remainder / slice_tier["per_slice"])
        fee = highest_flat_fee + (slices * slice_tier["fee"])

        # Apply max_fee cap if present (on the tier or rule level)
        tier_max = slice_tier.get("max_fee")
        effective_max = tier_max or max_fee
        if effective_max is not None:
            fee = min(fee, effective_max)

        return fee + handling_fee

    return 0.0


# Mapping from common broker name variations to canonical names
BROKER_ALIASES: Dict[str, str] = {
    "degiro": "degiro belgium",
    "degiro belgium": "degiro belgium",
    "degiro be": "degiro belgium",
    "bolero": "bolero",
    "keytrade": "keytrade bank",
    "keytrade bank": "keytrade bank",
    "ing": "ing self invest",
    "ing self invest": "ing self invest",
    "rebel": "rebel",
    "revolut": "revolut",
}


def _normalize_broker(broker: str) -> str:
    """Normalize broker name to match FEE_RULES keys."""
    return BROKER_ALIASES.get(broker.lower().strip(), broker.lower().strip())


def _normalize_instrument(instrument: str) -> str:
    """Normalize instrument name."""
    instrument = instrument.lower().strip()
    if instrument in ("stock", "stocks", "aandelen"):
        return "stocks"
    if instrument in ("etf", "etfs", "trackers"):
        return "etfs"
    if instrument in ("bond", "bonds", "obligaties"):
        return "bonds"
    return instrument


def calculate_fee(broker: str, instrument: str, amount: float) -> Optional[float]:
    """Compute exact fee for a broker/instrument/amount combination.

    Returns None if no rule exists for this combination.
    Result is rounded to 2 decimal places.
    """
    _ensure_rules_loaded()
    key = (_normalize_broker(broker), _normalize_instrument(instrument))
    rule = FEE_RULES.get(key)
    if rule is None:
        return None
    fee = _compute_from_tiers(rule.tiers, amount, rule.handling_fee, rule.max_fee)
    return round(fee, 2)


def calculate_all_fees(broker: str, instrument: str, amounts: List[float]) -> Dict[str, Optional[float]]:
    """Compute fees for multiple amounts."""
    return {str(int(a)): calculate_fee(broker, instrument, a) for a in amounts}


# ========================================================================================
# JSON PERSISTENCE
# ========================================================================================

def _default_fee_rules_path() -> Path:
    """Resolve the fee_rules.json file path."""
    cwd_path = Path("data") / "output" / "fee_rules.json"
    if cwd_path.exists():
        return cwd_path
    repo_root = Path(__file__).resolve().parents[3]
    fallback = repo_root / "data" / "output" / "fee_rules.json"
    return fallback


def _ensure_rules_loaded() -> None:
    """Auto-load fee rules from JSON on first call, if the file exists."""
    global _rules_loaded_from_json
    if _rules_loaded_from_json:
        return
    _rules_loaded_from_json = True

    path = _default_fee_rules_path()
    if path.exists():
        try:
            load_fee_rules(path)
            logger.info(f"Loaded fee rules from {path}")
        except Exception as e:
            logger.warning(f"Failed to load fee_rules.json: {e}")


def load_fee_rules(path: Optional[Path] = None) -> Dict[tuple, FeeRule]:
    """Load fee rules from a JSON file into the global FEE_RULES registry.

    Also loads hidden_costs into the HIDDEN_COSTS registry if present.
    Returns the loaded rules dict.
    """
    if path is None:
        path = _default_fee_rules_path()

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    rules_list = data.get("rules", [])
    for rule_dict in rules_list:
        rule = FeeRule(
            broker=rule_dict["broker"],
            instrument=rule_dict["instrument"],
            pattern=rule_dict.get("pattern", "unknown"),
            tiers=rule_dict.get("tiers", []),
            handling_fee=rule_dict.get("handling_fee", 0.0),
            min_fee=rule_dict.get("min_fee"),
            max_fee=rule_dict.get("max_fee"),
        )
        _register(rule.broker, rule.instrument, rule)

    # Load hidden costs
    hidden_costs_data = data.get("hidden_costs", {})
    for broker_name, costs_dict in hidden_costs_data.items():
        HIDDEN_COSTS[broker_name] = HiddenCosts(
            custody_fee_monthly_pct=costs_dict.get("custody_fee_monthly_pct", 0.0),
            custody_fee_monthly_min=costs_dict.get("custody_fee_monthly_min", 0.0),
            connectivity_fee_per_exchange_year=costs_dict.get("connectivity_fee_per_exchange_year", 0.0),
            connectivity_fee_max_pct_account=costs_dict.get("connectivity_fee_max_pct_account", 0.0),
            subscription_fee_monthly=costs_dict.get("subscription_fee_monthly", 0.0),
            fx_fee_pct=costs_dict.get("fx_fee_pct", 0.0),
            handling_fee_per_trade=costs_dict.get("handling_fee_per_trade", 0.0),
            dividend_fee_pct=costs_dict.get("dividend_fee_pct", 0.0),
            dividend_fee_min=costs_dict.get("dividend_fee_min", 0.0),
            dividend_fee_max=costs_dict.get("dividend_fee_max", 0.0),
            notes=costs_dict.get("notes", ""),
        )

    logger.info(f"Loaded {len(rules_list)} fee rules and {len(hidden_costs_data)} hidden cost entries from {path}")

    # QA check: warn if any rule produces 0 for ALL transaction sizes
    for (broker_key, instr_key), rule in FEE_RULES.items():
        all_zero = all(
            _compute_from_tiers(rule.tiers, amt, rule.handling_fee, rule.max_fee) == 0.0
            for amt in TRANSACTION_SIZES
        )
        if all_zero:
            logger.warning(
                f"QA WARNING: {rule.broker} {rule.instrument} computes to EUR 0.00 for ALL "
                f"transaction sizes. This is likely an LLM extraction error. "
                f"Tiers: {rule.tiers}, handling_fee: {rule.handling_fee}"
            )

    return dict(FEE_RULES)


def save_fee_rules(rules: Optional[Dict[tuple, FeeRule]] = None, path: Optional[Path] = None,
                   source: str = "default") -> Path:
    """Save fee rules and hidden costs to a JSON file.

    Args:
        rules: Rules dict to save. Defaults to current FEE_RULES.
        path: Output path. Defaults to data/output/fee_rules.json.
        source: Source tag ("default", "llm_extracted").

    Returns:
        The path the file was saved to.
    """
    if rules is None:
        rules = FEE_RULES
    if path is None:
        path = _default_fee_rules_path()

    rules_list = []
    for (_broker_key, _instr_key), rule in sorted(rules.items()):
        rule_dict = {
            "broker": rule.broker,
            "instrument": rule.instrument,
            "pattern": rule.pattern,
            "tiers": rule.tiers,
            "handling_fee": rule.handling_fee,
        }
        if rule.min_fee is not None:
            rule_dict["min_fee"] = rule.min_fee
        if rule.max_fee is not None:
            rule_dict["max_fee"] = rule.max_fee
        rules_list.append(rule_dict)

    # Serialize hidden costs
    hidden_costs_dict = {}
    for broker_name, costs in HIDDEN_COSTS.items():
        hidden_costs_dict[broker_name] = asdict(costs)

    data = {
        "rules": rules_list,
        "hidden_costs": hidden_costs_dict,
        "updated_at": datetime.now().isoformat(),
        "source": source,
    }

    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    logger.info(f"Saved {len(rules_list)} fee rules to {path}")
    return path


def get_rules_diff(old_rules: Dict[tuple, FeeRule], new_rules: Dict[tuple, FeeRule]) -> List[str]:
    """Compare two rule sets and return a list of human-readable change descriptions."""
    changes = []
    all_keys = set(old_rules.keys()) | set(new_rules.keys())

    for key in sorted(all_keys):
        broker_key, instr_key = key
        old = old_rules.get(key)
        new = new_rules.get(key)

        if old is None and new is not None:
            changes.append(f"ADDED {new.broker} {new.instrument}: {new.tiers}")
        elif old is not None and new is None:
            changes.append(f"REMOVED {old.broker} {old.instrument}")
        elif old is not None and new is not None:
            if old.tiers != new.tiers or old.handling_fee != new.handling_fee or old.max_fee != new.max_fee:
                changes.append(
                    f"CHANGED {old.broker} {old.instrument}: "
                    f"tiers {old.tiers} -> {new.tiers}, "
                    f"handling {old.handling_fee} -> {new.handling_fee}"
                )

    return changes


# ========================================================================================
# EXPLANATION GENERATOR (generic, reads from rule structure)
# ========================================================================================

def generate_explanation(broker: str, instrument: str, amount: float) -> str:
    """Generate human-readable fee calculation explanation from rule structure."""
    _ensure_rules_loaded()
    key = (_normalize_broker(broker), _normalize_instrument(instrument))
    rule = FEE_RULES.get(key)
    if rule is None:
        return f"No fee rule for {broker} {instrument}"

    expected = calculate_fee(broker, instrument, amount)
    if expected is None:
        return f"No fee rule for {broker} {instrument}"

    tiers = rule.tiers

    # Simple flat
    if len(tiers) == 1 and "flat" in tiers[0]:
        parts = [f"Flat fee EUR{tiers[0]['flat']:.2f}"]
        if rule.handling_fee > 0:
            parts.append(f"+ EUR{rule.handling_fee:.2f} handling")
        parts.append(f"= EUR{expected:.2f}")
        return " ".join(parts)

    # Percentage with min
    if len(tiers) == 1 and "rate" in tiers[0]:
        rate_pct = tiers[0]["rate"] * 100
        raw = amount * tiers[0]["rate"]
        min_f = tiers[0].get("min_fee", 0.0)
        if raw < min_f:
            return f"EUR{amount:.0f} x {rate_pct:.2f}% = EUR{raw:.2f} < EUR{min_f:.2f} minimum -> EUR{expected:.2f}"
        return f"EUR{amount:.0f} x {rate_pct:.2f}% = EUR{expected:.2f}"

    # Base + slice (single-tier dict with base_up_to)
    if len(tiers) == 1 and "base_up_to" in tiers[0]:
        tier = tiers[0]
        if amount <= tier["base_up_to"]:
            return f"Base fee EUR{tier['base_fee']:.2f} (amount EUR{amount:.0f} <= EUR{tier['base_up_to']:,.0f})"
        remainder = amount - tier["base_up_to"]
        slices = math.ceil(remainder / tier["per_slice"])
        return (f"EUR{tier['base_fee']:.2f} base + {slices} x EUR{tier['slice_fee']:.2f} "
                f"(EUR{remainder:.0f} remainder / EUR{tier['per_slice']:,} slices) = EUR{expected:.2f}")

    # Tiered flat + optional slice
    flat_tiers = [t for t in tiers if "up_to" in t]
    slice_tiers = [t for t in tiers if "per_slice" in t and "up_to" not in t]

    # Check if amount falls in a flat tier
    for tier in flat_tiers:
        if amount <= tier["up_to"]:
            return f"Flat fee EUR{tier['fee']:.2f} (amount EUR{amount:.0f} <= EUR{tier['up_to']:,.0f})"

    # Amount exceeds all flat tiers
    if slice_tiers:
        slice_tier = slice_tiers[0]
        highest_flat = max(flat_tiers, key=lambda t: t["up_to"]) if flat_tiers else None
        if highest_flat:
            remainder = amount - highest_flat["up_to"]
            slices = math.ceil(remainder / slice_tier["per_slice"])
            base_part = f"EUR{highest_flat['fee']:.2f} base"
            slice_part = f"{slices} x EUR{slice_tier['fee']:.2f} (EUR{remainder:.0f} / EUR{slice_tier['per_slice']:,} slices)"
            raw_fee = highest_flat["fee"] + slices * slice_tier["fee"]

            effective_max = slice_tier.get("max_fee") or rule.max_fee
            if effective_max and raw_fee > effective_max:
                return f"{base_part} + {slice_part} = EUR{raw_fee:.2f}, capped at EUR{effective_max:.2f} -> EUR{expected:.2f}"
            return f"{base_part} + {slice_part} = EUR{expected:.2f}"
        else:
            slices = math.ceil(amount / slice_tier["per_slice"])
            return f"{slices} x EUR{slice_tier['fee']:.2f} per EUR{slice_tier['per_slice']:,} slice = EUR{expected:.2f}"

    return f"Fee: EUR{expected:.2f}"


# ========================================================================================
# COMPARISON TABLE BUILDER
# ========================================================================================

# Canonical broker display names (key -> display)
_CANONICAL_NAMES: Dict[str, str] = {
    "degiro belgium": "Degiro Belgium",
    "bolero": "Bolero",
    "keytrade bank": "Keytrade Bank",
    "ing self invest": "ING Self Invest",
    "rebel": "Rebel",
    "revolut": "Revolut",
}


def _get_display_name(broker: str) -> str:
    """Get canonical display name for a broker."""
    normalized = _normalize_broker(broker)
    return _CANONICAL_NAMES.get(normalized, broker)


def build_comparison_tables(broker_names: List[str]) -> dict:
    """Build complete euronext_brussels comparison table structure.

    Returns dict with stocks/etfs/bonds fee matrices + calculation_logic.
    Notes field is left empty (populated by LLM or fallback separately).
    """
    _ensure_rules_loaded()

    stocks = {}
    etfs = {}
    bonds = {}
    calculation_logic = {}

    for broker in broker_names:
        display = _get_display_name(broker)
        calc_broker = {}

        for asset_type, target_dict in [("stocks", stocks), ("etfs", etfs), ("bonds", bonds)]:
            fees = {}
            calc_asset = {}

            for amount in TRANSACTION_SIZES:
                fee = calculate_fee(broker, asset_type, amount)
                amount_str = str(amount)
                if fee is not None:
                    fees[amount_str] = fee
                    calc_asset[amount_str] = generate_explanation(broker, asset_type, amount)

            if fees:
                target_dict[display] = fees
                calc_broker[asset_type] = calc_asset

        if calc_broker:
            calculation_logic[display] = calc_broker

    return {
        "euronext_brussels": {
            "stocks": stocks,
            "etfs": etfs,
            "bonds": bonds,
            "calculation_logic": calculation_logic,
            "notes": {},
        }
    }


# ========================================================================================
# BROKER NOTES (generated from hidden costs structure)
# ========================================================================================

def _generate_note_from_hidden_costs(broker_name: str) -> str:
    """Generate a text note from structured hidden costs."""
    costs = HIDDEN_COSTS.get(broker_name)
    if costs is None:
        return ""

    if costs.notes:
        return costs.notes

    parts = []
    if costs.custody_fee_monthly_pct > 0:
        parts.append(f"Custody: {costs.custody_fee_monthly_pct}%/month (min EUR{costs.custody_fee_monthly_min:.2f}/month)")
    if costs.connectivity_fee_per_exchange_year > 0:
        parts.append(f"Connectivity: EUR{costs.connectivity_fee_per_exchange_year:.2f}/exchange/year")
    if costs.subscription_fee_monthly > 0:
        parts.append(f"Subscription: EUR{costs.subscription_fee_monthly:.2f}/month")
    if costs.fx_fee_pct > 0:
        parts.append(f"FX: {costs.fx_fee_pct}%")
    if costs.dividend_fee_pct > 0:
        parts.append(f"Dividend fee: {costs.dividend_fee_pct}%")
    if not parts:
        parts.append("No significant hidden costs")

    return ". ".join(parts) + "."


BROKER_NOTES: Dict[str, str] = {}


def _build_broker_notes() -> Dict[str, str]:
    """Build broker notes dict from hidden costs. Falls back to static notes."""
    _ensure_rules_loaded()
    notes = {}
    for broker_name in HIDDEN_COSTS:
        notes[broker_name] = _generate_note_from_hidden_costs(broker_name)
    # Fallback statics for brokers with no hidden cost data
    _STATIC_NOTES = {
        "Bolero": "No custody fees for Belgian residents. Connectivity fee of EUR2.50/exchange/year.",
        "Keytrade Bank": "No account fees. Phone/international orders cost extra.",
        "Degiro Belgium": "EUR2 commission + EUR1 handling per trade. Connectivity fee EUR2.50/exchange/year.",
        "ING Self Invest": "Web rate 0.35%. Minimum EUR1.00. Currency exchange margins apply.",
        "Rebel": "No custody fees for Belgian stocks. Non-Belgian dividend collection fee. Part of Belfius.",
        "Revolut": "Standard plan (free): 0.25% commission, EUR1 min, 1 free trade/month. FX fees above monthly limits.",
    }
    for name, note in _STATIC_NOTES.items():
        if name not in notes:
            notes[name] = note
    return notes
