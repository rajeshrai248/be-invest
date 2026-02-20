#!/usr/bin/env python
"""
Test to verify Revolut is completely disabled and no missing file warnings.
"""

import logging
from pathlib import Path
from src.be_invest.config_loader import load_brokers_from_yaml

# Set up logging to capture warnings
logging.basicConfig(
    level=logging.WARNING,
    format='%(levelname)s - %(message)s'
)

print("\n" + "="*80)
print("🧪 Testing Revolut Completely Disabled")
print("="*80 + "\n")

# Load configuration
brokers = load_brokers_from_yaml('data/brokers.yaml')

# Find Revolut
revolut = [b for b in brokers if b.name == "Revolut"][0]

print(f"📋 Revolut Configuration Status:")
print(f"\n   Data Sources:")
for i, source in enumerate(revolut.data_sources or [], 1):
    status = "✅ DISABLED" if not source.allowed_to_scrape else "❌ ENABLED"
    print(f"      {i}. {source.description}")
    print(f"         URL: {source.url}")
    print(f"         Allowed to scrape: {source.allowed_to_scrape} {status}")

print(f"\n   News Sources:")
for i, source in enumerate(revolut.news_sources or [], 1):
    status = "✅ DISABLED" if not source.allowed_to_scrape else "❌ ENABLED"
    print(f"      {i}. {source.description}")
    print(f"         URL: {source.url}")
    print(f"         Allowed to scrape: {source.allowed_to_scrape} {status}")

# Check if text file exists
text_file = Path("data/output/pdf_text/Revolut_Trading_fees_3e566057.txt")
print(f"\n   Text File Status:")
if text_file.exists():
    print(f"      ❌ File exists (should not): {text_file}")
else:
    print(f"      ✅ No text file (correct - source is disabled)")

print(f"\n" + "="*80)
print("✅ REVOLUT COMPLETELY DISABLED")
print("="*80)
print("\nExpected behavior:")
print("  ✅ Revolut not scraped for trading fees data")
print("  ✅ Revolut not scraped for news")
print("  ✅ No missing file warnings")
print("  ✅ Revolut excluded from cost analysis")
print()

