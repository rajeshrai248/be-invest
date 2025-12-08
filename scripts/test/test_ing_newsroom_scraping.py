#!/usr/bin/env python
"""
Test script to verify ING newsroom scraping fix.
"""

import logging
from pathlib import Path
from src.be_invest.config_loader import load_brokers_from_yaml
from src.be_invest.sources.news_scrape import NewsScraper

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

def test_ing_newsroom_scraping():
    """Test scraping ING newsroom specifically."""
    print("\n" + "="*80)
    print("🧪 Testing ING Newsroom Scraping Fix")
    print("="*80 + "\n")

    # Load brokers config
    brokers_file = Path("data/brokers.yaml")
    if not brokers_file.exists():
        print(f"❌ {brokers_file} not found")
        return False

    brokers = load_brokers_from_yaml(brokers_file)
    
    # Find ING Self Invest
    ing_broker = None
    for broker in brokers:
        if broker.name == "ING Self Invest":
            ing_broker = broker
            break
    
    if not ing_broker:
        print("❌ ING Self Invest broker not found in config")
        return False
    
    if not ing_broker.news_sources:
        print("❌ No news sources configured for ING Self Invest")
        return False
    
    print(f"✅ Found ING Self Invest broker")
    print(f"✅ News sources configured: {len(ing_broker.news_sources)}")
    
    # Create scraper
    scraper = NewsScraper()
    
    # Test scraping
    print(f"\n📢 Testing ING Self Invest scraping...\n")
    results = scraper.scrape_all_broker_news([ing_broker], force=True)
    
    if "ING Self Invest" in results:
        news_items = results["ING Self Invest"]
        print(f"\n✅ SUCCESS!")
        print(f"   Found {len(news_items)} news items")
        
        if news_items:
            print(f"\n📰 Sample news items:")
            for i, item in enumerate(news_items[:3], 1):
                print(f"\n   {i}. Title: {item.title[:60]}...")
                print(f"      Summary: {item.summary[:80]}...")
                print(f"      URL: {item.url if item.url else 'N/A'}")
        
        return True
    else:
        print(f"\n❌ No news items found for ING Self Invest")
        print(f"   Results keys: {list(results.keys())}")
        return False

if __name__ == "__main__":
    success = test_ing_newsroom_scraping()
    
    print("\n" + "="*80)
    if success:
        print("✅ ING NEWSROOM SCRAPING TEST PASSED")
    else:
        print("❌ ING NEWSROOM SCRAPING TEST FAILED")
    print("="*80 + "\n")

