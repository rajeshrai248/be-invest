"""Generate comprehensive Cost and Charges summary for ALL brokers.

This script:
1. Loads all brokers from brokers.yaml
2. Extracts PDF text from data/output/pdf_text/*.txt
3. Uses GPT-4o to analyze and compare all brokers
4. Generates a detailed multi-broker summary report
"""
from __future__ import annotations

import argparse
import json
import sys
import os
from pathlib import Path
import logging
from typing import Optional
import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from be_invest.models import Broker, DataSource
from be_invest.config_loader import load_brokers_from_yaml

DEFAULT_DATA_DIR = Path("data")
DEFAULT_BROKERS_PATH = DEFAULT_DATA_DIR / "brokers.yaml"
DEFAULT_PDF_TEXT_DIR = DEFAULT_DATA_DIR / "output" / "pdf_text"
DEFAULT_OUTPUT_DIR = DEFAULT_DATA_DIR / "output"
DEFAULT_OUTPUT_FILE = DEFAULT_OUTPUT_DIR / "broker_summary.md"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def load_pdf_text_files(pdf_text_dir: Path) -> dict[str, str]:
    """Load all PDF text files from directory.

    Returns:
        Dict mapping filename (without .txt) to content
    """
    texts = {}
    if not pdf_text_dir.exists():
        logger.warning(f"PDF text directory not found: {pdf_text_dir}")
        return texts

    for text_file in pdf_text_dir.glob("*.txt"):
        content = text_file.read_text(encoding="utf-8")
        texts[text_file.stem] = content
        logger.info(f"📄 Loaded: {text_file.name} ({len(content)} chars)")

    return texts


def infer_broker_from_filename(filename: str) -> Optional[str]:
    """Infer broker name from PDF text filename."""
    filename_lower = filename.lower()

    # Map filename patterns to broker names
    if "bolero" in filename_lower or "101_tarieven" in filename_lower:
        return "Bolero"
    elif "keytrade" in filename_lower or "tarifs_en" in filename_lower:
        return "Keytrade Bank"
    elif "degiro" in filename_lower or "tarievenoverzicht" in filename_lower:
        return "Degiro Belgium"
    elif "ing" in filename_lower or "tarifroerende" in filename_lower:
        return "ING Self Invest"

    return None


def extract_fees_with_gpt4o(text: str, broker_name: str, api_key: str, model: str = "gpt-4o") -> list[dict]:
    """Extract fees using GPT-4o.

    Args:
        text: PDF text content
        broker_name: Name of the broker
        api_key: OpenAI API key
        model: OpenAI model to use

    Returns:
        List of fee records as dictionaries
    """
    try:
        from openai import OpenAI
    except ImportError:
        logger.error("❌ OpenAI SDK not installed. Install with: pip install openai")
        return []

    logger.info(f"🚀 Extracting fees for {broker_name} using {model}...")
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
{text[:8000]}

Extract ALL fee tiers and structures. Be thorough. Return valid JSON only."""

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

        # Clean response (remove markdown code blocks if present)
        if response_text.startswith("```"):
            response_text = response_text.split("```")[1]
            if response_text.startswith("json"):
                response_text = response_text[4:]
        response_text = response_text.strip()

        records = json.loads(response_text)

        if not isinstance(records, list):
            records = [records]

        logger.info(f"✨ Extracted {len(records)} fee records from {broker_name}")

        # Add broker info to each record
        for record in records:
            record["broker"] = broker_name
            record["currency"] = record.get("currency", "EUR")
            record["source"] = f"GPT-4o extraction from tariff document"
            record["notes"] = record.get("notes", f"Extracted from {broker_name} tariff")

        return records

    except json.JSONDecodeError as e:
        logger.error(f"❌ Failed to parse JSON response: {e}")
        return []
    except Exception as e:
        logger.error(f"❌ Extraction failed: {e}")
        return []


def generate_multi_broker_summary(brokers: list[Broker], fee_records: list[dict], api_key: str, model: str = "gpt-4o") -> str:
    """Generate comprehensive multi-broker summary using GPT-4o.

    Args:
        brokers: List of broker objects
        fee_records: List of extracted fee records
        api_key: OpenAI API key
        model: OpenAI model to use

    Returns:
        Generated summary markdown
    """
    try:
        from openai import OpenAI
    except ImportError:
        logger.error("OpenAI SDK not installed")
        return generate_fallback_multi_broker_summary(brokers, fee_records)

    # Format fee data by broker
    fee_summary = "Broker Fee Data:\n"
    for broker in brokers:
        broker_fees = [r for r in fee_records if r.get("broker") == broker.name]
        fee_summary += f"\n{broker.name}:\n"
        fee_summary += f"  Website: {broker.website}\n"
        fee_summary += f"  Instruments: {', '.join(broker.instruments)}\n"
        if broker_fees:
            fee_summary += "  Fee Structure:\n"
            for r in broker_fees:
                fee_summary += f"    - {r.get('instrument_type', 'N/A')} ({r.get('order_channel', 'N/A')}): "
                fee_summary += f"€{r.get('base_fee', 'N/A')} + {r.get('variable_fee', 'N/A')}\n"
        else:
            fee_summary += "  (No fee data extracted - consider manual entry)\n"

    logger.info("📊 Generating comprehensive summary with GPT-4o...")

    client = OpenAI(api_key=api_key)

    summary_prompt = f"""Based on this comprehensive broker fee data for Belgian brokers, generate a detailed professional analysis:

{fee_summary}

Create a professional markdown report with these sections:

1. **Executive Summary** - Overview of all brokers, number of brokers analyzed, key takeaways
2. **Broker Breakdown** - For EACH broker (separate subsection):
   - Name, website, supported instruments
   - Fee structure table (Instrument | Order Channel | Base Fee | Variable Fee)
   - Key characteristics and notes
3. **Cost Comparisons** - Compare brokers across:
   - Most expensive brokers for each instrument type
   - Least expensive brokers for each instrument type
   - Best value propositions
4. **Trading Scenarios** - Cost examples for typical trades:
   - Small trade (€1,000)
   - Medium trade (€10,000)
   - Large trade (€50,000)
   - Compare across at least 3 brokers
5. **Recommendations** - Best brokers for:
   - Small retail investors
   - Active traders
   - Long-term investors
   - Different instrument preferences
6. **Key Observations** - Important patterns, warnings, advantages/disadvantages

Format as professional markdown with clear headers, tables, and bullet points.
Include all brokers mentioned above even if fee data is incomplete."""

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": "You are an expert financial analyst creating detailed broker comparison reports for Belgian investors. Be thorough and professional."
                },
                {
                    "role": "user",
                    "content": summary_prompt
                }
            ],
            temperature=0.3,
            max_tokens=4000,
        )

        summary = response.choices[0].message.content.strip()
        logger.info("✅ Summary generated successfully")
        return summary

    except Exception as e:
        logger.error(f"❌ Summary generation failed: {e}")
        return generate_fallback_multi_broker_summary(brokers, fee_records)


def generate_fallback_multi_broker_summary(brokers: list[Broker], fee_records: list[dict]) -> str:
    """Generate fallback summary when API fails."""
    summary = "# Belgian Broker Cost and Charges Summary\n\n"
    summary += "## Executive Summary\n\n"
    summary += f"This report analyzes **{len(brokers)} Belgian investment brokers** and their fee structures.\n\n"

    # Group records by broker
    by_broker = {}
    for r in fee_records:
        broker = r.get("broker", "Unknown")
        if broker not in by_broker:
            by_broker[broker] = []
        by_broker[broker].append(r)

    summary += "## Broker Overview\n\n"
    for broker in brokers:
        summary += f"### {broker.name}\n"
        summary += f"- **Website:** {broker.website}\n"
        summary += f"- **Country:** {broker.country}\n"
        summary += f"- **Instruments:** {', '.join(broker.instruments)}\n"

        if broker.name in by_broker:
            summary += "- **Fee Structure:**\n"
            for r in by_broker[broker.name]:
                summary += f"  - {r.get('instrument_type', 'N/A')} ({r.get('order_channel', 'N/A')}): "
                base = f"€{r.get('base_fee', 'N/A')}" if r.get('base_fee') else "N/A"
                var = r.get('variable_fee', 'N/A')
                summary += f"{base} + {var}\n"
        else:
            summary += "- **Fee Structure:** Not yet extracted\n"

        summary += "\n"

    return summary


def main():
    parser = argparse.ArgumentParser(
        description="Generate comprehensive Cost & Charges summary for ALL brokers",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python generate_multi_broker_summary.py
  python generate_multi_broker_summary.py --output my_report.md
  python generate_multi_broker_summary.py --model gpt-4 --log-level DEBUG
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
        default=DEFAULT_OUTPUT_FILE,
        help="Output file for summary (default: data/output/broker_summary.md)",
    )
    parser.add_argument(
        "--model",
        type=str,
        default="gpt-4o",
        help="OpenAI model (default: gpt-4o)",
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
        help="Only extract fees as JSON, don't generate summary",
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

    logger.info("=" * 80)
    logger.info("🚀 MULTI-BROKER COST & CHARGES SUMMARY - COMPREHENSIVE GENERATION")
    logger.info("=" * 80)

    # Load brokers from YAML
    logger.info(f"📖 Loading brokers from {args.brokers}")
    try:
        brokers = load_brokers_from_yaml(args.brokers)
        logger.info(f"✅ Loaded {len(brokers)} brokers: {[b.name for b in brokers]}")
    except Exception as e:
        logger.error(f"❌ Failed to load brokers: {e}")
        return 1

    # Load PDF text files
    logger.info(f"\n📁 Loading PDF text files from {args.pdf_text_dir}")
    pdf_texts = load_pdf_text_files(args.pdf_text_dir)
    logger.info(f"✅ Found {len(pdf_texts)} PDF text file(s)")

    # Check API key
    api_key = os.getenv(args.api_key_env)
    if not api_key and not args.extract_only and not args.no_summary:
        logger.error(f"❌ {args.api_key_env} environment variable not set")
        logger.error("Set it with: $env:OPENAI_API_KEY = 'sk-...'")
        # Continue with fallback
        api_key = None

    # Extract fees from PDF text files
    logger.info("\n" + "=" * 80)
    logger.info("📊 EXTRACTING FEES FROM PDF TEXT")
    logger.info("=" * 80)

    all_records = []
    for filename, content in pdf_texts.items():
        inferred_broker = infer_broker_from_filename(filename)
        if inferred_broker:
            if api_key:
                records = extract_fees_with_gpt4o(content, inferred_broker, api_key, args.model)
                all_records.extend(records)
            else:
                logger.warning(f"⚠️  Skipping extraction for {filename} (no API key)")
        else:
            logger.warning(f"⚠️  Could not infer broker from filename: {filename}")

    logger.info(f"✅ Total records extracted: {len(all_records)}")

    # Save extracted fees as JSON
    json_output = args.output.parent / "extracted_fees.json"
    json_output.parent.mkdir(parents=True, exist_ok=True)
    with open(json_output, "w", encoding="utf-8") as f:
        json.dump(all_records, f, indent=2, ensure_ascii=False)
    logger.info(f"💾 Extracted fees saved: {json_output}")

    if args.extract_only or args.no_summary:
        logger.info("✅ Extraction complete (summary generation skipped)")
        return 0

    # Generate summary
    logger.info("\n" + "=" * 80)
    logger.info("📝 GENERATING COMPREHENSIVE SUMMARY")
    logger.info("=" * 80)

    if api_key:
        summary = generate_multi_broker_summary(brokers, all_records, api_key, args.model)
    else:
        logger.warning("⚠️  No API key available, generating fallback summary")
        summary = generate_fallback_multi_broker_summary(brokers, all_records)

    # Save summary
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(summary, encoding="utf-8")
    logger.info(f"✅ Summary saved: {args.output}")

    # Display summary
    logger.info("\n" + "=" * 80)
    logger.info("📋 GENERATED REPORT")
    logger.info("=" * 80 + "\n")
    print(summary)

    logger.info("\n" + "=" * 80)
    logger.info("✅ COMPLETE")
    logger.info("=" * 80)

    return 0


if __name__ == "__main__":
    sys.exit(main())

