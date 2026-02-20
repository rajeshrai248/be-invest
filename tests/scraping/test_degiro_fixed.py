#!/usr/bin/env python
"""
Test Degiro news scraping with the improved configuration.
"""

import sys
import logging
from pathlib import Path

# Setup path
sys.path.append('src')

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')

try:
    from be_invest.config_loader import load_brokers_from_yaml
    from be_invest.sources.news_scrape import NewsScraper

    print("\n" + "="*80)
    print("🧪 TESTING DEGIRO NEWS SCRAPING (FIXED)")
    print("="*80 + "\n")

    # Load configuration
    brokers = load_brokers_from_yaml(Path('data/brokers.yaml'))

    # Find Degiro
    degiro = None
    for broker in brokers:
        if "Degiro" in broker.name:
            degiro = broker
            break

    if not degiro:
        print("❌ Degiro broker not found!")
        exit(1)

    print(f"📰 Degiro Configuration:")
    print(f"   Broker: {degiro.name}")
    print(f"   News sources: {len(degiro.news_sources)}")

    for i, source in enumerate(degiro.news_sources, 1):
        print(f"\n   Source {i}:")
        print(f"      URL: {source.url}")
        print(f"      Selector: {source.selector}")
        print(f"      Allowed: {source.allowed_to_scrape}")
        print(f"      Notes: {source.notes}")

    if not any(source.allowed_to_scrape for source in degiro.news_sources):
        print("❌ All Degiro news sources are disabled!")
        exit(1)

    # Test scraping
    print(f"\n🔍 Testing News Scraping:")
    scraper = NewsScraper()

    try:
        results = scraper.scrape_all_broker_news([degiro], force=True)

        if "Degiro Belgium" in results and results["Degiro Belgium"]:
            print(f"✅ SUCCESS: Found {len(results['Degiro Belgium'])} news items")

            for i, item in enumerate(results["Degiro Belgium"][:3], 1):  # Show first 3
                print(f"\n   Article {i}:")
                print(f"     Title: {item.title}")
                print(f"     Summary: {item.summary[:100]}..." if len(item.summary) > 100 else f"     Summary: {item.summary}")
                print(f"     URL: {item.url}")
                print(f"     Date: {item.date}")

        else:
            print("❌ No news items found")
            if "Degiro Belgium" in results:
                print(f"   Degiro result: {results['Degiro Belgium']}")
            else:
                print(f"   Available results: {list(results.keys())}")

    except Exception as e:
        print(f"❌ Error during scraping: {e}")
        import traceback
        traceback.print_exc()

    print("\n" + "="*80)
    print("✅ DEGIRO TEST COMPLETE")
    print("="*80 + "\n")

except ImportError as e:
    print(f"❌ Import error: {e}")
except Exception as e:
    print(f"❌ Unexpected error: {e}")
    import traceback
    traceback.print_exc()
