"""Quick test to see Playwright debug logs."""
import sys
import logging
from pathlib import Path

# Setup path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

# Configure debug logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

from be_invest.config_loader import load_brokers_from_yaml
from be_invest.sources.news_scrape import NewsScraper

# Load brokers
brokers_file = PROJECT_ROOT / "data" / "brokers.yaml"
brokers_list = load_brokers_from_yaml(brokers_file)  # Returns list directly

# Initialize scraper
print("=" * 80)
print("Testing news scraper with DEBUG logging")
print("=" * 80)
scraper = NewsScraper()

# Try to scrape one broker only
test_broker = brokers_list[0]  # First broker
print(f"\nTesting with {test_broker.name}...")
print(f"   News sources: {len(test_broker.news_sources)}")

results = scraper.scrape_all_broker_news([test_broker], force=True)

print("\n" + "=" * 80)
print("RESULTS:")
print(f"  News items: {sum(len(items) for items in results.values())}")
print("=" * 80)

