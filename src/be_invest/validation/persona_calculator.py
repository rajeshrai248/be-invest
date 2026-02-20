"""Investor persona calculator for Total Cost of Ownership (TCO) comparison.

Defines three investor personas (Passive, Moderate, Active) and computes
annual TCO including trading costs + hidden costs (custody, connectivity,
FX, dividends) for each broker.
"""

import logging
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional

from .fee_calculator import (
    calculate_fee, _ensure_rules_loaded, _get_display_name,
    HIDDEN_COSTS, HiddenCosts, _CANONICAL_NAMES,
)

logger = logging.getLogger(__name__)


@dataclass
class Trade:
    """A single trade type within a persona definition."""
    instrument: str  # "stocks" or "etfs"
    amount: float  # trade amount in EUR
    count_per_year: int  # how many times per year


@dataclass
class PersonaDefinition:
    """Definition of an investor persona."""
    key: str
    name: str
    description: str
    trades: List[Trade]
    portfolio_value: float  # assumed total portfolio value
    exchanges_used: int  # number of exchanges the investor uses
    fx_volume_annual: float  # assumed annual FX conversion volume
    dividend_income_annual: float  # assumed annual dividend income


@dataclass
class TradeCostDetail:
    """Breakdown of cost for one trade type."""
    instrument: str
    amount: float
    count_per_year: int
    fee_per_trade: float
    total: float


@dataclass
class PersonaCostResult:
    """Full TCO result for one broker + one persona."""
    broker: str
    trading_costs: float
    trading_cost_details: List[TradeCostDetail]
    custody_cost_annual: float
    connectivity_cost_annual: float
    subscription_cost_annual: float
    fx_cost_annual: float
    dividend_cost_annual: float
    total_annual_tco: float
    rank: int = 0


# ========================================================================================
# PERSONA DEFINITIONS
# ========================================================================================

PERSONAS: Dict[str, PersonaDefinition] = {
    "passive_investor": PersonaDefinition(
        key="passive_investor",
        name="Passive Investor",
        description="Monthly EUR500 ETF purchases. Long-term buy-and-hold strategy.",
        trades=[Trade(instrument="etfs", amount=500, count_per_year=12)],
        portfolio_value=30000,
        exchanges_used=1,
        fx_volume_annual=0,
        dividend_income_annual=600,
    ),
    "moderate_investor": PersonaDefinition(
        key="moderate_investor",
        name="Moderate Investor",
        description="Mix of ETF and stock purchases. Semi-active portfolio management.",
        trades=[
            Trade(instrument="etfs", amount=1000, count_per_year=6),
            Trade(instrument="stocks", amount=2500, count_per_year=6),
        ],
        portfolio_value=50000,
        exchanges_used=2,
        fx_volume_annual=5000,
        dividend_income_annual=1000,
    ),
    "active_trader": PersonaDefinition(
        key="active_trader",
        name="Active Trader",
        description="Frequent stock trades including large positions. Active portfolio management.",
        trades=[
            Trade(instrument="stocks", amount=2500, count_per_year=120),
            Trade(instrument="stocks", amount=10000, count_per_year=24),
        ],
        portfolio_value=200000,
        exchanges_used=3,
        fx_volume_annual=50000,
        dividend_income_annual=4000,
    ),
}


def compute_persona_costs(broker: str, persona_key: str) -> Optional[PersonaCostResult]:
    """Compute annual TCO for a broker + persona combination.

    Returns None if no fee rules exist for this broker.
    """
    _ensure_rules_loaded()

    persona = PERSONAS.get(persona_key)
    if persona is None:
        return None

    display = _get_display_name(broker)
    hidden = HIDDEN_COSTS.get(display, HiddenCosts())

    # Trading costs
    trading_details = []
    trading_total = 0.0
    has_any_rule = False

    for trade in persona.trades:
        fee = calculate_fee(broker, trade.instrument, trade.amount)
        if fee is not None:
            has_any_rule = True
            total_for_type = fee * trade.count_per_year
            trading_total += total_for_type
            trading_details.append(TradeCostDetail(
                instrument=trade.instrument,
                amount=trade.amount,
                count_per_year=trade.count_per_year,
                fee_per_trade=fee,
                total=round(total_for_type, 2),
            ))

    if not has_any_rule:
        return None

    # Custody costs
    custody_annual = 0.0
    if hidden.custody_fee_monthly_pct > 0:
        monthly_pct = hidden.custody_fee_monthly_pct / 100.0
        monthly_cost = max(persona.portfolio_value * monthly_pct, hidden.custody_fee_monthly_min)
        custody_annual = monthly_cost * 12

    # Connectivity costs
    connectivity_annual = hidden.connectivity_fee_per_exchange_year * persona.exchanges_used
    if hidden.connectivity_fee_max_pct_account > 0:
        max_connectivity = persona.portfolio_value * (hidden.connectivity_fee_max_pct_account / 100.0)
        connectivity_annual = min(connectivity_annual, max_connectivity)

    # Subscription costs
    subscription_annual = hidden.subscription_fee_monthly * 12

    # FX costs
    fx_annual = 0.0
    if hidden.fx_fee_pct > 0 and persona.fx_volume_annual > 0:
        fx_annual = persona.fx_volume_annual * (hidden.fx_fee_pct / 100.0)

    # Dividend costs
    dividend_annual = 0.0
    if hidden.dividend_fee_pct > 0 and persona.dividend_income_annual > 0:
        dividend_annual = persona.dividend_income_annual * (hidden.dividend_fee_pct / 100.0)
        if hidden.dividend_fee_min > 0:
            dividend_annual = max(dividend_annual, hidden.dividend_fee_min)
        if hidden.dividend_fee_max > 0:
            dividend_annual = min(dividend_annual, hidden.dividend_fee_max)

    total_tco = (
        trading_total
        + custody_annual
        + connectivity_annual
        + subscription_annual
        + fx_annual
        + dividend_annual
    )

    return PersonaCostResult(
        broker=display,
        trading_costs=round(trading_total, 2),
        trading_cost_details=trading_details,
        custody_cost_annual=round(custody_annual, 2),
        connectivity_cost_annual=round(connectivity_annual, 2),
        subscription_cost_annual=round(subscription_annual, 2),
        fx_cost_annual=round(fx_annual, 2),
        dividend_cost_annual=round(dividend_annual, 2),
        total_annual_tco=round(total_tco, 2),
    )


def build_persona_comparison(broker_names: List[str]) -> dict:
    """Build persona comparison for all brokers.

    Returns dict with:
      - persona_key -> list of PersonaCostResult (sorted by TCO, with ranks)
      - persona_definitions -> persona metadata
    """
    _ensure_rules_loaded()

    investor_personas = {}
    for persona_key, persona_def in PERSONAS.items():
        results = []
        for broker in broker_names:
            result = compute_persona_costs(broker, persona_key)
            if result is not None:
                results.append(result)

        # Sort by TCO and assign ranks
        results.sort(key=lambda r: r.total_annual_tco)
        for i, result in enumerate(results):
            result.rank = i + 1

        # Convert to serializable dicts
        investor_personas[persona_key] = [
            {
                "broker": r.broker,
                "trading_costs": r.trading_costs,
                "custody_cost_annual": r.custody_cost_annual,
                "connectivity_cost_annual": r.connectivity_cost_annual,
                "subscription_cost_annual": r.subscription_cost_annual,
                "fx_cost_annual": r.fx_cost_annual,
                "dividend_cost_annual": r.dividend_cost_annual,
                "total_annual_tco": r.total_annual_tco,
                "rank": r.rank,
                "trading_cost_details": [
                    {
                        "instrument": d.instrument,
                        "amount": d.amount,
                        "count_per_year": d.count_per_year,
                        "fee_per_trade": d.fee_per_trade,
                        "total": d.total,
                    }
                    for d in r.trading_cost_details
                ],
            }
            for r in results
        ]

    # Persona definitions for the frontend
    persona_definitions = {
        key: {
            "name": p.name,
            "description": p.description,
            "portfolio_value": p.portfolio_value,
            "exchanges_used": p.exchanges_used,
            "fx_volume_annual": p.fx_volume_annual,
            "dividend_income_annual": p.dividend_income_annual,
            "trades": [
                {
                    "instrument": t.instrument,
                    "amount": t.amount,
                    "count_per_year": t.count_per_year,
                }
                for t in p.trades
            ],
        }
        for key, p in PERSONAS.items()
    }

    return {
        "investor_personas": investor_personas,
        "persona_definitions": persona_definitions,
    }
