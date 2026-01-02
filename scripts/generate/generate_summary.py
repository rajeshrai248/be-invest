"""Generate detailed cost and charges summary from broker fee data with REAL-TIME progress.

Uses OpenAI GPT-4o (latest model) to analyze extracted PDF text and broker definitions,
producing a comprehensive summary of costs and charges per broker.

IMPROVEMENTS:
- Real-time progress display
- Better error handling and logging
- Fallback to template when API fails
- Direct OpenAI API calls with better error messages
"""
from __future__ import annotations

import argparse
import json
import sys
import os
from pathlib import Path
import logging
from dataclasses import asdict

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from be_invest.models import FeeRecord

DEFAULT_DATA_DIR = Path("data")
DEFAULT_PDF_TEXT_DIR = DEFAULT_DATA_DIR / "output" / "pdf_text"
DEFAULT_OUTPUT_DIR = DEFAULT_DATA_DIR / "output"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def extract_fees_with_gpt4o(text: str, broker_name: str, api_key: str) -> list[dict]:
    """Extract fees directly using GPT-4o with real-time progress.

    Args:
        text: PDF text content
        broker_name: Name of the broker
        api_key: OpenAI API key

    Returns:
        List of fee records as dictionaries
    """
    try:
        from openai import OpenAI
    except ImportError:
        logger.error("❌ OpenAI SDK not installed. Install with: pip install openai")
        return []

    logger.info(f"🚀 Initializing GPT-4o extraction for {broker_name}...")
    client = OpenAI(api_key=api_key)

    extraction_prompt = f"""You are a financial expert extracting broker fee information from tariff documents.

Extract ALL fee records from this document about {broker_name}. For each distinct fee scenario, create one record with:
- instrument_type: (Equities, ETFs, Bonds, Funds, Options, Futures)
- order_channel: (Online Platform, Phone, Branch)
- base_fee: numeric fee in EUR (or null if percentage only)
- variable_fee: percentage like "0.35%" or composite like "€1 + 0.35%" (or null if fixed only)

Return ONLY valid JSON array, no markdown, no code blocks, no explanations.
Example format:
[
{{"instrument_type":"Equities","order_channel":"Online Platform","base_fee":2.5,"variable_fee":"0.35%"}},
{{"instrument_type":"ETFs","order_channel":"Online Platform","base_fee":5.0,"variable_fee":null}}
]

DOCUMENT:
{text}

Extract ALL fee tiers and structures. Be thorough. Return valid JSON only."""

    logger.info(f"📤 Sending to GPT-4o for analysis...")

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": "You are a financial analyst extracting broker fees. Return ONLY valid JSON arrays, no other text."
                },
                {
                    "role": "user",
                    "content": extraction_prompt
                }
            ],
            temperature=0.0,
            max_tokens=2000,
        )

        response_text = response.choices[0].message.content.strip()
        logger.info(f"✅ Received response from {model}")

        # Clean response (remove markdown code blocks if present)
        if response_text.startswith("```"):
            response_text = response_text.split("```")[1]
            if response_text.startswith("json"):
                response_text = response_text[4:]
        response_text = response_text.strip()

        logger.info(f"📋 Parsing extracted fees...")
        records = json.loads(response_text)

        if not isinstance(records, list):
            logger.warning(f"⚠️  Response was not a list, wrapping it")
            records = [records]

        logger.info(f"✨ Successfully extracted {len(records)} fee records from {broker_name}")

        # Add broker name and source to each record
        for record in records:
            record["broker"] = broker_name
            record["currency"] = "EUR"
            record["source"] = "GPT-4o extraction"
            record["notes"] = f"Extracted from {broker_name} tariff document"

        return records

    except json.JSONDecodeError as e:
        logger.error(f"❌ Failed to parse JSON response: {e}")
        logger.error(f"Response was: {response_text[:200]}...")
        return []
    except Exception as e:
        logger.error(f"❌ GPT-4o extraction failed: {e}")
        return []


def generate_summary_with_gpt4o(fee_records: list[dict], api_key: str) -> str:
    """Generate summary using GPT-4o with real-time progress.

    Args:
        fee_records: List of extracted fee records
        api_key: OpenAI API key

    Returns:
        Generated summary text
    """
    try:
        from openai import OpenAI
    except ImportError:
        return ""

    # Group records by broker
    by_broker = {}
    for r in fee_records:
        broker = r.get("broker", "Unknown")
        if broker not in by_broker:
            by_broker[broker] = []
        by_broker[broker].append(r)

    fee_summary = "Extracted Fee Data:\n"
    for broker, records in sorted(by_broker.items()):
        fee_summary += f"\n{broker}:\n"
        for i, r in enumerate(records, 1):
            fee_summary += f"  {i}. {r.get('instrument_type', 'N/A')} - "
            fee_summary += f"Base: €{r.get('base_fee', 'N/A')} + "
            fee_summary += f"Variable: {r.get('variable_fee', 'N/A')}\n"

    logger.info("📊 Generating professional summary with GPT-4o...")

    client = OpenAI(api_key=api_key)

    summary_prompt = f"""Based on this extracted broker fee data, generate a professional, detailed summary report:

{fee_summary}

Create a comprehensive analysis that includes:
1. Executive Summary - Overview of broker fees
2. Broker Breakdown - Fees organized by broker and instrument type
3. Cost Comparisons - Which brokers are most/least expensive
4. Trading Scenarios - Cost examples for common trades (€1000, €10000, €50000)
5. Recommendations - Best brokers for different trader profiles
6. Key Observations - Important patterns and notes

Format as professional markdown suitable for investment decision-making.
Include tables where helpful for comparison."""

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": "You are a professional financial analyst creating detailed broker fee comparison reports."
                },
                {
                    "role": "user",
                    "content": summary_prompt
                }
            ],
            temperature=0.3,
            max_tokens=3000,
        )

        summary = response.choices[0].message.content.strip()
        logger.info("✅ Summary generated successfully")
        return summary

    except Exception as e:
        logger.error(f"❌ Summary generation failed: {e}")
        return ""


def generate_fallback_summary(fee_records: list[dict]) -> str:
    """Generate fallback summary when API fails."""
    summary = "# Belgian Broker Cost and Charges Summary\n\n"
    summary += "## Executive Summary\n"
    summary += f"Fee data extracted from {len(fee_records)} records.\n\n"

    by_broker = {}
    for r in fee_records:
        broker = r.get("broker", "Unknown")
        if broker not in by_broker:
            by_broker[broker] = []
        by_broker[broker].append(r)

    for broker, records in sorted(by_broker.items()):
        summary += f"### {broker}\n"
        for r in records:
            summary += f"- **{r.get('instrument_type')}**: "
            summary += f"€{r.get('base_fee', 'N/A')} + {r.get('variable_fee', 'N/A')}\n"
        summary += "\n"

    return summary


def main():
    parser = argparse.ArgumentParser(
        description="Generate broker cost summaries using GPT-4o (real-time)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python generate_summary.py --model claude-sonnet-4-20250514
  python generate_summary.py --pdf-text-dir data/output/pdf_text
  python generate_summary.py --output my_report.md --log-level DEBUG
        """
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
        default=DEFAULT_OUTPUT_DIR / "broker_summary.md",
        help="Output file for summary (default: data/output/broker_summary.md)",
    )
    parser.add_argument(
        "--model",
        type=str,
        default="claude-sonnet-4-20250514",
        help="LLM model (default: claude-sonnet-4-20250514)",
    )
    parser.add_argument(
        "--api-key-env",
        type=str,
        default="OPENAI_API_KEY",
        help="Environment variable with API key (default: OPENAI_API_KEY)",
    )
    parser.add_argument(
        "--extract-only",
        action="store_true",
        help="Only extract fees, don't generate summary",
    )
    parser.add_argument(
        "--no-summary",
        action="store_true",
        help="Extract and save JSON but don't generate summary",
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Logging level (default: INFO)",
    )

    args = parser.parse_args()

    # Set logging level
    logging.getLogger().setLevel(getattr(logging, args.log_level))

    # Check API key
    api_key = os.getenv(args.api_key_env)
    if not api_key:
        logger.error(f"❌ {args.api_key_env} environment variable not set")
        logger.error("Set it with: $env:OPENAI_API_KEY = 'sk-...'")
        return 1

    logger.info("=" * 70)
    logger.info("🚀 BROKER COST & CHARGES SUMMARY - REAL-TIME GENERATION")
    logger.info("=" * 70)
    logger.info(f"Model: {args.model}")
    logger.info(f"Output: {args.output}")
    logger.info("=" * 70)

    # Find text files
    if not args.pdf_text_dir.exists():
        logger.error(f"❌ PDF text directory not found: {args.pdf_text_dir}")
        return 1

    text_files = list(args.pdf_text_dir.glob("*.txt"))
    if not text_files:
        logger.error(f"❌ No .txt files found in {args.pdf_text_dir}")
        return 1

    logger.info(f"📁 Found {len(text_files)} text file(s)")

    # Extract fees from all files
    all_records = []
    for text_file in text_files:
        logger.info(f"\n📄 Processing: {text_file.name}")
        text_content = text_file.read_text(encoding="utf-8")

        # Infer broker name from filename
        broker_name = text_file.stem.replace("_", " ").replace("pdf", "").title()
        if "101" in text_file.stem:
            broker_name = "Bolero"

        records = extract_fees_with_gpt4o(text_content, broker_name, api_key)
        all_records.extend(records)
        logger.info(f"✅ Total records so far: {len(all_records)}")

    if not all_records:
        logger.warning("⚠️  No records extracted")
        return 1

    # Save extracted fees
    json_output = args.output.parent / "extracted_fees.json"
    with open(json_output, "w", encoding="utf-8") as f:
        json.dump(all_records, f, indent=2, ensure_ascii=False)
    logger.info(f"💾 Extracted fees saved: {json_output}")

    if args.extract_only or args.no_summary:
        logger.info("✅ Extraction complete (summary skipped)")
        return 0

    # Generate summary
    logger.info("\n" + "=" * 70)
    logger.info("📊 GENERATING SUMMARY")
    logger.info("=" * 70)

    summary = generate_summary_with_gpt4o(all_records, api_key)
    if not summary:
        logger.warning("⚠️  Summary generation failed, using fallback template")
        summary = generate_fallback_summary(all_records)

    # Save summary
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(summary, encoding="utf-8")
    logger.info(f"✅ Summary saved: {args.output}")

    # Display summary
    logger.info("\n" + "=" * 70)
    logger.info("📋 GENERATED REPORT")
    logger.info("=" * 70)
    print(summary)

    logger.info("\n" + "=" * 70)
    logger.info("✅ COMPLETE")
    logger.info("=" * 70)

    return 0


if __name__ == "__main__":
    sys.exit(main())

