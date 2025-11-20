"""
Integration test and runner for the broker summary generation system.

This script demonstrates the complete workflow of extracting broker fees
and generating detailed cost summaries using the latest AI models.
"""

import sys
from pathlib import Path
import json

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))


def main():
    """Run a complete demonstration of the broker summary system."""

    print("\n" + "="*80)
    print("BROKER COST & CHARGES SUMMARY SYSTEM - DEMONSTRATION")
    print("="*80 + "\n")

    # Show available scripts
    print("📋 AVAILABLE SCRIPTS:\n")

    print("1. FULL LLM PIPELINE (Recommended with valid OpenAI API key):")
    print("   python scripts/generate_summary.py --model gpt-4o\n")
    print("   Features:")
    print("   - Uses GPT-4o (latest OpenAI model)")
    print("   - Intelligent fee structure extraction")
    print("   - AI-generated detailed analysis and recommendations")
    print("   - Caches results to avoid re-billing\n")

    print("2. DEMO PIPELINE (Works without API key):")
    print("   python scripts/generate_summary_demo.py --skip-llm --no-api\n")
    print("   Features:")
    print("   - Pattern matching for fee extraction")
    print("   - Template-based analysis")
    print("   - No external API calls required")
    print("   - Good for testing and demonstration\n")

    print("3. HYBRID MODE (LLM extraction + Template summary):")
    print("   python scripts/generate_summary_demo.py --no-api\n")
    print("   Features:")
    print("   - Uses GPT-4o for fee extraction only")
    print("   - Template-based summary (no extra API cost)")
    print("   - Good compromise for cost/accuracy\n")

    print("4. EXTRACT ONLY (Get fees without summary):")
    print("   python scripts/generate_summary_demo.py --extract-only --skip-llm\n")
    print("   Features:")
    print("   - Fast extraction for integration workflows")
    print("   - Outputs JSON for further processing")
    print("   - No summary generation\n")

    # Check for extracted fees
    extracted_path = PROJECT_ROOT / "data" / "output" / "extracted_fees.json"
    if extracted_path.exists():
        print("✅ EXTRACTED FEES AVAILABLE:\n")
        try:
            with open(extracted_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            print(f"   Found {len(data)} fee records")

            # Group by broker
            by_broker = {}
            for record in data:
                broker = record.get('broker', 'Unknown')
                if broker not in by_broker:
                    by_broker[broker] = []
                by_broker[broker].append(record)

            for broker, records in sorted(by_broker.items()):
                print(f"\n   {broker}:")
                by_instrument = {}
                for r in records:
                    inst = r.get('instrument_type', 'Unknown')
                    by_instrument.setdefault(inst, []).append(r)

                for inst, inst_records in sorted(by_instrument.items()):
                    print(f"     - {inst}: {len(inst_records)} records")
        except Exception as e:
            print(f"   Error reading extracted fees: {e}")
    else:
        print("❌ NO EXTRACTED FEES FOUND\n")
        print("   Run extraction first:")
        print("   python scripts/generate_summary_demo.py --skip-llm --extract-only\n")

    # Check for summary
    summary_path = PROJECT_ROOT / "data" / "output" / "broker_summary.md"
    if summary_path.exists():
        print("✅ SUMMARY AVAILABLE:\n")
        print(f"   Location: {summary_path}\n")
        with open(summary_path, 'r', encoding='utf-8') as f:
            content = f.read()
        # Show first 500 chars
        preview = content[:500]
        print("   Preview:")
        for line in preview.split('\n')[:10]:
            print(f"   {line}")
        print("\n   ... [truncated, see full file for complete summary]")
    else:
        print("❌ NO SUMMARY GENERATED YET\n")
        print("   Generate a summary:")
        print("   python scripts/generate_summary_demo.py --skip-llm --no-api\n")

    print("\n" + "="*80)
    print("CONFIGURATION")
    print("="*80 + "\n")

    print("Broker definitions: data/brokers.yaml")
    print("PDF text files:    data/output/pdf_text/")
    print("Output directory:  data/output/\n")

    # List available text files
    pdf_text_dir = PROJECT_ROOT / "data" / "output" / "pdf_text"
    if pdf_text_dir.exists():
        txt_files = list(pdf_text_dir.glob("*.txt"))
        if txt_files:
            print(f"Available PDF text files ({len(txt_files)}):")
            for f in txt_files:
                size_kb = f.stat().st_size / 1024
                print(f"  - {f.name} ({size_kb:.1f} KB)")
        else:
            print("No PDF text files found in data/output/pdf_text/")
    print()

    print("="*80)
    print("QUICK START")
    print("="*80 + "\n")

    print("Option A: Fast Demo (no API needed, ~5 seconds):")
    print("  python scripts/generate_summary_demo.py --skip-llm --no-api\n")

    print("Option B: With OpenAI API (requires OPENAI_API_KEY set):")
    print("  python scripts/generate_summary.py --model gpt-4o\n")

    print("Option C: Just extract fees as JSON:")
    print("  python scripts/generate_summary_demo.py --skip-llm --extract-only\n")

    print("See BROKER_SUMMARY_USAGE.md for detailed documentation\n")

    print("="*80 + "\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())

