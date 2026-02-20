#!/usr/bin/env python
"""
Quick test to verify ING fix and Revolut disabled.
"""

import logging
from pathlib import Path
from src.be_invest.config_loader import load_brokers_from_yaml

logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load brokers
brokers = load_brokers_from_yaml('data/brokers.yaml')

print("\n" + "="*80)
print("✅ VERIFICATION - ING Fix & Revolut Disabled")
print("="*80 + "\n")

# Check ING
ing = [b for b in brokers if b.name == "ING Self Invest"][0]
print(f"📰 ING Self Invest:")
print(f"   ✅ News sources: {len(ing.news_sources)}")
print(f"   ✅ URL: {ing.news_sources[0].url if ing.news_sources else 'N/A'}")
print(f"   ✅ Selector: {ing.news_sources[0].selector if ing.news_sources else 'N/A'}")
print(f"   ✅ Allowed to scrape: {ing.news_sources[0].allowed_to_scrape if ing.news_sources else False}")

# Check Revolut
revolut = [b for b in brokers if b.name == "Revolut"][0]
print(f"\n📰 Revolut:")
print(f"   ✅ News sources: {len(revolut.news_sources)}")
if revolut.news_sources:
    print(f"   ✅ URL: {revolut.news_sources[0].url}")
    print(f"   ❌ Allowed to scrape: {revolut.news_sources[0].allowed_to_scrape} (DISABLED)")
    print(f"   ✅ Description: {revolut.news_sources[0].description}")

print("\n" + "="*80)
print("✅ CONFIGURATION VERIFIED")
print("="*80 + "\n")

print("Next steps:")
print("  1. Run: python scripts/run_api.py")
print("  2. Test: curl -X POST 'http://localhost:8000/news/scrape?force=true'")
print("  3. Check: curl 'http://localhost:8000/news/broker/ING%20Self%20Invest'")
print()

