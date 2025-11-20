"""Generate exhaustive Cost and Charges summary for all brokers.

This script:
1. Loads all extracted PDF texts
2. Uses GPT-4o to generate detailed cost and charges analysis
3. Produces comprehensive markdown report with tables and comparisons
4. Saves structured JSON data for each broker
"""
from __future__ import annotations

import argparse
import json
import sys
import os
from pathlib import Path
import logging
from typing import Optional
from datetime import datetime

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from be_invest.config_loader import load_brokers_from_yaml

DEFAULT_DATA_DIR = Path("data")
DEFAULT_BROKERS_PATH = DEFAULT_DATA_DIR / "brokers.yaml"
DEFAULT_PDF_TEXT_DIR = DEFAULT_DATA_DIR / "output" / "pdf_text"
DEFAULT_OUTPUT_DIR = DEFAULT_DATA_DIR / "output"
DEFAULT_SUMMARY_FILE = DEFAULT_OUTPUT_DIR / "exhaustive_cost_charges_summary.md"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def load_pdf_texts(text_dir: Path) -> dict[str, dict]:
    """Load all extracted PDF text files.

    Returns:
        Dict mapping broker name to list of texts
    """
    texts = {}
    if not text_dir.exists():
        logger.warning(f"PDF text directory not found: {text_dir}")
        return texts

    for text_file in sorted(text_dir.glob("*.txt")):
        content = text_file.read_text(encoding="utf-8")
        # Infer broker from filename
        filename = text_file.stem.lower()

        if "bolero" in filename:
            broker = "Bolero"
        elif "keytrade" in filename:
            broker = "Keytrade Bank"
        elif "degiro" in filename:
            broker = "Degiro Belgium"
        elif "ing" in filename:
            broker = "ING Self Invest"
        else:
            broker = filename.title()

        if broker not in texts:
            texts[broker] = []

        texts[broker].append({
            "filename": text_file.name,
            "content": content,
            "size": len(content)
        })

        logger.info(f"📄 Loaded: {text_file.name} ({len(content):,} chars) → {broker}")

    return texts


def analyze_broker_costs_with_gpt4o(broker_name: str, texts: list[dict], api_key: str, model: str = "gpt-5") -> dict:
    """Analyze broker costs using GPT-5 (with fallback to gpt-4o).

    Args:
        broker_name: Name of the broker
        texts: List of text content dicts from PDFs
        api_key: OpenAI API key
        model: Model to use (default: gpt-5)

    Returns:
        Dictionary with analysis results
    """
    try:
        from openai import OpenAI
    except ImportError:
        logger.error("❌ OpenAI SDK not installed")
        return {"error": "OpenAI not installed"}

    if not texts:
        return {"error": "No text data provided"}

    # Combine texts
    combined_text = "\n\n".join(t["content"] for t in texts)
    logger.info(f"🔍 Analyzing {broker_name} ({len(combined_text):,} chars)...")

    client = OpenAI(api_key=api_key)

    analysis_prompt = f"""Extract ALL broker fees from {broker_name} tariffs with EXACT details.

CRITICAL: Capture ALL nuances including:
- Conditions and exceptions (e.g., "free for X type", "charged for Y type")
- Volume/balance thresholds
- Instrument-specific fees
- Account type variations
- Minimum amounts
- Timing details

Return ONLY valid JSON (no text):
{{
  "broker_name": "{broker_name}",
  "summary": "Complete fee overview",
  "fee_categories": [
    {{
      "category": "Trading - Equities",
      "description": "Detailed breakdown",
      "tiers": [
        {{"condition": "Up to €5,000", "fee": "€X+Y%", "notes": "exact conditions"}}
      ]
    }}
  ],
  "custody_charges": {{
    "general": "Annual fee or amount",
    "by_instrument": [
      {{"instrument": "Equities", "fee": "amount or free", "conditions": "when applicable"}}
    ],
    "exceptions": "Any free custody conditions"
  }},
  "deposit_withdrawal": [
    {{"method": "Bank transfer", "fee": "Free or amount", "timing": "1-2 days", "conditions": "any limits"}}
  ],
  "account_fees": {{
    "opening": "Free or amount",
    "closure": "Free or amount",
    "inactivity": "Conditions and amount",
    "minimum_balance": "Amount or None",
    "minimum_deposit": "Amount or None"
  }},
  "special_fees": [
    {{"name": "FX conversion", "rate": "0.5%", "conditions": "when charged", "exceptions": "when free"}}
  ],
  "supported_instruments": ["Equities", "ETFs", "Bonds"],
  "notes": "Important details, exceptions, conditions",
  "key_observations": [
    "Observation with specifics",
    "Conditions that affect fees"
  ]
}}

TARIFFS FROM {broker_name}:
{combined_text[:10000]}

IMPORTANT: Include ALL conditions, exceptions, and nuances. Don't generalize.
Output ONLY valid JSON."""

    try:
        # Try gpt-4o first (stable), then fallback to requested model if explicitly set to gpt-5
        if model == "gpt-5":
            models_to_try = ["gpt-4o", "gpt-5"]  # Try gpt-4o first, then gpt-5
        else:
            models_to_try = [model]  # Use specified model

        for current_model in models_to_try:
            try:
                logger.info(f"Analyzing with {current_model}...")

                response = client.chat.completions.create(
                    model=current_model,
                    messages=[
                        {
                            "role": "system",
                            "content": "You are a financial analyst. Return ONLY valid JSON, no explanations."
                        },
                        {
                            "role": "user",
                            "content": analysis_prompt
                        }
                    ],
                    temperature=1 if current_model == "gpt-5" else 0.1,
                    max_completion_tokens=4000,
                )

                response_text = response.choices[0].message.content.strip()

                if not response_text:
                    logger.warning(f"⚠️  Empty response from {current_model}")
                    continue

                # Clean response
                if response_text.startswith("```"):
                    response_text = response_text.split("```")[1]
                    if response_text.startswith("json"):
                        response_text = response_text[4:]
                response_text = response_text.strip()

                if not response_text:
                    logger.warning(f"⚠️  Response empty after cleaning")
                    continue

                analysis = json.loads(response_text)
                logger.info(f"✅ Analysis complete with {current_model}")
                return analysis

            except (json.JSONDecodeError, Exception) as e:
                logger.warning(f"⚠️  Failed with {current_model}: {e}")
                continue

        return {"error": "All models failed"}
    except Exception as e:
        logger.error(f"❌ Analysis failed for {broker_name}: {e}")
        return {"error": str(e)}


def generate_comprehensive_summary(brokers_yaml: Path, pdf_texts: dict[str, list], api_key: str, model: str = "gpt-5") -> tuple[str, dict]:
    """Generate comprehensive summary for all brokers.

    Returns:
        Tuple of (markdown_summary, json_data)
    """
    try:
        from openai import OpenAI
    except ImportError:
        logger.error("❌ OpenAI SDK not installed")
        return "", {}

    # Load broker info
    brokers = load_brokers_from_yaml(brokers_yaml)

    # Analyze each broker
    logger.info("\n" + "="*80)
    logger.info("📊 ANALYZING BROKER COSTS & CHARGES")
    logger.info("="*80)

    all_analyses = {}
    for broker in brokers:
        if broker.name in pdf_texts:
            analysis = analyze_broker_costs_with_gpt4o(
                broker.name,
                pdf_texts[broker.name],
                api_key,
                model
            )
            all_analyses[broker.name] = analysis
        else:
            logger.warning(f"⚠️  No PDF text found for {broker.name}")
            all_analyses[broker.name] = {"error": "No text data"}

    # Reorder analyses with ING Self Invest first
    ordered_analyses = {}
    if "ING Self Invest" in all_analyses:
        ordered_analyses["ING Self Invest"] = all_analyses.pop("ING Self Invest")
    # Add remaining brokers
    ordered_analyses.update(all_analyses)
    all_analyses = ordered_analyses

    # Generate comprehensive comparison report
    logger.info("\n" + "="*80)
    logger.info("📝 GENERATING COMPREHENSIVE SUMMARY")
    logger.info("="*80)

    client = OpenAI(api_key=api_key)

    # Format analyses for GPT
    analyses_summary = json.dumps(all_analyses, indent=2, ensure_ascii=False)

    # Log which brokers are included
    brokers_included = [b for b in all_analyses.keys() if "error" not in all_analyses[b]]
    logger.info(f"📊 Brokers with complete data: {', '.join(brokers_included)}")

    comparison_prompt = f"""You are an expert financial analyst creating a comprehensive broker comparison guide.

CRITICAL INSTRUCTIONS:
- Include ALL conditions and exceptions (e.g., "free for X but charged for Y")
- Preserve nuances (e.g., "ING doesn't charge custody for certain types")
- List instrument-specific details separately
- Show all thresholds and minimums
- Highlight when fees vary by condition

Based on these detailed cost analyses for Belgian brokers:

{analyses_summary}

Generate a professional, exhaustive markdown report with these sections:

# 1. Executive Summary
- Overview of all brokers
- Key differences and highlights
- When to choose each broker

# 2. Detailed Broker Analysis
For EACH broker (use H2 headers like ## Bolero, ## ING Self Invest):

## Trading Commissions
- By instrument type (Equities, ETFs, Bonds, Options, Funds)
- All tiers with conditions
- Volume thresholds if applicable

## Custody Charges
- General custody fees
- **IMPORTANT: Show exceptions and free conditions**
  - Example format: "Free for Equities, €X annually for Bonds"
- By instrument type if applicable

## Deposit/Withdrawal Fees
- All methods (bank transfer, card, etc.)
- Exact amounts or conditions
- Timing details

## Account Fees
- Opening, closure, inactivity fees
- Minimum balance requirements
- Minimum deposit requirements

## Special Fees
- Currency conversion fees
- International trading fees
- Other charges

## Supported Instruments & Order Channels
- Complete list
- Any limitations

## Advantages & Disadvantages
- Cost advantages
- Limitations
- Best suited for

# 3. Detailed Fee Comparison Tables
Create detailed tables showing:
- All fee types (trading, custody, deposits, etc.)
- ALL conditions and nuances
- Exact fees or "Free" or "N/A"
- Use footnotes for complex conditions

# 4. Cost Analysis by Instrument Type
For each instrument:
- Which broker is cheapest (with conditions)
- Cost differences
- Conditions that affect pricing

# 5. Trading Scenarios & Examples
Calculate exact costs for:
- Small trader (€1,000 quarterly, Equities only)
- Medium trader (€10,000 monthly, mixed instruments)
- Large trader (€50,000 weekly, Equities heavy)
- Long-term investor (annual costs)
- Include ALL applicable fees in calculations

# 6. Ranking & Recommendations
- Best for cost-conscious traders
- Best for active traders
- Best for long-term investors
- Best for specific instruments
- Best value overall

# 7. Important Considerations & Warnings
- Hidden fees or nuances
- Account minimums
- Conditions that may surprise users
- Differences between broker types
- **Explicitly call out conditions** (e.g., "ING has free custody for Equities but charged for Bonds")

**REQUIREMENTS:**
- Be exhaustive and detailed
- Include ALL conditions and exceptions
- Use exact language from source data
- Don't generalize or omit conditions
- Format with clear headers, bold, tables, and bullet points
- This is a comprehensive guide for investment decision-making"""

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": "You are a professional financial analyst creating detailed broker comparison guides. Be thorough, accurate, and well-organized. Include ALL brokers in the report."
                },
                {
                    "role": "user",
                    "content": comparison_prompt
                }
            ],
            temperature=1,
            max_completion_tokens=12000,
        )

        summary = response.choices[0].message.content.strip()
        logger.info("✅ Comprehensive summary generated")
        return summary, all_analyses

    except Exception as e:
        logger.error(f"❌ Summary generation failed: {e}")
        return "", all_analyses


def main():
    parser = argparse.ArgumentParser(
        description="Generate exhaustive Cost and Charges summary for all brokers",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python generate_exhaustive_summary.py
  python generate_exhaustive_summary.py --output my_summary.md
  python generate_exhaustive_summary.py --log-level DEBUG --model gpt-4
        """
    )

    parser.add_argument(
        "--brokers",
        type=Path,
        default=DEFAULT_BROKERS_PATH,
        help="Path to brokers.yaml (default: data/brokers.yaml)",
    )
    parser.add_argument(
        "--pdf-text-dir",
        type=Path,
        default=DEFAULT_PDF_TEXT_DIR,
        help="Directory with extracted PDF text files (default: data/output/pdf_text)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_SUMMARY_FILE,
        help="Output file for summary (default: data/output/exhaustive_cost_charges_summary.md)",
    )
    parser.add_argument(
        "--model",
        type=str,
        default="gpt-5",
        help="OpenAI model (default: gpt-5 - latest available)",
    )
    parser.add_argument(
        "--api-key-env",
        type=str,
        default="OPENAI_API_KEY",
        help="Environment variable with API key (default: OPENAI_API_KEY)",
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Logging level (default: INFO)",
    )
    parser.add_argument(
        "--json-only",
        action="store_true",
        help="Only save JSON analysis, not markdown summary",
    )

    args = parser.parse_args()

    # Set logging level
    logging.getLogger().setLevel(getattr(logging, args.log_level))

    logger.info("="*80)
    logger.info("🚀 EXHAUSTIVE COST & CHARGES SUMMARY GENERATOR")
    logger.info("="*80)
    logger.info(f"📖 Brokers: {args.brokers}")
    logger.info(f"📁 PDF texts: {args.pdf_text_dir}")
    logger.info(f"📄 Output: {args.output}")
    logger.info("="*80)

    # Load PDF texts
    logger.info("\n📂 Loading extracted PDF texts...")
    pdf_texts = load_pdf_texts(args.pdf_text_dir)
    if not pdf_texts:
        logger.error("❌ No PDF texts found. Run download_broker_pdfs.py first.")
        return 1

    logger.info(f"✅ Loaded texts for {len(pdf_texts)} broker(s)")

    # Check API key
    api_key = os.getenv(args.api_key_env)
    if not api_key:
        logger.error(f"❌ {args.api_key_env} environment variable not set")
        return 1

    # Generate summary
    summary, analyses = generate_comprehensive_summary(
        args.brokers,
        pdf_texts,
        api_key,
        args.model
    )

    # Save JSON analyses
    json_output = args.output.parent / "broker_cost_analyses.json"
    json_output.parent.mkdir(parents=True, exist_ok=True)
    with open(json_output, "w", encoding="utf-8") as f:
        json.dump(analyses, f, indent=2, ensure_ascii=False)
    logger.info(f"💾 JSON analyses saved: {json_output}")

    # Save markdown summary
    if summary and not args.json_only:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(summary, encoding="utf-8")
        logger.info(f"💾 Summary saved: {args.output}")

        # Print summary
        logger.info("\n" + "="*80)
        logger.info("📋 GENERATED SUMMARY")
        logger.info("="*80 + "\n")
        print(summary)

    logger.info("\n" + "="*80)
    logger.info("✅ COMPLETE")
    logger.info("="*80)

    return 0


if __name__ == "__main__":
    sys.exit(main())

