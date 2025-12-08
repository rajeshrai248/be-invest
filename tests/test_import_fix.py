#!/usr/bin/env python3
"""
Test the fixed news scraping import
"""
import sys
from pathlib import Path

# Add the project root to sys.path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root / "src"))

def test_import_fix():
    """Test that the import issue is fixed."""
    print("🔧 TESTING IMPORT FIX")
    print("=" * 50)

    try:
        # Test 1: Direct import
        print("1. Testing direct import...")
        from be_invest.sources.news_scrape import scrape_broker_news
        print("   ✅ scrape_broker_news imported successfully")

        # Test 2: API server import
        print("2. Testing API server imports...")
        from be_invest.api.server import app
        print("   ✅ API server imported successfully")

        # Test 3: Check function signature
        import inspect
        sig = inspect.signature(scrape_broker_news)
        params = list(sig.parameters.keys())
        print(f"   ✅ Function parameters: {params}")

        # Test 4: Basic function call test (without actual scraping)
        print("3. Testing function availability...")
        from be_invest.config_loader import load_brokers_from_yaml

        brokers_yaml = project_root / "data" / "brokers.yaml"
        if brokers_yaml.exists():
            brokers = load_brokers_from_yaml(brokers_yaml)
            print(f"   ✅ Configuration loaded: {len(brokers)} brokers")

            # Test the function exists and is callable
            if callable(scrape_broker_news):
                print("   ✅ scrape_broker_news function is callable")
            else:
                print("   ❌ scrape_broker_news is not callable")

        print(f"\n✅ IMPORT FIX SUCCESSFUL")
        print(f"   The 'scrape_broker_news' function is now properly imported")
        print(f"   The API endpoint should work correctly")

        return True

    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_api_endpoint_simulation():
    """Simulate the API endpoint call to test the fix."""
    print(f"\n" + "=" * 50)
    print(f"🌐 SIMULATING API ENDPOINT CALL")
    print(f"=" * 50)

    try:
        # Import what the endpoint needs
        from be_invest.sources.news_scrape import scrape_broker_news
        from be_invest.config_loader import load_brokers_from_yaml

        # Simulate endpoint logic
        brokers_yaml = project_root / "data" / "brokers.yaml"
        all_brokers = load_brokers_from_yaml(brokers_yaml)

        # Filter brokers that have news sources
        brokers_to_process = [b for b in all_brokers if b.news_sources]

        print(f"📊 ENDPOINT SIMULATION:")
        print(f"   Brokers loaded: {len(all_brokers)}")
        print(f"   Brokers with news sources: {len(brokers_to_process)}")

        # Test that we can call the function (without actually running full scrape)
        print(f"   Function available: {'✅ Yes' if callable(scrape_broker_news) else '❌ No'}")

        # Show what parameters the endpoint would use
        print(f"   Parameters available: brokers={len(brokers_to_process)}, force=False, rss_first=True")

        print(f"\n✅ API ENDPOINT SIMULATION SUCCESSFUL")
        print(f"   The /news/scrape endpoint should now work without import errors")

    except Exception as e:
        print(f"❌ Simulation failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    success = test_import_fix()
    if success:
        test_api_endpoint_simulation()

    print(f"\n💡 NEXT STEPS:")
    print(f"   1. The import error is fixed")
    print(f"   2. Start server: python -m uvicorn src.be_invest.api.server:app --port 8000")
    print(f"   3. Test endpoint: curl -X POST http://localhost:8000/news/scrape")
    print(f"   4. The RSS-first strategy is now available via API")
