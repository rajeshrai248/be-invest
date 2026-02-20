#!/usr/bin/env python3
"""
Improved News Scraping Test - Better error handling and feedback
"""
import sys
import time
from pathlib import Path

# Add the project root to sys.path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root / "src"))

def test_improved_scraping():
    """Test the improved news scraping with better error handling."""
    print("🔧 TESTING IMPROVED NEWS SCRAPING")
    print("=" * 60)

    # Load brokers configuration
    try:
        from be_invest.config_loader import load_brokers_from_yaml
        from be_invest.sources.news_scrape import scrape_broker_news

        brokers_yaml = project_root / "data" / "brokers.yaml"
        brokers = load_brokers_from_yaml(brokers_yaml)
        brokers_with_news = [b for b in brokers if b.news_sources]

        print(f"📊 CONFIGURATION:")
        print(f"   Total brokers: {len(brokers)}")
        print(f"   Brokers with news sources: {len(brokers_with_news)}")

        print(f"\n📰 NEWS SOURCES CONFIGURED:")
        for broker in brokers_with_news:
            allowed = sum(1 for s in broker.news_sources if s.allowed_to_scrape)
            total = len(broker.news_sources)
            print(f"   • {broker.name}: {allowed}/{total} sources allowed")
            for source in broker.news_sources:
                status = "✅" if source.allowed_to_scrape else "❌"
                print(f"     - {status} {source.description}: {source.url}")

        print(f"\n🚀 STARTING IMPROVED SCRAPING...")
        print(f"   (With better error handling and shorter timeouts)")

        start_time = time.time()

        # Test with just one broker first
        print(f"\n🎯 TESTING WITH SINGLE BROKER (Keytrade Bank)...")
        keytrade = [b for b in brokers_with_news if b.name == "Keytrade Bank"]
        if keytrade:
            single_result = scrape_broker_news(keytrade, force=False)
            print(f"   Single broker test: {len(single_result)} items")

        # Now test with all brokers
        print(f"\n🌐 TESTING WITH ALL BROKERS...")
        results = scrape_broker_news(brokers_with_news, force=False)

        duration = time.time() - start_time

        print(f"\n📊 RESULTS:")
        print(f"   Duration: {duration:.1f} seconds")
        print(f"   Total news items: {len(results)}")

        if results:
            broker_counts = {}
            for news in results:
                broker_counts[news.broker] = broker_counts.get(news.broker, 0) + 1

            print(f"   Success by broker:")
            for broker, count in broker_counts.items():
                print(f"     📰 {broker}: {count} items")

            print(f"\n📄 SAMPLE RESULTS:")
            for i, news in enumerate(results[:3]):
                print(f"{i+1}. [{news.broker}] {news.title}")
                print(f"   Summary: {news.summary[:60]}...")
                print(f"   Source: {news.source}")
        else:
            print(f"   ℹ️ No new items (may be due to deduplication or site issues)")

    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()

def show_error_explanations():
    """Explain what the common errors mean and how to handle them."""
    print(f"\n" + "=" * 60)
    print(f"📚 UNDERSTANDING SCRAPING ERRORS")
    print(f"=" * 60)

    explanations = {
        "404 Client Error": {
            "meaning": "Page Not Found",
            "cause": "URL has changed or page doesn't exist",
            "solution": "Normal - brokers change their website structure frequently",
            "action": "URLs in brokers.yaml have been updated with working alternatives"
        },
        "403 Client Error": {
            "meaning": "Access Forbidden",
            "cause": "Anti-bot protection or access restrictions",
            "solution": "Normal - some sites block automated access",
            "action": "System gracefully handles this and continues with other sources"
        },
        "Connection timeout": {
            "meaning": "Website is slow or blocking connections",
            "cause": "Network issues or deliberate blocking",
            "solution": "Normal - some sites are slow or have geographic restrictions",
            "action": "Timeout reduced to 15 seconds to fail faster"
        },
        "Read timeout": {
            "meaning": "Website took too long to respond",
            "cause": "Server overload or slow response",
            "solution": "Normal - banking websites can be slow",
            "action": "System continues with other sources automatically"
        }
    }

    for error, info in explanations.items():
        print(f"\n🔍 {error}:")
        print(f"   📖 Meaning: {info['meaning']}")
        print(f"   🔧 Cause: {info['cause']}")
        print(f"   ✅ Why it's normal: {info['solution']}")
        print(f"   🎯 What we did: {info['action']}")

    print(f"\n💡 KEY POINTS:")
    print(f"   • These errors are EXPECTED and NORMAL in web scraping")
    print(f"   • The system is designed to handle failures gracefully")
    print(f"   • If 1-2 sources work, that's a success!")
    print(f"   • URLs have been updated to more reliable endpoints")
    print(f"   • Error handling has been improved for better feedback")

if __name__ == "__main__":
    test_improved_scraping()
    show_error_explanations()
