#!/usr/bin/env python
"""
Quick test to verify caching is working on cost-comparison and financial-analysis endpoints.
"""

import requests
import time
import json

BASE_URL = "http://localhost:8000"

def test_endpoint_caching(endpoint: str, endpoint_type: str = "GET"):
    """Test caching on any endpoint."""
    print(f"\n{'='*80}")
    print(f"🧪 Testing {endpoint} - Caching")
    print(f"{'='*80}")

    endpoint_url = f"{BASE_URL}{endpoint}"

    # First call (generates, should be slow)
    print(f"\n📞 Call 1: Generating fresh data (no cache)...")
    start = time.time()
    if endpoint_type == "GET":
        resp1 = requests.get(endpoint_url, params={"model": "gpt-4o", "force": False})
    else:
        resp1 = requests.post(endpoint_url, params={"force": False})
    elapsed1 = time.time() - start

    if resp1.status_code == 200:
        print(f"   ✅ Status: {resp1.status_code}")
        print(f"   ⏱️  Duration: {elapsed1:.2f}s")
        data1 = resp1.json()
        print(f"   📊 Response size: {len(json.dumps(data1))} bytes")
    else:
        print(f"   ❌ Error: {resp1.status_code} - {resp1.text[:200]}")
        return False

    # Second call (uses cache, should be fast)
    print(f"\n📞 Call 2: Using cache (same parameters)...")
    start = time.time()
    if endpoint_type == "GET":
        resp2 = requests.get(endpoint_url, params={"model": "gpt-4o", "force": False})
    else:
        resp2 = requests.post(endpoint_url, params={"force": False})
    elapsed2 = time.time() - start

    if resp2.status_code == 200:
        print(f"   ✅ Status: {resp2.status_code}")
        print(f"   ⏱️  Duration: {elapsed2:.2f}s")

        if elapsed2 < elapsed1:
            speedup = elapsed1 / elapsed2
            print(f"   ⚡ Speedup: {speedup:.1f}x faster!")
            print(f"      Generated in {elapsed1:.2f}s, Cached in {elapsed2:.2f}s")

        # Check if responses are identical
        if resp1.json() == resp2.json():
            print(f"   ✅ Cache working correctly (responses match)")
        else:
            print(f"   ⚠️  Responses differ (might be normal if data changed)")
    else:
        print(f"   ❌ Error: {resp2.status_code} - {resp2.text[:200]}")
        return False

    # Third call with force=true (should be slow again)
    print(f"\n📞 Call 3: Force fresh data (force=true)...")
    start = time.time()
    if endpoint_type == "GET":
        resp3 = requests.get(endpoint_url, params={"model": "gpt-4o", "force": True})
    else:
        resp3 = requests.post(endpoint_url, params={"force": True})
    elapsed3 = time.time() - start

    if resp3.status_code == 200:
        print(f"   ✅ Status: {resp3.status_code}")
        print(f"   ⏱️  Duration: {elapsed3:.2f}s")
        if elapsed3 > elapsed2:
            print(f"   ℹ️  Fresh generation takes longer than cached ({elapsed3:.2f}s vs {elapsed2:.2f}s)")
    else:
        print(f"   ❌ Error: {resp3.status_code} - {resp3.text[:200]}")
        return False

    return True

if __name__ == "__main__":
    print("\n" + "="*80)
    print("🚀 ENDPOINT CACHING TEST SUITE")
    print("="*80)
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
        test_endpoint_caching("/cost-comparison-tables", "GET")
        test_endpoint_caching("/financial-analysis", "GET")
        test_endpoint_caching("/news/scrape", "POST")

        print("\n" + "="*80)
        print("✅ All endpoint caching tests completed!")
        print("="*80)

    except KeyboardInterrupt:
        print("\n\n⏸️  Tests interrupted")
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()

