#!/usr/bin/env python3
"""
Test script for automated news scraping functionality.
"""
import sys
import logging
from pathlib import Path

# Add the project root to sys.path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root / "src"))

from be_invest.config_loader import load_brokers_from_yaml
from be_invest.sources.news_scrape import scrape_broker_news

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def main():
    """Test the news scraping functionality."""
    print("🚀 Testing Automated News Scraping")
    print("=" * 50)

    # Load brokers configuration
    brokers_yaml = project_root / "data" / "brokers.yaml"
    if not brokers_yaml.exists():
        print(f"❌ Brokers file not found: {brokers_yaml}")
        return

    print(f"📖 Loading brokers from: {brokers_yaml}")
    brokers = load_brokers_from_yaml(brokers_yaml)

    # Filter brokers with news sources
    brokers_with_news = [b for b in brokers if b.news_sources]

    print(f"📊 Total brokers: {len(brokers)}")
    print(f"📰 Brokers with news sources: {len(brokers_with_news)}")

    for broker in brokers_with_news:
        print(f"  • {broker.name}: {len(broker.news_sources)} news source(s)")
        for source in broker.news_sources:
            status = "✅ ALLOWED" if source.allowed_to_scrape else "❌ BLOCKED"
            print(f"    - {source.description}: {status}")

    if not brokers_with_news:
        print("❌ No brokers have news sources configured!")
        return

    print("\n🔄 Starting news scraping...")

    # Test scraping (only allowed sources)
    try:
        scraped_news = scrape_broker_news(brokers_with_news, force=False)

        print(f"\n✅ Scraping completed!")
        print(f"📰 Total news items scraped: {len(scraped_news)}")

        # Show summary by broker
        broker_counts = {}
        for news in scraped_news:
            broker_counts[news.broker] = broker_counts.get(news.broker, 0) + 1

        print("\n📊 News by broker:")
        for broker, count in broker_counts.items():
            print(f"  • {broker}: {count} news items")

        # Show first few news items
        if scraped_news:
            print(f"\n📄 Sample news items (first 3):")
            for i, news in enumerate(scraped_news[:3]):
                print(f"{i+1}. {news.broker}: {news.title}")
                print(f"   Summary: {news.summary[:100]}...")
                print(f"   Source: {news.source}")
                print()

    except Exception as e:
        print(f"❌ Scraping failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
