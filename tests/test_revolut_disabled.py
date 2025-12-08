#!/usr/bin/env python
"""
Test to verify Revolut news scraping is completely disabled and never scraped.
"""

import logging
from pathlib import Path
from src.be_invest.config_loader import load_brokers_from_yaml
from src.be_invest.sources.news_scrape import NewsScraper

# Set up logging to see what's happening
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

print("\n" + "="*80)
print("🧪 Testing Revolut Scraping Disabled")
print("="*80 + "\n")

# Load configuration
brokers = load_brokers_from_yaml('data/brokers.yaml')

# Find Revolut
revolut = [b for b in brokers if b.name == "Revolut"][0]

print(f"📰 Revolut Configuration:")
print(f"   Name: {revolut.name}")
print(f"   News sources: {len(revolut.news_sources)}")

if revolut.news_sources:
    for i, source in enumerate(revolut.news_sources, 1):
        print(f"\n   Source {i}:")
        print(f"      URL: {source.url}")
        print(f"      Allowed to scrape: {source.allowed_to_scrape}")
        print(f"      Description: {source.description}")
        
        if not source.allowed_to_scrape:
            print(f"      ✅ DISABLED - will not be scraped")
        else:
            print(f"      ❌ ENABLED - will be scraped")

# Test scraping
print(f"\n\n🔍 Testing Scraper Behavior:\n")

scraper = NewsScraper()

print("Test 1: Scraping with force=False (normal mode)")
results = scraper.scrape_all_broker_news([revolut], force=False)

if "Revolut" in results and len(results["Revolut"]) > 0:
    print(f"   ❌ FAILED: Found {len(results['Revolut'])} items (should be 0)")
    for item in results["Revolut"]:
        print(f"      - {item.title}")
else:
    print(f"   ✅ PASSED: No items scraped (correct)")

print("\nTest 2: Scraping with force=True (forced mode)")
results = scraper.scrape_all_broker_news([revolut], force=True)

if "Revolut" in results and len(results["Revolut"]) > 0:
    print(f"   ❌ FAILED: Found {len(results['Revolut'])} items (should be 0)")
    for item in results["Revolut"]:
        print(f"      - {item.title}")
else:
    print(f"   ✅ PASSED: No items scraped even with force=True (correct)")

print("\n" + "="*80)
print("✅ TEST COMPLETE")
print("="*80 + "\n")

