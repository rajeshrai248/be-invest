#!/usr/bin/env python3
"""
News Dashboard Demo - Shows how to use the automated news system
"""
import sys
import time
from pathlib import Path

# Add the project root to sys.path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root / "src"))

from be_invest.news import load_news, get_news_statistics
from be_invest.config_loader import load_brokers_from_yaml
from be_invest.sources.news_scrape import scrape_broker_news

def print_separator(title=""):
    print("=" * 60)
    if title:
        print(f" {title}")
        print("=" * 60)

def show_news_dashboard():
    """Display a news dashboard with current data."""
    print_separator("📰 BROKER NEWS DASHBOARD")

    # Load current news
    try:
        all_news = load_news()
        stats = get_news_statistics()

        print(f"📊 NEWS STATISTICS:")
        print(f"   Total News Items: {stats['total_news']}")
        print(f"   Brokers with News: {stats['brokers_with_news']}")
        print(f"   Date Range: {stats['oldest_news']} to {stats['newest_news']}")

        print(f"\n📈 NEWS BY BROKER:")
        for broker, count in stats['news_per_broker'].items():
            print(f"   📰 {broker}: {count} items")

        print(f"\n📄 RECENT NEWS (last 5):")
        for i, news in enumerate(all_news[:5], 1):
            print(f"{i}. [{news.broker}] {news.title}")
            print(f"   📅 {news.date or 'No date'}")
            print(f"   📝 {news.summary[:80]}...")
            print(f"   🔗 Source: {news.source}")
            print()

    except Exception as e:
        print(f"❌ Error loading news: {e}")

def run_automated_scraping():
    """Run automated news scraping and show results."""
    print_separator("🤖 AUTOMATED NEWS SCRAPING")

    try:
        # Load brokers
        brokers_yaml = project_root / "data" / "brokers.yaml"
        brokers = load_brokers_from_yaml(brokers_yaml)

        # Filter brokers with news sources
        brokers_with_news = [b for b in brokers if b.news_sources]

        print(f"🎯 Brokers configured for scraping: {len(brokers_with_news)}")

        # Show what will be scraped
        for broker in brokers_with_news:
            allowed_sources = [s for s in broker.news_sources if s.allowed_to_scrape]
            print(f"   📰 {broker.name}: {len(allowed_sources)} allowed source(s)")

        print(f"\n🔄 Starting automated scraping...")
        start_time = time.time()

        # Run the scraping
        scraped_news = scrape_broker_news(brokers_with_news, force=False)

        duration = time.time() - start_time
        print(f"\n✅ Scraping completed in {duration:.1f} seconds")
        print(f"📊 Results:")
        print(f"   New items scraped: {len(scraped_news)}")

        if scraped_news:
            # Group by broker
            broker_counts = {}
            for news in scraped_news:
                broker_counts[news.broker] = broker_counts.get(news.broker, 0) + 1

            print(f"   Breakdown by broker:")
            for broker, count in broker_counts.items():
                print(f"     📰 {broker}: {count} items")

            print(f"\n📄 Sample scraped news:")
            for news in scraped_news[:3]:
                print(f"   • [{news.broker}] {news.title}")
                print(f"     Summary: {news.summary[:60]}...")
        else:
            print(f"   ℹ️  No new news items found (may be due to deduplication)")

    except Exception as e:
        print(f"❌ Scraping error: {e}")
        import traceback
        traceback.print_exc()

def main():
    """Main dashboard demo."""
    print("🚀 BE-INVEST NEWS DASHBOARD DEMO")
    print("This demo shows the automated news scraping system in action")
    print()

    # Show current dashboard
    show_news_dashboard()

    # Ask if user wants to run scraping
    print("\n" + "=" * 60)
    response = input("Run automated news scraping now? [y/N]: ").lower().strip()

    if response in ['y', 'yes']:
        print()
        run_automated_scraping()

        # Show updated dashboard
        print()
        show_news_dashboard()
    else:
        print("✅ Demo completed. Use 'python test_news_scraping.py' to run scraping anytime.")

    print(f"\n💡 NEXT STEPS:")
    print(f"   1. Set up scheduled scraping (cron job every 6 hours)")
    print(f"   2. Integrate with your frontend using the REST API")
    print(f"   3. Update broker URLs in brokers.yaml if needed")
    print(f"   4. Monitor data/output/news.jsonl for new items")

if __name__ == "__main__":
    main()
