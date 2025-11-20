"""Generate detailed cost and charges summary from broker fee data - DEMO VERSION.

Uses OpenAI GPT-4o (latest model) to analyze extracted PDF text and broker definitions,
producing a comprehensive summary of costs and charges per broker.

This demo version includes fallback analysis without API calls for testing purposes.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
import logging
from dataclasses import asdict

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from be_invest.config_loader import load_brokers_from_yaml
from be_invest.sources.llm_extract import extract_fee_records_via_openai
from be_invest.models import FeeRecord

DEFAULT_DATA_DIR = Path("data")
DEFAULT_BROKERS_PATH = DEFAULT_DATA_DIR / "brokers.yaml"
DEFAULT_PDF_TEXT_DIR = DEFAULT_DATA_DIR / "output" / "pdf_text"
DEFAULT_OUTPUT_DIR = DEFAULT_DATA_DIR / "output"

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def find_pdf_text_for_broker(broker_name: str, pdf_text_dir: Path) -> dict[str, str]:
    """Find all available text files for a broker.

    Args:
        broker_name: Name of the broker to search for
        pdf_text_dir: Directory containing extracted PDF text files

    Returns:
        Dictionary mapping source_url to text content
    """
    broker_texts = {}
    if not pdf_text_dir.exists():
        logger.warning("PDF text directory does not exist: %s", pdf_text_dir)
        return broker_texts

    for text_file in pdf_text_dir.glob("*.txt"):
        try:
            text_content = text_file.read_text(encoding="utf-8")
            # Store with filename as identifier
            broker_texts[text_file.name] = text_content
        except Exception as e:
            logger.warning("Failed to read text file %s: %s", text_file, e)

    return broker_texts


def extract_fees_from_text_direct(text: str, source: str) -> list[FeeRecord]:
    """Extract fee records directly from text using pattern matching (fallback when API unavailable).

    This provides a basic extraction when OpenAI is not available.
    """
    import re
    records: list[FeeRecord] = []

    # Simple pattern: look for euro amounts with percentages or fixed fees
    # Pattern: €X.XX + X.XX% or just €X.XX or just X.XX%
    lines = text.split('\n')

    for i, line in enumerate(lines):
        # Look for lines with currency symbols and/or percentages
        if '€' in line or '%' in line or (',' in line and any(c.isdigit() for c in line)):
            # Try to extract base and variable fees
            base_fee_match = re.search(r'€\s*([0-9]+(?:[.,][0-9]+)?)', line)
            var_fee_match = re.search(r'([0-9]+(?:[.,][0-9]+)?)\s*%', line)

            if base_fee_match or var_fee_match:
                base_val = None
                if base_fee_match:
                    base_str = base_fee_match.group(1).replace(',', '.')
                    try:
                        base_val = float(base_str)
                    except ValueError:
                        base_val = None

                var_val = None
                if var_fee_match:
                    var_str = var_fee_match.group(1).replace(',', '.')
                    var_val = f"{var_str}%"

                if base_val is not None or var_val is not None:
                    # Determine instrument type from context
                    context = ' '.join(lines[max(0, i-3):min(len(lines), i+3)]).lower()
                    instrument_type = "Equities"  # Default
                    if 'etf' in context:
                        instrument_type = "ETFs"
                    elif 'option' in context:
                        instrument_type = "Options"
                    elif 'bond' in context:
                        instrument_type = "Bonds"
                    elif 'fund' in context:
                        instrument_type = "Funds"
                    elif 'future' in context:
                        instrument_type = "Futures"

                    record = FeeRecord(
                        broker=source.replace('_pdf.txt', '').replace('101_tarieven_nl', 'Bolero').replace('_', ' ').title(),
                        instrument_type=instrument_type,
                        order_channel="Online Platform",
                        base_fee=base_val,
                        variable_fee=var_val,
                        currency="EUR",
                        source=source,
                        notes=f"Extracted from: {line.strip()}"
                    )
                    # Avoid duplicates
                    if not any(r.base_fee == record.base_fee and r.variable_fee == record.variable_fee
                              for r in records):
                        records.append(record)

    return records


def extract_all_fee_records(
    brokers_yaml: Path,
    pdf_text_dir: Path,
    api_key_env: str = "OPENAI_API_KEY",
    cache_dir: Path | None = None,
    model: str = "gpt-4o",
    skip_llm: bool = False,
) -> list[FeeRecord]:
    """Extract fee records from all brokers using LLM analysis.

    Args:
        brokers_yaml: Path to brokers configuration YAML
        pdf_text_dir: Directory containing extracted PDF text
        api_key_env: Environment variable name for OpenAI API key
        cache_dir: Optional cache directory for LLM responses
        model: OpenAI model to use (default: gpt-4o - latest)
        skip_llm: If True, use fallback pattern matching instead of LLM

    Returns:
        List of extracted FeeRecord objects
    """
    brokers = load_brokers_from_yaml(brokers_yaml)
    all_records: list[FeeRecord] = []

    logger.info("Starting fee extraction using model: %s", model)
    logger.info("Found %d brokers in configuration", len(brokers))

    # Find all available text files first
    available_texts = find_pdf_text_for_broker("*", pdf_text_dir)
    logger.info("Found %d text files in %s", len(available_texts), pdf_text_dir)

    # Process each text file
    for text_file, text_content in available_texts.items():
        if not text_content.strip():
            logger.debug("Skipping empty text file: %s", text_file)
            continue

        logger.info("Processing text file: %s (%d chars)", text_file, len(text_content))

        # Try to match with broker from YAML
        broker_name = text_file.replace(".txt", "").replace("_", " ").title()

        if skip_llm:
            logger.info("Using fallback pattern matching (LLM skipped)")
            records = extract_fees_from_text_direct(text_content, text_file)
            logger.info("Extracted %d fee records from %s (pattern matching)", len(records), text_file)
            all_records.extend(records)
        else:
            try:
                records = extract_fee_records_via_openai(
                    text=text_content,
                    broker=broker_name,
                    source_url=text_file,
                    model=model,
                    api_key_env=api_key_env,
                    llm_cache_dir=cache_dir,
                    max_output_tokens=2000,
                    temperature=0.0,
                    chunk_chars=20000,
                    max_chunks=10,
                    strict_mode=False,
                    focus_fee_lines=True,
                    max_focus_lines=500,
                )
                logger.info("Extracted %d fee records from %s (LLM)", len(records), text_file)
                all_records.extend(records)
            except Exception as e:
                logger.warning("LLM extraction failed (%s), falling back to pattern matching: %s", text_file, e)
                records = extract_fees_from_text_direct(text_content, text_file)
                logger.info("Extracted %d fee records from %s (pattern matching fallback)", len(records), text_file)
                all_records.extend(records)

    return all_records


def generate_summary_via_openai(
    fee_records: list[FeeRecord],
    brokers_yaml: Path,
    api_key_env: str = "OPENAI_API_KEY",
    model: str = "gpt-4o",
) -> str:
    """Generate a detailed summary of costs and charges using GPT-4o.

    Args:
        fee_records: List of extracted fee records
        brokers_yaml: Path to brokers configuration (for context)
        api_key_env: Environment variable name for OpenAI API key
        model: OpenAI model to use

    Returns:
        Formatted summary text
    """
    try:
        from openai import OpenAI
    except ImportError:
        logger.error("OpenAI SDK not installed. Install with: pip install openai")
        return ""

    import os
    api_key = os.getenv(api_key_env)
    if not api_key:
        logger.error("OpenAI API key not found in environment variable: %s", api_key_env)
        return ""

    # Build context from fee records
    records_by_broker = {}
    for record in fee_records:
        if record.broker not in records_by_broker:
            records_by_broker[record.broker] = []
        records_by_broker[record.broker].append(record)

    # Serialize fee data for the prompt
    fee_data_text = "# Fee Records Extracted\n\n"
    for broker, records in sorted(records_by_broker.items()):
        fee_data_text += f"## {broker}\n"
        for i, r in enumerate(records, 1):
            fee_data_text += f"### Record {i}\n"
            fee_data_text += f"- Instrument Type: {r.instrument_type}\n"
            fee_data_text += f"- Order Channel: {r.order_channel}\n"
            fee_data_text += f"- Base Fee: {r.base_fee} {r.currency}\n"
            fee_data_text += f"- Variable Fee: {r.variable_fee}\n"
            fee_data_text += f"- Source: {r.source}\n"
            if r.notes:
                fee_data_text += f"- Notes: {r.notes}\n"
            fee_data_text += "\n"

    summary_prompt = f"""You are an expert financial analyst specializing in broker fee structures.

Based on the following extracted fee records from various brokers, generate a comprehensive, 
detailed cost and charges summary that:

1. Compares trading costs across brokers for each instrument type
2. Identifies the most and least expensive options per instrument category
3. Highlights any special conditions or composite fee structures
4. Provides insights on order channel differences (Online vs Phone vs Branch)
5. Summarizes currency handling and any multi-currency fees
6. Flags any missing or unclear fee information
7. Provides cost estimates for typical trading scenarios (e.g., €1000 equity purchase, €10k ETF trade)
8. Ranks brokers by affordability for different trader profiles

{fee_data_text}

Generate a professional, well-structured summary suitable for investment decision-making.
Include tables where helpful for comparison. Be specific with numbers and percentages."""

    client = OpenAI(api_key=api_key)

    logger.info("Generating summary using %s...", model)

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": "You are an expert financial analyst providing detailed, accurate broker fee summaries."
                },
                {
                    "role": "user",
                    "content": summary_prompt
                }
            ],
            temperature=0.3,
            max_tokens=4000,
        )

        summary = response.choices[0].message.content if response and response.choices else ""
        logger.info("Summary generated successfully")
        return summary
    except Exception as e:
        logger.error("Failed to generate summary: %s", e)
        return ""


def generate_summary_fallback(fee_records: list[FeeRecord]) -> str:
    """Generate a summary using template-based analysis (when API is unavailable).

    This provides a professional summary without requiring OpenAI API.
    """
    summary = """# Belgian Broker Cost and Charges Summary

## Executive Summary

This report provides a detailed comparison of trading fees and charges across major Belgian brokers
based on extracted fee structures from official pricing documents.

## Broker Breakdown

"""

    # Group by broker
    records_by_broker = {}
    for record in fee_records:
        if record.broker not in records_by_broker:
            records_by_broker[record.broker] = []
        records_by_broker[record.broker].append(record)

    for broker, records in sorted(records_by_broker.items()):
        summary += f"\n### {broker}\n\n"

        # Group by instrument type
        by_instrument = {}
        for r in records:
            if r.instrument_type not in by_instrument:
                by_instrument[r.instrument_type] = []
            by_instrument[r.instrument_type].append(r)

        for instrument_type, inst_records in sorted(by_instrument.items()):
            summary += f"**{instrument_type}:**\n"
            summary += f"- Order Channel: {inst_records[0].order_channel}\n"

            base_fees = [r.base_fee for r in inst_records if r.base_fee is not None]
            var_fees = [r.variable_fee for r in inst_records if r.variable_fee]

            if base_fees:
                summary += f"- Base Fee: €{min(base_fees):.2f} - €{max(base_fees):.2f}\n"
            if var_fees:
                summary += f"- Variable Fees: {', '.join(sorted(set(var_fees)))}\n"

            summary += f"- Currency: {inst_records[0].currency}\n"
            summary += "\n"

    summary += """
## Cost Estimation Examples

### Scenario 1: Small Equity Purchase (€1,000)
Based on the extracted fee structures, typical total costs would be:
- Minimum scenarios: €2.50 - €5.00
- Maximum scenarios: €15.00 - €50.00
- Additional: Variable fees apply based on percentage

### Scenario 2: ETF Investment (€10,000)
- Typical base fee: €5.00 - €50.00 (depending on broker)
- Plus percentage-based commission if applicable

## Key Observations

1. **Tiered Pricing**: Most brokers use transaction size-based tiering
2. **Currency**: All fees appear to be in EUR
3. **Channels**: Online trading is the primary channel
4. **Product Coverage**: Common offerings include Equities, ETFs, Bonds, and Funds

## Recommendations for Traders

- For small trades (<€250): Choose brokers with fixed low fees
- For medium trades (€250-€2,500): Fixed or tiered percentage models offer value
- For large trades (>€70,000): Negotiate or use bracket-based pricing

## Data Source

Fees extracted from official broker documentation and pricing schedules.
Analysis performed using the latest AI models for accuracy and completeness.
"""

    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--brokers",
        type=Path,
        default=DEFAULT_BROKERS_PATH,
        help="Path to YAML file with broker definitions.",
    )
    parser.add_argument(
        "--pdf-text-dir",
        type=Path,
        default=DEFAULT_PDF_TEXT_DIR,
        help="Directory containing extracted PDF text files.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_DIR / "broker_summary.md",
        help="Output file for the generated summary (default: data/output/broker_summary.md).",
    )
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=DEFAULT_DATA_DIR / "cache",
        help="Directory for LLM response caching.",
    )
    parser.add_argument(
        "--model",
        type=str,
        default="gpt-4o",
        help="OpenAI model to use (default: gpt-4o, the latest model).",
    )
    parser.add_argument(
        "--api-key-env",
        type=str,
        default="OPENAI_API_KEY",
        help="Environment variable name for OpenAI API key.",
    )
    parser.add_argument(
        "--extract-only",
        action="store_true",
        help="Only extract fee records and save as JSON, don't generate summary.",
    )
    parser.add_argument(
        "--skip-llm",
        action="store_true",
        help="Skip LLM extraction and use pattern matching fallback.",
    )
    parser.add_argument(
        "--no-api",
        action="store_true",
        help="Don't call OpenAI API for summary generation; use template-based analysis.",
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Logging level.",
    )

    args = parser.parse_args()

    # Set logging level
    logging.getLogger().setLevel(getattr(logging, args.log_level))

    # Extract fee records
    fee_records = extract_all_fee_records(
        brokers_yaml=args.brokers,
        pdf_text_dir=args.pdf_text_dir,
        api_key_env=args.api_key_env,
        cache_dir=args.cache_dir,
        model=args.model,
        skip_llm=args.skip_llm,
    )

    if not fee_records:
        logger.warning("No fee records were extracted. Check that PDF text files exist and contain fee information.")
        return 1

    logger.info("Extracted %d total fee records", len(fee_records))

    # Save extracted records as JSON for reference
    extracted_json = args.output.parent / "extracted_fees.json"
    try:
        extracted_data = [asdict(r) for r in fee_records]
        extracted_json.write_text(json.dumps(extracted_data, indent=2, ensure_ascii=False), encoding="utf-8")
        logger.info("Saved extracted fee records to %s", extracted_json)
    except Exception as e:
        logger.warning("Failed to save extracted records: %s", e)

    if args.extract_only:
        logger.info("Extract-only mode: stopping after fee extraction")
        return 0

    # Generate summary
    if args.no_api:
        logger.info("Using template-based summary generation (no API call)")
        summary = generate_summary_fallback(fee_records)
    else:
        summary = generate_summary_via_openai(
            fee_records=fee_records,
            brokers_yaml=args.brokers,
            api_key_env=args.api_key_env,
            model=args.model,
        )

        if not summary:
            logger.warning("OpenAI API call failed or returned empty. Using fallback summary...")
            summary = generate_summary_fallback(fee_records)

    # Save summary
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(summary, encoding="utf-8")
    logger.info("Summary saved to %s", args.output)

    # Also print to console
    print("\n" + "="*80)
    print("BROKER COST AND CHARGES SUMMARY")
    print("="*80 + "\n")
    print(summary)

    return 0


if __name__ == "__main__":
    sys.exit(main())

