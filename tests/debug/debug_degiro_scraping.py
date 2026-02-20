#!/usr/bin/env python
"""
Debug script to test Degiro scraping and save HTML response for analysis.
"""

import sys
import logging
import requests
from pathlib import Path
from datetime import datetime

# Setup path
sys.path.append('src')

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(levelname)s - %(message)s')

try:
    from be_invest.fetchers import Fetcher
    from bs4 import BeautifulSoup

    print("\n" + "="*80)
    print("🔍 DEGIRO SCRAPING DEBUG ANALYSIS")
    print("="*80 + "\n")

    degiro_url = "https://www.degiro.nl/blog/"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    print(f"Target URL: {degiro_url}")
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
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
        }

        response = requests.get(degiro_url, headers=headers, timeout=10)
        print(f"   Status Code: {response.status_code}")
        print(f"   Content-Type: {response.headers.get('content-type', 'Unknown')}")
        print(f"   Content Length: {len(response.content)} bytes")

        # Save basic requests response
        basic_file = f"data/output/degiro_basic_response_{timestamp}.html"
        Path(basic_file).parent.mkdir(parents=True, exist_ok=True)
        with open(basic_file, 'w', encoding='utf-8') as f:
            f.write(response.text)
        print(f"   ✅ Basic response saved to: {basic_file}")

        # Check for anti-bot indicators
        response_text = response.text.lower()
        bot_indicators = [
            'captcha', 'recaptcha', 'cloudflare', 'access denied',
            'blocked', 'bot', 'robot', 'automated', 'security check',
            'ddos protection', 'ray id'
        ]

        found_indicators = [indicator for indicator in bot_indicators if indicator in response_text]
        if found_indicators:
            print(f"   ⚠️  Anti-bot indicators found: {', '.join(found_indicators)}")
        else:
            print(f"   ✅ No obvious anti-bot protection detected")

    except Exception as e:
        print(f"   ❌ Basic requests failed: {e}")

    # Test 2: Playwright fetcher
    print(f"\n2️⃣ Testing with Playwright fetcher...")
    try:
        fetcher = Fetcher(use_playwright=True)
        print(f"   Fetcher initialized with Playwright: {fetcher.use_playwright}")

        html_bytes, error = fetcher.fetch(degiro_url)

        if error:
            print(f"   ❌ Playwright error: {error}")
        elif html_bytes:
            print(f"   ✅ Playwright success: {len(html_bytes)} bytes")

            # Decode HTML
            try:
                html_content = html_bytes.decode('utf-8', errors='ignore')
            except:
                html_content = str(html_bytes)

            # Save Playwright response
            playwright_file = f"data/output/degiro_playwright_response_{timestamp}.html"
            with open(playwright_file, 'w', encoding='utf-8') as f:
                f.write(html_content)
            print(f"   ✅ Playwright response saved to: {playwright_file}")

            # Analyze content
            soup = BeautifulSoup(html_content, 'html.parser')
            title = soup.title.get_text() if soup.title else "No title"
            print(f"   Page title: {title}")

            # Check for blocking indicators
            content_lower = html_content.lower()
            block_indicators = [
                'blocked', 'access denied', 'forbidden', 'security check',
                'myracloud', 'ddos protection', 'captcha', 'verification'
            ]

            found_blocks = [indicator for indicator in block_indicators if indicator in content_lower]
            if found_blocks:
                print(f"   🚫 Blocking detected: {', '.join(found_blocks)}")

            # Check for news content
            h2_elements = soup.find_all('h2')
            print(f"   Found {len(h2_elements)} h2 elements")

            if h2_elements:
                print(f"   Sample h2 content:")
                for i, h2 in enumerate(h2_elements[:3], 1):
                    text = h2.get_text(strip=True)
                    print(f"     {i}. {text[:100]}...")

            # Look for blog articles or news items
            potential_selectors = [
                'article', '.post', '.news', '.blog-item',
                '[class*="post"]', '[class*="article"]', '[class*="blog"]'
            ]

            for selector in potential_selectors:
                elements = soup.select(selector)
                if elements:
                    print(f"   Found {len(elements)} elements with selector '{selector}'")
        else:
            print(f"   ❌ No content received from Playwright")

    except Exception as e:
        print(f"   ❌ Playwright test failed: {e}")
        import traceback
        traceback.print_exc()

    # Test 3: Check robots.txt
    print(f"\n3️⃣ Checking robots.txt...")
    try:
        robots_url = "https://www.degiro.nl/robots.txt"
        robots_response = requests.get(robots_url, timeout=5)
        print(f"   Status: {robots_response.status_code}")

        if robots_response.status_code == 200:
            robots_file = f"data/output/degiro_robots_{timestamp}.txt"
            with open(robots_file, 'w', encoding='utf-8') as f:
                f.write(robots_response.text)
            print(f"   ✅ Robots.txt saved to: {robots_file}")

            # Check for bot restrictions
            robots_text = robots_response.text.lower()
            if '/blog' in robots_text or 'disallow: /' in robots_text:
                print(f"   ⚠️  Robots.txt may restrict blog access")
            else:
                print(f"   ✅ No obvious blog restrictions in robots.txt")

    except Exception as e:
        print(f"   ⚠️  Could not fetch robots.txt: {e}")

    print(f"\n" + "="*80)
    print("📋 SUMMARY")
    print("="*80)
    print(f"• HTML responses saved to data/output/ with timestamp {timestamp}")
    print(f"• Check the saved files to analyze the actual content received")
    print(f"• Look for anti-bot protection, JavaScript requirements, or content blocking")
    print(f"• Compare basic requests vs Playwright responses for differences")
    print(f"\n")

except ImportError as e:
    print(f"❌ Import error: {e}")
except Exception as e:
    print(f"❌ Unexpected error: {e}")
    import traceback
    traceback.print_exc()
