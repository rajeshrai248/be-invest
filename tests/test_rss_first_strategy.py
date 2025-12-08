#!/usr/bin/env python3
"""
Test RSS-First News Scraping Strategy
"""
import sys
import time
from pathlib import Path

# Add the project root to sys.path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root / "src"))

def test_rss_first_strategy():
    """Test the RSS-first news scraping strategy."""
    print("🚀 TESTING RSS-FIRST NEWS SCRAPING STRATEGY")
    print("=" * 60)

    try:
        from be_invest.config_loader import load_brokers_from_yaml
        from be_invest.sources.news_scrape import scrape_broker_news
        from be_invest.news import get_news_statistics

        # Load configuration
        brokers_yaml = project_root / "data" / "brokers.yaml"
        brokers = load_brokers_from_yaml(brokers_yaml)
        brokers_with_news = [b for b in brokers if b.news_sources]

        print(f"📊 CONFIGURATION ANALYSIS:")
        print(f"   Total brokers: {len(brokers)}")
        print(f"   Brokers with news sources: {len(brokers_with_news)}")

        # Analyze news source types
        total_rss = total_web = total_api = 0
        for broker in brokers_with_news:
            rss = sum(1 for s in broker.news_sources if s.type == "rss")
            web = sum(1 for s in broker.news_sources if s.type == "webpage")
            api = sum(1 for s in broker.news_sources if s.type == "json_api")

            total_rss += rss
            total_web += web
            total_api += api

            print(f"   • {broker.name}: {rss} RSS, {web} web, {api} API")

        print(f"\n📈 SOURCE TYPE SUMMARY:")
        print(f"   📡 RSS feeds: {total_rss}")
        print(f"   🌐 Web pages: {total_web}")
        print(f"   🔗 JSON APIs: {total_api}")

        # Get baseline stats
        baseline_stats = get_news_statistics()
        print(f"\n📊 CURRENT NEWS DATA:")
        print(f"   Total items: {baseline_stats['total_news']}")
        print(f"   Brokers with news: {baseline_stats['brokers_with_news']}")

        print(f"\n🎯 TESTING RSS-FIRST STRATEGY...")
        print(f"   Strategy: RSS feeds first, web scraping fallback")
        print(f"   Expected: Better reliability, faster execution")

        start_time = time.time()

        # Test RSS-first strategy
        scraped_news = scrape_broker_news(brokers_with_news, force=False, rss_first=True)

        duration = time.time() - start_time

        # Get updated stats
        updated_stats = get_news_statistics()
        new_items = updated_stats['total_news'] - baseline_stats['total_news']

        print(f"\n📊 RSS-FIRST RESULTS:")
        print(f"   ⏱️  Duration: {duration:.1f} seconds")
        print(f"   📰 New items found: {new_items}")
        print(f"   📈 Total items now: {updated_stats['total_news']}")

        if scraped_news:
            # Analyze by broker
            broker_counts = {}
            rss_items = web_items = 0

            for news in scraped_news:
                broker_counts[news.broker] = broker_counts.get(news.broker, 0) + 1
                if "RSS:" in news.source:
                    rss_items += 1
                elif "Website:" in news.source:
                    web_items += 1

            print(f"\n🎯 SUCCESS BY BROKER:")
            for broker, count in broker_counts.items():
                print(f"     📰 {broker}: {count} items")

            print(f"\n📡 SOURCE TYPE SUCCESS:")
            print(f"   RSS feeds: {rss_items} items")
            print(f"   Web scraping: {web_items} items")
            print(f"   RSS success rate: {(rss_items/(rss_items+web_items)*100):.1f}%" if (rss_items+web_items) > 0 else "   No new items found")

            print(f"\n📄 SAMPLE NEW ITEMS:")
            for i, news in enumerate(scraped_news[:3]):
                source_type = "📡 RSS" if "RSS:" in news.source else "🌐 Web"
                print(f"{i+1}. {source_type} [{news.broker}] {news.title}")
                print(f"   📝 {news.summary[:60]}...")
                print(f"   📅 {news.date or 'No date'}")

        else:
            print(f"   ℹ️  No new items (deduplication working or sources unavailable)")

        # Compare with old strategy
        print(f"\n🔄 COMPARING WITH WEB-ONLY STRATEGY...")
        start_time = time.time()

        # Test traditional web-only strategy for comparison
        web_only_news = scrape_broker_news(brokers_with_news[:2], force=False, rss_first=False)

        web_duration = time.time() - start_time

        print(f"   ⏱️  Web-only duration (2 brokers): {web_duration:.1f} seconds")
        print(f"   📰 Web-only new items: {len(web_only_news)}")

        print(f"\n✅ STRATEGY COMPARISON:")
        print(f"   📡 RSS-first: {len(scraped_news)} items in {duration:.1f}s")
        print(f"   🌐 Web-only: {len(web_only_news)} items in {web_duration:.1f}s")

        if duration > 0 and web_duration > 0:
            efficiency = web_duration / duration if duration > 0 else 1
            print(f"   ⚡ RSS-first is {efficiency:.1f}x faster per broker")

    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()

def demonstrate_rss_benefits():
    """Explain the benefits of RSS-first strategy."""
    print(f"\n" + "=" * 60)
    print(f"📚 WHY RSS-FIRST STRATEGY IS BETTER")
    print(f"=" * 60)

    benefits = {
        "🚀 Speed": [
            "RSS feeds are typically 2-5x faster to parse than web pages",
            "No need to download and parse HTML, CSS, JavaScript",
            "Structured data format reduces processing time"
        ],
        "🎯 Reliability": [
            "RSS feeds are specifically designed for automated consumption",
            "Less likely to be blocked by anti-bot protection",
            "More stable URLs and consistent format"
        ],
        "📊 Data Quality": [
            "RSS provides structured metadata (title, date, summary, URL)",
            "Standardized format reduces parsing errors",
            "Usually contains the most important/recent news"
        ],
        "⚡ Efficiency": [
            "Falls back to web scraping only when needed",
            "Reduces server load on broker websites",
            "Fewer network requests overall"
        ]
    }

    for category, points in benefits.items():
        print(f"\n{category}:")
        for point in points:
            print(f"   • {point}")

    print(f"\n💡 YOUR UPDATED CONFIGURATION:")
    print(f"   • Bolero: RSS + webpage fallback")
    print(f"   • Keytrade Bank: RSS + webpage fallback")
    print(f"   • Other brokers: Webpage scraping (no RSS found)")
    print(f"   • Strategy: Try RSS first, fallback to web if RSS fails")

if __name__ == "__main__":
    test_rss_first_strategy()
    demonstrate_rss_benefits()
