#!/usr/bin/env python
"""
Test script to scrape Revolut trading fees from webpage using LLM extraction.
"""

import logging
from pathlib import Path
from src.be_invest.config_loader import load_brokers_from_yaml
from src.be_invest.sources.scrape import scrape_fee_records

# Set up logging - disable debug logs
logging.basicConfig(
    level=logging.WARNING,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

print("\n" + "="*80)
print("🧪 Testing Revolut Cost & Charges Scraping")
print("="*80 + "\n")

# Load brokers
brokers = load_brokers_from_yaml('data/brokers.yaml')

# Find Revolut
revolut = [b for b in brokers if b.name == "Revolut"][0]

print(f"📋 Revolut Configuration:")
print(f"   Broker: {revolut.name}")
print(f"   Data sources: {len(revolut.data_sources)}")

if revolut.data_sources:
    for i, ds in enumerate(revolut.data_sources, 1):
        print(f"\n   Source {i}:")
        print(f"      Type: {ds.type}")
        print(f"      Description: {ds.description}")
        print(f"      URL: {ds.url}")
        print(f"      Allowed to scrape: {ds.allowed_to_scrape}")

print(f"\n\n🔍 Scraping Revolut Trading Fees using LLM:\n")

# Scrape with LLM enabled
try:
    records = scrape_fee_records(
        [revolut],
        force=False,
        timeout=15.0,
        pdf_text_dump_dir=Path("data/output/pdf_text"),
        use_llm=True,
        llm_model="gpt-4o"
    )
    
    if records:
        print(f"\n✅ SUCCESS! Extracted {len(records)} fee records for Revolut:\n")
        for i, record in enumerate(records, 1):
            print(f"   {i}. {record.broker} - {record.instrument_type}")
            print(f"      Channel: {record.order_channel}")
            print(f"      Base fee: {record.base_fee}")
            print(f"      Variable fee: {record.variable_fee}")
            print(f"      Currency: {record.currency}")
            print(f"      Notes: {record.notes[:100]}..." if record.notes else "")
            print()
    else:
        print(f"\n⚠️  No records extracted (may need LLM API key set)")
        print(f"   Make sure OPENAI_API_KEY is set in environment")
        print(f"   Set use_llm=True to enable LLM extraction")

except Exception as e:
    print(f"\n❌ Scraping failed: {e}")
    import traceback
    traceback.print_exc()

print("="*80)

