"""Refresh fee_rules.json from existing PDF text files (no scraping).

This script re-runs the two-step LLM extraction pipeline that normally runs inside
/refresh-and-analyze, but skips the PDF scraping step entirely.

Usage:
    # Re-extract ALL brokers (from cached broker_cost_analyses.json if present)
    python scripts/refresh_fee_rules.py

    # Force re-analysis even if broker_cost_analyses.json exists
    python scripts/refresh_fee_rules.py --force-reanalyze

    # Re-extract specific brokers only
    python scripts/refresh_fee_rules.py "Revolut" "Keytrade Bank"

    # Re-extract specific brokers AND force step-1 re-analysis
    python scripts/refresh_fee_rules.py --force-reanalyze "Revolut"

Two-step pipeline:
    Step 1 (can be skipped if cache exists):
        Read data/output/pdf_text/*.txt → LLM analysis → broker_cost_analyses.json
    Step 2 (always runs):
        broker_cost_analyses.json → LLM structured extraction → fee_rules.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import math
import os
import re
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import anthropic

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data" / "output"
PDF_TEXT_DIR = DATA_DIR / "pdf_text"
ANALYSES_CACHE = DATA_DIR / "broker_cost_analyses.json"
FEE_RULES_PATH = DATA_DIR / "fee_rules.json"
BROKERS_YAML = REPO_ROOT / "data" / "brokers.yaml"
COMPARISON_TABLES_PATH = DATA_DIR / "cost_comparison_tables.json"

# Make sure project src is importable (for fee_calculator helpers)
sys.path.insert(0, str(REPO_ROOT / "src"))

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Anthropic client
# ---------------------------------------------------------------------------
_api_key = os.getenv("ANTHROPIC_API_KEY")
if not _api_key:
    logger.error("ANTHROPIC_API_KEY is not set. Exiting.")
    sys.exit(1)

_client = anthropic.Anthropic(api_key=_api_key)
MODEL = "claude-sonnet-4-20250514"


# ---------------------------------------------------------------------------
# LLM helper
# ---------------------------------------------------------------------------
def _call_llm(system: str, user: str) -> str:
    """Call Claude and return the response text (JSON mode)."""
    response = _client.messages.create(
        model=MODEL,
        max_tokens=8192,
        temperature=0.0,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return response.content[0].text


# ---------------------------------------------------------------------------
# Broker / PDF-text helpers (no imports from server.py)
# ---------------------------------------------------------------------------

def _safe_name(s: str) -> str:
    """Match the filename-safe convention used when saving PDF texts."""
    return re.sub(r"[^\w\-]", "_", s)


def _url_hash(url: str) -> str:
    return hashlib.md5(url.encode()).hexdigest()[:8]


def _load_brokers() -> List[Any]:
    """Load broker list from YAML (returns Broker dataclass objects)."""
    from be_invest.config_loader import load_brokers_from_yaml
    return load_brokers_from_yaml(BROKERS_YAML)


def _collect_pdf_texts(
    brokers: List[Any],
    target_names: Optional[List[str]] = None,
) -> Dict[str, List[Dict[str, str]]]:
    """Map broker display names → list of {filename, content} from pdf_text dir."""
    target_lower = {n.lower() for n in target_names} if target_names else None

    pdf_texts: Dict[str, List[Dict[str, str]]] = {}
    for broker in brokers:
        if target_lower and broker.name.lower() not in target_lower:
            continue
        broker_texts: List[Dict[str, str]] = []
        for source in broker.data_sources:
            if source.type != "pdf" or not source.url:
                continue
            safe_broker = _safe_name(broker.name)
            safe_desc = _safe_name(source.description or "")
            h = _url_hash(source.url)
            filename = f"{safe_broker}_{safe_desc}_{h}.txt"
            text_path = PDF_TEXT_DIR / filename
            if text_path.exists():
                content = text_path.read_text(encoding="utf-8")
                broker_texts.append({"filename": filename, "content": content})
                logger.info(f"  Loaded {filename} ({len(content):,} chars)")
            else:
                logger.warning(f"  PDF text not found: {filename}")
        if broker_texts:
            pdf_texts[broker.name] = broker_texts
    return pdf_texts


# ---------------------------------------------------------------------------
# Step 1 – PDF text → broker_cost_analyses.json
# ---------------------------------------------------------------------------

def _run_step1_analysis(
    pdf_texts: Dict[str, List[Dict[str, str]]],
) -> Dict[str, Any]:
    """Run step-1 LLM analysis for each broker and return analyses dict."""
    system_prompt = "You are a financial analyst. Return ONLY valid JSON, no explanations."
    analyses: Dict[str, Any] = {}

    for broker_name, texts in pdf_texts.items():
        combined = "\n\n".join(t["content"] for t in texts)
        logger.info(f"  Analyzing {broker_name} ({len(combined):,} chars)…")

        user_prompt = (
            f"Extract ALL broker fees from the following tariffs for {broker_name}.\n"
            f"Return ONLY a valid JSON object with structured fee data.\n\n"
            f"{combined[:15000]}"
        )

        try:
            text = _call_llm(system_prompt, user_prompt)
            # Strip markdown code fences if present
            stripped = text.strip()
            if stripped.startswith("```"):
                first_newline = stripped.index("\n")
                stripped = stripped[first_newline + 1:]
                if stripped.rstrip().endswith("```"):
                    stripped = stripped.rstrip()[:-3].rstrip()
            if not stripped or not stripped.startswith("{"):
                logger.error(f"  Invalid response for {broker_name}")
                analyses[broker_name] = {"error": "Invalid LLM response"}
            else:
                analyses[broker_name] = json.loads(stripped)
                logger.info(f"  ✓ {broker_name} step-1 complete")
        except Exception as exc:
            logger.error(f"  Step-1 failed for {broker_name}: {exc}")
            analyses[broker_name] = {"error": str(exc)}

    return analyses


# ---------------------------------------------------------------------------
# Step 2 – broker_cost_analyses.json → fee rules (same prompt as server.py)
# ---------------------------------------------------------------------------

def _build_extraction_prompt(broker_name: str, broker_data: Any) -> str:
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


def _run_step2_extraction(
    analyses: Dict[str, Any],
    target_names: Optional[List[str]] = None,
) -> Tuple[Dict[tuple, Any], Dict[str, Any]]:
    """Run step-2 structured extraction.

    Returns:
        (new_rules, new_hidden_costs) — dicts keyed by (broker, instr, exchange) tuples
        and broker display names respectively.
    """
    from be_invest.validation.fee_calculator import FeeRule, HiddenCosts, _compute_from_tiers, TRANSACTION_SIZES

    system_prompt = (
        "You are a financial data extractor specialising in Belgian broker fee structures. "
        "Return ONLY valid JSON."
    )

    target_lower = {n.lower() for n in target_names} if target_names else None

    new_rules: Dict[tuple, FeeRule] = {}
    new_hidden: Dict[str, HiddenCosts] = {}

    for broker_name, broker_data in analyses.items():
        if target_lower and broker_name.lower() not in target_lower:
            continue
        if not isinstance(broker_data, dict) or "error" in broker_data:
            logger.warning(f"  Skipping {broker_name}: invalid or error data")
            continue

        logger.info(f"  Extracting rules for {broker_name}…")
        user_prompt = _build_extraction_prompt(broker_name, broker_data)

        try:
            text = _call_llm(system_prompt, user_prompt)
            # Strip markdown code fences if present
            stripped = text.strip()
            if stripped.startswith("```"):
                # Remove opening fence (```json or ```)
                first_newline = stripped.index("\n")
                stripped = stripped[first_newline + 1:]
                # Remove closing fence
                if stripped.rstrip().endswith("```"):
                    stripped = stripped.rstrip()[:-3].rstrip()
            data = json.loads(stripped)
        except Exception as exc:
            logger.error(f"  Step-2 failed for {broker_name}: {exc}")
            logger.error(f"  Raw response (first 200 chars): {text[:200]}")
            continue

        # Parse rules
        broker_rule_count = 0
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
            key = (broker.lower(), instrument.lower(), rule.exchange.lower())

            # QA: skip all-zero rules
            all_zero = all(
                _compute_from_tiers(rule.tiers, amt, rule.handling_fee, rule.max_fee) == 0.0
                for amt in TRANSACTION_SIZES
            )
            if all_zero:
                logger.warning(
                    f"  QA: {broker} {instrument} has all-zero fees — skipping. Tiers: {rule.tiers}"
                )
                continue

            new_rules[key] = rule
            broker_rule_count += 1

        # Parse hidden costs
        for hc_name, costs_dict in data.get("hidden_costs", {}).items():
            if isinstance(costs_dict, dict):
                new_hidden[hc_name] = HiddenCosts(
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

        logger.info(f"  ✓ {broker_name}: {broker_rule_count} rules extracted")

    return new_rules, new_hidden


# ---------------------------------------------------------------------------
# Save fee_rules.json (standalone, no server.py dependency)
# ---------------------------------------------------------------------------

def _save_fee_rules(
    rules: Dict[tuple, Any],
    hidden: Dict[str, Any],
    path: Path = FEE_RULES_PATH,
) -> None:
    from be_invest.validation.fee_calculator import FeeRule

    rules_list = []
    for key, rule in sorted(rules.items()):
        rule_dict: Dict[str, Any] = {
            "broker": rule.broker,
            "instrument": rule.instrument,
            "pattern": rule.pattern,
            "tiers": rule.tiers,
            "handling_fee": rule.handling_fee,
            "exchange": rule.exchange,
        }
        if rule.min_fee is not None:
            rule_dict["min_fee"] = rule.min_fee
        if rule.max_fee is not None:
            rule_dict["max_fee"] = rule.max_fee
        if rule.min_order is not None:
            rule_dict["min_order"] = rule.min_order
        if rule.conditions:
            rule_dict["conditions"] = rule.conditions
        if rule.notes:
            rule_dict["notes"] = rule.notes
        if rule.source:
            rule_dict["source"] = rule.source
        rules_list.append(rule_dict)

    hidden_dict = {name: asdict(hc) for name, hc in hidden.items()}

    data = {
        "rules": rules_list,
        "hidden_costs": hidden_dict,
        "updated_at": datetime.now().isoformat(),
        "source": "llm_extracted",
    }

    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    logger.info(f"Saved {len(rules_list)} fee rules → {path}")


# ---------------------------------------------------------------------------
# Post-extraction validation against known-good reference values
# ---------------------------------------------------------------------------

# Known-correct Euronext Brussels fees for all brokers/instruments/tiers.
# This is the authoritative reference — if the LLM extraction disagrees,
# the extraction is wrong and must be corrected.
_EURONEXT_BRUSSELS_REFERENCE: Dict[str, Dict[str, Dict[int, float]]] = {
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
# Each entry is (broker, instrument, exchange) → rule kwargs that produce correct fees.
_EURONEXT_BRUSSELS_CORRECT_RULES: Dict[tuple, dict] = {
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
        "notes": "Online orders on Euronext Brussels. Stocks have different tiers than ETFs/trackers. Above €10K: 0.09% × order amount.",
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
        "notes": "Standard stock fees on Euronext Brussels. €3 up to €2500, then €10 per started €10K slice.",
    },
    ("Bolero", "bonds", "all"): {
        "pattern": "base_plus_slice",
        "tiers": [
            {"base_up_to": 10000, "base_fee": 25.0, "per_slice": 10000, "slice_fee": 25.0},
        ],
        "handling_fee": 0.0,
        "notes": "€25 per started €10,000 slice. Non-listed bonds secondary market.",
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
        "notes": "Rebel ETF/tracker fees on Euronext Brussels. €1/€2/€3 tiered, then €10 per started €10K slice.",
    },
    ("Trade Republic", "bonds", "all"): {
        "pattern": "flat",
        "tiers": [
            {"flat": 1.0},
        ],
        "handling_fee": 0.0,
        "notes": "€1 flat fee per trade. Trade Republic bonds.",
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


def _validate_and_fix_extracted_rules(
    rules: Dict[tuple, Any],
) -> Tuple[Dict[tuple, Any], int]:
    """Validate LLM-extracted rules against known-good reference values.

    For each broker/instrument/amount in the reference, compute the fee
    from the extracted rule and compare.  If ANY fee mismatches, replace
    the rule with the known-correct version from _EURONEXT_BRUSSELS_CORRECT_RULES.

    Returns:
        (fixed_rules, fix_count) — the corrected rules dict and number of fixes applied.
    """
    from be_invest.validation.fee_calculator import (
        FeeRule, _compute_from_tiers, _sanitize_tiers, _normalize_broker, _normalize_instrument,
    )

    fix_count = 0

    for instrument, broker_ref in _EURONEXT_BRUSSELS_REFERENCE.items():
        for broker_display, expected_fees in broker_ref.items():
            # Find the matching rule
            norm_broker = _normalize_broker(broker_display)
            norm_instr = _normalize_instrument(instrument)

            # Try euronext_brussels first, then 'all'
            key_exch = (norm_broker, norm_instr, "euronext_brussels")
            key_all = (norm_broker, norm_instr, "all")
            rule = rules.get(key_exch) or rules.get(key_all)
            matched_key = key_exch if key_exch in rules else key_all if key_all in rules else None

            if rule is None:
                # No rule exists → need to inject one
                logger.warning(
                    f"  VALIDATION: No rule for {broker_display} {instrument} on euronext_brussels — injecting correct rule"
                )
                correct = _EURONEXT_BRUSSELS_CORRECT_RULES.get((broker_display, instrument, "euronext_brussels"))
                if correct is None:
                    correct = _EURONEXT_BRUSSELS_CORRECT_RULES.get((broker_display, instrument, "all"))
                if correct:
                    exch = "euronext_brussels" if (broker_display, instrument, "euronext_brussels") in _EURONEXT_BRUSSELS_CORRECT_RULES else "all"
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
                logger.warning(
                    f"  VALIDATION: {broker_display} {instrument} has {len(mismatches)} fee mismatches:"
                )
                for amt, exp, act in mismatches[:5]:
                    logger.warning(f"    EUR {amt}: expected={exp}, got={act}")
                if len(mismatches) > 5:
                    logger.warning(f"    ... and {len(mismatches) - 5} more")

                # Look up the correct rule
                correct = _EURONEXT_BRUSSELS_CORRECT_RULES.get((broker_display, instrument, rule.exchange))
                if correct is None:
                    # Try broader search
                    for ck, cv in _EURONEXT_BRUSSELS_CORRECT_RULES.items():
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
                    logger.error(
                        f"  VALIDATION: {broker_display} {instrument} has errors but no "
                        f"correct reference rule available — manual fix needed"
                    )

    return rules, fix_count


# ---------------------------------------------------------------------------
# Regenerate comparison tables
# ---------------------------------------------------------------------------

def _regenerate_comparison_tables() -> None:
    """Recompute cost_comparison_tables.json from updated fee rules."""
    from be_invest.validation.fee_calculator import (
        load_fee_rules,
        calculate_fee,
        TRANSACTION_SIZES,
        ASSET_TYPES,
        FEE_RULES,
        HIDDEN_COSTS,
        build_comparison_tables,
    )

    # Reload updated rules
    load_fee_rules(FEE_RULES_PATH)

    brokers = sorted({rule.broker for rule in FEE_RULES.values()})

    # Use build_comparison_tables which properly passes the exchange parameter
    data = build_comparison_tables(brokers, exchange="euronext_brussels")

    COMPARISON_TABLES_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(COMPARISON_TABLES_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    logger.info(f"Saved comparison tables -> {COMPARISON_TABLES_PATH}")


# ---------------------------------------------------------------------------
# Merge helpers (keep rules for un-targeted brokers)
# ---------------------------------------------------------------------------

def _load_existing_fee_rules_raw() -> Tuple[Dict[tuple, Any], Dict[str, Any]]:
    """Load existing fee_rules.json into raw dicts (no global mutation)."""
    from be_invest.validation.fee_calculator import FeeRule, HiddenCosts

    if not FEE_RULES_PATH.exists():
        return {}, {}

    with open(FEE_RULES_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    rules: Dict[tuple, FeeRule] = {}
    for rd in data.get("rules", []):
        broker = rd.get("broker", "")
        instrument = rd.get("instrument", "")
        exchange = rd.get("exchange", "all")
        if not broker or not instrument:
            continue
        key = (broker.lower(), instrument.lower(), exchange.lower())
        rules[key] = FeeRule(
            broker=broker,
            instrument=instrument,
            pattern=rd.get("pattern", "unknown"),
            tiers=rd.get("tiers", []),
            handling_fee=rd.get("handling_fee", 0.0),
            min_fee=rd.get("min_fee"),
            max_fee=rd.get("max_fee"),
            min_order=rd.get("min_order"),
            exchange=exchange,
            conditions=rd.get("conditions", []),
            notes=rd.get("notes", ""),
            source=rd.get("source", {}),
        )

    hidden: Dict[str, Any] = {}
    from be_invest.validation.fee_calculator import HiddenCosts
    for name, cd in data.get("hidden_costs", {}).items():
        hidden[name] = HiddenCosts(
            custody_fee_monthly_pct=cd.get("custody_fee_monthly_pct", 0.0),
            custody_fee_monthly_min=cd.get("custody_fee_monthly_min", 0.0),
            connectivity_fee_per_exchange_year=cd.get("connectivity_fee_per_exchange_year", 0.0),
            connectivity_fee_max_pct_account=cd.get("connectivity_fee_max_pct_account", 0.0),
            subscription_fee_monthly=cd.get("subscription_fee_monthly", 0.0),
            subscription_plan_name=cd.get("subscription_plan_name", ""),
            fx_fee_pct=cd.get("fx_fee_pct", 0.0),
            handling_fee_per_trade=cd.get("handling_fee_per_trade", 0.0),
            dividend_fee_pct=cd.get("dividend_fee_pct", 0.0),
            dividend_fee_min=cd.get("dividend_fee_min", 0.0),
            dividend_fee_max=cd.get("dividend_fee_max", 0.0),
            notes=cd.get("notes", ""),
        )

    return rules, hidden


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Re-extract fee_rules.json from existing PDF text files (no scraping)."
    )
    parser.add_argument(
        "brokers",
        nargs="*",
        help="Optional broker names to re-extract (e.g. 'Revolut' 'Keytrade Bank'). "
             "Omit to process ALL brokers.",
    )
    parser.add_argument(
        "--force-reanalyze",
        action="store_true",
        help="Always re-run step-1 LLM analysis even if broker_cost_analyses.json exists.",
    )
    args = parser.parse_args()

    target_names: Optional[List[str]] = args.brokers if args.brokers else None
    force_reanalyze: bool = args.force_reanalyze

    logger.info("=" * 70)
    logger.info("refresh_fee_rules.py  —  skipping PDF scraping")
    if target_names:
        logger.info(f"Target brokers: {target_names}")
    else:
        logger.info("Target brokers: ALL")
    logger.info("=" * 70)

    # ------------------------------------------------------------------
    # Step 1: get broker_cost_analyses
    # ------------------------------------------------------------------
    if not force_reanalyze and ANALYSES_CACHE.exists():
        logger.info(f"Loading cached step-1 analyses from {ANALYSES_CACHE}")
        with open(ANALYSES_CACHE, "r", encoding="utf-8") as f:
            all_analyses: Dict[str, Any] = json.load(f)

        # If targeting specific brokers, re-analyze only those
        if target_names:
            target_lower = {n.lower() for n in target_names}
            missing_in_cache = [
                n for n in target_names
                if n.lower() not in {k.lower() for k in all_analyses}
            ]
            needs_reanalysis = (
                missing_in_cache
                or any(
                    k.lower() in target_lower and "error" in v
                    for k, v in all_analyses.items()
                )
            )
            if needs_reanalysis or force_reanalyze:
                logger.info("Some target brokers missing or errored in cache — running step-1 for them…")
                brokers = _load_brokers()
                pdf_texts = _collect_pdf_texts(brokers, target_names)
                fresh = _run_step1_analysis(pdf_texts)
                all_analyses.update(fresh)
                # Save merged cache
                with open(ANALYSES_CACHE, "w", encoding="utf-8") as f:
                    json.dump(all_analyses, f, indent=2, ensure_ascii=False)
                logger.info(f"Updated cache → {ANALYSES_CACHE}")
    else:
        # Run step-1 for required brokers
        logger.info("Running step-1 LLM analysis…")
        brokers = _load_brokers()
        pdf_texts = _collect_pdf_texts(brokers, target_names)

        if not pdf_texts:
            logger.error("No PDF text files found. Run /refresh-and-analyze first to scrape PDFs.")
            sys.exit(1)

        if ANALYSES_CACHE.exists() and not force_reanalyze:
            with open(ANALYSES_CACHE, "r", encoding="utf-8") as f:
                all_analyses = json.load(f)
        else:
            all_analyses = {}

        fresh = _run_step1_analysis(pdf_texts)
        all_analyses.update(fresh)

        with open(ANALYSES_CACHE, "w", encoding="utf-8") as f:
            json.dump(all_analyses, f, indent=2, ensure_ascii=False)
        logger.info(f"Saved step-1 analyses → {ANALYSES_CACHE}")

    # ------------------------------------------------------------------
    # Step 2: structured extraction → new rules
    # ------------------------------------------------------------------
    logger.info("Running step-2 structured extraction…")
    new_rules, new_hidden = _run_step2_extraction(all_analyses, target_names)

    if not new_rules:
        logger.error("No rules extracted. Check LLM responses above.")
        sys.exit(1)

    # ------------------------------------------------------------------
    # Merge with existing rules (keep rules for brokers not targeted)
    # ------------------------------------------------------------------
    existing_rules, existing_hidden = _load_existing_fee_rules_raw()

    if target_names:
        target_lower = {n.lower() for n in target_names}
        # Keep rules for brokers outside the target set
        merged_rules = {k: v for k, v in existing_rules.items() if k[0] not in target_lower}
        merged_hidden = {k: v for k, v in existing_hidden.items() if k.lower() not in target_lower}
    else:
        merged_rules = {}
        merged_hidden = {}

    merged_rules.update(new_rules)
    merged_hidden.update(new_hidden)

    # ------------------------------------------------------------------
    # Step 3: Validate extracted rules against known-good reference
    # ------------------------------------------------------------------
    logger.info("Validating extracted rules against reference values…")
    merged_rules, fix_count = _validate_and_fix_extracted_rules(merged_rules)
    if fix_count > 0:
        logger.warning(f"Applied {fix_count} auto-corrections to LLM-extracted rules")
    else:
        logger.info("All extracted rules match reference values ✓")

    # ------------------------------------------------------------------
    # Save fee_rules.json
    # ------------------------------------------------------------------
    _save_fee_rules(merged_rules, merged_hidden)

    # ------------------------------------------------------------------
    # Regenerate comparison tables
    # ------------------------------------------------------------------
    logger.info("Regenerating comparison tables…")
    _regenerate_comparison_tables()

    logger.info("=" * 70)
    logger.info(f"Done. {len(merged_rules)} rules, {len(merged_hidden)} hidden-cost entries saved.")
    logger.info("=" * 70)


if __name__ == "__main__":
    main()
