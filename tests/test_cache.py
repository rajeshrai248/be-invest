#!/usr/bin/env python
"""
Quick test script to verify caching is working in API endpoints.
"""

import requests
import time
import json
from pathlib import Path

BASE_URL = "http://localhost:8000"

def test_cost_comparison_caching():
    """Test /cost-comparison-tables endpoint caching."""
    print("\n" + "=" * 80)
    print("🧪 Testing /cost-comparison-tables caching")
    print("=" * 80)

    endpoint = f"{BASE_URL}/cost-comparison-tables"

    # First call (should hit LLM)
    print("\n📞 Call 1: Fetching from LLM (no cache yet)...")
    start = time.time()
    resp1 = requests.get(endpoint, params={"model": "gpt-4o", "force": False})
    elapsed1 = time.time() - start
    print(f"   ✅ Status: {resp1.status_code}, Duration: {elapsed1:.2f}s")

    if resp1.status_code == 200:
        data1 = resp1.json()
        print(f"   📊 Response keys: {list(data1.keys())}")
    else:
        print(f"   ❌ Error: {resp1.text[:200]}")
        return False

    # Second call (should use cache)
    print("\n📞 Call 2: Should return cached result...")
    start = time.time()
    resp2 = requests.get(endpoint, params={"model": "gpt-4o", "force": False})
    elapsed2 = time.time() - start
    print(f"   ✅ Status: {resp2.status_code}, Duration: {elapsed2:.2f}s")

    if resp2.status_code == 200:
        # Compare responses
        if resp1.json() == resp2.json():
            print(f"   ✅ Responses match")
            speedup = elapsed1 / elapsed2 if elapsed2 > 0 else float('inf')
            print(f"   ⚡ Speedup: {speedup:.1f}x faster ({elapsed2:.2f}s vs {elapsed1:.2f}s)")
        else:
            print(f"   ⚠️  Responses differ (might be normal)")

    # Force refresh
    print("\n📞 Call 3: Force refresh (force=true)...")
    start = time.time()
    resp3 = requests.get(endpoint, params={"model": "gpt-4o", "force": True})
    elapsed3 = time.time() - start
    print(f"   ✅ Status: {resp3.status_code}, Duration: {elapsed3:.2f}s")

    return True

def test_financial_analysis_caching():
    """Test /financial-analysis endpoint caching."""
    print("\n" + "=" * 80)
    print("🧪 Testing /financial-analysis caching")
    print("=" * 80)

    endpoint = f"{BASE_URL}/financial-analysis"

    # First call
    print("\n📞 Call 1: Fetching from LLM...")
    start = time.time()
    resp1 = requests.get(endpoint, params={"model": "gpt-4o", "force": False})
    elapsed1 = time.time() - start
    print(f"   ✅ Status: {resp1.status_code}, Duration: {elapsed1:.2f}s")

    if resp1.status_code != 200:
        print(f"   ❌ Error: {resp1.text[:200]}")
        return False

    # Second call (cached)
    print("\n📞 Call 2: Should return cached result...")
    start = time.time()
    resp2 = requests.get(endpoint, params={"model": "gpt-4o", "force": False})
    elapsed2 = time.time() - start
    print(f"   ✅ Status: {resp2.status_code}, Duration: {elapsed2:.2f}s")

    if elapsed2 < elapsed1:
        speedup = elapsed1 / elapsed2 if elapsed2 > 0 else float('inf')
        print(f"   ⚡ Speedup: {speedup:.1f}x faster")

    return True

def test_news_scraping_caching():
    """Test /news/scrape endpoint caching."""
    print("\n" + "=" * 80)
    print("🧪 Testing /news/scrape caching")
    print("=" * 80)

    endpoint = f"{BASE_URL}/news/scrape"

    # First call
    print("\n📞 Call 1: Performing news scrape...")
    start = time.time()
    resp1 = requests.post(endpoint, params={"force": False})
    elapsed1 = time.time() - start
    print(f"   ✅ Status: {resp1.status_code}, Duration: {elapsed1:.2f}s")

    if resp1.status_code == 200:
        data1 = resp1.json()
        print(f"   📰 News items: {data1.get('total_scraped', 'unknown')}")
        print(f"   💾 From cache: {data1.get('from_cache', False)}")
    else:
        print(f"   ❌ Error: {resp1.text[:200]}")
        return False

    # Second call (should use cache)
    print("\n📞 Call 2: Should return cached news...")
    start = time.time()
    resp2 = requests.post(endpoint, params={"force": False})
    elapsed2 = time.time() - start
    print(f"   ✅ Status: {resp2.status_code}, Duration: {elapsed2:.2f}s")

    if resp2.status_code == 200:
        data2 = resp2.json()
        print(f"   📰 News items: {data2.get('total_scraped', 'unknown')}")
        print(f"   💾 From cache: {data2.get('from_cache', False)}")

        if data2.get('from_cache'):
            print(f"   ✅ Cache working! Saved {elapsed1 - elapsed2:.2f}s")
        else:
            print(f"   ⚠️  Response not from cache")

    # Force refresh
    print("\n📞 Call 3: Force refresh (force=true)...")
    start = time.time()
    resp3 = requests.post(endpoint, params={"force": True})
    elapsed3 = time.time() - start
    print(f"   ✅ Status: {resp3.status_code}, Duration: {elapsed3:.2f}s")

    if resp3.status_code == 200:
        data3 = resp3.json()
        print(f"   💾 From cache: {data3.get('from_cache', False)}")

    return True

if __name__ == "__main__":
    print("\n" + "=" * 80)
    print("🚀 API Caching Test Suite")
    print("=" * 80)
    print(f"Base URL: {BASE_URL}")
    print(f"Time: {time.strftime('%Y-%m-%d %H:%M:%S')}")

    # Check server is running
    try:
        resp = requests.get(f"{BASE_URL}/health", timeout=5)
        if resp.status_code == 200:
            print("✅ API server is running")
        else:
            print(f"❌ API server health check failed: {resp.status_code}")
            exit(1)
    except requests.ConnectionError:
        print(f"❌ Cannot connect to API server at {BASE_URL}")
        print("   Make sure to run: python scripts/run_api.py")
        exit(1)

    # Run tests
    try:
        test_cost_comparison_caching()
        test_financial_analysis_caching()
        test_news_scraping_caching()

        print("\n" + "=" * 80)
        print("✅ All tests completed!")
        print("=" * 80)

    except KeyboardInterrupt:
        print("\n\n⏸️  Tests interrupted")
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()

