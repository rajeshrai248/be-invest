"""Deterministic fee calculator for Belgian broker cost comparison tables.

Computes exact fees for (broker, instrument, trade_amount) tuples using known
calculation rules. These rules are structural (how tiers/slices/minimums work)
and rarely change, even when the exact amounts in PDFs change.

When PDF fee schedules change, only the FEE_RULES dict needs updating.
"""

import math
from dataclasses import dataclass, field
from typing import Optional, Dict, List


@dataclass
class FeeRule:
    """A single fee rule for a broker/instrument combination."""
    broker: str
    instrument: str  # "stocks", "etfs", "bonds"
    tiers: List[dict] = field(default_factory=list)
    # Tiers can contain:
    #   {"up_to": 2500, "fee": 7.50}          -- flat fee for amounts <= up_to
    #   {"per_slice": 10000, "fee": 15.0}      -- per-started-slice fee for amounts above tiers
    #   {"base_up_to": 10000, "base_fee": 14.95, "per_slice": 10000, "slice_fee": 7.50}
    #                                           -- base fee + per-slice for remainder
    #   {"rate": 0.0035, "min_fee": 1.00}      -- percentage rate with minimum
    #   {"flat": 3.00}                          -- simple flat fee for all amounts
    handling_fee: float = 0.0
    min_fee: Optional[float] = None


# Registry of known fee rules (from server.py prompt lines 441-512)
FEE_RULES: Dict[tuple, FeeRule] = {}


def _register(broker: str, instrument: str, rule: FeeRule) -> None:
    """Register a fee rule in the global registry."""
    FEE_RULES[(broker.lower(), instrument.lower())] = rule


# --- Degiro Belgium: €2 commission + €1 handling = €3 flat for all ---
for _instr in ("stocks", "etfs", "bonds"):
    _register("Degiro Belgium", _instr, FeeRule(
        broker="Degiro Belgium",
        instrument=_instr,
        tiers=[{"flat": 2.00}],
        handling_fee=1.00,
    ))

# --- Bolero: <=€2500 -> €7.50; >€2500 -> €15 per started €10k slice ---
for _instr in ("stocks", "etfs", "bonds"):
    _register("Bolero", _instr, FeeRule(
        broker="Bolero",
        instrument=_instr,
        tiers=[
            {"up_to": 2500, "fee": 7.50},
            {"per_slice": 10000, "fee": 15.00},
        ],
    ))

# --- Keytrade Bank: <=€10k -> €14.95; >€10k -> +€7.50 per started €10k slice ---
for _instr in ("stocks", "etfs"):
    _register("Keytrade Bank", _instr, FeeRule(
        broker="Keytrade Bank",
        instrument=_instr,
        tiers=[
            {"base_up_to": 10000, "base_fee": 14.95, "per_slice": 10000, "slice_fee": 7.50},
        ],
    ))

# --- ING Self Invest: 0.35% with €1.00 minimum (Web rate) ---
for _instr in ("stocks", "etfs", "bonds"):
    _register("ING Self Invest", _instr, FeeRule(
        broker="ING Self Invest",
        instrument=_instr,
        tiers=[{"rate": 0.0035, "min_fee": 1.00}],
    ))

# --- Rebel stocks: <=€2500 -> €3; >€2500 -> €10 per started €10k slice ---
_register("Rebel", "stocks", FeeRule(
    broker="Rebel",
    instrument="stocks",
    tiers=[
        {"up_to": 2500, "fee": 3.00},
        {"per_slice": 10000, "fee": 10.00},
    ],
))

# --- Rebel ETFs: tiered flats then slice ---
# <=€250: €1; <=€1000: €2; <=€2500: €3; >€2500: €10 per started €10k slice
_register("Rebel", "etfs", FeeRule(
    broker="Rebel",
    instrument="etfs",
    tiers=[
        {"up_to": 250, "fee": 1.00},
        {"up_to": 1000, "fee": 2.00},
        {"up_to": 2500, "fee": 3.00},
        {"per_slice": 10000, "fee": 10.00},
    ],
))


def _compute_from_tiers(tiers: List[dict], amount: float, handling_fee: float = 0.0) -> float:
    """Compute fee from a tier list for a given amount."""
    # Check for simple flat fee
    if len(tiers) == 1 and "flat" in tiers[0]:
        return tiers[0]["flat"] + handling_fee

    # Check for percentage rate
    if len(tiers) == 1 and "rate" in tiers[0]:
        fee = amount * tiers[0]["rate"]
        min_fee = tiers[0].get("min_fee", 0.0)
        return max(fee, min_fee) + handling_fee

    # Check for base + slice model (Keytrade)
    if len(tiers) == 1 and "base_up_to" in tiers[0]:
        tier = tiers[0]
        if amount <= tier["base_up_to"]:
            return tier["base_fee"] + handling_fee
        remainder = amount - tier["base_up_to"]
        slices = math.ceil(remainder / tier["per_slice"])
        return tier["base_fee"] + (slices * tier["slice_fee"]) + handling_fee

    # Tiered flat fees + optional per-slice tier at the end
    # Find the applicable flat tier
    for tier in tiers:
        if "up_to" in tier and amount <= tier["up_to"]:
            return tier["fee"] + handling_fee

    # If we get here, amount exceeds all flat tiers -> use per_slice tier
    for tier in tiers:
        if "per_slice" in tier and "up_to" not in tier:
            slices = math.ceil(amount / tier["per_slice"])
            return (slices * tier["fee"]) + handling_fee

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
}


def _normalize_broker(broker: str) -> str:
    """Normalize broker name to match FEE_RULES keys."""
    return BROKER_ALIASES.get(broker.lower().strip(), broker.lower().strip())


def _normalize_instrument(instrument: str) -> str:
    """Normalize instrument name."""
    instrument = instrument.lower().strip()
    # Handle common variations
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
    key = (_normalize_broker(broker), _normalize_instrument(instrument))
    rule = FEE_RULES.get(key)
    if rule is None:
        return None
    fee = _compute_from_tiers(rule.tiers, amount, rule.handling_fee)
    return round(fee, 2)


def calculate_all_fees(broker: str, instrument: str, amounts: List[float]) -> Dict[str, Optional[float]]:
    """Compute fees for multiple amounts.

    Returns dict mapping amount string to fee (or None if no rule exists).
    """
    return {str(int(a)): calculate_fee(broker, instrument, a) for a in amounts}
