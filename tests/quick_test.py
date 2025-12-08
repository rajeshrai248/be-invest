#!/usr/bin/env python3
"""
Simple News System Test - Quick verification
"""
import sys
from pathlib import Path

# Add the project root to sys.path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root / "src"))

def test_news_system():
    """Test all aspects of the news system."""
    print("🧪 TESTING BE-INVEST NEWS SYSTEM")
    print("=" * 50)

    # Test 1: Check if we can load existing news
    print("1. Testing news data loading...")
    try:
        from be_invest.news import load_news, get_news_statistics
        news = load_news()
        stats = get_news_statistics()

        print(f"   ✅ Successfully loaded {len(news)} news items")
        print(f"   📊 Brokers with news: {stats['brokers_with_news']}")
        print(f"   📰 News breakdown:")
        for broker, count in stats['news_per_broker'].items():
            print(f"      • {broker}: {count} items")
    except Exception as e:
        print(f"   ❌ Failed to load news: {e}")
        return False

    # Test 2: Check broker configuration
    print(f"\n2. Testing broker configuration...")
    try:
        from be_invest.config_loader import load_brokers_from_yaml
        brokers = load_brokers_from_yaml(project_root / "data" / "brokers.yaml")
        brokers_with_news = [b for b in brokers if b.news_sources]

        print(f"   ✅ Loaded {len(brokers)} total brokers")
        print(f"   📰 {len(brokers_with_news)} brokers have news sources")

        for broker in brokers_with_news:
            allowed_sources = sum(1 for s in broker.news_sources if s.allowed_to_scrape)
            print(f"      • {broker.name}: {allowed_sources}/{len(broker.news_sources)} sources allowed")
    except Exception as e:
        print(f"   ❌ Failed to load brokers: {e}")
        return False

    # Test 3: Test news scraping (limited to avoid timeout)
    print(f"\n3. Testing news scraping (quick test)...")
    try:
        from be_invest.sources.news_scrape import scrape_broker_news

        # Test with just one broker to avoid timeouts
        keytrade = [b for b in brokers_with_news if b.name == "Keytrade Bank"]
        if keytrade:
            print(f"   🎯 Testing with Keytrade Bank only...")
            scraped = scrape_broker_news(keytrade[:1], force=False)
            print(f"   ✅ Scraping test completed: {len(scraped)} new items")
        else:
            print(f"   ⚠️ Keytrade Bank not found, skipping scrape test")
    except Exception as e:
        print(f"   ❌ Scraping test failed: {e}")
        # Don't return False here - scraping can fail due to network issues

    # Test 4: Check news file
    print(f"\n4. Testing news file storage...")
    try:
        news_file = project_root / "data" / "output" / "news.jsonl"
        if news_file.exists():
            with open(news_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            print(f"   ✅ News file exists with {len(lines)} entries")

            # Show sample entry
            if lines:
                import json
                sample = json.loads(lines[-1])
                print(f"   📄 Latest entry: {sample.get('broker')} - {sample.get('title', 'No title')}")
        else:
            print(f"   ⚠️ News file not found (will be created on first scrape)")
    except Exception as e:
        print(f"   ❌ News file test failed: {e}")

    print(f"\n" + "=" * 50)
    print(f"✅ NEWS SYSTEM TEST COMPLETE")
    print(f"\n💡 HOW TO USE:")
    print(f"   • Interactive demo:     python news_dashboard_demo.py")
    print(f"   • Full scraping test:   python test_news_scraping.py")
    print(f"   • Improved test:        python test_improved_scraping.py")
    print(f"   • Manual API test:      curl -X POST http://localhost:8000/news/scrape")
    print(f"   • Check news file:      cat data/output/news.jsonl")

    print(f"\n🔍 ABOUT SCRAPING ERRORS:")
    print(f"   • 404/403/timeout errors are NORMAL in web scraping")
    print(f"   • Financial websites often block automated access")
    print(f"   • The system handles these gracefully and continues")
    print(f"   • Even 1-2 successful sources is a win!")
    print(f"   • See NEWS_SCRAPING_ERRORS_EXPLAINED.md for details")

    return True

if __name__ == "__main__":
    test_news_system()
