#!/usr/bin/env python
"""
Test the improved Revolut news scraping configuration.
"""

import sys
from pathlib import Path
import logging

# Setup path
sys.path.append('src')

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')

try:
    from be_invest.config_loader import load_brokers_from_yaml
    from be_invest.sources.news_scrape import NewsScraper

    print("\n" + "="*80)
    print("🧪 TESTING IMPROVED REVOLUT NEWS SCRAPING")
    print("="*80 + "\n")

    # Load configuration
    brokers = load_brokers_from_yaml(Path('data/brokers.yaml'))

    # Find Revolut
    revolut = None
    for broker in brokers:
        if broker.name == "Revolut":
            revolut = broker
            break

    if not revolut:
        print("❌ Revolut broker not found!")
        exit(1)

    print(f"📰 Revolut News Sources Configuration:")
    for i, source in enumerate(revolut.news_sources, 1):
        print(f"   {i}. {source.description}")
        print(f"      URL: {source.url}")
        print(f"      Selector: {source.selector}")
        print(f"      Allowed: {source.allowed_to_scrape}")
        if source.notes:
            print(f"      Notes: {source.notes}")
        print()

    # Test scraping
    print("🔍 Testing News Scraping:")
    scraper = NewsScraper()

    try:
        results = scraper.scrape_all_broker_news([revolut], force=True)

        if "Revolut" in results and results["Revolut"]:
            print(f"✅ SUCCESS: Found {len(results['Revolut'])} news items")

            for i, item in enumerate(results["Revolut"][:3], 1):  # Show first 3
                print(f"\n   Item {i}:")
                print(f"     Title: {item.title}")
                print(f"     Summary: {item.summary[:100]}..." if len(item.summary) > 100 else f"     Summary: {item.summary}")
                print(f"     URL: {item.url}")
                print(f"     Date: {item.date}")
                print(f"     Source: {item.source}")

                # Check for quality indicators
                quality_issues = []
                if not item.url or item.url == "null" or "mailto:" in str(item.url):
                    quality_issues.append("Invalid URL")
                if not item.title or len(item.title.strip()) < 10:
                    quality_issues.append("Poor title")
                if item.title in ["News & media", "Press enquiries"]:
                    quality_issues.append("Navigation element")

                if quality_issues:
                    print(f"     ⚠️  Quality issues: {', '.join(quality_issues)}")
                else:
                    print(f"     ✅ Good quality article")
        else:
            print("❌ No news items found")

    except Exception as e:
        print(f"❌ Error during scraping: {e}")
        import traceback
        traceback.print_exc()

    print("\n" + "="*80)
    print("✅ TEST COMPLETE")
    print("="*80 + "\n")

except ImportError as e:
    print(f"❌ Import error: {e}")
except Exception as e:
    print(f"❌ Unexpected error: {e}")
    import traceback
    traceback.print_exc()
