#!/usr/bin/env python
"""
Debug script to test ING scraping and save HTML response for analysis.
"""

import sys
import logging
import requests
from pathlib import Path
from datetime import datetime
from bs4 import BeautifulSoup

# Setup path
sys.path.append('src')

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(levelname)s - %(message)s')

def test_ing_scraping():
    print("\n" + "="*80)
    print("🔍 ING SCRAPING DEBUG ANALYSIS")
    print("="*80 + "\n")

    ing_url = "https://newsroom.ing.be/en"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    print(f"Target URL: {ing_url}")
    print(f"Timestamp: {timestamp}\n")

    # Test 1: Basic requests
    print("1️⃣ Testing with basic requests...")
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9,nl;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }

        response = requests.get(ing_url, headers=headers, timeout=10)
        print(f"   Status Code: {response.status_code}")
        print(f"   Content-Type: {response.headers.get('content-type', 'Unknown')}")
        print(f"   Content Length: {len(response.content)} bytes")

        # Save basic requests response
        basic_file = f"data/output/ing_basic_response_{timestamp}.html"
        Path(basic_file).parent.mkdir(parents=True, exist_ok=True)
        with open(basic_file, 'w', encoding='utf-8') as f:
            f.write(response.text)
        print(f"   ✅ Basic response saved to: {basic_file}")

        # Quick analysis
        soup = BeautifulSoup(response.text, 'html.parser')
        title = soup.title.get_text() if soup.title else "No title"
        print(f"   Page title: {title}")

        # Check for anti-bot indicators
        response_text = response.text.lower()
        bot_indicators = [
            'captcha', 'recaptcha', 'cloudflare', 'access denied',
            'blocked', 'bot', 'robot', 'automated', 'security check',
            'ddos protection', 'ray id', 'loading', 'please wait'
        ]

        found_indicators = [indicator for indicator in bot_indicators if indicator in response_text]
        if found_indicators:
            print(f"   ⚠️  Potential issues found: {', '.join(found_indicators)}")
        else:
            print(f"   ✅ No obvious blocking detected")

        # Look for news content
        news_indicators = ['article', 'news', 'press', 'release', 'announcement']
        found_news = [indicator for indicator in news_indicators if indicator in response_text]
        print(f"   📰 News indicators found: {', '.join(found_news) if found_news else 'None'}")

    except Exception as e:
        print(f"   ❌ Basic requests failed: {e}")

    # Test 2: Test with category parameter from config
    print(f"\n2️⃣ Testing with category parameter...")
    try:
        ing_category_url = "https://newsroom.ing.be/en?category=9986"
        print(f"   Category URL: {ing_category_url}")

        response = requests.get(ing_category_url, headers=headers, timeout=10)
        print(f"   Status Code: {response.status_code}")

        if response.status_code == 200:
            # Save category response
            category_file = f"data/output/ing_category_response_{timestamp}.html"
            with open(category_file, 'w', encoding='utf-8') as f:
                f.write(response.text)
            print(f"   ✅ Category response saved to: {category_file}")

            soup = BeautifulSoup(response.text, 'html.parser')
            title = soup.title.get_text() if soup.title else "No title"
            print(f"   Category page title: {title}")
        else:
            print(f"   ❌ Category page failed with status {response.status_code}")

    except Exception as e:
        print(f"   ❌ Category test failed: {e}")

    # Test 3: Playwright fetcher
    print(f"\n3️⃣ Testing with Playwright fetcher...")
    try:
        from be_invest.fetchers import Fetcher

        fetcher = Fetcher(use_playwright=True)
        print(f"   Fetcher initialized with Playwright: {fetcher.use_playwright}")

        html_bytes, error = fetcher.fetch(ing_url)

        if error:
            print(f"   ❌ Playwright error: {error}")
        elif html_bytes:
            print(f"   ✅ Playwright success: {len(html_bytes)} bytes")

            # Decode and save
            try:
                html_content = html_bytes.decode('utf-8', errors='ignore')
                playwright_file = f"data/output/ing_playwright_response_{timestamp}.html"
                with open(playwright_file, 'w', encoding='utf-8') as f:
                    f.write(html_content)
                print(f"   ✅ Playwright response saved to: {playwright_file}")

                # Analyze content
                soup = BeautifulSoup(html_content, 'html.parser')
                title = soup.title.get_text() if soup.title else "No title"
                print(f"   Playwright page title: {title}")

                # Look for potential selectors
                potential_selectors = [
                    'article', '.news-item', '.press-release', '.post',
                    '[class*="news"]', '[class*="article"]', '[class*="press"]',
                    '.card', '.item', '.entry'
                ]

                print(f"   Analyzing potential selectors:")
                for selector in potential_selectors:
                    elements = soup.select(selector)
                    if elements:
                        print(f"     {selector}: {len(elements)} elements")
                        # Show sample content from first element
                        if elements[0].get_text(strip=True):
                            sample_text = elements[0].get_text(strip=True)[:80]
                            print(f"       Sample: {sample_text}...")

            except Exception as e:
                print(f"   ⚠️  Could not decode Playwright response: {e}")
        else:
            print(f"   ❌ No content received from Playwright")

    except ImportError:
        print(f"   ⚠️  Playwright not available for testing")
    except Exception as e:
        print(f"   ❌ Playwright test failed: {e}")

    # Test 4: URL analysis
    print(f"\n4️⃣ Testing URL patterns...")

    test_urls = [
        ing_url,
        "https://newsroom.ing.be/en?category=9986",
        "https://newsroom.ing.be/",
        "https://www.ing.be/en/about/news",
    ]

    for url in test_urls:
        try:
            print(f"   Testing: {url}")
            response = requests.get(url, headers=headers, timeout=5, allow_redirects=True)
            print(f"     Status: {response.status_code}")
            if response.status_code != 200:
                print(f"     Final URL: {response.url}")
        except Exception as e:
            print(f"     Error: {str(e)[:50]}")

    print(f"\n" + "="*80)
    print("📋 ING ANALYSIS SUMMARY")
    print("="*80)
    print(f"• HTML responses saved to data/output/ with timestamp {timestamp}")
    print(f"• Check the saved files to analyze:")
    print(f"  - Content structure and available selectors")
    print(f"  - Whether news articles are present")
    print(f"  - Any JavaScript requirements or dynamic loading")
    print(f"  - Differences between basic requests and Playwright")
    print(f"• Test different URL patterns to find the correct endpoint")
    print(f"\n")

if __name__ == "__main__":
    try:
        test_ing_scraping()
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
