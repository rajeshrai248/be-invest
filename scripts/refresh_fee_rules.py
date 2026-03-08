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
    from be_invest.validation.fee_extraction import build_extraction_prompt
    return build_extraction_prompt(broker_name, broker_data)


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
    from be_invest.validation.fee_extraction import parse_llm_extraction_response

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
            parsed_rules, parsed_hidden = parse_llm_extraction_response(text)
        except Exception as exc:
            logger.error(f"  Step-2 failed for {broker_name}: {exc}")
            logger.error(f"  Raw response (first 200 chars): {text[:200]}")
            continue

        # Register parsed rules (with all-zero QA check)
        broker_rule_count = 0
        for rule in parsed_rules:
            key = (rule.broker.lower(), rule.instrument.lower(), rule.exchange.lower())

            # QA: skip all-zero rules
            all_zero = all(
                _compute_from_tiers(rule.tiers, amt, rule.handling_fee, rule.max_fee) == 0.0
                for amt in TRANSACTION_SIZES
            )
            if all_zero:
                logger.warning(
                    f"  QA: {rule.broker} {rule.instrument} has all-zero fees — skipping. Tiers: {rule.tiers}"
                )
                continue

            new_rules[key] = rule
            broker_rule_count += 1

        # Register hidden costs
        for hc_name, hc in parsed_hidden.items():
            new_hidden[hc_name] = hc

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

def _validate_and_fix_extracted_rules(
    rules: Dict[tuple, Any],
) -> Tuple[Dict[tuple, Any], int]:
    """Validate LLM-extracted rules against known-good reference values.

    Delegates to the shared module. Returns (fixed_rules, fix_count).
    """
    from be_invest.validation.fee_extraction import validate_and_fix_extracted_rules
    rules, fix_count, _warnings = validate_and_fix_extracted_rules(rules)
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
    # Step 3: Validate and auto-correct extracted rules (sanity checks + golden reference)
    # ------------------------------------------------------------------
    from be_invest.validation.fee_extraction import validate_and_fix_extraction
    logger.info("Validating extracted rules (sanity checks + golden reference)…")
    merged_rules, fix_count, validation_warnings = validate_and_fix_extraction(merged_rules, merged_hidden)
    for w in validation_warnings:
        logger.warning(f"  {w}")
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
