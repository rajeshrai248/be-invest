#!/usr/bin/env python
"""
Test Revolut scraping - always uses Playwright to bypass 403 errors.
"""

import logging
from pathlib import Path
from src.be_invest.config_loader import load_brokers_from_yaml
from src.be_invest.sources.scrape import scrape_fee_records

# Set up logging - only warnings
logging.basicConfig(
    level=logging.WARNING,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

print("\n" + "="*80)
print("🧪 Testing Revolut Scraping (Always Uses Playwright)")
print("="*80 + "\n")

# Load brokers
brokers = load_brokers_from_yaml('data/brokers.yaml')
revolut = [b for b in brokers if b.name == "Revolut"][0]

print(f"📋 Revolut Configuration:")
print(f"   URL: {revolut.data_sources[0].url}")
print(f"   Allowed to scrape: {revolut.data_sources[0].allowed_to_scrape}")
print(f"   Strategy: Always use Playwright (bypasses bot detection)")

print(f"\n🔄 Scraping Revolut with Playwright...\n")

try:
    records = scrape_fee_records(
        [revolut],
        force=False,
        timeout=30.0,
        pdf_text_dump_dir=Path("data/output/pdf_text"),
        use_llm=True,
        llm_model="gpt-4o"
    )
    
    if records:
        print(f"\n✅ SUCCESS! Scraped {len(records)} fee records from Revolut:\n")
        for i, record in enumerate(records[:5], 1):
            print(f"   {i}. {record.instrument_type}")
            print(f"      Channel: {record.order_channel}")
            print(f"      Base: {record.base_fee}, Variable: {record.variable_fee}")
            print(f"      Currency: {record.currency}")
            print()
        
        if len(records) > 5:
            print(f"   ... and {len(records) - 5} more records")
    else:
        print(f"\n⚠️  No records extracted")
        print(f"   Check that OPENAI_API_KEY is set")

except Exception as e:
    print(f"\n❌ Scraping failed: {e}")

print("\n" + "="*80)
print("✅ TEST COMPLETE")
print("="*80 + "\n")

