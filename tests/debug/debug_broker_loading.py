#!/usr/bin/env python
"""
Debug broker loading issue.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.append('src')

try:
    from be_invest.config_loader import load_brokers_from_yaml

    print("✅ Successfully imported config_loader")

    brokers = load_brokers_from_yaml(Path('data/brokers.yaml'))
    print(f"✅ Loaded {len(brokers)} brokers")

    if brokers:
        first_broker = brokers[0]
        print(f"✅ First broker: {first_broker.name}")
        print(f"✅ Attributes: {[attr for attr in dir(first_broker) if not attr.startswith('_')]}")

        # Test specific attributes
        if hasattr(first_broker, 'news_sources'):
            print(f"✅ news_sources exists: {len(first_broker.news_sources)} items")
        else:
            print("❌ news_sources NOT found")

        # Check Revolut specifically
        revolut = [b for b in brokers if b.name == 'Revolut']
        if revolut:
            revolut = revolut[0]
            print(f"\n🎯 Revolut broker found!")
            print(f"   Name: {revolut.name}")
            print(f"   Has news_sources attr: {hasattr(revolut, 'news_sources')}")
            if hasattr(revolut, 'news_sources'):
                print(f"   News sources count: {len(revolut.news_sources)}")
                for ns in revolut.news_sources:
                    print(f"     - {ns.description}: allowed={ns.allowed_to_scrape}")
        else:
            print("❌ Revolut not found")

except ImportError as e:
    print(f"❌ Import error: {e}")
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
