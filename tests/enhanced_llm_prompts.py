"""Enhanced LLM extraction prompts for accurate broker fee data extraction.

This module provides improved prompts specifically designed to capture:
1. Handling fees that are often missed (like Degiro's 1€ fee)
2. Correct market-specific pricing (Brussels vs Paris/Amsterdam for Belfius)
3. Accurate tier-based pricing structures
4. Custody fee information
5. Fee structure type identification (flat, percentage, tiered, composite)
"""
from __future__ import annotations

import json
from typing import Dict, List, Any

# Enhanced system prompt with specific focus areas
ENHANCED_SYSTEM_PROMPT = (
    "You are a precision financial data extraction specialist. Your task is to extract "
    "ALL fee components with absolute accuracy. Pay special attention to:\n"
    "1. HANDLING FEES - Often overlooked but critical (e.g., €1 handling fee)\n"
    "2. MARKET-SPECIFIC PRICING - Different fees for different exchanges (Brussels vs Paris/Amsterdam)\n"
    "3. COMPOSITE FEES - Combinations of flat + percentage fees\n"
    "4. CUSTODY FEES - Annual portfolio management fees\n"
    "5. FEE TIERS - Different fees based on trade size\n"
    "Return ONLY valid JSON array. Never invent data. If unclear, use null."
)

# Keywords for more precise text focusing
ENHANCED_FEE_KEYWORDS = [
    # Multi-language fee terms
    "tarif", "tariff", "fee", "commission", "kosten", "charges", "pricing", "courtage",
    "brokerage", "transaction", "handel", "trading", "vergoeding", "provisie",

    # Specific fee types to catch
    "handling", "afhandeling", "verwerkings", "processing", "service",
    "custody", "bewaring", "depot", "portfolio", "portefeuille",
    "minimum", "maximum", "max", "min", "tier", "schijf", "schaal",

    # Market indicators
    "euronext", "brussels", "paris", "amsterdam", "bruxelles", "brussel",
    "NYSE", "NASDAQ", "XBRU", "XPAR", "XAMS",

    # Currency and percentage indicators
    "EUR", "€", "USD", "$", "%", "percent", "procent", "pct",

    # Instrument types
    "ETF", "equity", "equities", "aandeel", "aandelen", "stock", "stocks",
    "bond", "bonds", "obligatie", "obligaties", "fund", "funds", "fonds"
]

# Enhanced JSON schema with more validation
ENHANCED_JSON_SCHEMA = {
    "type": "array",
    "items": {
        "type": "object",
        "required": [
            "broker", "instrument_type", "order_channel",
            "base_fee", "variable_fee", "currency", "source"
        ],
        "properties": {
            "broker": {"type": "string"},
            "instrument_type": {
                "type": "string",
                "enum": ["Equities", "ETFs", "Options", "Bonds", "Funds", "Futures"]
            },
            "order_channel": {
                "type": "string",
                "enum": ["Online Platform", "Phone", "Branch", "Other"],
                "default": "Online Platform"
            },
            "base_fee": {
                "type": ["number", "null"],
                "description": "Fixed fee component in EUR (exclude currency symbols)"
            },
            "variable_fee": {
                "type": ["string", "null"],
                "description": "Percentage or tiered fee description (keep original format)"
            },
            "currency": {"type": "string", "default": "EUR"},
            "source": {"type": "string"},
            "notes": {
                "type": ["string", "null"],
                "description": "Free trade allowances, conditions, market specifics"
            },
            "page": {
                "type": ["integer", "null"],
                "description": "Page number if identifiable"
            },
            "evidence": {
                "type": ["string", "null"],
                "maxLength": 200,
                "description": "Verbatim snippet supporting this fee"
            },
            "market": {
                "type": ["string", "null"],
                "description": "Specific market/exchange if mentioned (e.g., Euronext Brussels)"
            },
            "fee_structure_type": {
                "type": ["string", "null"],
                "enum": ["flat", "percentage", "tiered", "composite"],
                "description": "Type of fee structure identified"
            },
            "handling_fee": {
                "type": ["number", "null"],
                "description": "Separate handling/processing fee if mentioned"
            },
            "custody_fee": {
                "type": ["string", "null"],
                "description": "Annual custody/depot fee if mentioned"
            },
            "minimum_fee": {
                "type": ["number", "null"],
                "description": "Minimum fee threshold"
            },
            "maximum_fee": {
                "type": ["number", "null"],
                "description": "Maximum fee cap"
            }
        }
    }
}


def create_enhanced_prompt(broker: str, source_url: str, text: str) -> List[Dict[str, str]]:
    """Create enhanced extraction prompt with specific focus on problem areas."""

    # Broker-specific instructions based on Rudolf's feedback
    broker_specific_instructions = {
        "Bolero": (
            "CRITICAL: Bolero charges €15 for trades, not €10. "
            "Look for the correct tier structure and verify the 5k trade cost is €15."
        ),
        "Degiro Belgium": (
            "CRITICAL: Degiro has a €1 handling fee that is often missed. "
            "Look for 'handling fee', 'verwerkingskosten', or similar terms. "
            "Total cost = commission + €1 handling fee."
        ),
        "Degiro": (
            "CRITICAL: Degiro has a €1 handling fee that is often missed. " 
            "Look for 'handling fee', 'verwerkingskosten', or similar terms. "
            "Total cost = commission + €1 handling fee."
        ),
        "Rebel": (
            "CRITICAL: Use Euronext Brussels pricing, NOT Paris/Amsterdam. "
            "Look for 'Brussels', 'Bruxelles', 'XBRU' market codes. "
            "For stocks up to €2.5k: €3. Verify market-specific pricing."
        ),
        "Revolut": (
            "Focus on trading fee information regardless of region headers. "
            "Extract commission structures, free order allowances, ADR fees, and currency exchange fees. "
            "The content may show 'United Kingdom' region selector but trading fees are relevant for Belgium. "
            "Look for plan-based fee structures (Standard, Plus, Premium, Metal, Ultra)."
        ),
        "ING Self Invest": (
            "ING typically has flat fee structures. Verify if custody fees apply."
        ),
        "Keytrade Bank": (
            "Keytrade typically uses percentage-based fees. Look for tiered structures."
        )
    }

    specific_instruction = broker_specific_instructions.get(broker, "")

    example_output = [
        {
            "broker": broker,
            "instrument_type": "Equities",
            "order_channel": "Online Platform",
            "base_fee": 2.0,
            "variable_fee": "0.026%",
            "currency": "EUR",
            "source": source_url,
            "notes": "Euronext Brussels pricing",
            "page": 1,
            "evidence": "Transaction fee: €2 + 0.026% for Euronext Brussels",
            "market": "Euronext Brussels",
            "fee_structure_type": "composite",
            "handling_fee": 1.0,
            "custody_fee": None,
            "minimum_fee": None,
            "maximum_fee": None
        }
    ]

    instruction = f"""
Extract brokerage fee records for broker '{broker}' from: {source_url}

{specific_instruction}

EXTRACTION REQUIREMENTS:
1. IDENTIFY ALL FEE COMPONENTS:
   - Base/fixed fees (strip currency symbols, use numbers only)
   - Variable/percentage fees (keep as strings with % symbol)
   - Handling/processing fees (often overlooked!)
   - Custody/depot fees (annual portfolio fees)
   - Minimum/maximum fee limits

2. MARKET SPECIFICITY:
   - Pay attention to exchange-specific pricing
   - Note if fees differ for Brussels vs Paris/Amsterdam
   - Include market information in 'market' field

3. FEE STRUCTURE CLASSIFICATION:
   - flat: Fixed amount regardless of trade size
   - percentage: Percentage of trade value only
   - tiered: Different rates for different trade sizes  
   - composite: Combination of fixed + percentage

4. HANDLING FEE DETECTION:
   - Look for terms: handling, processing, verwerkingskosten, afhandelingskosten
   - Often €1-€3 additional to main commission
   - Include in separate 'handling_fee' field

5. EVIDENCE CAPTURE:
   - Include verbatim text snippet supporting each fee
   - Maximum 200 characters
   - Prefer exact quotes from fee tables

VALIDATION CHECKLIST:
□ All fees accounted for (not just commission)?
□ Market-specific pricing identified?
□ Handling fees captured?
□ Fee structure type classified?
□ Evidence provided for verification?

Return ONLY a JSON array matching this structure:
{json.dumps(example_output, indent=2, ensure_ascii=False)}

PDF/DOCUMENT TEXT:
{text}
"""

    return [
        {"role": "system", "content": ENHANCED_SYSTEM_PROMPT},
        {"role": "user", "content": instruction}
    ]


def create_focused_text_for_extraction(text: str, max_lines: int = 500) -> str:
    """Create focused text that prioritizes fee-related content."""
    lines = text.strip().split('\n')

    # Score lines based on fee-related keywords
    scored_lines = []
    for i, line in enumerate(lines):
        score = 0
        line_lower = line.lower()

        # Primary fee indicators (high score)
        for keyword in ["tarif", "fee", "commission", "kosten", "charges", "pricing"]:
            if keyword in line_lower:
                score += 10

        # Secondary indicators
        for keyword in ["€", "%", "eur", "minimum", "maximum", "handling"]:
            if keyword in line_lower:
                score += 5

        # Market indicators
        for keyword in ["brussels", "paris", "amsterdam", "euronext"]:
            if keyword in line_lower:
                score += 3

        # Instrument indicators
        for keyword in ["etf", "equity", "stock", "bond", "aandeel"]:
            if keyword in line_lower:
                score += 2

        scored_lines.append((score, i, line))

    # Sort by score and take top lines
    scored_lines.sort(key=lambda x: x[0], reverse=True)
    top_lines = [line for _, _, line in scored_lines[:max_lines]]

    return '\n'.join(top_lines)


def validate_enhanced_extraction_result(result: List[Dict]) -> List[Dict]:
    """Validate and clean extraction results with enhanced checks."""
    validated = []

    for record in result:
        if not isinstance(record, dict):
            continue

        # Required field validation
        if not all(k in record for k in ["broker", "instrument_type", "base_fee", "variable_fee"]):
            continue

        # Enhanced validation
        cleaned_record = {
            "broker": str(record.get("broker", "")).strip(),
            "instrument_type": str(record.get("instrument_type", "")).strip(),
            "order_channel": str(record.get("order_channel", "Online Platform")).strip(),
            "base_fee": record.get("base_fee"),
            "variable_fee": record.get("variable_fee"),
            "currency": str(record.get("currency", "EUR")).strip(),
            "source": str(record.get("source", "")).strip(),
            "notes": record.get("notes"),
            "page": record.get("page"),
            "evidence": record.get("evidence"),
            "market": record.get("market"),
            "fee_structure_type": record.get("fee_structure_type"),
            "handling_fee": record.get("handling_fee"),
            "custody_fee": record.get("custody_fee"),
            "minimum_fee": record.get("minimum_fee"),
            "maximum_fee": record.get("maximum_fee")
        }

        # Combine handling fee with base fee if present
        if cleaned_record["handling_fee"] is not None:
            handling_amount = float(cleaned_record["handling_fee"])
            base_amount = float(cleaned_record["base_fee"] or 0)
            cleaned_record["base_fee"] = base_amount + handling_amount

            # Update notes to reflect handling fee inclusion
            notes = cleaned_record["notes"] or ""
            if notes:
                notes += f"; includes €{handling_amount} handling fee"
            else:
                notes = f"includes €{handling_amount} handling fee"
            cleaned_record["notes"] = notes

        # Instrument type validation
        allowed_instruments = {"Equities", "ETFs", "Options", "Bonds", "Funds", "Futures"}
        if cleaned_record["instrument_type"] not in allowed_instruments:
            continue

        # Order channel validation
        allowed_channels = {"Online Platform", "Phone", "Branch", "Other"}
        if cleaned_record["order_channel"] not in allowed_channels:
            cleaned_record["order_channel"] = "Online Platform"

        validated.append(cleaned_record)

    return validated


def create_broker_specific_validation_rules(broker: str) -> Dict[str, Any]:
    """Create validation rules specific to each broker based on Rudolf's feedback."""

    rules = {
        "Bolero": {
            "expected_etf_fee_5k": 15.0,  # Not 10€
            "expected_stock_fee_5k": 15.0,  # Not 10€
            "fee_structure": "flat",
            "validation_notes": "Verify €15 fee for 5k trades, not €10"
        },
        "Degiro Belgium": {
            "requires_handling_fee": True,
            "handling_fee_amount": 1.0,
            "fee_structure": "composite",
            "validation_notes": "Must include €1 handling fee"
        },
        "Degiro": {
            "requires_handling_fee": True,
            "handling_fee_amount": 1.0,
            "fee_structure": "composite",
            "validation_notes": "Must include €1 handling fee"
        },
        "Rebel": {
            "market_specific": "Euronext Brussels",
            "stock_fee_up_to_2500": 3.0,
            "fee_structure": "tiered",
            "validation_notes": "Use Brussels pricing, not Paris/Amsterdam"
        },
        "ING Self Invest": {
            "fee_structure": "flat",
            "has_custody_fee": True,
            "validation_notes": "Flat fee structure confirmed"
        },
        "Keytrade Bank": {
            "fee_structure": "percentage",
            "validation_notes": "Percentage-based fees confirmed"
        }
    }

    return rules.get(broker, {})


if __name__ == "__main__":
    # Test the enhanced prompt creation
    test_broker = "Degiro Belgium"
    test_url = "https://example.com/fees.pdf"
    test_text = """
    Transaction fees:
    Euronext Brussels: €2.00 + 0.026%
    Handling fee: €1.00 per transaction
    Custody fee: None
    """

    prompt = create_enhanced_prompt(test_broker, test_url, test_text)
    print("Enhanced prompt created successfully")
    print(f"System prompt length: {len(prompt[0]['content'])}")
    print(f"User prompt length: {len(prompt[1]['content'])}")
